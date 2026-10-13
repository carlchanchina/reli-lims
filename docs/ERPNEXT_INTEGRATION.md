# ERPNext Integration Boundary

## Reuse Matrix

| Laboratory need | Reuse | Reli LIMS responsibility |
|---|---|---|
| Customer | ERPNext Customer | Link only |
| Contact / Address | ERPNext Contact / Address | Link/read only when needed |
| Commercial order | Quotation / Sales Order | Optional reference only |
| Testing job container | ERPNext Project | Required parent context |
| Generic task | ERPNext Task | Use only where generic project task tracking is useful |
| Equipment | ERPNext Asset | Required equipment master reuse |
| Work area / station | ERPNext Workstation | Optional reuse |
| Engineer / reviewer | ERPNext User / Employee | Reuse |
| Structured numeric inspection | ERPNext Quality Inspection | Optional per Test Program Item |
| Attachments | Frappe File | Reuse |
| Permissions | Frappe Roles / Permissions | Reuse |
| Workflow | Frappe Workflow | Reuse |
| Internal UI | Frappe Desk / Workspace | Reuse |
| Accounting / invoicing | ERPNext Accounting | No duplicate model |
| Sample | No suitable ERPNext equivalent | Reli LIMS owns |
| Test Standard | No suitable core master | Reli LIMS owns |
| Test Method | No suitable core master | Reli LIMS owns |
| Test Program | No suitable exact equivalent | Reli LIMS owns |
| Test Program Item | No suitable exact equivalent | Reli LIMS owns |
| Test Report | Laboratory-specific deliverable | Reli LIMS owns |

## Important Constraints

### Do not model Sample as Item

ERPNext Item is a reusable product/material master. A Sample is a physical specimen received for a specific Project. Keep them separate.

### Do not use Work Order as the main testing order

ERPNext Work Order carries manufacturing-specific semantics such as manufactured item, BOM quantity, raw material/WIP/finished goods flows. Reli LIMS should use Project + Test Program instead.

### Do not duplicate Quality Inspection

Use Quality Inspection when a test requires structured parameters/readings. Do not require every experiment to use it; some tests only need conditions, raw evidence, result and conclusion.

### Do not create a second Asset master

Laboratory chambers, vibration tables, meters and other equipment should use ERPNext Asset where practical. Reli LIMS may later add laboratory-specific custom fields or companion records only when required.

## Integration Hooks Planned for V1

- Sample validates `project` exists and may derive customer from Project.
- Test Program validates all selected Samples belong to the same Project.
- Test Program Item validates selected samples belong to the program.
- Test Program Item can link Asset and optional Workstation.
- Test Program Item can create/link a Quality Inspection only through an explicit user action or dedicated service, not automatically for every item.
- Test Report derives project/customer/program summary and blocks issue until required program items are Reviewed.

## Future Portal Boundary

A future ReliLab customer portal may call APIs for:
- Project/test progress
- Sample status
- Test Program progress
- Issued report metadata/download

The portal is a separate frontend concern and is not part of Reli LIMS V1.
