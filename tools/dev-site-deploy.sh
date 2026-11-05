#!/usr/bin/env bash
# Carl 开发站唯一部署入口。
#
# 设计目标：所有 Agent / 人共用一条串行部署通道，任何并行会话都不能在
# 运行目录里直接 checkout、migrate 或 build。
#
#   * 运行目录只接受"远端已有的提交"，本地未推送的提交一律拒绝；
#   * 工作树必须是干净的，脏文件由脚本报出后由提交者自行处理；
#   * 全程持有 flock 排他锁，第二个部署会等待或超时失败；
#   * 迁移/构建/健康检查任一步失败自动回滚到部署前的提交；
#   * 每次部署把 ref、sha、操作者、耗时、健康结果写入状态文件，便于审计。
#
# 用法：
#   tools/dev-site-deploy.sh                       # 部署 origin/feat/customer-collaboration
#   tools/dev-site-deploy.sh --ref origin/main     # 指定分支
#   tools/dev-site-deploy.sh --sha <40位sha>       # 指定提交（仍需在远端可达）
#   tools/dev-site-deploy.sh --dry-run             # 只做预检与解析，不改运行目录
#   tools/dev-site-deploy.sh --status              # 查看当前部署状态
#   tools/dev-site-deploy.sh --wait 600            # 等待锁的最长秒数（默认 900）

set -euo pipefail

BENCH_DIR="${RELI_BENCH_DIR:-$HOME/pilot/benches/dev-bench}"
APP_DIR="${RELI_APP_DIR:-$BENCH_DIR/apps/reli_lims}"
SITE="${RELI_SITE:-carl}"
STATE_DIR="${RELI_STATE_DIR:-$HOME/pilot/state}"
LOCK_FILE="$STATE_DIR/dev-site-deploy.lock"
STATE_FILE="$STATE_DIR/dev-site-deploy.json"
LOG_FILE="$STATE_DIR/dev-site-deploy.log"
PILOT_BIN="${PILOT_BIN:-$HOME/pilot/bin/pilot}"
DEFAULT_REF="origin/feat/customer-collaboration"

REF="$DEFAULT_REF"
TARGET_SHA=""
WAIT_SECONDS=900
DO_DB=1
DO_BUILD=1
DRY_RUN=0
STATUS_ONLY=0

usage() { sed -n '2,26p' "$0" | sed 's/^# \{0,1\}//'; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --ref) REF="${2:?缺少 --ref 参数}"; shift 2 ;;
    --sha) TARGET_SHA="${2:?缺少 --sha 参数}"; shift 2 ;;
    --wait) WAIT_SECONDS="${2:?缺少 --wait 参数}"; shift 2 ;;
    --no-db) DO_DB=0; shift ;;
    --no-build) DO_BUILD=0; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    --status) STATUS_ONLY=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "未知参数：$1" >&2; usage; exit 2 ;;
  esac
done

mkdir -p "$STATE_DIR"

if [[ "$STATUS_ONLY" == 1 ]]; then
  echo "运行目录：$APP_DIR"
  if [[ -d "$APP_DIR/.git" || -f "$APP_DIR/.git" ]]; then
    echo "当前提交：$(git -C "$APP_DIR" rev-parse --short HEAD) ($(git -C "$APP_DIR" rev-parse --abbrev-ref HEAD))"
    if [[ -n "$(git -C "$APP_DIR" status --porcelain --untracked-files=no)" ]]; then
      echo "工作树：脏（有未提交改动）"
    else
      echo "工作树：干净"
    fi
  else
    echo "未找到 git 运行目录"
  fi
  if [[ -f "$STATE_FILE" ]]; then
    echo "最近部署："; cat "$STATE_FILE"; echo
  fi
  if command -v fuser >/dev/null 2>&1 && fuser "$LOCK_FILE" >/dev/null 2>&1; then
    echo "部署锁：被占用（$LOCK_FILE）"
  else
    echo "部署锁：空闲"
  fi
  exit 0
fi

log() { printf '%s [%s] %s\n' "$(date '+%F %T')" "$$" "$*" | tee -a "$LOG_FILE"; }
fail() { log "失败：$*"; exit 1; }

write_state() {
  local status="$1"
  python3 - "$STATE_FILE" "$status" "$PREV_SHA" "$NEW_SHA" "$REF" "$STARTED_AT" \
           "$(date -u '+%F %T')" "$LOG_FILE" <<'PY'
import json, os, sys
path, status, prev, new, ref, started, finished, logfile = sys.argv[1:9]
state = {
    "status": status,
    "ref": ref,
    "sha": new or None,
    "previous_sha": prev or None,
    "started_at": started,
    "finished_at": finished,
    "actor": os.environ.get("SSH_CONNECTION") or os.environ.get("USER") or "unknown",
    "host": os.uname().nodename,
    "log": logfile,
}
with open(path, "w", encoding="utf-8") as handle:
    json.dump(state, handle, ensure_ascii=False, indent=2)
    handle.write("\n")
PY
}

health_check() {
  local body attempt
  # 开发站开启 reload_python：切换提交后 runner 会重启，端口短暂不可用，必须重试。
  for attempt in $(seq 1 45); do
    body="$(curl -fsS --max-time 5 -H "Host: $SITE" "http://127.0.0.1:8000/api/method/ping" 2>/dev/null || true)"
    if [[ "$body" == *pong* ]] \
      && curl -fsS -o /dev/null --max-time 5 -H "Host: $SITE" "http://127.0.0.1:8000/login" 2>/dev/null; then
      [[ "$attempt" -gt 1 ]] && log "服务在约 $((attempt * 2)) 秒后恢复"
      return 0
    fi
    sleep 2
  done
  log "健康检查连续 90 秒未通过"
  return 1
}

[[ -d "$APP_DIR" ]] || fail "找不到运行目录 $APP_DIR"
git -C "$APP_DIR" rev-parse --git-dir >/dev/null 2>&1 || fail "$APP_DIR 不是 git 仓库"

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  log "部署锁被占用，等待最多 ${WAIT_SECONDS}s（$LOCK_FILE）"
  flock -w "$WAIT_SECONDS" 9 || fail "等待部署锁超时，说明另一个部署仍在执行。请先用 --status 查看。"
fi

log "=========== 部署开始 ==========="
PREV_SHA="$(git -C "$APP_DIR" rev-parse HEAD)"
STARTED_AT="$(date -u '+%F %T')"
log "运行目录 $APP_DIR"
log "部署前提交 $PREV_SHA"

DIRTY="$(git -C "$APP_DIR" status --porcelain --untracked-files=no)"
if [[ -n "$DIRTY" ]]; then
  printf '%s\n' "$DIRTY" | tee -a "$LOG_FILE"
  fail "运行目录有未提交改动。请先提交并推送到远端（开发应在独立 worktree 进行），再执行部署。"
fi

log "拉取远端引用"
git -C "$APP_DIR" fetch --prune origin >>"$LOG_FILE" 2>&1 || fail "git fetch 失败"

if [[ -n "$TARGET_SHA" ]]; then
  RESOLVED="$(git -C "$APP_DIR" rev-parse --verify "${TARGET_SHA}^{commit}" 2>/dev/null)" \
    || fail "无法解析提交 $TARGET_SHA"
else
  RESOLVED="$(git -C "$APP_DIR" rev-parse --verify "${REF}^{commit}" 2>/dev/null)" \
    || fail "无法解析引用 $REF"
fi

if [[ -z "$(git -C "$APP_DIR" branch -r --contains "$RESOLVED" 2>/dev/null)" ]]; then
  fail "提交 $RESOLVED 不在任何远端分支上。请先推送，禁止部署只在本地存在的提交。"
fi
for marker in "WIP" "wip " "DO NOT MERGE" "临时提交"; do
  if git -C "$APP_DIR" log -1 --format=%s "$RESOLVED" | grep -qi -- "$marker"; then
    fail "目标提交像是临时提交（$marker），拒绝部署。"
  fi
done

NEW_SHA="$RESOLVED"
log "目标提交 $NEW_SHA ($(git -C "$APP_DIR" log -1 --format=%s "$NEW_SHA"))"

log "密钥泄露预检（客户免登录链接 key 不得入库）"
if git -C "$APP_DIR" cat-file -e "$NEW_SHA:tools/check_no_secrets.py" 2>/dev/null; then
  SECRET_CHECK="$(mktemp)"
  git -C "$APP_DIR" show "$NEW_SHA:tools/check_no_secrets.py" >"$SECRET_CHECK"
  if ! python3 "$SECRET_CHECK" --repo "$APP_DIR" --rev "$NEW_SHA" 2>&1 | tee -a "$LOG_FILE"; then
    rm -f "$SECRET_CHECK"
    fail "待部署提交包含完整客户链接密钥。请改为占位写法并撤销该链接后再部署。"
  fi
  rm -f "$SECRET_CHECK"
else
  log "目标提交尚无密钥检查脚本，跳过"
fi

if [[ "$NEW_SHA" == "$PREV_SHA" ]]; then
  log "运行目录已是目标提交，仅做健康检查"
  health_check || fail "健康检查失败"
  write_state "no-op"
  log "=========== 无需部署 ==========="
  exit 0
fi

if [[ "$DRY_RUN" == 1 ]]; then
  log "dry-run：将把 $PREV_SHA 切换到 $NEW_SHA，随后执行 migrate/build/健康检查。"
  write_state "dry-run"
  exit 0
fi

restore_previous() {
  log "回滚到 $PREV_SHA"
  git -C "$APP_DIR" checkout --detach "$PREV_SHA" >>"$LOG_FILE" 2>&1 || return 1
  if [[ "$DO_BUILD" == 1 ]]; then
    "$PILOT_BIN" build --apps reli_lims >>"$LOG_FILE" 2>&1 || true
  fi
  health_check
}

on_error() {
  log "部署中断，准备回滚"
  if restore_previous; then
    write_state "rolled_back"
    log "已回滚到部署前状态，服务可用"
  else
    write_state "failed_and_rollback_failed"
    log "回滚失败，需要人工介入"
  fi
  exit 1
}
trap 'on_error' ERR

log "切换到目标提交"
git -C "$APP_DIR" checkout --detach "$NEW_SHA" >>"$LOG_FILE" 2>&1

if [[ "$DO_DB" == 1 ]]; then
  log "执行数据库迁移（bench --site $SITE migrate）"
  "$PILOT_BIN" frappe --site "$SITE" migrate >>"$LOG_FILE" 2>&1
fi

if [[ "$DO_BUILD" == 1 ]]; then
  log "构建前端资源（reli_lims）"
  "$PILOT_BIN" build --apps reli_lims >>"$LOG_FILE" 2>&1
fi

log "健康检查"
health_check
trap - ERR

write_state "ok"
log "部署完成：$PREV_SHA -> $NEW_SHA"
log "=========== 部署结束 ==========="
