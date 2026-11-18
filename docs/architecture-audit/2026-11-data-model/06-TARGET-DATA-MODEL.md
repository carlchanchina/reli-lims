# 06 · 目标数据模型（建议，未实施）

原则：**不加只是"看起来优雅"的表**。新增只在它能承担现有代码无法表达的信息（实验室范围、规格、价格条件）时才成立。所有 `PROPOSED` 均未实现。

## 6.1 概念去留总表

| 概念 | 现状 | 建议 | 理由 |
|---|---|---|---|
| `Capability Source` | 已实现 | **保留** | 批次溯源 + 幂等，价值明确 |
| `Capability Upload` | 已实现 | **保留** | 上传请求幂等壳，与 Source 分工清楚 |
| `Laboratory Capability` | 已实现 | **保留为唯一事实层** | 条款/限制/条件/来源行都在这里 |
| `Test Object` / `Test Standard` | 已实现 | **保留** | 共享字典，去重价值高 |
| `Test Project` | 已实现 | **保留，但重新定义**：能力归并单元，**不承载价格、不冒充商品** | 现在被当成"商品的原型"，才产生 1:1 硬绑 |
| `Test Method` | 旧字典 | **降级为历史兼容**，新流程一律用 Project + Standard | 与 Project 概念重叠（自带 project/standard/asset） |
| `Item.custom_reli_test_method` | 兼容字段 | **冻结**（不再写新数据） | 旧数据引用 |
| `Item` | ERPNext 原生 | **保留，但只做商业载体** | 库存/税务/价目表/订单都靠它，不该替换 |
| `Service Specification` | **PROPOSED** | **新增（先以 JSON schema + 视图形态，后建 DocType）** | 承载"对象族 + 标准族 + 条件模板 + 设备/箱体约束 + 实验室范围 + 计价口径" |
| `Service Offering` | **PROPOSED** | **建议不建** | 与 Item 职责重复；商城侧已有 Medusa Offer |
| `Pricing Rule` | ERPNext 原生 | **复用**（若需按规格定价，用 `Item Price` + 规格维度或自定义价目视图） | 不另建价格体系 |
| `Quotation Item` 快照 | 已实现（半） | **改造**：三列字典改为写入时冻结 | 见 5.7 |
| `Test Project Standard/Object` | child，无实验室维度 | **改造**：加 `laboratory` 维度，或改为"按实验室视图" | 多实验室失真 |

## 6.2 关系调整（谁该从单值变多值）

| 关系 | 现状 | 建议 |
|---|---|---|
| `Item → Test Project` | 单值 Link（硬 1:1） | 改为 `Item → Service Specification → Test Project`；Item 不再直挂项目 |
| `Test Project → 标准/对象` | 子表（无实验室） | 子表加实验室维度，或保留子表 + 新增"实验室范围视图" |
| `Laboratory Capability → Item` | 能力行被 Item 反向单值引用 | 由 Specification 承接，Item 通过发布映射关联 |
| `Quotation Item → 字典` | 活引用（validate 时覆写） | 写入时冻结 |
| 商品 ↔ 商城 Offer | `Mercur External Mapping` 单条映射 | 保留；Specification 映射到 Offer 的 `variant`/metadata |

## 6.3 两种商品模型的正面对比（高温试验案例）

**场景**：一个"高温试验"项目，覆盖
- 对象：电子组件、整车部件、涂层材料；
- 标准：GB/T 2423.2、IEC 60068-2-2、企业标准；
- 条件：+85℃/85%RH、+125℃ 干热、不同箱体（1m³ 与 8m³）；
- 实验室：苏州实验室（只做电子件，8m³ 箱体）；盐城实验室（做整车件，不做涂层）。

### A 案：一个项目 = 一个 Item（现状）

- 优点：简单、与 ERPNext 天然契合、报价快；每项目一个价目表条目。
- 缺点（在本案例中全部暴露）：
  1. 四种条件组合只能一个价 → 要么报均价（亏/丢单），要么每次手工改价（不可追溯）；
  2. 两个实验室能力不同但共用一个 Item → 客户可能买到"本实验室做不了"的组合，直到履约才暴露；
  3. 想区分价格只能再造 Item（项目相同即可通过校验，没有规则约束），最终出现"一个项目 N 个价格不同的同名商品"，商品库变成手工台账。

### B 案：一个项目 = 多个规格，规格可复用/对应不同 Item

- 优点：
  1. 规格承载"对象族 + 标准族 + 条件 + 箱体/设备 + 实验室范围"，只在这些维度内计价，价格可解释；
  2. 报价选的是规格，条件来自规格模板，不用每次从 schema 现填；
  3. 一个规格可映射到一个 Item（一规格一价）；也可多规格共用 Item + 属性区分（ERPNext Item Variant/Attribute）；
  4. 能力/标准的变更先影响规格，规格审核后才影响对外商品——有缓冲层。
- 缺点：多一层实体、需要规格维护与审核、迁移期要并行 A 案。

### 推荐：**B 案，但分两步落地**

- 第一步（不动 DocType）：把现有 `Test Project.condition_template` 升级为"规格模板集合"（JSON 里允许多个 `specification` 块），Desk 上用视图呈现"项目 → 规格"，报价仍走 `capability`。
- 第二步（验证后再建表）：新 `Service Specification` DocType（`project / object_scope / standard_scope / condition_template / equipment_constraint / laboratory_scope / pricing_mode`），`Item` 增加 `custom_reli_specification` Link；`Item.custom_reli_test_project` 降级为派生字段。
- 不建议一次性重构：现有 660 条能力、120 个项目、9 个商品和 35 张历史报价都依赖当前路径。

## 6.4 数据归属：ERPNext 还是 RELI LIMS 还是 NTBLN

| 数据 | 归属 | 说明 |
|---|---|---|
| Item、Item Price、Pricing Rule、Quotation、Sales Order、Customer、Contact、Address、Asset、Project、Quality Inspection、Web Form、File | **ERPNext/Frappe 原生** | 不复制、不重建；reli_lims 只加自定义字段与校验 |
| 能力、能力源、上传壳、审核日志、项目/对象/标准字典、检测条件 schema | **RELI LIMS** | 实验室专有语义，ERPNext 无对应 |
| 委托/样品/方案/报告 | **RELI LIMS** | 原生单据之外的必要补充 |
| 门户身份、工作区、成员、文件柜 | **Bridge（mercur_erpnext）** | 与 ERP 用户/客户解耦的身份模型 |
| 营销内容、客户工作台界面、询价入口 | **NTBLN** | 只读 ERP 的"有界投影"，写操作全部经 Bridge |
| 商品目录、Offer、卖家、订单（面向外部买家） | **my-marketplace（Medusa/Mercur）** | 通过 `Mercur External Mapping` + 签名目录同步 |

## 6.5 Bridge 该承担什么

1. **唯一的跨系统写入口**：门户/商城的一切写操作经 `portal_runtime.dispatch` 的动作白名单（3.6 列出），不允许直连 ERPNext REST。
2. **身份与授权转换**：`NTBLN Portal Identity/Workspace/Membership` 映射到 `Customer` 与 `Company`，`authorize_actor` 收口。
3. **发布闸门**：`capability_publication.publish` 的审批绑定（`approval_reference` + `scope_snapshot` + `pricing_mode`）保证"对外可见"与"内部可用"分离。
4. **幂等与重放**：`Mercur Sync Event`（`idempotency_key`/`payload_hash`/`retry_count`/`Dead Letter`）与 `Mercur External Mapping`（`mapping_key`）承担至少一次投递的收敛。
5. **不该承担的**：业务定价、能力归并、报告排版——这些留在各自领域。

## 6.6 明确不推荐的改动

- 不新建 `Service Offering`（与 Item/Medusa Offer 三重身份）。
- 不把 `Laboratory Capability` 拆成"能力 + 条件"两张表（条件已经是 JSON schema，拆开只会增加写入路径）。
- 不把 ERPNext `Quotation/Sales Order` 替换成自定义单据。
- 不在迁移期删除 `Test Method`（旧委托/旧方案仍有 `test_method` 引用）。
