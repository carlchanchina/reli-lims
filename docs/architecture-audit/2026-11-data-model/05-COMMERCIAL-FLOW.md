# 05 · 商品、报价、订单与委托（逐问逐答，全部附代码依据）

## 5.1 Item 在哪里创建？

| 创建方式 | 代码 | 备注 |
|---|---|---|
| 报价时懒创建/复用 | `reli_lims/capability_quotation.py:14-59` `service_item(capability, item_code=None)` | 按 `custom_reli_test_project` 查已有销售型非库存 Item，取 `name asc` 第一条；没有再建 `RELI-SVC-<sha256(project)[:16]>` |
| 手工建后关联 | 能力中心"服务商品关联"（`reli_capability_hub.js:45-46`） | route_options 限定 `is_stock_item=0, is_sales_item=1` |
| 发布到商城 | `mercur_erpnext_bridge.item_publication.publish_item(item_code, expected_modified, version, state)` | 只发布，不创建 |
| 同步到商城目录 | `api.ingest_signed_catalog`（签名目录）→ `my-marketplace/workflows/erp-catalog-sync.ts` | 商城侧 Medusa Product/Variant/Offer |

`service_item` 的硬校验（逐条）：非库存（45）、可销售（45）、`business_type` 不得为"普通服务/实物商品"（52-53）、项目必须一致（48-51）。**这些校验说明设计意图就是"项目 ↔ 商品"一一对应。**

## 5.2 一个 Test Project 能否对应多个 Item？一个 Item 能否对应多个项目？

- **Item → Project：不能。** `custom_reli_test_project` 是单值 Link，且 `capability_quotation.py:50-51` 在项目不一致时 throw。
- **Project → Item：代码未禁止，但语义上排斥。** 复用逻辑按项目取第一条（`order_by="name asc", limit 1`），若存在第二个 Item 指向同一项目，永远不被自动选中；开发站实测 9 个商品对应 9 个不同项目，**没有一对多实例**。
- 结论：现行是 A 案（一对一），并且是**硬编码的一对一**，不是"约定"。

## 5.3 同一服务不同规格，是否要不同 Item？

现状：**没有规格这层，规格差异只能落在报价行的 JSON 快照里**（`capability_selection.build_configuration` 产出的 `snapshot` 含 `product_scope / project_label / standard_label / limitation / condition_schema / conditions`）。因此：

- 同一项目、不同箱体尺寸 → **同一个 Item、同一个 `rate`**，价格无法区分；
- 想让尺寸影响价格，只能建第二个 Item（绕过懒创建手动建），但 `capability_quotation.py:50` 会因项目一致而**不报错**（项目相同即可复用），于是两个 Item 都能被选，选择完全依赖人工 `item_code` 传参，没有规则。
- 这不是"设计如此"，而是"缺规格层"的直接后果。

## 5.4 报价行如何选择能力、如何保存对象/标准/条件

`capability_quotation.prepare_lines(selections)`（62-82）：

1. 传入 `selections` 数组（1-30 条），每条 `{capability_id, conditions, item_code?}`；
2. 逐条 `build_configuration(capability_id, conditions, "quotation")`：校验条件是否符合 `condition_schema`（未知键、类型、必填、select 选项、文本长度），产出 `{schema_version, capability_id, conditions, snapshot}`；
3. 选/建 Item；
4. 返回行数据：`item_code, item_name(=项目名称), uom, description, qty=1, custom_reli_capability, custom_reli_test_project, custom_reli_test_object, custom_reli_test_standard, custom_reli_configuration`。

`validate(doc)`（94-124）在保存/提交时：校验 `config.capability_id == row.custom_reli_capability`（103-104）；条件变化则重建 config 与描述（105-110）；**用活的 capability 覆盖三个字典列**（111-115）；提交（docstatus=1）时要求能力已发布且 `rate ≥ 0`（120-124）。

## 5.5 价格来自哪里？能否动态定价？

- `rate` 由用户在报价行填/由 ERPNext `Item Price` 取，reli_lims **不计算价格**，只在提交时校验非负。
- 尺寸、温度、时间、设备占用、箱体：**不参与定价**。它们只进入 `configuration.conditions` 与描述文本（`description()` 85-91）。
- 结论：动态定价在当前代码中**不存在**；需要"规格 + 价目表/Pricing Rule 带条件"或"规格级价格表"才能实现。

## 5.6 报价如何变成 Sales Order 和 Test Request

```
Quotation ──(ERPNext 原生 map)──→ Sales Order
   │                                   │
   └── quotation.accept → Quotation Portal Acceptance（客户接受记录）
                                       │
                     sales_order_testing.prepare_lines(selections)  ← 从订单行取可履约范围
                                       ▼
                              Test Request（capability_request.prepare_items）
                                       ▼
                          Test Program（services/test_request.make_test_program）
                                       ▼
                                  Test Report
```

关键约束：
- `quotation_origin.fulfillable_lines()`（187-209）只认 `custom_reli_business_type='检测服务'` 且 `custom_reli_capability` 非空、`configuration` 非空的行——**没有能力/配置的普通商品行不进入检测履约**。
- 幂等与容量：`quotation_origin.lock_quotation_lines / validate_order_capacity / validate_line_capacity`（255-307）会出现 `CAPACITY_CONFLICT`，防止同一报价行被超额转委托。
- 委托行保存 `source_quotation / source_quotation_item / quoted_quantity / quoted_rate` 与 `technical_configuration`，方案行再带 `equipment_snapshot`。

## 5.7 报价快照能否不受后续字典修改影响？

**半能。**
- `custom_reli_configuration` 是保存时的 capability snapshot（含标准名、产品范围、限制、条件 schema），字典改动**不会**改它，`description` 也不会变。
- 但 `custom_reli_test_project / test_object / test_standard` 三列每次 validate 都从 live capability 重写（111-115）；若能力被重新归类到别的项目/对象/标准，**历史报价行的这三列会跟着变**。
- 也就是说：文本与条件是快照，外键是活引用。`AUDIT_EVIDENCE.md` 里给了确切的调用点。

## 5.8 商城侧如何承接

- 商品发布：`item_publication.publish_item` → `Mercur External Mapping`（source_type/target_type + `mapping_key`）→ 商城 `erp-item-publication` 工作流 → Medusa Product/Variant/Offer。
- 能力发布：`capability_publication.publish` 需审批绑定，`scope_snapshot` 与 `pricing_mode` 必须与命令一致。
- 询价：`commerce.inquiry.create` / `inquiry.quotation.request|create`；客户接受：`quotation.accept`。
