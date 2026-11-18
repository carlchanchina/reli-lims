# 2026-11 数据模型与商业架构审计（只读）

基线：GitHub `main` = `35c15e6`（2026-11-18）。
性质：READ-ONLY。未改代码、未 migrate、未动数据、未合并 PR。仅新增本目录文档。

| 文件 | 内容 |
|---|---|
| `00-EXECUTIVE-SUMMARY.md` | 总体结论、七条判断、风险与优先级 |
| `01-REPOSITORY-INVENTORY.md` | 四仓库现状（版本、DocType、API、部署） |
| `02-CURRENT-DATA-MODEL.md` | 当前实体、字段、基数、写入/读取方 |
| `03-CENTER-RESPONSIBILITIES.md` | 三中心 + 门户的页面、权限、API 链 |
| `04-CAPABILITY-PARSING-FLOW.md` | 能力表上传→解析→归并→发布 |
| `05-COMMERCIAL-FLOW.md` | Item/报价/价格/快照/订单/委托逐问逐答 |
| `06-TARGET-DATA-MODEL.md` | 目标模型、A/B 商品模型对比、归属划分 |
| `07-MIGRATION-ROADMAP.md` | 五阶段改造与"不要动"清单 |
| `08-PHASE0-DATA-AUDIT.md` | 阶段 0 只读数据审计：660→120 实测、覆盖矩阵、跨实验室错配、高温试验案例、报价漂移基线、异常清单 |
| `data/` | 审计原始导出：`coverage_matrix.csv`（120 行）、`project_variance.csv`（74 行）、`quotation_drift.csv`（漂移基线） |
| `tools/a2_audit.py` | 只读复跑脚本（不写数据、不 migrate） |
| `AUDIT_EVIDENCE.md` | 每条结论对应的文件/函数/行号与证据不足项 |
| `diagrams/` | 7 张 Mermaid 图（总体架构、ER、能力→商品、三中心、解析流程、交易履约时序、阶段 0 数据现实） |

图表说明：`Service Specification` / `Service Offering` 均标注 `PROPOSED`（代码中不存在）。
