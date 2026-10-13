# START HERE — Codex

Work in this repository as the new clean Reli LIMS implementation for ERPNext/Frappe 16.

## First task

Start with GitHub Issue #1: make the app installable on ERPNext 16.

Read these files before changing code:
1. `AGENTS.md`
2. `docs/ARCHITECTURE.md`
3. `docs/DATA_MODEL.md`
4. `docs/ERPNEXT_INTEGRATION.md`
5. `docs/DEVELOPMENT_PLAN.md`

## Non-negotiable architecture

- Do not copy the old `lims_next` architecture.
- Do not build a separate React/Next.js admin frontend.
- Do not duplicate ERPNext Customer, Project, Asset, Employee, Sales, Accounting, or Quality masters.
- V1 core flow is:
  `ERPNext Project -> Sample -> Test Program -> Test Program Item -> Result / Quality Inspection -> Test Report`
- One Test Program may contain multiple Samples.
- One Test Program contains multiple Test Program Items.
- Each Test Program Item uses exactly one execution Test Standard.
- A Test Method is reusable and is not permanently 1:1 with a Test Standard.

## First implementation order

1. Verify/repair Frappe app package structure.
2. Add app metadata required by Frappe 16.
3. Add `Reli LIMS` module and `Testing Center` workspace scaffolding.
4. Add roles: Lab Manager, Lab Engineer, Lab Reviewer.
5. Make install + migrate succeed on ERPNext 16.
6. Only after Issue #1 is green, start Issue #2 core DocTypes.

Do not jump ahead to portal, report styling, AI features, marketplace integration, or UI beautification.
