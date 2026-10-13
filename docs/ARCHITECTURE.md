# Architecture

## System Boundary

Reli LIMS is a thin laboratory execution app inside ERPNext/Frappe.

### Reuse from ERPNext

- Customer
- Contact / Address
- Sales Order / Quotation references
- Project
- Asset
- Employee / User
- Quality Inspection (optional structured result layer)
- File / Attachment
- Workflow / Permission / Workspace
- Accounting and invoicing

### Owned by Reli LIMS

- Sample
- Test Standard
- Test Method
- Test Program
- Test Program Sample
- Test Program Item
- Test Report

## Business Flow

```text
Customer / Sales Order
        |
        v
ERPNext Project
        |
        v
Sample(s)
        |
        v
Test Program
        |
        +--> Test Program Item: Low Temperature -> one Standard
        +--> Test Program Item: High Temperature -> one Standard
        +--> Test Program Item: Vibration -> one Standard
        |
        v
Execution / Optional Quality Inspection
        |
        v
Review
        |
        v
Test Report
```

## Design Rules

- Project is the commercial/testing job container.
- Sample represents the actual received physical specimen(s).
- Test Program is the experiment outline for one job and can reference multiple samples.
- Test Program Item is one concrete experiment to execute.
- Each Test Program Item uses exactly one execution standard.
- Test Method is reusable capability vocabulary, e.g. Low Temperature, Vibration.
- Standards and methods are not hard-wired 1:1 at master-data level.
- Structured numerical inspection can use ERPNext Quality Inspection where useful.
- Do not force every test through Quality Inspection.
- V1 does not introduce standalone Test Execution unless repeated-run history becomes necessary.

## UI

Use Frappe Desk only for V1.

Workspace: `Testing Center`

Cards:
- Pending
- Running
- Awaiting Review
- Completed Today

Shortcuts:
- New Sample
- New Test Program
- Standards
- Methods
- Reports
- Assets

No standalone React/Next.js admin frontend in this repository.
