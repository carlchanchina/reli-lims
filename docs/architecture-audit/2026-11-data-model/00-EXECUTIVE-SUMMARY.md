# RELI LIMS × NTBLN 四仓库数据模型与商业架构审计 · 总体结论

- 审计日期：2026-11-18
- 审计基线：`reli-lims` GitHub `main` = `35c15e6`（本地工作区 `9f1f7dc`，落后 56 提交，本次以 main 为准）
- 方式：只读。未修改任何 DocType、数据、部署配置；未切分支（文档写在独立 worktree 分支 `docs/architecture-audit-2026-11`）
- 代码证据：开发站（`dev-bench`，`192.168.10.204`）实际检出的 main 代码 + GitHub `origin/main` 工作树

## 一句话结论

**技术能力层（Capability）是干净的，商业层是"借用 ERPNext 商品壳"的临时方案，两者之间只靠两个单值 Link 和一段隐形的懒创建逻辑连接；真正的缺口是缺一层"可售规格（Service Specification）"，而这一层代码里从不存在（全仓搜索 `service offering / service specification` 零命中）。**

## 七条主要结论

1. **没有 Service Offering / Service Specification。** 在四个仓库全文检索 `service offering|service_offering|service specification|service_specification` 结果为零。`docs/` 里有类似规划的叙述，但没有任何 DocType、表、字段或接口对应它们。凡本报告中标 `PROPOSED` 的实体均**尚未实现**。

2. **现行商品模型是 A 案，但“1:1”是三层不同的事实，不能混为一谈。** （a）**数据库层**：`Item.custom_reli_test_project` 是普通 Link 字段，`unique=0`、非必填，`tabItem` 上**连普通索引都没有**（`SHOW INDEX` 无该列），因此**不存在任何数据库唯一性约束**；（b）**代码层**：`capability_quotation.service_item()`（`reli_lims/capability_quotation.py:14-59`）按项目查已有商品、`order_by="name asc" limit 1` 只取第一条复用，找不到才建 `RELI-SVC-<sha256(project)[:16]>`，且传入的 `item_code` 若项目不一致直接 `throw("商品关联的统一检测项目不一致")`（`:50-51`）——这是**代码路径上的偏好**，不是约束；（c）**数据层**：开发站 9 个检测服务商品落在 9 个不同项目（`count(*)=9, count(distinct project)=9`，`having count>1` 为空），只是**当前现象**，随时可以被手工建第二个商品打破。

3. **能力的归并发生在 Capability → Test Project 这一层，而不是 Project → Item。** Test Project 的 `normalized_name`（`test_project.py:43`）+ `aliases`（`test_project.py:51-69`）是归并键；开发站 660 条 Laboratory Capability 已全部归入 120 个 Test Project，单个项目最多挂 55 条能力、51 条标准、30 个对象。

4. **Test Project 的"标准/对象"子表缺实验室维度。** `Test Project Standard` / `Test Project Object` 只挂 parent，没有 laboratory 字段。多实验室共用同一项目时，子表会被写成各实验室的**并集**，"某实验室只做其中一部分"这一事实只能回到 `Laboratory Capability` 行上才能看到。

5. **价格完全来自 ERPNext，能力与条件不参与定价。** `capability_quotation.py:123-124` 只校验 `row.rate` 非负；`build_configuration`（`capability_selection.py`）把对象、标准、产品范围、限制、条件 schema 全量塞进 JSON 快照，但**不产生任何价格**。尺寸、温度、箱体、设备占用目前无法形成不同报价，只能写进描述文本。

6. **报价行的"技术快照"只冻结了一半。** `custom_reli_configuration`（JSON）冻结 capability 快照与条件；但 `capability_quotation.py:111-115` 每次 validate 都用**活的** capability 覆盖 `custom_reli_test_project / test_object / test_standard` 三列。字典后续修改会改到历史报价行的这三列，快照并非完全不可变。

7. **三个中心的分工是清晰的，但它们没有共享一个"服务目录"实体。** 商业接单中心直接引用 ERPNext/CRM 原生单据；实验室能力中心的"服务商品"链接指向**裸 Item 列表**（`laboratory_capability_center.json`，`link_to = Item`）；检测履约中心管委托与方案。市场侧（ntbln）走 Bridge 的 `portal_runtime.dispatch`。

## 推荐架构（详见 `06-TARGET-DATA-MODEL.md`）

- **保留**：Capability Source、Laboratory Capability、Test Object、Test Standard、Test Project（作为"能力归并单元"，不含价格）、Quotation/Quotation Item、Sales Order、Test Request、Test Program。
- **降级/合并**：Test Method 明确为历史字典（仅保留给旧委托兼容）；`Item.custom_reli_test_method` 视作遗留字段。
- **新增（PROPOSED）**：`Service Specification`（服务规格：项目 + 对象族 + 标准族 + 条件模板 + 设备/箱体约束 + 实验室范围），作为唯一"可售单元"；Item 只做商业载体（一个 Item 可挂多个规格，或一规格一 Item 由发布策略决定）。
- **改造**：`Item ↔ Test Project` 从单值 Link 改为经 Specification 的间接关系；Test Project 子表增加 laboratory 维度或改为按实验室视图读取。
- **推荐商品模型 B**（一项目多规格），理由见 `06` 章的高温试验案例；但用 A→B 的渐进迁移，不一次性重建。

## 风险清单（按严重度）

| 级别 | 风险 | 位置 |
|---|---|---|
| 高 | 历史报价行的项目/对象/标准被字典变更改写 | `capability_quotation.py:111-115` |
| 高 | 多实验室共用项目导致标准/对象集合失真 | `Test Project Standard/Object` 无 laboratory |
| 高 | 尺寸/设备/箱体无法定价，报价靠人工 | `capability_quotation.py:120-124` |
| 中 | 一个 Item 只记首个来源能力，多能力合并后溯源丢失 | `Item.custom_reli_service_capability` 单值 |
| 中 | Test Method 与 Test Project 概念重叠，两条字典并行 | `Test Method.test_project` 等 |
| 中 | 生产/开发仓库版本漂移（reli-lims 本地落后 56 提交） | `01` 章 |
| 低 | 演示数据与真实数据混在同一站点 | 生产 7 个 CRM Organization 全为演示 |

## 实施优先级（只审计，不实施）

1. 先补"证据链"：给每个 Test Project 记录实验室范围（视图或字段），不动数据结构；
2. 再冻结报价：把 `test_project/test_object/test_standard` 从 live 覆写改为写入时快照；
3. 再引入 Specification（先作为 JSON schema + 目录视图，不建 DocType）；
4. 最后才谈 Item 与 Medusa Offer 的再映射。
