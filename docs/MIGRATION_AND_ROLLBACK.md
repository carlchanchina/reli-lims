# 数据迁移与回滚方案

## 1. 迁移的唯一入口

Carl 开发站的代码、数据库、前端资源**只允许**通过一条通道更新：

```bash
ssh frappe@192.168.10.204 '~/pilot/benches/dev-bench/apps/reli_lims/tools/dev-site-deploy.sh'
```

不允许任何人或 Agent 直接在 `~/pilot/benches/dev-bench/apps/reli_lims` 里 `git checkout`、
`bench migrate` 或 `bench build`。开发在独立 worktree 做，改动推送到远端分支后由脚本部署。

脚本按顺序做这些事，任一步失败即回滚：

| 步骤 | 行为 | 失败时 |
| --- | --- | --- |
| 1. 加锁 | `flock` 排他，最多等 900 秒 | 超时退出，不动运行目录 |
| 2. 脏树检查 | `git status --porcelain --untracked-files=no` 必须为空 | 列出脏文件后退出 |
| 3. 拉取远端 | `git fetch --prune origin` | 退出 |
| 4. 解析目标 | `--sha` 或默认 `origin/feat/customer-collaboration` | 退出 |
| 5. 远端可达性 | 提交必须被某个远端分支包含 | 拒绝部署「只在本地存在」的提交 |
| 6. 临时提交识别 | 标题含 `WIP` / `DO NOT MERGE` / `临时提交` | 拒绝部署 |
| 7. **密钥闸门** | 跑目标提交自带的 `tools/check_no_secrets.py --rev <sha>` | 拒绝部署并说明原因 |
| 8. 切换 | `git checkout --detach <sha>` | 回滚 |
| 9. 迁移 | `bench --site carl migrate` | 回滚 |
| 10. 构建 | `bench build --apps reli_lims` | 回滚 |
| 11. 健康检查 | `ping` 返回 pong 且 `/login` 200，每 2 秒重试，最长 90 秒 | 回滚 |

每次部署把 `ref`、`sha`、操作者（`SSH_CONNECTION`）、主机、起止时间、日志路径、结果
（`ok` / `no-op` / `dry-run` / `rolled_back` / `failed_and_rollback_failed`）写入
`~/pilot/state/dev-site-deploy.json`，日志追加到 `~/pilot/state/dev-site-deploy.log`。

其他用法：

```bash
tools/dev-site-deploy.sh --dry-run          # 只预检 + 解析目标，不动运行目录
tools/dev-site-deploy.sh --status           # 当前提交 / 工作树 / 最近部署 / 锁状态
tools/dev-site-deploy.sh --sha <commit>     # 部署指定提交（仍需远端可达）
tools/dev-site-deploy.sh --no-db            # 只换代码，不迁移（改前端/文档时用）
```

## 2. 本版数据库变更

全部为**增量、向后兼容**，没有破坏性 DDL，没有数据改写：

| 变更 | 类型 | 对旧代码的影响 |
| --- | --- | --- |
| 新表 `tabCapability Review Log` | 新建子表 + 索引 | 无（旧代码不读它） |
| `Laboratory Capability` 新字段：`demo_only`、`review_section`、`reviewed_by/on`、`published_by/on`、`review_note`、`review_log` | 加列 | 无（新列默认 NULL / 0） |
| `accreditation_type` 增加选项「演示（非认可）」 | Select 选项扩展 | 无（旧值仍有效） |
| `status`、`laboratory` 加 `in_standard_filter` | 仅元数据 | 无 |
| 新增角色权限 `Lab Engineer`（read/print/report）、`Sales User`/`Sales Manager`（read/print/export） | DocPerm 新增行 | 无（只加不减） |
| `Test Report` / `Test Program` 设 `default_print_format` | 属性 | 无（只影响默认值） |
| 工作台 shortcut 改为「待确认能力」+「能力审核台」 | 元数据 | 无 |

关键点：**没有删除列、没有改列类型、没有 `ALTER` 既有数据**。所以旧代码（`a20d800` 之前）
在新库上仍能正常运行，回滚只需要切代码，不需要回滚数据库。

> 唯一需要注意的是 `accreditation_type` 的选项扩展：如果不回滚代码就只回滚数据库（本流程不做），
> 已写入「演示（非认可）」的记录在旧选项集下会显示异常。因此**回滚一律只切代码、不动数据库**。

## 3. 回滚

### 3.1 自动回滚（脚本已内置）

`migrate` / `build` / 健康检查任一步失败，`ERR` trap 触发 `restore_previous()`：

1. `git checkout --detach <部署前提交>`
2. `bench build --apps reli_lims`（构建失败不阻塞回滚）
3. 健康检查（最长 90 秒）
4. 写 `rolled_back`（成功）或 `failed_and_rollback_failed`（需人工介入）

**这套机制在本次收口里被真实触发过一次**：`8369763 → f0cb0be` 时新子表缺
`capability_review_log.py` 控制器，`migrate` 报 `No module named ...capability_review_log.capability_review_log`，
脚本自动回滚到 `8369763` 并恢复服务，随后补控制器重部署成功。日志在
`~/pilot/state/dev-site-deploy.log`。

### 3.2 手工回滚

```bash
# 先看部署前提交和当前状态
ssh frappe@192.168.10.204 '~/pilot/benches/dev-bench/apps/reli_lims/tools/dev-site-deploy.sh --status'

# 回到上一个提交（同样走统一脚本，不手敲 git）
ssh frappe@192.168.10.204 \
  '~/pilot/benches/dev-bench/apps/reli_lims/tools/dev-site-deploy.sh --sha <上一个提交> --no-db'
```

`--no-db` 是刻意的：数据库变更向后兼容，回滚代码即可，不需要（也不应该）反向迁移。
若确实需要清掉新表，属于人工决策，不在自动流程里。

### 3.3 回滚后的验证

```bash
curl -fsS -H 'Host: carl' http://carl:8000/api/method/ping     # pong
curl -fsS -o /dev/null -w '%{http_code}\n' -H 'Host: carl' http://carl:8000/login  # 200
```

再跑一遍 `tools/acceptance/formal_acceptance_flow.py`，确认委托→方案→报告链路可用。

## 4. 生产（Carl-1）迁移注意事项

Carl-1 **本次不部署**。将来部署前必须逐项确认：

1. `host_name` 必须是生产域名（开发站曾误指向 `https://carl-1.taila47902.ts.net`，导致客户链接指向错误主机）。
2. 迁移前做一次数据库快照，并确认可以恢复到该快照（本版变更虽向后兼容，生产无回滚演练不冒险）。
3. 确认 `wkhtmltopdf` 为 **patched qt**。开发站是 unpatched，`printview` 出 PDF 会报网络错误，
   本次证据改用无头 Chrome 生成；生产若同样 unpatched，正式打印会失败。
4. 先跑 `migrate`，再跑四个验收脚本，全绿后才开流量。
5. 迁移会在生产建 `tabCapability Review Log` 与索引，651 条历史能力保持 `待确认` 不变 ——
   这是预期行为，不要在生产上做批量发布。

## 5. 与代码合并的关系

- 代码合并（#18 → #19 → #20）与生产部署是两件事。合并只改仓库，不碰任何数据库。
- 合并 #19 之后需要在预发环境执行一次 `migrate`，会建能力审核记录表。
- 合并 #20 建议 squash，避免历史提交里的演示链接密钥进入 `main`（密钥已在开发站全部撤销，
  squash 是纵深防御，不是唯一依靠 —— 部署前还有 `check_no_secrets.py` 闸门）。
