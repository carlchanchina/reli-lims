# Execution ledger — plan: docs/DEVELOPMENT_PLAN.md

Scope: Phase 1, as required by START_HERE.md. Architecture and data-model documents are the specification.

Pre-flight: roles and workspace share module Reli LIMS; no business DocTypes yet.

Ruling: Stop at Phase 1 until installation and migration are verified — START_HERE.md explicitly gates Phase 2 — cost if wrong: delayed core implementation.
Ruling: Use role fixtures and an Asset-only workspace scaffold until core DocTypes exist — prevents broken links during installation — cost if wrong: workspace expanded in Phase 2.

Task 1: in progress — package metadata, fixtures, workspace and installation tests.
Environment: no bench root found at repository, parent candidates or conventional frappe-bench paths; Python has no frappe or flit_core.

Offline verification: distribution checks observed RED (2 failures: missing fixtures/workspace), then GREEN (2/2); wheel build succeeded and includes module, fixtures, workspace and integration tests. git diff --check passed.
Final review: fresh code-reviewer found no actionable defects; runtime acceptance remains pending.
Environment update: ERPNext is hosted at 192.168.10.204 (user provided). SSH responds, but carl authentication failed. Awaiting SSH username/alias before install and migrate verification.
Task 1: implementation ready, NOT acceptance-complete. Integration tests have not run.

## Server acceptance — 2026-10-13

User authorized verification on existing `wekona-test.localhost` at `192.168.10.204`, SSH account `frappe`.
Bench: `/home/frappe/pilot/benches/dev-bench`, managed by Pilot.
Backup completed before installation: `20261013_072448-wekona-test_localhost-database.sql.gz` with matching site-config backup in the site's private/backups directory.

Ruling: Use Pilot's underlying Frappe CLI dispatcher because this deployment has no bench executable — preserves the same Frappe install/migrate/test commands without adding another manager — cost if wrong: adapt invocation for future Pilot changes.

Uploaded commit a3a9a36 and installed editable package in the existing bench environment. Git metadata and Pilot app inventory preserved; branch has not been pushed.
`install-app reli_lims`: exit 0.
`migrate`: exit 0. Existing test-site Frappe/ERPNext schema was behind bench code; migration also applied their pending patches. Final installed versions: Frappe 16.51.1, ERPNext 16.50.0, Reli LIMS 0.1.0.
`run-tests --app reli_lims`: 2 integration tests passed, exit 0.
Desk `get_desktop_page` with the correct JSON page descriptor returned the Assets shortcut successfully as Administrator. The first attempt used an invalid plain-string page descriptor and failed; corrected request passed. Browser rendering has not been inspected.
Migration emitted an existing ERPNext sidebar-fixture-format warning (22 fixtures); no migration failure. No unrelated navigation conversion performed.

Task 1: server installation, migration and integration-test acceptance passed. Browser visual inspection remains pending.

## Task 2 — Core masters

Pre-flight: Sample consumes ERPNext Project.customer; Method links optional Standard/Asset/Workstation without exclusivity.
Ruling: Require positive received quantity — a received specimen count must be positive — cost if wrong: adjust validation for zero-quantity registrations.
Ruling: Use Frappe-generated standard DocTypes and explicit transactional Company test data — recursive ERPNext fixtures hit absent Payment Gateway; no framework patches — cost if wrong: test setup needs adjustment on future ERPNext versions.
Naming: SMP/STD/MTH sequential document names, standards retain distinct version fields; User reused for received_by.
RED: six tests failed because masters absent; after schema creation and fixture corrections, four business-rule tests failed for missing derivation/validation/display behavior.
GREEN: full server suite 8/8 passed after implementation, and again after migration. Offline suite 2/2 passed. Wheel built and contains all schemas/controllers. Desk returned all four shortcuts. Migration exit 0 (also removed pre-existing orphan China Enterprise Data Gaps report).
Final review: fresh code-reviewer found no Important/Critical findings.
Final: minor (deferred): role-based permission integration tests, including ERPNext Project/Asset access, remain for end-to-end acceptance.
Task 2: complete.
