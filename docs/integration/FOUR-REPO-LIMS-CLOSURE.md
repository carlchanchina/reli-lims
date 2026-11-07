# Reli LIMS 四仓库收尾实施

2026-11-07，阶段 2。分支 `codex/four-repo-lims-closure`，基线 `c79113e9f01c5dac8b55deae30acbe59804d4b9d`（PR #23 候选）。基线包含 CNAS 分支及原生 Quotation → SO → Test Request 收尾。

## 实施范围

- 私有 CNAS 文件校验、按请求及内容去重，复用 Incoming Document 和 Parse Run。重复解析保留同一文档包的运行历史，批准版本必须属于本次 Parse Run。新原件建立新文档包。
- 只有 Documents 原生 `output_versions.resolve` 验证通过的 Structured Approved Version 能建立不可变 Capability Source。人工导入、能力审核和商业批准继续分别执行。
- 资格事件持久化递增 revision，包含撤回、过期、撤销和替代状态。真实已审 PDF、页码、不可变结构化版本、有效期、标准及实验室审核缺一即不可售。演示能力不可用于公开销售。
- 专用服务用户与角色、精确实验室绑定、每文档权限及列表约束。Portal 客户没有 ERPNext 通用报价写入权限。
- 原生接受业务方法及追加 Portal actor 审计。Bridge 负责当前 fingerprint、pre/post 变更关联、命令幂等和事务。
- 原生 SO 映射与直接委托共用报价及报价行锁，合并计算非取消 SO、非订单来源委托和本次拟创建数量。普通商品不经过能力链。
- 自动报价仅支持一个批准能力对应一条原生行。多能力方案返回 `TECHNICAL_APPROVAL_REQUIRED`，须人工批准完整行分配和价格，避免重复计费。

## 精确内部接口

| 函数 | 约束 |
| --- | --- |
| `portal_capabilities.upload(identity, context, payload, idempotency_key)` | context 含服务器已验证 source_instance、organization_id、laboratory_id；payload 遵循冻结文件契约 |
| `portal_capabilities.get(identity, context, payload)` | payload 仅 request_id，按当前组织与实验室查 receipt |
| `capability_api.list_bridge_eligibility(cursor=None, limit=100)` | GET，持久事件游标、含 tombstone |
| `capability_api.get_bridge_eligibility(capability_ids)` | POST，1–100 个 ID，重新校验当前资格并持久化变化 |
| `portal_sales_order.accept_for_portal(name, customer_contact, expected_customer, expected_company, actor_id)` | 内部窄权限方法，原生接受校验与 Portal actor 审计 |
| `portal_sales_order.make_for_portal(name, expected_customer, expected_company)` | 返回已 insert 的原生 SO 草稿；调用原生 expiry 校验和 `_make_sales_order` |
| `portal_sales_order.bind_request_for_portal(name, expected_customer, expected_company, fields)` | 返回带精确报价行、技术快照及剩余数量的原生委托 fields |
| `portal_sales_order.apply_inquiry_scope(fields, reference)` | 严格单能力版本及完整 scope 匹配；多能力需人工批准 |
| `capability_eligibility.invalidate_source(source_name, state, reason)` | 人工权限及实验室约束，追加状态事件，不改原始来源 |

失效通知调用 Bridge `capability_publication.invalidate_capabilities`，通过已有事件恢复机制处理。未部署 Bridge 新模块前不能启用通知及真实发布。

## 必需配置与角色

配置只写 DEV 站点私有配置，不写 Git。以下均为变量名称。

- `reli_lims_portal_bridge_user` 指定现有窄权限 gateway 用户，赋予 `Mercur Integration` 和 `LIMS Portal Adapter`。
- `reli_lims_capability_reader_user` 指定独立用户，赋予 `LIMS Capability Reader`。
- `reli_lims_portal_laboratories` 为精确对象数组，每个对象只含 source_instance、organization_id、laboratory_id。
- `reli_lims_cnas_extraction_profile` 是已核实的 Documents `Document Template` 名称，类型为 Extraction Profile，绑定 `source_schema`。
- `reli_lims_cnas_ai_provider` 是已核实的本地 Document AI Provider。适配器不自动选择云服务。
- 实验室人工用户须通过 User Permission 显式绑定 Laboratory Profile。System Manager 维持受控管理范围。

`integration_setup.after_migrate` 创建角色及收窄后所需 DocPerm，不自动给任何用户授角色。已有 ERP/Frappe 角色权限先复制保留，再追加新角色。适配权限仅允许已上传文档、配置中的 Schema/Profile/Provider 及当前内部商业操作的单个 Item。新机器角色误授其他用户也不能获得这些对象权限。

## DEV 部署前置与最小结构清单

2026-11-07 的 Carl DEV HEAD 为 `2579615a9cc2c2658c799cfbdafd3bdfc8afba8d`，存在已有覆盖。不得用本分支文件直接覆盖运行目录。

| 文件 | 与 DEV 的关系 | 所需操作 |
| --- | --- | --- |
| capability_api.py | DEV 等于 c791 基线 | 追加资格 API 与无歧义标准匹配 |
| capability_review.py | DEV 等于 c791 基线 | 将实验室筛选从 get_all 改为有权限的 get_list |
| hooks.py | DEV 含额外修改 | 三方合并已有 hooks，仅追加本轮事件与权限注册 |
| quotation_origin.py | DEV 为已有未跟踪文件 | 保留已有 CRM 来源逻辑，替换末尾额度校验并新增共享锁方法 |
| sales_order_testing.py | DEV 含已有商业修改 | 三方合并，只追加容量校验和原生接受 helper，不覆盖 CRM/交期逻辑 |
| tests/test_request_commercial.py | DEV 等于基线 | 仅离线测试依赖隔离，无运行部署需求 |

新增原生 DocType 为 Capability Upload、Capability Eligibility Event、Capability Source Status、Quotation Portal Acceptance。新增 Python 模块的完整路径及哈希见同目录清单。

结构同步对应 `reli_lims` 模块的 `capability_upload`、`capability_eligibility_event`、`capability_source_status`、`quotation_portal_acceptance`。标准迁移调用 integration_setup 后建立角色/DocPerm并初始化资格事件。若使用等价精确 reload_doc，仍须调用该幂等 setup 并清除 hooks/权限缓存。本轮没有前端资源修改，不需要新增 JS build。

部署唯一入口保持 `tools/dev-site-deploy.sh`。先在独立整合 worktree 将远端已有差异纳入可审计提交，确认不丢失任何修改，推送后通过脚本串行执行结构更新和健康检查。运行目录脏树未整合前，部署 BLOCKED。不能绕过其脏树守卫，不能手工在运行目录 checkout/reset/migrate。

## 验证与限制

离线使用现有 bundled Python（含 openpyxl）运行全部 tests。新增回归覆盖文件欺骗、过期/未审/演示资格、私有 PDF 页码、专用 reader 身份、ptype 权限、旧 Parse Run 批准不复用、部分订单加直接委托的共同余额及重复行数量。现有商业单测增加 customer resolver 依赖隔离，修复基线离线桩导入不完整的问题。

本轮未部署新代码，也未在真实站点执行新 DocType 迁移和并发事务测试。离线测试不替代新模块的 Frappe 集成测试或真实浏览器闭环。

Carl DEV 已发布 8 条能力均为软件/演示数据，缺合格审核来源。CAPSRC-00499、sel_dev_cnas_L11464 保持原审核状态，不能用于公开验收。公开实验室 E2E 为 BLOCKED，所需真实材料包括有效认可范围 PDF、哈希与逐条页码、证书有效期和核验记录、完整标准和限制、Documents 结构化批准、实验室 Seller/组织关系及独立商业批准。
