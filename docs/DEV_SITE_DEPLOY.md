# Carl 开发站部署流程（唯一入口）

本文件约束所有人和 Agent 对 Carl 开发站的部署行为。目标是消除"多个并行会话各自
在运行目录 checkout / migrate / build"导致的互相覆盖。

## 环境事实

| 项目 | 值 |
| --- | --- |
| 主机 | Carl（`frappe@192.168.10.204`，内网开发站） |
| bench | `~/pilot/benches/dev-bench` |
| 站点 | `carl`（访问时必须带 `Host: carl`） |
| 应用运行目录 | `~/pilot/benches/dev-bench/apps/reli_lims` |
| 访问入口 | `http://192.168.10.204:8000` |
| 部署锁 | `~/pilot/state/dev-site-deploy.lock` |
| 部署状态 | `~/pilot/state/dev-site-deploy.json` |
| 部署日志 | `~/pilot/state/dev-site-deploy.log` |

生产站 Carl-1 **不在本流程范围内，禁止操作**。

## 分工

- **开发**：在本机独立 worktree 中改代码，例如 `/Users/carl/projects/reli-lims-collab`
  （分支 `feat/customer-collaboration`）。运行目录 `apps/reli_lims` 不是开发目录。
- **部署**：提交并推送后，用 `tools/dev-site-deploy.sh` 在运行目录做一次性切换。
- 任何 Agent 都不得在 `apps/reli_lims` 里手工 `git checkout`、`git reset`、`bench migrate`、
  `bench build`。运行目录只接受部署脚本写入。

## 部署命令

```bash
# 1) 开发 worktree 中提交并推送
git push origin feat/customer-collaboration

# 2) 只做预检，不改运行目录
ssh frappe@192.168.10.204 '~/pilot/benches/dev-bench/apps/reli_lims/tools/dev-site-deploy.sh --dry-run'

# 3) 正式部署（脚本内 flock 串行，默认等锁 900 秒）
ssh frappe@192.168.10.204 '~/pilot/benches/dev-bench/apps/reli_lims/tools/dev-site-deploy.sh'

# 4) 查看状态
ssh frappe@192.168.10.204 '~/pilot/benches/dev-bench/apps/reli_lims/tools/dev-site-deploy.sh --status'
```

脚本固定部署 `origin/feat/customer-collaboration`；如需其他分支显式传 `--ref`。

## 脚本会做什么

1. 获取 `flock` 排他锁，第二个部署排队或超时失败，不会并发执行。
2. 校验运行目录干净；有未提交改动直接失败并列出文件。
3. `git fetch` 后解析目标提交，确认它**存在于远端分支**，拒绝部署本地孤立提交。
4. `checkout --detach` 到目标提交（不切分支，避免并行会话互相改分支指针）。
5. `pilot frappe --site carl migrate` → `pilot build --apps reli_lims`。
6. 健康检查：`/api/method/ping` 返回 `pong` 且 `/login` 返回 200。
7. 任一步失败：自动回滚到部署前提交、重建资源、复查健康，并在状态文件写
   `rolled_back`；回滚也失败则写 `failed_and_rollback_failed`，需人工介入。
8. 成功时把 ref、sha、前一版 sha、起止时间、操作者、日志路径写入状态文件。

## 禁止事项

- 禁止在运行目录保留未推送提交（脚本会拒绝部署，且并行会话会丢代码）。
- 禁止多个会话同时对同一站点跑 `migrate`；需要迁移就通过脚本排队。
- 禁止用 `git reset --hard` 解决运行目录问题；正确做法是把提交推送到远端，再部署。
- 禁止把 Carl-1 的任何配置、数据或路径写进本流程。

## 故障处理

| 现象 | 处理 |
| --- | --- |
| `等待部署锁超时` | 另一个部署仍在跑；`--status` 看当前 sha 与状态，必要时等其结束 |
| `运行目录有未提交改动` | 在运行目录执行 `git status` 看是谁改的，把改动提交推送后再部署；不要直接丢弃 |
| `提交不在任何远端分支上` | 先把开发 worktree 的提交推送到 origin |
| `rolled_back` | 目标提交迁移失败。看 `~/pilot/state/dev-site-deploy.log` 定位，修复后重试 |
| 页面仍是旧样式 | `pilot build --apps reli_lims` 已被脚本执行；检查浏览器缓存与 Service Worker |

## 并行 Agent 约定

- 一个会话只操作自己的 worktree；运行目录是共享的，只能通过部署脚本写。
- 需要验证运行时时，用 `--status` 确认当前部署的 sha 与自己的提交一致；
  不一致说明别人刚部署过，重新部署自己的提交（排队）即可，不要手工覆盖。
