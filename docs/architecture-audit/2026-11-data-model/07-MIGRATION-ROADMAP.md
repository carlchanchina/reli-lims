# 07 · 分阶段改造计划（建议，未实施）

原则：**先让现有数据可信，再谈新实体**。每一阶段都可以独立回滚，且不触碰 ERPNext 核心。

## 阶段 0（只读改善，零 DDL）— 已完成，结果见 `08-PHASE0-DATA-AUDIT.md`

| 动作 | 产出 | 风险 |
|---|---|---|
| 生成"项目 × 实验室 × 标准 × 对象"覆盖矩阵（只读脚本） | 找出项目子表被多实验室污染的条目 | 无 |
| 生成"项目 × 商品 × 报价行"对账表 | 找出多 Item 挂同项目、报价行字典漂移 | 无 |
| 把 660→120 的归并清单与 `aliases` 缺口导出 | 同义未登记清单 | 无 |

验收：能用一张报表回答"某实验室到底能做哪些对象/标准"。

## 阶段 1（最小改造，约 1 周，不动 DocType）

最小改造清单（按优先级，全部是既有函数内的小改，不新增 DocType、不改表结构）：

1. **冻结三列**（必做，1 处）：`capability_quotation.validate` 中 `:111-115` 的覆写改为"仅当行内为空时回填"，已写入的值不再覆盖。同时给 `custom_reli_configuration` 增加 `snapshot_at` 与 `capability_modified` 时间戳，便于追溯。
2. **写入即快照**（必做）：`prepare_lines` 生成行时一次性写全三列 + 配置 + `item_name`，`validate` 只校验不重写。
3. **脏数据隔离**（低成本）：给 `Test Project` 加 `demo_only`（Check，默认 0），把 `TPR-01440`/`TPR-01541` 标出，目录与统计过滤；`TPR-01353` 名称拆分/别名修正在字典层处理。
4. **跨实验室提示**（只读逻辑）：能力中心在项目详情里显示"本项目由 N 个实验室并集构成，无单一实验室覆盖全部标准"，仅提示，不阻断。
5. **孤儿商品补溯源**：`publish`/保存时若 `custom_reli_service_capability` 为空，写入推算出来的首个能力并记 `source_inferred=1`。
6. **索引**（可选，DDL，需单独批准）：`tabItem(custom_reli_test_project)` 普通索引。当前表小，不紧急。
7. **回归检查**：把 `tools/a2_audit.py` 的漂移查询做成只读巡检项，纳入日常脚本（不自动修数据）。

验收：改一条能力的项目/对象/标准，历史报价与委托单据字段**不变**；`data/quotation_drift.csv` 复跑仍为 0 行。

不做的事：不建 `Service Specification`、不拆 `Test Method`、不动 ERPNext 字段、不批量改历史单据。

## 阶段 2（规格模板，3-4 周，仍不建表）

1. `Test Project.condition_template` 扩展为多规格 JSON（`[{spec_key, object_scope, standard_scope, conditions, equipment}]`）。
2. Desk 能力中心增加"项目规格"视图（读 JSON，不写新表）。
3. 报价 `build_configuration` 支持按 `spec_key` 取模板，条件默认值来自规格。
4. 价格仍走 ERPNext，但规格可绑定 `Item Price` 的 price list（一规格一 Item 或一 Item 多规格，用属性区分）。

验收：一个项目能报出两种不同尺寸/温度的价格，且价格来源可解释。

## 阶段 3（建 Service Specification，4-6 周）

1. 新 DocType（`project / object_scope / standard_scope / condition_template / equipment_constraint / laboratory_scope / pricing_mode / status`），带审核状态。
2. `Item` 增 `custom_reli_specification`；`custom_reli_test_project` 改为 fetch/派生。
3. Bridge 发布链路：`capability_publication` 的 `scope_snapshot` 改为引用规格。
4. 迁移：把阶段 2 的 JSON 规格批量落成记录；一个项目多条规格。

验收：商城 Offer 与规格一一对应，报价行能追溯到规格版本。

## 阶段 4（收口与清理，2 周）

1. `Test Method` 标记 deprecated，新单据不写；旧引用保留。
2. `Item.custom_reli_test_method` 停止写入。
3. `Laboratory Capability.merchant_offer_id / wiki_page_id` 迁移到 `Mercur External Mapping`，能力行只留内部字段。

## 暂时不要动（本轮明确建议保留原样）

- `Laboratory Capability` 的字段结构（事实层，任何改动都会伤历史）。
- `Capability Source.structured_json`（原始批次是唯一可回放的证据）。
- ERPNext `Quotation/Sales Order/Item` 的任何原生字段。
- `Quotation Portal Acceptance` / `Test Request Share Event`（客户共填链路的审计凭据）。
- 生产/开发站的演示数据（不进迁移脚本，不与真实数据混算）。

## 依赖与顺序

阶段 0 →（阶段 1 可并行）→ 阶段 2 → 阶段 3 → 阶段 4。阶段 2 未验收前**不要**建规格 DocType，否则会重复造一套"看起来对但没人填"的表。
