# Reli LIMS

Lean laboratory execution module for ERPNext / Frappe.

## Product Positioning

Reli LIMS is not a standalone LIMS suite and does not duplicate ERPNext CRM, Project, Asset, Sales, Accounting, HR, or Quality capabilities.

It focuses on the laboratory execution flow after a commercial order has been won:

`ERPNext Project -> Sample -> Test Program -> Test Program Item -> Result / Quality Inspection -> Test Report`

## Core Principles

1. ERPNext is the operational backbone.
2. No separate admin SPA for V1; use Frappe Desk and Workspace.
3. One Test Program can contain one or many Samples.
4. One Test Program contains many Test Program Items.
5. Each Test Program Item selects exactly one execution standard.
6. A Test Method can be reusable across multiple standards.
7. Asset, Employee/User, Project, Customer and Quality Inspection are reused from ERPNext.
8. Keep V1 deliberately small.

## Core DocTypes

- Sample
- Test Standard
- Test Method
- Test Program
- Test Program Sample (child)
- Test Program Item (child)
- Test Report

## V1 Non-Goals

- Customer portal UI
- Certification recommendation
- Target-market logic
- CRM replacement
- Accounting replacement
- Independent equipment master
- Independent project/task system
- Independent quality system

## Recommended Environment

- Frappe / ERPNext 16.x
- Python 3.11+
- MariaDB / Redis as required by Frappe

See `docs/` for architecture, data model, ERPNext integration and development plan.
