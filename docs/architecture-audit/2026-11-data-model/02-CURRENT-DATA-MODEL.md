# 02 · 当前数据模型（以代码为准）

来源：开发站 main 代码 27 个 DocType 的 JSON 字段定义 + ERPNext/CRM 原生 DocType + Medusa 侧对象。凡本表标 `PROPOSED` 者代码中不存在。

## 2.1 技术能力层

| 实体 | 主键/命名 | 关键字段（Link 与类型） | 基数 | 写入方 | 读取方 |
|---|---|---|---|---|---|
| `Laboratory Profile` | `field:mercur_seller_id` | `laboratory_name`, `review_status`(Draft/Pending/Approved/Rejected), `draft_json`, `published_json`, `draft_revision`, `published_revision` | 1 实验室 = 1 档案 | Bridge `laboratory.submit_vendor_profile`（带 `expected_revision`） | 能力表、Bridge、商城卖家页 |
| `Capability Source` | `CAPSRC-{#####}` | `laboratory`→Laboratory Profile, `source_type`(CNAS/CMA/Excel/PDF/其他), `documents_source_id`（幂等键）, `documents_review_status`, `structured_json`(JSON, 必填), `import_status` | 一批文件 = 一条 Source | 解析入口（cnas-workbench / 手工） | `capability_api.import_capability_source` |
| `Capability Upload` | `hash` | `request_key`(唯一请求), `content_hash`, `parser_version`, `dedupe_key`, `previous_request`→自身, `reused_request`→自身, `status`, `revision` | 一次上传 = 一条（含重放关系） | ntbln `routes/api/testing/upload.ts` 经 Bridge | 解析与幂等判定 |
| `Laboratory Capability` | `CAP-{#####}` | `laboratory`→, `test_project`→Test Project, `test_object`→Test Object, `test_standard`→Test Standard(必填), `test_method`→Test Method, `product_scope`, `capability_scope`(必填), `clause`, `limitation`, `condition_schema`(JSON), `status`(待确认/已确认/已发布/已停用), `published`, `cnas_scope_key`(幂等), `merchant_offer_id`, `wiki_page_id`, `review_log`(Table) | 一条 = 一行认可范围 | `capability_api.import_capability_source` / 审核流程 | 报价、委托、商城资格校验 |
| `Test Project` | `TPR-{#####}` | `project_name`, `normalized_name`(归并键), `aliases`, `category`, `classification_status`, `condition_template`(JSON), `standards`(child), `objects`(child) | 一个 = 归并后的可卖单元 | 补丁字典 + 人工归类 | 能力归类、商品、报价 |
| `Test Project Standard` / `Test Project Object` | child | `test_standard`→, `basis_type` / `test_object`→, `category` | 多对多子表，**无 laboratory 字段** | 同上 | 同上 |
| `Test Object` | `OBJ-{#####}` | `object_name`, `normalized_name`, `aliases`, `category`, `active` | 44 条（开发站） | 字典维护 | 项目、能力、委托 |
| `Test Standard` | `STD-{#####}` | `standard_code`, `version`, `title`, `full_name`, `basis_type`, `status`, `effective_date`, `attachment` | 216 条 | 导入/人工 | 能力、项目、报价、方案 |
| `Test Method` | `MTH-{#####}` | `method_name`, `test_project`→, `category`, `default_standard`→, `default_workstation`→Workstation, `default_asset`→Asset, `default_condition`, `active` | 128 条，**历史字典** | 旧数据 | 能力（`test_method`）、委托、方案 |
| `Laboratory Equipment Scope` | child | `test_project`→, `capability`→ | 设备范围子表 | 人工 | 能力中心 |

技术层结论：

- 能力的"事实"全在 `Laboratory Capability` 一行（对象 + 标准 + 条款 + 限制 + 条件 schema + 来源行号），这是**唯一不丢信息的层**。
- `Test Project` 是**归并结果的投影**（名称 + 别名 + 标准集合 + 对象集合），本身不存条款/限制。
- `Test Method` 与 `Test Project` 有字段级重叠（方法自带 `test_project`/`default_standard`/`default_asset`），属于两条字典并行。

## 2.2 商业服务层（ERPNext 原生 + reli_lims 自定义字段）

| 实体 | 主键 | reli_lims 增加的关键字段 | 说明 |
|---|---|---|---|
| `Item` | `item_code` | `custom_reli_business_type`(检测服务/普通服务/实物商品)、`custom_reli_test_project`→Test Project、`custom_reli_service_capability`→Laboratory Capability（只读溯源）、`custom_reli_test_method`→Test Method（"原检测项目（兼容）"）、`custom_reli_business_relations`(HTML 面板) | 检测服务商品只由 `capability_quotation.service_item()` 懒创建，编码 `RELI-SVC-<sha256(project)[:16]>` |
| `Quotation Item` | 行 | `custom_reli_business_type`（从 `item_code` fetch）、`custom_reli_capability`→Laboratory Capability、`custom_reli_configuration`(JSON 快照)、`custom_reli_test_project/object/standard`→三个字典 | 快照与实时字典并存，见风险 |
| `Sales Order Item` | 行 | `custom_reli_business_type`（fetch） | 订单行靠 item_code 反查能力 |
| `Price` | ERPNext | 无 reli 字段 | `rate` 来自 Item Price / Pricing Rule，**能力与条件不参与定价** |
| `Customer` / `Contact` / `Address` | ERPNext | 无 | 由 CRM 桥接层 `ensure_customer` 或手工建 |
| CRM `CRM Lead` / `CRM Deal` / `CRM Organization` | Frappe CRM | `custom_cn_*`（企业资料/UUSCC/核验状态/侧栏面板，wekkona_china 提供） | 报价来源解析 `quotation_origin.deal_customers()` 从这里取客户 |

`PROPOSED`（**不存在**）：`Service Offering`、`Service Specification`、规格级价格（无 `Specification Price` 字段/表）、`Capability Price`。

## 2.3 检测履约层

| 实体 | 主键 | 关键字段 | 基数与流向 |
|---|---|---|---|
| `Test Request` | `REQ-{#####}`（submittable） | `customer`→, `company`→, `quotation`→Quotation, `sales_order`→Sales Order, `items`(child), `samples`(child), `business_stage`(待确认…已完成), `order_scope_snapshot`(JSON), `order_difference` | 一张委托可来自报价或订单，桥接见 `sales_order_testing.prepare_lines` |
| `Test Request Item` | child | `item_code`, `test_project`→, `test_object`→, `standard`→, `capability`→, `technical_configuration`(JSON), `service_item`→Item, `source_quotation`/`source_quotation_item`, `quoted_rate`, `requested_quantity`, `quotation_difference` | 一行 = 一个检测服务；技术配置从报价快照复制 |
| `Sample` / `Test Request Sample` | `SMP-{#####}` / child | 产品名、型号、尺寸、重量、序列号 | 委托收样后建 `Sample` |
| `Test Program` | `PRG-{#####}` | `project`→, `test_request`→, `items`(child), `samples`, `sample_assignments` | 由 `services/test_request.make_test_program` 生成 |
| `Test Program Item` | child | `test_project`/`test_object`/`standard`/`test_method`/`capability`, `technical_configuration`, `equipment_snapshot`, `result`, `quality_inspection`→ | 一行 = 一个执行任务 |
| `Test Report` | `RPT-{#####}` | `test_program`→, `version`, `status`(Draft/Review/Approved/Issued), `pdf_file` | 报告不与委托直连，只通过方案 |

## 2.4 客户与组织层

| 实体 | 主键 | 关系 | 备注 |
|---|---|---|---|
| `CRM Organization`（Frappe CRM） | name | 1↔N `CRM Lead`/`CRM Deal`；`custom_cn_enterprise_profile`→`China Enterprise Profile` | 生产 7 条全为演示数据，均未映射 |
| `China Enterprise Profile` | `ENT-{#####}` | 被 `China Enterprise Link` 引用 | 工商主档 |
| `China Enterprise Link` | name | `reference_doctype` ∈ {Company, Customer, Supplier, CRM Organization, Laboratory Profile} | 唯一的多态桥接表 |
| `Customer` | ERPNext | 1→N Quotation/Sales Order/Test Request | 一企一客户由桥接保证 |
| `NTBLN Portal Identity / Workspace / Membership` | Bridge | 用户—工作区—角色（OWNER…LAB_ADMIN） | 门户身份与 ERP 客户通过 `Workspace.erp_customer` 关联 |

## 2.5 谁创建、谁维护、谁读取（一句话版）

- **创建**：能力行 ← 解析导入；项目 ← 字典补丁 + 人工；商品 ← 报价时懒创建；委托 ← 报价/订单桥接；方案 ← 委托生成。
- **维护**：能力状态与发布 ← 实验室审核角色；项目归类 ← 实验室管理员；商品 ← 有 Item 权限者（报价时自动，故常由销售触发）。
- **读取**：门户与商城只读"已发布"能力（`capability_api.get_bridge_eligibility`）与已发布商品（`item_publication.get_published_service`）；Desk 三个中心读全量。

## 2.6 真实存在的重复与兼容

1. `Test Method` 与 `Test Project` 双字典（方法自带项目/标准/设备默认值）。
2. `Item.custom_reli_test_method` 与 `Item.custom_reli_test_project` 并存，前者标注"兼容"。
3. `Laboratory Capability.capability_scope`（必填自由文本）与 `project_parameter` / `product_scope` / `industry` 语义交叉。
4. `Test Request Item` 同时存 `quoted_rate`（报价快照价）与 `rate`（订单价）、`quotation` 与 `sales_order` 双来源。
5. 外部系统 ID（`merchant_offer_id`, `wiki_page_id`）直接放在能力行上，跨系统耦合。
