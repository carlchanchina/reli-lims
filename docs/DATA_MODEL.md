# Data Model

## 1. Sample

Represents a real received specimen.

Suggested fields:

| Field | Type | Notes |
|---|---|---|
| sample_no | Data / naming series | Unique sample number |
| project | Link -> Project | Required |
| customer | Link -> Customer | Read-only/derived where practical |
| product_name | Data | Human-readable product name |
| model | Data | Model/type |
| serial_no | Data | Optional |
| quantity | Float | Received quantity |
| received_date | Date | Required |
| received_by | Link -> User/Employee | Receiver |
| condition | Small Text | Condition on receipt |
| status | Select | Received / Testing / Completed / Retained / Returned / Disposed |
| storage_location | Data | Optional |
| notes | Small Text | Optional |
| attachments | File(s) | Photos/files via Frappe File |

## 2. Test Standard

Represents a standard/version used as execution basis.

| Field | Type | Notes |
|---|---|---|
| standard_code | Data | e.g. GB/T 2423.1 |
| title | Data | Standard title |
| version | Data | e.g. 2008 |
| full_name | Data | Display value |
| status | Select | Active / Superseded / Draft |
| effective_date | Date | Optional |
| attachment | Attach | Standard file/reference |
| notes | Small Text | Optional |

## 3. Test Method

Reusable test capability vocabulary.

Examples: Low Temperature, High Temperature, Temperature Cycling, Vibration, Shock, Drop, Salt Spray, Electric Strength.

| Field | Type | Notes |
|---|---|---|
| method_name | Data | Required |
| category | Data/Link | Optional grouping |
| default_standard | Link -> Test Standard | Optional convenience only |
| default_workstation | Link -> Workstation | Optional |
| default_asset | Link -> Asset | Optional |
| default_condition | Small Text | Optional |
| active | Check | Default 1 |
| notes | Small Text | Optional |

Important: Test Method and Test Standard are not permanently 1:1. The concrete Test Program Item selects one actual standard.

## 4. Test Program

The experiment outline for one ERPNext Project.

| Field | Type | Notes |
|---|---|---|
| program_no | Data / naming series | Unique |
| project | Link -> Project | Required |
| customer | Link -> Customer | Derived/read-only where practical |
| title | Data | Optional display title |
| responsible_engineer | Link -> User/Employee | Owner |
| planned_start | Date | Optional |
| planned_end | Date | Optional |
| status | Select | Draft / Approved / Running / Completed / Cancelled |
| samples | Table -> Test Program Sample | One or many samples |
| items | Table -> Test Program Item | Concrete experiments |
| notes | Small Text | Optional |

## 5. Test Program Sample (Child)

| Field | Type | Notes |
|---|---|---|
| sample | Link -> Sample | Required |
| sample_label | Data | Optional local label, e.g. #1 |
| remarks | Data | Optional |

## 6. Test Program Item (Child)

One concrete experiment inside an outline.

| Field | Type | Notes |
|---|---|---|
| idx | Int | Frappe child row order |
| test_method | Link -> Test Method | Required |
| standard | Link -> Test Standard | Required; exactly one |
| applicable_samples | Table/MultiSelect child relation | One or more samples from the program |
| test_condition | Small Text | e.g. -20C / 2h |
| engineer | Link -> User/Employee | Assigned person |
| workstation | Link -> Workstation | Optional |
| asset | Link -> Asset | Optional |
| planned_start | Datetime | Optional |
| planned_end | Datetime | Optional |
| actual_start | Datetime | Optional |
| actual_end | Datetime | Optional |
| status | Select | Pending / Ready / Running / Completed / Reviewed |
| result | Data/Select | PASS / FAIL / N/A or domain value |
| conclusion | Small Text | Required before completion where appropriate |
| quality_inspection | Link -> Quality Inspection | Optional |
| notes | Small Text | Optional |
| raw_data | Attach | Optional raw result file |

### V1 Validation

- `standard` is mandatory for every row.
- applicable samples must belong to the same Test Program.
- Completed requires result/conclusion.
- Reviewed requires completed state first.

## 7. Test Report

Final laboratory deliverable.

| Field | Type | Notes |
|---|---|---|
| report_no | Data / naming series | Unique |
| project | Link -> Project | Required |
| test_program | Link -> Test Program | Required |
| customer | Link -> Customer | Derived/read-only |
| engineer | Link -> User/Employee | Optional |
| reviewer | Link -> User/Employee | Optional |
| approver | Link -> User | Hidden legacy audit field; no third approval step |
| test_start | Date | Optional |
| test_end | Date | Optional |
| overall_conclusion | Select/Data | PASS / FAIL / Other |
| version | Data | e.g. V1.0 |
| status | Select | Draft / Review / Approved / Issued |
| issued_date | Date | Optional until issued |
| pdf_file | Attach | Final issued PDF |
| notes | Small Text | Optional |

## Relationship Summary

```text
Project 1 --- N Sample
Project 1 --- N Test Program
Test Program 1 --- N Test Program Sample --- 1 Sample
Test Program 1 --- N Test Program Item
Test Program Item N --- 1 Test Method
Test Program Item N --- 1 Test Standard
Test Program Item N --- 0..1 Asset
Test Program Item N --- 0..1 Quality Inspection
Test Program 1 --- N Test Report (versions/revisions allowed later)
```


## V1 收口（2026-10-22）

内部 DocType、fieldname 和执行状态英文键保持兼容。业务名称统一：检测委托单、样品、试验方案、检测项目、检测标准、检测报告。字段标签及用户提示使用中文，Select 通过 Frappe 上下文翻译显示中文。

### 检测委托单

表单仅四块：基本信息、样品信息、检测项目、客户特殊要求。公司自动采用用户/系统默认值；未配置默认值且只有一个可读公司时自动选择。多公司无默认值时提示设置默认公司。原开票/报告抬头、夹具、报告份数、工程审核等字段保留数据库列但从日常界面隐藏，避免历史数据损失。样品序列号随真实收样传入 Sample。样品/检测行编号由表单自动生成，底层来源和关联校验继续执行。

### 试验方案

继续使用顶层 Test Program Item Sample 子表按不可变 item_code 关联样品，不使用嵌套子表。关系表隐藏，用户在检测项目行选择适用样品并查看只读摘要；摘要不参与已复核业务内容锁定比较。未开始行删除时清理关联，已开始行不可移除或改执行依据。

### 检测报告

四状态：Draft（草稿）→ Review（待审核）→ Approved（已批准）→ Issued（已签发）。进入待审核要求方案全部检测项目已复核。批准由 Lab Reviewer 或 Lab Manager 执行，审核人写入实际操作人；签发由 Lab Manager 执行并要求本报告私有 PDF。已批准/已签发内容保护继续有效。

迁移将 Engineering Complete 合并为 Review、Revised 合并为 Issued，写入审计评论并保留版本、附件、原审批信息。修订创建新草稿版本，旧签发报告保持不可变；不新增第三层签批。

### 主流程阶段与工作台

Test Request.business_stage 为服务端派生字段：待确认 → 待收样 → 已收样 → 待试验 → 试验中 → 待报告 → 报告审核 → 已完成。样品以原委托样品行核对是否收齐，取消方案不参与进度；多方案须全部复核且各有已签发报告才能完成。业务阶段不取代样品、试验或报告内部状态，用户通过实际业务动作推进。

sample_summary、test_summary、overdue_status 只用于原生 Kanban 卡片展示。超期由要求完成日期与当前站点日期比较，已完成/已取消委托除外；每日任务和业务变更更新标记。数字卡片实时日期筛选并沿用 Frappe 列表权限。

检测工作台使用六个原生 Number Card、八列原生 Kanban 入口、六个高频快捷入口。Project、Task、Asset、Customer、样品列表和历史报告位于二级分类。没有新增业务 DocType 或独立前端。
