# 03 · 三个中心（+ 门户营销）的真实职责

## 3.1 页面结构（Desk Workspace，来自 `reli_lims/reli_lims/workspace/*/*.json`）

| 工作区 | 标题 | 菜单（links） | 性质 |
|---|---|---|---|
| `testing_center` | 工作台首页 | 无 links（仪表盘式入口） | 聚合入口 |
| `testing_fulfillment_center` | 检测履约中心 | 检测委托单→`Test Request`、样品→`Sample`、试验方案→`Test Program`、检测报告→`Test Report`、项目→`Project`、设备→`Asset` | 履约执行 |
| `laboratory_capability_center` | 实验室能力中心 | 检测项目→`Test Project`、检测对象→`Test Object`、检测依据（标准/方法）→`Test Standard`、实验室管理→`Laboratory Profile`、能力来源→`Capability Source`、全部能力明细→`Laboratory Capability`、服务商品→**`Item`（裸列表）**、实验设备→`Asset` | 主数据 |
| `commercial_intake_center` | 商业接单中心 | 客户→`Customer`、询价跟进→`Opportunity`、联系人→`Contact`、地址→`Address`、销售订单→`Sales Order`、客户组织→`CRM Organization`、线索→`CRM Lead`、商机→`CRM Deal` | 商业 |

能力中心另有独立 Page `reli_capability_hub`（`reli_lims/page/reli_capability_hub/`），顶部计数包含"未归类能力 / 服务商品"，动作含"实验室管理""服务商品关联（以中文服务名称关联检测项目与 Item）"。

## 3.2 角色与权限

`hooks.py:10-12` 固定 fixture 五个角色：`Lab Manager`、`Lab Engineer`、`Lab Reviewer`、`Mercur Integration`、`Laboratory Directory Reader`。

| 角色 | 典型权限面 |
|---|---|
| Lab Manager | 能力审核/发布/停用、项目归类、商品关联 |
| Lab Engineer | 委托执行、方案、结果录入 |
| Lab Reviewer | 报告复核、能力复核 |
| Mercur Integration | 仅服务身份，用于 Bridge 服务端调用（`integration_access.py`） |
| Laboratory Directory Reader | 只读能力目录（供 Bridge 读已发布能力） |

商业单据读取不是无界的：`commercial_access.py` 只暴露"有界投影"（客户/报价/订单查询函数 `customer_query` / `quotation_query` / `sales_order_query`，均带 filters）。

## 3.3 各中心读写哪些 DocType

| 中心 | 写 | 读 |
|---|---|---|
| 实验室能力中心 | `Capability Source`(导入)、`Laboratory Capability`(审核/发布)、`Test Project`/`Test Object`/`Test Standard`(字典)、`Laboratory Profile`、`Item`(关联) | 全部技术层 |
| 检测履约中心 | `Test Request`、`Sample`、`Test Program`、`Test Report`、`Project` | 能力（只读已发布）、报价/订单（只读） |
| 商业接单中心 | `Quotation`、`Sales Order`、`Customer`、`Opportunity`、CRM 对象 | 能力/商品（选择用）、委托（反查） |

## 3.4 API 调用链（实际函数名）

- 能力目录 → Desk 与外部：`capability_catalog.dashboard/projects/objects/standards/laboratories/service_items/laboratory_details/source_details/reassign_capabilities`。
- 能力检索与配置：`capability_selection.search/line_details/configure`（`configure` 走 `build_configuration`，按 `condition_schema` 校验条件）。
- 审核发布：`capability_review.search/preview/review/publish/retire`；确认与发布单条：`capability_api.confirm_capability/publish_capability/unpublish_capability`。
- 导入：`capability_api.import_capability_source(source_name)`。
- 报价：`capability_quotation.prepare_lines(selections)` → 每行返回 `custom_reli_capability / test_project / test_object / test_standard / configuration`。
- 委托：`capability_request.prepare_items / quotation_items / execution_items`。
- 订单→委托：`sales_order_testing.prepare_lines/resolve_quotation_customer/retry/requests/accept_quotation`。
- 门户：`mercur_erpnext_bridge.portal_runtime.dispatch`，动作集见 3.6。

## 3.5 三个中心之间靠什么贯通

```
能力行(CAP) ─┬─ 审核发布 ─→ 可报价
             ├─ test_project ─→ Item(服务商品) ─→ Quotation.Item
             └─ condition_schema ─→ config JSON ─→ Quotation.Item.custom_reli_configuration
                                                        │
                         Quotation ──(Sales Order)──────┴─→ Test Request Item.technical_configuration → Test Program Item
```

即：**唯一的贯通键是 `capability` + `configuration`**，`Item` 只是价格壳。中心之间没有"服务目录"这层实体，所以商业中心看到的商品列表 = ERPNext 所有 Item（能力中心里那条链接就是裸 `Item`）。

## 3.6 门户侧的"营销/商务"（ntbln，不属于 Desk 三中心）

- 路由：`_marketing`（营销/内容页）、`_authenticated`（客户工作台）、`api/testing/upload`（能力表上传）。
- 商业动作全部经 `portal_runtime.dispatch`，实际动作名（`portal_runtime.py:215-300`）：
  `me`、`capability.source.upload|get`、`command.get`、`mercur.customer.session`、`commerce.inquiry.create`、`quotation.sales-order.create`、`capability.publication.check`、`test-report.list|pdf`、`test-request.progress`、`test-request.get|save|confirm|file.upload|file.get`、`quotation.test-request.create`、`quotation.list|get|pdf|accept`、`inquiry.quotation.request|create`、`inquiry.create|get`、`suite.provision|membership.sync`、`cabinet.*`、`buyer.provision`、`buyer.exceptions`、`party.candidates|link|unlink`、`onboarding*`。
- 门户对 ERP 的可见面严格受 `NTBLN Portal Membership`（用户-工作区-角色）约束，工作区绑定 `erp_customer`。

## 3.7 中心设计的三个实际缺陷

1. 能力中心的"服务商品"入口无筛选（裸 Item 列表），销售与实验室看到同一张表，但没有"哪些项目已商品化"的视图（靠近的替代是 `capability_catalog.service_items(project=...)`）。
2. 商业中心没有"服务目录"页，只能从 Item 反查项目（`item_relations.js` + `business_relations.item_relations`）。
3. 履约中心的技术配置是"只读复制"，不能回写能力条件模板，导致同一能力每次报价都从 schema 重新填。
