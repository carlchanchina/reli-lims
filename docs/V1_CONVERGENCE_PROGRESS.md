# Execution ledger — plan: docs/V1_CONVERGENCE_PLAN.md

Base: 6820f0129d4939d327d74b3f8fd4e76ec14dfaba. User authorizes Sprint A–F and production release after verification.

Pre-flight: intake creates Project; receipt maps requested rows to Sample; Program shares sample assignments; Report freezes approved/issued results; Workspace derives progress from these documents.
Ruling: retain internal English status keys except the report's reduced workflow; translate display through Frappe translations to preserve existing records/integrations. Legacy report states migrate explicitly.
Ruling: hide unused legacy fields rather than drop columns, preserving historical records.
Environment: dev 192.168.10.204, dev-bench; existing developer modifications must be backed up and preserved. Dedicated acceptance site reli-acceptance-20261020.localhost. Production identity requested, work continues.

Sprint A: complete — tested localization reused; core labels/messages and V1 vocabulary Chinese.
Sprint B: complete — four sections, legacy fields hidden, serial retention, defaults.
Sprint C: complete — hidden relations, execution UI, sample final states.
Sprint D: complete — four report states, private PDF, legacy migration.
Sprint E: complete — native cards/Kanban and server-derived stages.
Sprint F: complete — 40 integration, 10 offline and 3 Node tests passed; dev/production migrations, builds and native Desk smoke passed; business counts unchanged. Visual review awaits user login. Release tag v1.0.0.

Final review: independent code, Python and JS reviews completed. Stale asynchronous program lookup reproduced RED and fixed GREEN; full evidence in IMPLEMENTATION_LOG.md.
Ruling: retain production main's test-only local commit and deploy a separate release branch tracking origin/main — cost if wrong: future deployment must use the release branch or explicitly align main.
Ruling: do not activate the previously inactive global Frappe scheduler during application release, as it can run unrelated queued work — cost if wrong: persisted overdue labels await business events or normal scheduler restoration; live overdue Number Card remains accurate.
