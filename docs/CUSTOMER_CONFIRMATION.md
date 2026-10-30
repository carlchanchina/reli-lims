# Native Test Request customer confirmation (Cross-System V1 Sprint4)

This adds collaboration fields to the existing Test Request and a visibility flag to native private File; no new business DocType. Deploy native code/hooks and run the registered `request_confirmation_setup.after_migrate` installer before enabling the Bridge collaboration flag. The idempotent installer uses standard CustomField validation. All native Test Request mandatory/business validations still apply.

Native `validate` protects customer_confirmation_state/customer_confirmed_by/customer_confirmed_at/customer_confirmation_fingerprint with an in-process sentinel. A normal Desk or API save cannot forge them. `request_customer_confirmation` requires Lab Manager or Lab Engineer and native write permission, reloads the persisted locked Request (ignores unsaved caller receipt fields), sets Awaiting Customer Confirmation on Draft. Desk buttons require saving first. `share_customer_attachment` checks both native Request write and File read, exact private Draft binding, then marks visible via protected helper. No customer gets lab roles.

Bridge uses the native `confirm` helper only after trusted mapping/identity/current revision checks. It requires docstatus0, complete customer-side required fields and accessible shared native sample photos. It writes actor UUID/time/current fingerprint under the sentinel with normal native validation; it never invokes Submit. Accepted is reserved for later Sprint5; no Sprint4 path sets it.

## Explicit fingerprint fields

`TECHNICAL_FIELDS`: customer/company/quotation/sales_order/execution_company/delivery_date; customer_requirements/expected_tests/reference_standards/declared_conditions/shipping_details; contact_person/phone/email/applicant_address; report_requirements/company/address/language/copies/format; sample_handling_notes/sample_return; result_judgment/judgment_basis; fixture_required/provider; method_choice_consent/subcontract_consent.

`CHILD_FIELDS`: samples code/customer_sample_code/product_name/model/serial_no/quantity/dimensions/weight_kg; items item_code/test_method/standard/test_condition; sample_assignments item_code/sample_code; photos sample_code/photo. Visible private File manifest includes name/file_name/content_hash sorted by ID. SHA256 canonical JSON, normalized numeric quantity/weight, no generated row names. Every top-level field must be either shown editable or read-only (`technical_details` coverage assertion). Photo projection resolves only scoped private shared File IDs; unshared native photos prevent confirmation.

Excluded: notes (internal), item.notes, engineer, engineering_review_notes, internal final execution/audit fields, modified/owner, lab intake administrative notes. Customer requirements live in a dedicated new field, not notes. Laboratory method/standard/conditions/assignment stay native fields; customer declarations cannot replace them.

After a confirmed Draft changes technical content, native `validate` stores Needs Reconfirmation and preserves old actor/time/hash as historical. File after_insert/on_update/after_delete also compare current technical content and invalidate; default invisible internal File changes don't. Shared File ownership/path cannot be rebound, and private visibility cannot be forged through normal File saves. A shared File grants only the configured trusted Gateway service a read-only DocShare, enabling native File permission validation without lab roles for customers.

## DEV and tests

Only carl DEV REQ-00160, Company zhai, Quotation SAL-QTN-2026-00001. All native critical-field categories and private/internal File behavior verified. Browser explicitly reconfirmed after laboratory condition/share changes. Final Customer Confirmed, docstatus0, projectnull; unchanged whole-site counts Project2 / Sample2 / Test Program1 / Test Report1.

Python tests: `uv run --no-project --with openpyxl --with python-docx --with docxtpl python -m unittest discover -s tests` **38 passed**; `node --test tests/*.js` **5 passed**. Regression tests cover technical/internal distinctions, complete visible confirmation scope, native dirty-document receipt forgery, shared File rebind. Independent reviewers' high/medium findings corrected and retested.

DEV has a pre-existing hidden mandatory Company metadata customization; only its additive DEV field installation used `create_custom_fields(ignore_validate=True)` to skip unrelated full-meta layout validation. This is not in the shipped installer and does not bypass mandatory/business validation. No ignore_mandatory. Existing DEV dirty changes were backed up and preserved; no reset or whole-bench migration. Installed Suite File override was left intact; no Drive/Suite API integration was introduced.

See `carlchanchina/ntbln` `docs/CROSS_SYSTEM_V1_SPRINT4_ACCEPTANCE.md` and evidence folder for exact revisions, confirmations, screenshots, 10-replay/recovery and permission results. Production untouched; stop before Sprint5.
