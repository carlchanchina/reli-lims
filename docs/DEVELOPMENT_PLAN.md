# Reli LIMS V1 Development Plan

## Objective

Build the smallest usable laboratory execution module for ERPNext 16 / Frappe.

Primary path:

`ERPNext Project -> Sample -> Test Program -> Test Program Item -> Result / optional Quality Inspection -> Review -> Test Report`

## Phase 1 — Frappe App Skeleton

Deliver:
- App package `reli_lims`
- Module `Reli LIMS`
- Workspace `Testing Center`
- Roles: Lab Manager, Lab Engineer, Lab Reviewer
- Basic permissions
- Naming series placeholders

Acceptance:
- Installs on ERPNext 16.
- Migrates cleanly.
- Workspace opens.
- No standalone SPA/admin frontend.

## Phase 2 — Core Masters

Implement:
1. Sample
2. Test Standard
3. Test Method

Acceptance:
- Sample must link ERPNext Project.
- Standard supports code/version/title/status/file.
- Method supports reusable capabilities such as low temperature/high temperature/vibration.

## Phase 3 — Experiment Outline

Implement:
1. Test Program
2. Test Program Sample child table
3. Test Program Item child table
4. Applicable sample relation for each item

Acceptance:
- One Test Program supports one or many samples.
- One Test Program supports many test items.
- Every item requires one Test Method and exactly one Test Standard.
- Item samples must be selected from the program's sample set.

## Phase 4 — Execution

Keep V1 execution in Test Program Item.

Required execution fields:
- engineer
- workstation
- asset
- test_condition
- planned_start/planned_end
- actual_start/actual_end
- status
- result
- conclusion
- quality_inspection (optional)
- raw_data
- notes

Status flow:
`Pending -> Ready -> Running -> Completed -> Reviewed`

Rules:
- Completed requires result/conclusion where applicable.
- Reviewed requires Completed first.
- Do not add standalone Test Execution yet.

## Phase 5 — Test Report

Implement Test Report and workflow:

`Draft -> Engineering Complete -> Review -> Approved -> Issued -> Revised`

Block `Issued` unless required Test Program Items are Reviewed.

## Phase 6 — Workspace

Testing Center should expose:
- Pending Tests
- Running Tests
- Awaiting Review
- Completed Today
- Samples
- Test Programs
- Test Standards
- Test Methods
- Test Reports
- ERPNext Assets

## Phase 7 — Reports

First reports:
- Project/Test Program progress
- Engineer workload
- Tests awaiting review

Equipment utilization can wait until enough execution timing data exists.

## Phase 8 — APIs

Only after the internal workflow is stable, add read APIs for a future customer portal:
- project progress
- sample status
- program progress
- issued reports

## V1 Definition of Done

A laboratory user can:
1. Open an ERPNext Project representing an already-sold testing job.
2. Register one or more physical samples.
3. Create an experiment outline for those samples.
4. Add multiple experiments such as low-temperature, high-temperature and vibration.
5. Select exactly one standard for each experiment.
6. Assign samples, engineer and equipment.
7. Execute and record result/conclusion/raw evidence.
8. Review the experiments.
9. Issue a Test Report.

Anything not required for this path is secondary.


## 商家检测履约工作台（2026-10-23）

[跨仓库分工与权限计划](SELLER_WORKBENCH_INTEGRATION.md)。第一切片实现订单归属校验、内部显式关联和只读委托/进度展示；不包含自动建委托、确认、报告下载。现有主线和数据不变。部署及实际启用以验收记录为准。

## 文档输出与检测工作台最终收口（2026-10-29）

开发及自动回归完成，进入 PR 交付。复用 ERPNext 客户／联系人／地址／报价／销售订单及财务入口，Test Request 保留直接送检及可选商业关联；三类单据共用“生成文档”，默认 PDF，支持 DOCX／XLSX，报价 Excel 基于指定真实模板。现有检测、报告审核及签发主线保留，无 Core／Bridge／生产修改。

本地 36 项 Python、5 项 JS 和隔离站点 43 项 Frappe 回归通过；提供九份虚构示例。ONLYOFFICE 10.0.0.169 原生引擎载入／打印六份 Office 示例及长文本续页已补验通过，兼容证据与分页差异已记录；LibreOffice Calc 打开／打印亦通过。详见 [收口验收记录](DOCUMENT_OUTPUT_WORKSPACE_FINALIZE_ACCEPTANCE.md)。PR 合并后本阶段结束，本分支不再追加需求。
