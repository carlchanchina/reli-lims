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

## Install and verify

In an existing ERPNext 16 bench, replace `lab-test.localhost` with a dedicated
test site that already has ERPNext installed:

```sh
bench get-app https://github.com/carlchanchina/reli-lims.git --branch codex/installable-app
bench --site lab-test.localhost install-app reli_lims
bench --site lab-test.localhost migrate
bench --site lab-test.localhost run-tests --app reli_lims
```

The branch must be available on the remote before using `get-app`; for local
verification, pass this checkout's absolute path instead of the URL.

Assign Lab Manager, Lab Engineer or Lab Reviewer to a test user, then open
Testing Center in Desk. The initial workspace exposes ERPNext Assets; lab
shortcuts and permissions will be added with the corresponding DocTypes.
Roles do not grant additional ERPNext Asset access; existing ERPNext permissions
still apply. No business DocTypes or naming series are introduced in Phase 1.

Offline distribution checks (do not verify Frappe installation):

```sh
python3 -m unittest discover -s tests -v
python3 -m pip wheel --no-deps --wheel-dir /tmp/reli-lims-dist .
```
