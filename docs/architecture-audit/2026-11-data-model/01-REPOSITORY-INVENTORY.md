# 01 · 四仓库现状盘点

盘点时间 2026-11-18。数值来自 `git` 与开发站 `dev-bench` 实际检出的 main 代码。**本地工作区普遍落后于 origin/main**，下表把两列分开，避免"看到旧代码下结论"。

## 1.1 版本与部署状态

| 仓库 | 技术栈 | 本地 HEAD | GitHub `origin/main` | 本地落后/领先 | 实际部署 |
|---|---|---|---|---|---|
| `carlchanchina/reli-lims` | Frappe/ERPNext app（Python） | `9f1f7dc`（分支 `codex/cnas-p1-5`，11-05，工作树 2 个 js bundle 未提交） | `35c15e6`（11-18） | 落后 56 | 生产 `apps/reli_lims` @ `35c15e6`；开发 `dev-bench` @ `35c15e6` |
| `carlchanchina/ntbln` | TanStack Start + Supabase（TS） | `266ba41`（`feat/ntbln-unified-portal`，10-30，76 个未提交文件） | `8e02484`（11-16） | 落后 69 | 节点侧门户服务（不在 Frappe bench 内） |
| `carlchanchina/mercur_erpnext` | Frappe app（Bridge，Python） | `76048db`（`codex/bridge-product-v1`，11-06，15 个未提交） | `b94d326`（11-14） | 落后 25 | `apps/mercur_erpnext_bridge`（开发站 `b94d326`；生产目录**无 .git**） |
| `carlchanchina/my-marketplace` | Medusa/MercurJS（TS + Postgres） | `0055e3f`（`fix/dev-panel-interop`，10-17，7 个未提交） | `ebd66ba`（11-14） | 落后 57 / 领先 5 | 独立容器（`docker-compose.yml`: postgres/redis/api） |

同一 bench 上构成"四仓库"运行面的还有 ERPNext 原生与两个支撑 app：`frappe`、`erpnext`、`crm`、`wiki`、`wekona_documents`、`suite`。其中 `wekona_china` 是 CRM 桥接层（只有自定义字段，**没有自己的 DocType**）。

## 1.2 reli-lims：27 个 DocType

主数据/技术能力层：`Capability Source`、`Capability Source Status`、`Capability Upload`、`Laboratory Capability`、`Laboratory Profile`、`Laboratory Equipment Scope`(child)、`Test Project`、`Test Project Object`(child)、`Test Project Standard`(child)、`Test Object`、`Test Standard`、`Test Method`。

商业/报价层：无自有 DocType，全部扩展现有 ERPNext 单据（`Quotation`、`Quotation Item`、`Sales Order`、`Sales Order Item`、`Item` 通过自定义字段接入）。

履约层：`Test Request`、`Test Request Item`、`Test Request Item Sample`、`Test Request Sample`、`Test Request Photo`、`Test Request Share Event`、`Sample`、`Test Program`、`Test Program Item`、`Test Program Item Sample`、`Test Program Sample`、`Test Report`、`Quotation Portal Acceptance`、`Capability Eligibility Event`、`Capability Review Log`。

模块（顶层 `.py`，按行数）：`customer_share.py` 649、`sales_order_testing.py` 382、`business_relations.py` 355、`capability_review.py` 312、`quotation_origin.py` 307、`customer_share_setup.py` 307、`capability_catalog.py` 298、`portal_capabilities.py` 294、`request_confirmation.py` 239、`capability_eligibility.py` 207、`capability_api.py` 195、`commercial_access.py` 184、`capability_selection.py` 171、`laboratory_api.py` 170、`capability_request.py` 167、`integration_access.py` 153、`portal_sales_order.py` 132、`hooks.py` 132、`request_scope.py` 127、`capability_quotation.py` 124、其余 ≤110。

hooks（`reli_lims/hooks.py`）：`app_include_js = ["business_relations.bundle.js"]`（17）；`doc_events` 把 `Test Request/Sample/Test Program/Test Report` 的四个事件统一挂到 `progress.update_progress`（31-35）；`after_migrate` 依次挂 6 个 setup 入口（36, 46, 49-53, 62）；`doctype_js["Quotation"]` 增加 `capability_quotation.js`（54）；`doc_events["Quotation"]["validate"] = capability_quotation.validate`（55）；`Test Request` 同理挂 `capability_request.validate`（57）；`Item` 挂 `item_relations.js`（58）；`File` 挂客户共填相关的三个事件（45-47）。

## 1.3 ntbln：门户（TanStack Start + Supabase）

- 工作区：`apps/web`（主体）、`apps/e2e`、`packages/{features,supabase,policies,billing,cms,mcp-server,...}`。
- 数据库：Supabase，迁移在 `apps/web/supabase/migrations`（7 个文件，最近 2026-10-28），内容集中在组织、邀请、能力类型、企业访问；**业务目录数据不在 Supabase**。
- 商业动作全部走 Bridge：`mercur_erpnext_bridge.portal_runtime.dispatch`，调用点 10 处：`commerce.server.ts`、`portal.service.server.ts`、`quotation-bridge.server.ts`、`suite-bridge.server.ts`、`party-bridge.server.ts`、`inquiry-bridge.server.ts`、`buyer-bridge.server.ts` 等。另有 `item_publication.get_published_service`（`live-service.server.ts`）。
- 解析能力：`apps/web/src/lib/testing/testing-model.ts` 明确"只描述解析服务（cnas-workbench）返回的结构，不新增业务对象"；`routes/api/testing/upload.ts` 是上传入口。

## 1.4 mercur_erpnext（Bridge）：8 个 DocType + 20 个模块

DocType：`Mercur Bridge Setting`、`Mercur External Mapping`、`Mercur Sync Event`、`NTBLN Portal Identity`、`NTBLN Portal Workspace`、`NTBLN Portal Membership`、`NTBLN Portal Folder`、`NTBLN Portal File`。

模块：`portal_runtime.py`（唯一的门户动作分发入口 `dispatch(action, identity, ...)`，206 行）、`portal_identity.py`、`portal_buyer.py`、`portal_party_schema.py`、`portal_party_store.py`、`ntbln.py`、`ntbln_intake.py`、`laboratory.py`、`seller_workbench.py`、`item_publication.py`、`capability_publication.py`、`commerce_inquiries.py`、`integration_contract.py` / `integration_mapping.py` / `integration_events.py` / `integration_setup.py` / `integration_center.py`、`closure_contract.py` / `closure_transport.py` / `closure_gateway.py`、`contracts.py`、`api.py`、`mercur_adapter.py`。

对外 API（节选，均 `@frappe.whitelist`）：`portal_runtime.dispatch`、`api.ingest_event` / `replay_event` / `ingest_signed_catalog`、`item_publication.publish_item` / `get_published_service`、`capability_publication.publish` / `check_offers` / `get_status` / `get_catalog_target`、`laboratory.get_vendor_profile` / `submit_vendor_profile` / `list_published_profiles` / `get_order_workbench` / `create_order_draft`、`ntbln.register_workspace` / `create_request` / `request_status` / `services`、`seller_workbench.bind_order_request`、`portal_identity.*`、`integration_center.connection_status`。

`capability_publication.publish` 的入参要求一份审批绑定（`mercur_capability_publication_bindings`），字段集为 `source_instance, organization_id, seller_id, laboratory_id, product_id, variant_id, approval_reference, approval_revision, required_groups, scope_snapshot, pricing_mode, approved_by, approved_at`——**这是"能力→商品"走向市场的唯一受控出口**，缺一项即 422 `COMMERCIAL_APPROVAL_REQUIRED`。

## 1.5 my-marketplace：Medusa/Mercur 商业外壳

- `packages/api` 依赖 `@medusajs/framework`、`@mercurjs/core`、`@mercurjs/types`：商品/变体/Offer/卖家/订单来自 Medusa + Mercur 扩展，不是自建表。
- 自有业务模块只有两个：`portal-integration`（含 1 个迁移 `Migration20261107000000.ts`）、`gmail-notification`。
- 与 ERPNext 的对接点：`lib/erp-catalog.ts:52` → `mercur_erpnext_bridge.api.ingest_signed_catalog`；`lib/reli-lims-laboratory.ts:67` → `mercur_erpnext_bridge.laboratory.{method}`。
- 工作流：`workflows/{erp-item-publication,erp-catalog-sync,create-order-draft,submit-laboratory-profile,testing-service}.ts`。

## 1.6 三类代码要分清

- **已实现（代码 + 迁移 + 接口）**：能力源导入、能力审核发布、项目/对象/标准字典、能力→商品适配、报价校验与快照、销售订单→委托、委托→方案→报告、客户共填 Web Form、Bridge 的门户分发与能力发布闸门。
- **仅文档规划**：Service Offering / Service Specification / 规格级定价 / 实验室维度项目子表 / 能力表 PDF-Excel 在线解析的完整闭环。
- **历史兼容**：`Test Method`（旧字典）、`Item.custom_reli_test_method`（"原检测项目（兼容）"）、`Laboratory Capability.merchant_offer_id` / `wiki_page_id`（外部 ID 混在能力行）、`Test Request.order_scope_snapshot` / `order_difference`（订单差异追踪）。
