# Sprint5 — native acceptance guard

Native Test Request.before_submit retains existing Lab Manager role check and locked persisted Draft/no-Project check, then calls request_submission.validate_submission. The in-memory docstatus is already1 during Frappe before_submit, so the guard uses the locked row's Draft status.

Require current Customer Confirmed receipt with actor/time, equal current technical fingerprint, complete customer fields and shared native sample photos. Reuse validate_commercial_links; require active Customer/Company and submitted matching Quotation not cancelled/lost/closed/expired. Normal mandatory, technical scope, sample assignment, photo and native submit permission checks still execute. No ignore_mandatory.

Existing on_submit → services.test_request.create_project is untouched. No second Project creation adapter, new business DocType, receipt, Program or Report creation. Customer confirmation history remains; formal acceptance derives from docstatus1 and confirmed_on, not a prematurely assigned Accepted state.

carl DEV REQ-00160 was reviewed and submitted through the native UI by dev-acceptance-sprint5-lab-manager@example.invalid (Lab Manager + existing Projects Manager/Sales User). docstatus0→1, confirmed_on2026-10-30 09:56:36.173393; native Project PROJ-0003, correct Customer/Company zhai and expected_end_date2026-11-15. Source remains native Test Request.project; expected_start_date was null and not invented.

One matching Project; repeat Submit rejected, repeated reads unchanged. Site counts Project2→3, Task0→0, Sample2→2, Test Program1→1, Test Report1→1. No receiving action. Prior customer confirmation actor/time/fingerprint and one command per confirmed revision preserved.

Python unittest39 and native JS5 passed; actual DEV guard rejection tests cover Needs Reconfirmation, Awaiting, stale receipt, missing scope, invalid commercial source and non-Lab Manager. Independent Python/adversarial review completed; no unresolved native guard finding. No production modifications, no schema migration this Sprint. Existing dirty DEV work preserved with additive backed-up deployment.

Full evidence: carlchanchina/ntbln docs/CROSS_SYSTEM_V1_SPRINT5_ACCEPTANCE.md and docs/cross-system-v1/sprint5. Stop before Sprint6; no report delivery.
