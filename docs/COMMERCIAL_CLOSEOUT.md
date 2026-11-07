# 商业接单中心收口（Quotation → Sales Order → Test Request）

本轮只做收口与缺陷修复，不重写商业模型：报价、订单、委托仍是 ERPNext / Reli LIMS
原生单据，检测技术字段仍是 `custom_reli_*` 自定义字段。

环境：`carl` 开发站（Frappe 16.54.0 / ERPNext 16.53.0 / Frappe CRM 1.86.0）。
生产 `Carl-1` 全程未操作。

## 1. 先把「映射缺口」定位清楚

上一轮把 `make_sales_order` 返回空行记成了映射缺陷。复测结论：**空行是原生行为，不是缺陷**。

- 复现对象 `SAL-QTN-2026-00012` 当时已经是 `status = Ordered`，三行全部已下过单。
- `erpnext.selling.doctype.quotation.quotation._make_sales_order` 用
  `get_ordered_items() + get_qty_already_mapped()` 判断余额，`can_map_row()` 对无余额行返回
  `False`，因此映射结果为空。这是 ERPNext 的既有语义。

真实的缺口在别处，且都会造成实际业务损失：

| # | 现象 | 根因 | 处理 |
|---|------|------|------|
| 1 | 映射出的订单没有「交付日期」 | Quotation 没有 `delivery_date` 同名字段，`custom_reli_delivery_date`（承诺交期）不会被 `get_mapped_doc` 复制 | 服务端 `inherit_quotation_terms`（`before_validate`）按来源报价补齐；前端 `refresh` 同步预填 |
| 2 | 映射后订单保存被拦：`In 服务商品, 交付日期 is required in every row` | 行级交付日期列已被隐藏，但客户端仍要求逐行填写；表单级交期为空 → 死循环 | 前端从来源报价取承诺交期，同时回填 doc 与行 |
| 3 | 技术字段被上游漏掉时静默丢失 | `get_mapped_doc` 只复制同名字段 | `validate_lines` 已能从来源报价行回填；新增校验：来源有快照而订单行为空则报错 |
| 4 | CRM 生成的报价单无法记录客户接受、无法提交订单 | CRM 建单时 `quotation_to = "CRM Deal"`、`party_name` 是商机、没有 `customer` 字段 | 新增 `quotation_customer()`：按 CRM 组织 → `China Enterprise Link` → Customer 解析；4 处调用点改为用它 |
| 5 | 订单提交后委托「生成失败：来源报价与委托客户或公司不一致」 | `capability_request.validate` / `request_commercial.py` 直接用 `party_name` 比客户 | 同上，统一走 `quotation_customer()` |
| 6 | 报价页出现两个同义按钮（定制「创建销售订单」+ 原生「创建 → 销售订单」） | 历史定制按钮 | 删除定制按钮，只保留原生路径 |

> 设备规格说明：报价/订单不单独复制设备型号，设备由快照里的
> `snapshot.laboratory` + `capability_scope` 在履约阶段解析到 Asset（`custom_reli_model`、
> `custom_reli_parameters`）。商业单据冻结的是实验室与能力范围，避免和设备主数据双写漂移。

## 2. 改动清单

- `reli_lims/sales_order_testing.py`
  - `quotation_customer()` / `resolve_quotation_customer()`：客户解析（Customer / CRM Deal）
  - `inherit_quotation_terms()`：承诺交期 → 订单交期（含行级）
  - `validate_lines()`：客户比对改用解析结果；快照丢失时抛错
  - `accept_quotation()`：允许 CRM 来源报价
- `reli_lims/request_commercial.py`、`reli_lims/capability_request.py`：同一套客户解析
- `reli_lims/hooks.py`：注册 `Sales Order.before_validate`
- `public/js/sales_order_testing.js`：预填客户与交期（原生映射后即可保存）
- `public/js/quotation_acceptance.js`：`quotation_to ∈ {Customer, CRM Deal}`
- `public/js/capability_quotation.js`：移除重复的「创建销售订单」按钮
- `reli_lims/workspace/commercial_intake_center`：新增「CRM 客户关系」分组
  （客户组织 / 联系人 / 线索 / 商机），保留报价单与销售订单入口，不新增第四个中心
- `tests/test_p4_orders_equipment.py`：2 个原生映射回归

## 3. 浏览器 E2E（真实点击，不构造订单行）

两条链路都在 `carl` 开发站用 Chromium 跑通，截图为真实页面。

### A. 报价 → 原生订单 → 委托

| 步骤 | 结果 |
|------|------|
| 新建报价，选客户「苏州云杉检测技术有限公司」，承诺交期 2026-12-15 | OK |
| 「选择检测服务」→ 勾选已发布能力 → 使用所选能力 | 首屏即可确认（固定 footer） |
| 提交报价 `SAL-QTN-2026-00025` | OK |
| 记录客户接受 | OK |
| 原生「创建 → 销售订单」 | 1 行，能力/项目/依据/对象/快照/数量/单价全部带入 |
| 保存后交期自动补齐 2026-12-15 | OK |
| 提交 `SAL-ORD-2026-00015`，生成状态「已生成」 | OK |
| 打开委托 `REQ-01553` | 1 行检测项目，标准 STD-01543 |

截图：`docs/closeout/shots/11-*.png`

### B. CRM 商机 → 报价 → 原生订单 → 委托

| 步骤 | 结果 |
|------|------|
| 打开 CRM 商机 `CRM-DEAL-2026-00001` → 「创建报价」 | 新标签页打开报价 `SAL-QTN-2026-00029`（报价对象=CRM商机） |
| 选择检测服务、填承诺交期 2026-12-20、提交 | OK |
| 记录客户接受（此前不显示按钮，已修复） | OK |
| 原生「创建 → 销售订单」 | 客户自动解析为「苏州云杉检测技术有限公司」，技术字段完整 |
| 提交 `SAL-ORD-2026-00018` | 生成状态「已生成」 |
| 打开委托 `REQ-01554` | 1 行，客户/交期/技术条件与报价一致 |

## 4. 回归

```
bench --site carl run-tests --module reli_lims.tests.test_p4_orders_equipment
```

新增：
- `test_native_order_mapping_preserves_technical_scope_and_promised_date`
- `test_native_order_mapping_repairs_dropped_technical_snapshot`

## 5. 仍待处理

- ~~「从报价单创建委托」的报价选择器（`capability_request.quotation_items` /
  `commercial_access.quotation_query`）仍只收 `quotation_to = "Customer"`。~~ **已在第 6 节收口**：
  CRM 商机来源报价经企业主档解析出唯一客户后可被实验室选中，商机编号不出现在标签里。
- 销售用户仍持有 ERPNext 原生 `Customer` 的 create 权限，理论上可绕过企业主档查重直接建客户。
  建议下一轮用角色收敛或强制走 `ensure_customer`。
- 报价单 `custom_reli_delivery_date` 目前是普通字段，未做「客户接受后才锁定期限」的约束。

## 6. 报价来源与可履约边界（第二轮）

第一轮遗留的「实验室手工建委托只能选到原生客户报价」在本轮收口。核心是把散落在
4 处的客户解析收敛成一个模块，并给报价行加上**可履约数量**约束。

### 6.1 新增 `reli_lims/quotation_origin.py`

| 函数 | 职责 |
|---|---|
| `quotation_customer(name)` | 报价 → 唯一客户。原生报价直接返回 `party_name`；CRM 商机报价按 `CRM Deal → CRM Organization → China Enterprise Profile → China Enterprise Link(is_active=1) → Customer` 解析，解析不出返回 `None` |
| `deal_customers(deals)` | 批量版，固定 3 条 SQL，避免选择器里 N+1 |
| `deal_names_for_customer(customer)` | 反查：某客户名下有哪些商机（供选择器过滤） |
| `fulfillable_lines(quotation)` | 报价行 → 仍可履约的**检测服务**行：过滤普通服务/实物商品，扣掉已下单（`Sales Order Item`，`docstatus<2`）与已转委托（`Test Request Item`，非订单来源）的数量 |
| `validate_line_capacity(row, doc)` | 服务端守卫：累计委托数量不得超过报价行数量 |
| `fulfillable_exists_sql(alias)` | 与 `fulfillable_lines` 等价的 SQL 谓词，供选择器在库侧过滤 |

`sales_order_testing.quotation_customer` 改为转调本模块，保持旧调用点（4 处）不变。

### 6.2 行为变化

1. `capability_request.quotation_items` 接受 `quotation_to ∈ {Customer, CRM Deal}`，
   但**必须解析出唯一客户**才放行；解析失败抛「无法从该报价解析出唯一客户」。
   新增可选参数 `customer` / `company`，与当前委托不一致时直接拒绝（防串单）。
2. 只返回可履约检测行，`requested_quantity` 取**剩余数量**而非报价数量；
   全部行都已下单/已转委托时抛「该报价没有可履约的检测服务行」。
3. 选择器标签用解析后的客户名，不暴露商机编号。
4. 委托行新增 `quoted_rate`（币种快照字段，`read_only`，仅服务端写入）。
5. `_filters()` 兼容 HTTP 传入的 JSON 字符串——此前 Link 字段从 HTTP 调进来时
   `filters` 是字符串，`filters.get()` 会静默失配，商户/公司条件实际不生效。

### 6.3 部署注意

`test_request_item.json` 新增 `quoted_rate` 字段，合并后需
`bench --site <site> migrate` 才会建列；未迁移时 `validate` 写该字段会报
`Unknown column`。

### 6.4 回归

```
bench --site carl run-tests --module reli_lims.tests.test_quotation_origin
bench --site carl run-tests --module reli_lims.tests.test_p4_orders_equipment
```

- `test_quotation_origin`：5 项全 PASS（2026-11-07，`carl` 开发站，25.06s）
  - 原生客户报价只导入可履约检测行
  - CRM 商机报价解析出客户且可被选中、且不出现在其它客户的选择器里
  - 商机未关联企业主档时拒绝导入
  - 价格快照落库 + 超量委托被拦截
  - 已转订单的行从选择器消失
- `test_p4_orders_equipment`：28 项全 PASS（246.51s），无回归。
