# Sprint6 — reuse native issued-report guard

Fast Launch reuses the existing native Test Report and manual final PDF upload. No Report DocType, generation engine, template, signing, Drive or Office integration is added. Native business code is unchanged in this Sprint.

Existing TestReport.validate enforces Draft → Review → Approved → Issued. Leaving Draft requires all native Program items Reviewed and a conclusion. Approval records the actual Lab Reviewer/Lab Manager. Issuance requires Lab Manager, recorded reviewer and a .pdf private File bound to this exact Test Report; issued_date is server-derived. Issued report content is immutable; revisions use new reports. These native semantics are the only issuance truth.

Bridge independently rechecks current Issued status and report/program/request/project/customer relationship for every download, resolves the report's authoritative pdf_file to exactly one currently private bound File, verifies local private path and PDF bytes, and records a DownloadPrepared journal before returning bytes. NTBLN rechecks user/current org/membership and proxies an attachment without exposing private File URL. Manual upload is sufficient; automatic report generation is not a V1 launch prerequisite.

DEV carl: REQ-00160 / PROJ-0003 / PRG-00162 / RPT-00163, final File20dafed8f0. Existing Lab Manager native business actions created clearly marked simulated Sample/Program execution, reviewed and approved the report, manually supplied acceptance PDF and set Issued normally. All results/conclusions/PDF explicitly say DEV-ACCEPTANCE, no physical test/certification or genuine stamped report. This is not production acceptance.

Native Draft/Review/Approved download denials and Issued success were tested. Browser downloaded RPT-00163.pdf, 1680 bytes, SHA25677c58e4673c1eac4140bf2575fbeb3d78578d24937979d792c33648a13f9b25e, identical to the prepared fixture. Customer A/B, Guest, cross-org, disabled mappings, foreign report/program/File binding all reject; audit failure also rejects. No private URL returned.

Full evidence is in NTBLN docs/CROSS_SYSTEM_V1_SPRINT6_ACCEPTANCE.md and docs/cross-system-v1/sprint6. Sprint5 remains a prerequisite; this documentation-only branch is stacked on it. No production operations. Stop after Sprint6 PRs; Production Release Acceptance is a separate post-merge task requiring real customer/site/testing/final stamped PDF details.
