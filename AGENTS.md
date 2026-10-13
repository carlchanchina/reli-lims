# AGENTS.md — Reli LIMS

## Mission

Build Reli LIMS as a lean laboratory execution module on ERPNext/Frappe 16.

Do not recreate a standalone LIMS suite. Reuse ERPNext wherever practical.

## Canonical Business Model

`ERPNext Project -> Sample -> Test Program -> Test Program Item -> Result / optional Quality Inspection -> Test Report`

### Hard rules

- One Test Program may contain one or many Samples.
- One Test Program contains many Test Program Items.
- Each Test Program Item selects exactly one execution Test Standard.
- Test Method and Test Standard are not permanently 1:1 at master-data level.
- A Test Program Item may apply to one or many Samples in the same Test Program.
- Sample is NOT ERPNext Item.
- Test Program is NOT ERPNext Work Order.
- Do not duplicate ERPNext Customer, Project, Asset, Employee/User, Quality Inspection, Sales Order, Invoice, Payment or Accounting.
- No standalone React/Next/Vue admin frontend for V1.
- Use Frappe Desk and Workspace.

## Core DocTypes to implement

1. Sample
2. Test Standard
3. Test Method
4. Test Program
5. Test Program Sample (child)
6. Test Program Item (child)
7. Test Program Item Sample or equivalent child relation if needed for multi-sample selection
8. Test Report

## ERPNext dependencies

Prefer these existing DocTypes:
- Project
- Customer
- Asset
- Workstation (optional)
- User / Employee
- Quality Inspection (optional per test item)
- File

## Development order

1. Make the Frappe app installable.
2. Implement master DocTypes.
3. Implement Test Program and child tables.
4. Add validation for program/sample/project integrity.
5. Add execution fields and status transitions.
6. Add Test Report and issue rules.
7. Add Testing Center Workspace.
8. Add tests.
9. Only then add read APIs for future portal use.

## Coding constraints

- Favor standard Frappe DocType JSON + small Python controllers.
- Keep hooks minimal.
- Avoid monkey patches and core ERPNext modifications.
- Prefer link fields and explicit service functions over copying ERPNext data.
- Business validations need automated tests.
- Do not migrate legacy `lims_next` code wholesale. It may be consulted as reference only.

## Acceptance path

The first end-to-end demo must be:

1. Existing ERPNext Project
2. Create two Samples
3. Create one Test Program using both Samples
4. Add three Test Program Items:
   - Low Temperature + Standard A
   - High Temperature + Standard B
   - Vibration + Standard C
5. Assign applicable samples, equipment and engineer
6. Mark items Running -> Completed -> Reviewed
7. Record result/conclusion and optional raw file
8. Create and issue Test Report

If a feature does not help complete this path, defer it unless required for Frappe correctness/security.

## Read first

Before coding, read:
- `docs/ARCHITECTURE.md`
- `docs/DATA_MODEL.md`
- `docs/ERPNEXT_INTEGRATION.md`
- `docs/DEVELOPMENT_PLAN.md`
