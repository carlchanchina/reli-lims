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

## Tasks 3–6 — Program, execution and report

Pre-flight: Program consumes Sample.project; each Program Item consumes one Method/Standard; Report consumes Reviewed item states. Project integrity enforced in both Program and Sample.
Ruling: Use top-level Test Program Item Sample child rows keyed by immutable item_code — Frappe child tables cannot themselves hold child tables — cost if wrong: replace association UI/relation shape in a later migration.
Ruling: Keep report PDF as an uploaded private Frappe File; no PDF layout generator — the acceptance path needs issue, not styling — cost if wrong: add report generation later.
Ruling: Lock running item execution basis and reviewed results, freeze issued/revised report content and reported program — preserves reviewed evidence — cost if wrong: add explicit rework/version workflow later.
Ruling: Limit this increment to acceptance-path functionality; analytical reports, dashboard metrics and portal APIs stay deferred — AGENTS.md acceptance-path scope governs — cost if wrong: add those after laboratory workflow stabilizes.
RED: seven acceptance/integrity tests failed for absent Program/Report, then seven failed against generated schemas for missing validators. Three further security/integrity regressions failed before their guards were added.
Generated standard schemas natively on the authorized test site, then imported exports into this branch. Full suite initially 17 pass/1 setup error due invalid PDF fixture; replaced with a genuine PdfWriter document, acceptance path passed.
Final review: whole change plus Python and JavaScript specialist reviews running; final migration/suite pending.

Final review: two Important report-integrity defects and one cancellation defect (regraded Important by effect) reproduced as three failing regression tests. Single fix pass freezes Approved business content/approver, limits Approved PDF replacement to Lab Manager, prevents issued/revised report deletion, and compares full cancelled-program contents including child identities.
Ruling: Allow a manager to attach/replace the final private PDF after approval while keeping approved report fields frozen — supports final document upload without reopening reviewed business data — cost if wrong: move PDF attachment before approval and freeze it too.
Final: fixed approved-report rewrite — test_engineer_cannot_rewrite_approved_report RED→GREEN.
Final: fixed issued-report deletion/program unlock — test_issued_report_cannot_be_deleted_and_program_stays_locked RED→GREEN.
Final: fixed cancellation edits — test_cancellation_cannot_change_items_or_assignments RED→GREEN (remove/add/reassignment).
Final: minor (deferred): Desk retains stale assignment rows after removing unstarted items/samples; server rejects them, user must remove corresponding rows.

Final: fixed item-code dropdown HTML injection — runtime framework Autocomplete renders labels as HTML, so explicit escaped labels are required; Node regression test observed unescaped markup RED then escaped-label GREEN. Values stay unchanged.
Final server suite: 21/21 passed after all Python review fixes, including ERPNext Asset/raw file/PDF issue acceptance. Existing PDF parser emitted recoverable startxref/Object Streams warnings on generated fixture; no test errors. Migration passed and Desk endpoint loaded all six shortcuts plus Autocomplete metadata. Browser rendering and full role matrix remain unverified.

Task 3: complete — multi-sample Program and flat item/sample relation validated.
Task 4: complete — item execution, timings, review and immutable evidence tests passed.
Task 5: complete — report issue/private PDF/approval/immutability/deletion tests passed.
Task 6: acceptance-path Workspace shortcuts complete; dashboard metrics deferred by the scope ruling above.
Final local verification: distribution tests 2/2, Desk security regression 1/1, node syntax check and git diff --check passed. All core schemas/controllers are packaged in the wheel.
Branches and worktree preserved for user review; no push/merge.
