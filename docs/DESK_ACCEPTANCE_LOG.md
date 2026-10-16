# SDD ledger — plan: docs/plans/2026-10-16-desk-acceptance.md

Base: b4fb927. Worktree reused; branch codex/desk-acceptance.
Pre-flight: Task 1 consumes Test Program forms from Task 3 and role assignments tested by Task 2. Existing ERPNext roles must be reused without expanding app-global permissions.
Environment: remote site renamed wekona-test; wekona-test.localhost retained as alias. SSH tunnel localhost:18080 reaches login page; direct Ego LAN routing failed. TaskSpace 8 retained.
Task 1: blocked by database authentication, existing site credentials rejected on both local MariaDB ports 3306/3310. No account/password changes made; user asked for configuration correction.
Ruling: implement independent local form corrections before browser acceptance while database is unavailable — avoids unnecessary remote configuration changes — cost if wrong: adjust UI fixes after live verification.

Task 3 local verification: deletion regression tests observed 3 expected failures (missing guards), then Node suite 5/5 green; Python distribution suite 2/2 green; node syntax and diff checks passed. Live browser confirmation remains pending.
Task 2: added actual Frappe User/Role integration tests for master/sample permissions, draft report deletion rights and explicit ERPNext Asset/Project role separation. Syntax checked only; database unavailable, so these are NOT verified. Private-file and full workflow role cases still pending.

2026-10-16 continuation: Pilot UI lists Reli LIMS 0.1.0 on wekona-test; Login as admin did not open a Desk tab. The current IP-based Desk routes to carl (confirmed default_site). No app installation or database credential changes made.
Final local review: one confirmed empty-row guard defect reproduced, fixed with populated-key checks. Node suite 6/6 and distribution suite 2/2 pass; syntax/diff checks pass. Review confirms actual Frappe grid lifecycle and full role/private-file behavior still need live validation.
Task 1 remains incomplete: test-site database authentication fails (1045) using existing configuration. No persistent browser demo records created.
Task 2 remains incomplete: new role integration tests are prepared but unrun. They cover DocType-level permissions, not full document deletion/private-file access; those cases remain planned.
Task 3 local corrections ready for review, not deployed or visually accepted. No main merge or deployment is implied by pushing this branch.
