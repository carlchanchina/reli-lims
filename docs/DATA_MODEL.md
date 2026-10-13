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
| approver | Link -> User/Employee | Optional |
| test_start | Date | Optional |
| test_end | Date | Optional |
| overall_conclusion | Select/Data | PASS / FAIL / Other |
| version | Data | e.g. V1.0 |
| status | Select | Draft / Engineering Complete / Review / Approved / Issued / Revised |
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
