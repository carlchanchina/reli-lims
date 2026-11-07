# RELI LIMS 发布前收口报告（Carl 开发站）

- 报告时间：2026-11-05
- 目标提交：`a778e8f`（分支 `feat/customer-collaboration`，PR #20）
  功能提交停在 `a20d800`，`a778e8f` 只追加本文与权限矩阵、能力审核、迁移回滚三份文档和验收证据
- 环境：Carl 开发站 `http://carl:8000`（192.168.10.204，站点 `carl`），当前已部署 `a778e8f`
- 范围：只操作开发站；**未合并到 main，未部署 Carl-1**

## 1. 结论

| 判断 | 结论 | 说明 |
| --- | --- | --- |
| 代码合并（#18 → #19 → #20） | **GO** | 本地按序演练 0 冲突；三个 PR 实测均 `MERGEABLE / CLEAN`；单元/集成/验收全绿 |
| 生产部署（Carl-1） | **NO-GO** | 5 项业务/配置前置未关闭，见第 7 节 |

合并顺序必须是 `main → #18 → #19 → #20`，三者是严格链式依赖，不能单独上线。
建议以 squash 方式合并 #20，让历史提交里出现过的演示链接密钥不进入 main。

### 关于 PR #20 的 `mergeable=false`

用户报的阻断点（HEAD `8369763`）已排查，结论是**不是内容冲突**：

| 证据 | 结果 |
| --- | --- |
| 以 `origin/main` 为起点，按 `#18 → #19 → #20` 顺序合并 | 三次全部 exit=0，冲突文件 0 个，终态 `a778e8f` |
| PR 页面当前状态（HEAD `a778e8f`） | #18 `MERGEABLE/CLEAN`、#19 `MERGEABLE/CLEAN`、#20 `MERGEABLE/CLEAN` |
| 期间是否做过 rebase / 冲突解决 | 没有。只前进了修复与文档提交 |

`mergeable=false` 出现在栈式 PR 的合并性重算窗口里（base 分支更新后 GitHub 会短时间返回
`UNKNOWN`，重算期间也可能给出 false），不是三方合并真的对不上。判定以「本地按序合并演练 +
PR 当前状态」两个直接证据为准。#20 的 base 是 #19 的分支，因此必须先合 #18、再合 #19，
#20 的合并性才有意义。


## 2. 本次关闭的问题

1. **客户链接密钥外泄**：文档中原先写有完整 `web_form_request_key`，已全部撤销并改写占位符；
   新增 `tools/rotate_customer_links.py`（唯一撤销入口）、`tools/acceptance/make_demo_link.py`
   （完整链接只落本机 600 文件，终端只打印掩码）、`tools/check_no_secrets.py`（部署前硬闸门）。
   开发站现存可用链接 = 1 条（仅用于演示，文件在 `~/pilot/state/demo-link.json`，权限 600）。
   注：验收脚本每跑一次会自己签发新链接，因此复跑后要再执行一次轮换。最终复核时撤销了
   7 条脚本遗留的可用链接，只保留 1 条演示链接（`REQ-01509`，分享号 `m16ttdgclg`，
   有效期至 2026-11-13，密钥 `rFC****`，完整值只在上述 600 文件里）。
2. **开发站对外域名错误**：站点 `host_name` 原指向 `https://carl-1.taila47902.ts.net`（Tailscale
   100.98.232.97，不是本机），会签发指向生产域名的客户链接。已改为 `http://carl:8000`，
   并重新轮换链接。
3. **Lab Engineer 能力读取**：新增只读权限；按实验室限域走 User Permission（`Laboratory Profile`），
   工程师只能看到所属实验室的能力，看不到其它实验室（`CAP-00077` 被拒为证）。
4. **正式受理不再依赖 Sales User**：客户/报价改读有界投影（`reli_lims/commercial_access.py`），
   履约项目作为受控系统动作创建；受理账号最小组合 = `Lab Manager + Projects User`，
   执行账号 = `Lab Engineer + Projects User`（脚本断言不含 `Sales User`）。
5. **CNAS 能力批量审核工作流**：能力中心内置审核台，支持按实验室/项目/标准/状态筛选、
   批量勾选、逐条留痕、发布前置校验、演示能力隔离（见 `docs/CAPABILITY_REVIEW.md`）。
6. **报告/方案默认打印版式**：原先打印走通用字段清单，已把 `Reli Testing Report` /
   `Reli Test Program` 设为默认版式，PDF 输出含报告头、草稿水印、检测明细与样品。
7. **能力审核记录子表**：新增 `Capability Review Log`，每次审核/发布/停用都追加一条，
   含动作、前后状态、操作人、角色、时间、意见。

## 3. 测试总账（目标提交 a778e8f，全部在开发站实跑）

| 类型 | 命令 | 结果 |
| --- | --- | --- |
| 纯逻辑单元测试 | `pytest tests` | **107 passed / 7 subtests** |
| Frappe 集成测试 | `bench --site carl run-tests --app reli_lims` | **62 passed** |
| 免登录共享安全 | `tools/acceptance/customer_share_security.py` | **39 / 39** |
| 最小权限 + 能力审核 | `tools/acceptance/capability_review_and_roles.py` | **25 / 25** |
| 正式受理与执行链路 | `tools/acceptance/formal_acceptance_flow.py` | **26 / 26** |
| 打印与 PDF | `tools/acceptance/print_pdf_check.py` | **17 / 17** |

四项验收脚本在部署到 `a778e8f` 之后复跑，全部为最终提交的结果（不是 `a20d800` 的旧账）：
`39/39`、`25/25`、`26/26`、`17/17`。明细见
`docs/acceptance/customer-collab/SECURITY_AND_FORMAL_ACCEPTANCE.md` 与开发站 `~/pilot/state/*.json`。

## 4. 最终 E2E 走查（同一批单据）

| 环节 | 单据 | 证据 |
| --- | --- | --- |
| 三中心工作台（中文、无重复入口） | — | `01-three-centers-home.png` |
| 商业接单中心（商务角色） | `SAL-QTN-2026-00008` | `02-commercial-intake.png`、`06-quotation.png` |
| 检测履约中心 | — | `03-testing-fulfillment.png` |
| 实验室能力中心 + 审核台 | 库内 659 条能力 / 待确认 652 | `04-laboratory-capability.png`、`05-capability-review.png` |
| 委托单（含客户协作） | `REQ-01523` | `07-test-request.png`、`request.pdf` |
| 客户免登录填写（手机/桌面） | `REQ-01509` 草稿链接 | `08-customer-mobile.png`、`09-customer-desktop.png` |
| 正式受理 → 项目 → 收样 | `PROJ-0014`、`SMP-01524/01525` | 验收脚本断言 |
| 试验方案 | `PRG-01526` | `10-test-program.png`、`program.pdf` |
| 试验记录 | 本次执行 19 行 | `11-test-records.png` |
| 报告草稿 + 正式版式 PDF | `RPT-01527` | `12-test-report.png`、`report.pdf` |

技术传递逐项校验通过：样品 2 条、检测项目 2 条、标准/方法、技术条件
（-40℃/24h 低温贮存、85℃/48h 高温工作）、能力快照、来源委托行、样品分配 4 组，
全部从委托延续到方案、记录与报告。

`report.pdf` 实测：1 页、162 KB，含「检测报告」「草稿／未签发，不作为正式签发报告」水印、
客户、项目、试验方案、检测委托、检测明细表（执行标准/适用样品/结果/结论）、KZH-833 与 -40℃。

## 5. 安全与权限核验

| 项目 | 结果 |
| --- | --- |
| 无 key / 错 key / 跨单据 / 跨客户 | 403 或 410，页面不泄露对方客户与内部 `STD-`/`MTH-` 编码 |
| 越权字段注入（客户/公司/状态/检测项目） | 全部无效，0 数量被拒 417 |
| 附件私有访问 | 落盘 `/private/files/`，匿名下载 403；MIME 白名单 + 文件头嗅探 + 10MB + 单委托 20 个 |
| 重复确认 | 417；确认后禁止再改 |
| 撤销 / 过期 | 撤销与过期链接均 410/403 拒绝 |
| 审计完整性 | 发送/打开/保存/确认/审核/撤销，含操作者类型、时间、IP、变更字段；Guest 不可读 |
| Guest 打印 | `PermissionError`；无实验室角色打印委托同样被拒 |
| Lab Engineer 权限 | 能力只读、限本实验室；改/审/发全部 `PermissionError` |
| Lab Reviewer | 可审核/退回，不能发布（`PermissionError`） |
| 演示 vs 认可 | 演示能力必须 `演示（非认可）` + `DEMO` 证书；批量发布需显式勾选；对外投影带 `demo_only` |
| 批量上限 | 单次 > 50 条直接拒绝；未审核能力不能发布 |

## 6. 数据迁移与回滚

- 迁移入口唯一：`tools/dev-site-deploy.sh`（flock 串行、只接受远端提交、脏树拒绝、
  部署前跑密钥闸门、migrate + build + 90 秒健康检查、失败自动回滚、状态写
  `~/pilot/state/dev-site-deploy.json`）。
- 本次真实回滚已验证：`8369763 → f0cb0be` 迁移因缺子表控制器失败，脚本自动回滚到
  `8369763` 并恢复服务（日志在 `~/pilot/state/dev-site-deploy.log`），随后修复重部署成功。
- 数据库变更均为向后兼容：新增子表 `Capability Review Log`、能力表新增字段
  （`demo_only`、`reviewed_by/on`、`published_by/on`、`review_note`、`review_log`）、
  `accreditation_type` 增加选项、默认打印版式。无破坏性 DDL、无数据改写。
- 回滚方式：`tools/dev-site-deploy.sh --sha <上一个提交>`（迁移不回滚，但新增表/字段对旧代码无副作用）。
- 详见 `docs/MIGRATION_AND_ROLLBACK.md`。

## 7. 剩余阻断（生产部署 NO-GO 的原因）

| # | 阻断 | 影响 | 关闭方式 |
| --- | --- | --- | --- |
| 1 | 652 条历史能力仍为「待确认」；已发布仅 7 条，其中 6 条是演示能力 | 真实报价/委托选不到认可能力 | 由实验室按 `docs/CAPABILITY_REVIEW.md` 分批审核发布（业务动作，代码不代办） |
| 2 | 正式报告版式缺 CNAS 标识、授权签字人、页码/骑缝章位 | 不能对外签发 | 补 `Reli Testing Report` 模板字段（下一迭代，不属于本 PR 范围） |
| 3 | 客户链接为单因子 URL（有有效期、可撤销、限流），仍可能被转发 | 客户数据暴露面 | 生产前评估是否叠加短信验证码/邮箱验证 |
| 4 | 生产站需自行设置 `host_name`，并确认 wkhtmltopdf 为 patched qt（开发站是 unpatched，PDF 证据改用无头 Chrome） | 链接与 PDF 可能异常 | 部署 Carl-1 前逐项核对 |
| 5 | Lab Manager 不能打开报价单据页面（设计如此，改走有界投影） | 内勤看不到报价单据全文 | 若业务需要，改为「复制原生权限 + 追加只读」方案，需单独评审 |

## 8. 合并建议

1. 评审并合并 **#18**（骨架，5 文件）——单独无业务价值，但是 #19 的 base。
2. 合并 **#19**（129 文件），随后执行一次 `migrate`（会建能力审核记录表与索引）。
3. 合并 **#20**（58 文件，squash 合并），合并后按 `docs/DEV_SITE_DEPLOY.md` 在预发环境复跑
   四个验收脚本；全绿后再谈 Carl-1 部署。

## 9. 复现命令

```bash
# 部署（开发站唯一入口）
ssh frappe@192.168.10.204 '~/pilot/benches/dev-bench/apps/reli_lims/tools/dev-site-deploy.sh'

# 测试
cd ~/pilot/benches/dev-bench/apps/reli_lims
~/pilot/benches/dev-bench/env/bin/python -m pytest tests -q
~/pilot/bin/pilot frappe --site carl run-tests --app reli_lims

# 验收
cd ~/pilot/benches/dev-bench
./env/bin/python apps/reli_lims/tools/acceptance/customer_share_security.py
./env/bin/python apps/reli_lims/tools/acceptance/capability_review_and_roles.py
./env/bin/python apps/reli_lims/tools/acceptance/formal_acceptance_flow.py
./env/bin/python apps/reli_lims/tools/acceptance/print_pdf_check.py

# 浏览器证据（截图 + 正式 PDF）
node tools/acceptance/browser_evidence.js --base http://carl:8000 \
     --user demo-lab-manager@example.com --password '***' --out /tmp/evidence --job job.json
```
