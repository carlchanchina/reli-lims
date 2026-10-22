# Execution ledger — plan: docs/V1_CONVERGENCE_PLAN.md

Base: 6820f0129d4939d327d74b3f8fd4e76ec14dfaba. User authorizes Sprint A–F and production release after verification.

Pre-flight: intake creates Project; receipt maps requested rows to Sample; Program shares sample assignments; Report freezes approved/issued results; Workspace derives progress from these documents.
Ruling: retain internal English status keys except the report's reduced workflow; translate display through Frappe translations to preserve existing records/integrations. Legacy report states migrate explicitly.
Ruling: hide unused legacy fields rather than drop columns, preserving historical records.
Environment: dev 192.168.10.204, dev-bench; existing developer modifications must be backed up and preserved. Dedicated acceptance site reli-acceptance-20261020.localhost. Production identity requested, work continues.

Sprint A: reusing existing tested localization commits df6cf69/a7a2ff4/17ac5e8; remaining V1 vocabulary and new messages pending.
Sprint B: complete — four sections, legacy fields hidden, serial retention, defaults.
Sprint C: complete — hidden relations, execution UI, sample final states.
Sprint D: complete — four report states, private PDF, legacy migration.
Sprint E: complete — native cards/Kanban and server-derived stages.
Sprint F: tests and native Desk smoke passed; production release pending.
