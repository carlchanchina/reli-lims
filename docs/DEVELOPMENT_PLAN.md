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
