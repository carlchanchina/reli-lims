"""Regressions for upload trust, real qualification and dual fulfillment quotas."""
import base64
from contextlib import contextmanager
from datetime import date, datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]


class Row(dict):
    def __getattribute__(self, key):
        if key in self:
            return self[key]
        return super().__getattribute__(key)

    def __getattr__(self, key):
        return None

    def __setattr__(self, key, value):
        self[key] = value


@contextmanager
def module(name):
    frappe = ModuleType("frappe")
    frappe.whitelist = lambda **kw: lambda fn: fn
    frappe._ = lambda value: value
    frappe.PermissionError = PermissionError
    frappe.DoesNotExistError = LookupError
    frappe.throw = lambda text, exc=ValueError: (_ for _ in ()).throw(exc(text))
    frappe.conf = {"reli_lims_portal_bridge_user": "bridge@example.invalid"}
    frappe.session = SimpleNamespace(user="bridge@example.invalid")
    frappe.get_roles = Mock(return_value=["Mercur Integration"])
    frappe.db = Mock()
    utils = ModuleType("frappe.utils")
    utils.flt = lambda value: float(value or 0)
    utils.getdate = lambda value: date.fromisoformat(str(value)[:10])
    utils.today = lambda: "2026-11-07"
    utils.now_datetime = lambda: datetime(2026, 11, 7, 12)
    with patch.dict(sys.modules, {"frappe": frappe, "frappe.utils": utils}):
        spec = importlib.util.spec_from_file_location("four_repo_test_" + name, ROOT / "reli_lims" / (name + ".py"))
        loaded = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(loaded)
        yield loaded, frappe


class UploadValidation(unittest.TestCase):
    def payload(self, content=b"%PDF-1.7 test"):
        return dict(request_id="00000000-0000-4000-8000-000000000001", file_name="capability.pdf",
                    mime_type="application/pdf", sha256=hashlib.sha256(content).hexdigest(),
                    content_base64=base64.b64encode(content).decode())

    def test_valid_pdf_preserves_exact_bytes(self):
        with module("portal_capabilities") as (api, _):
            self.assertEqual(api.validate_file(self.payload()), b"%PDF-1.7 test")

    def test_rejects_bad_magic_digest_path_and_extra_fields(self):
        cases = [dict(file_name="../scope.pdf"), dict(sha256="0" * 64), dict(content_base64="!"),
                 dict(mime_type="text/plain"), dict(file_name="scope.png"), dict(laboratory_id="other")]
        with module("portal_capabilities") as (api, _):
            for changes in cases:
                with self.subTest(changes=changes), self.assertRaises(ValueError):
                    api.validate_file(dict(self.payload(), **changes))
            with self.assertRaises(ValueError):
                api.validate_file(self.payload(b"untrusted text"))

    def test_zero_byte_and_oversize_are_rejected(self):
        with module("portal_capabilities") as (api, _):
            for content in (b"", b"%PDF-" + b"x" * api.MAX_BYTES):
                with self.assertRaises(ValueError):
                    api.validate_file(self.payload(content))


class Qualification(unittest.TestCase):
    def records(self):
        cap = Row(status="已发布", published=1, reviewed_by="reviewer", demo_only=0,
                  certificate_no="L11464", accreditation_type="CNAS", scope_effective_date="2026-01-01",
                  test_project="TPR-1")
        return cap, Row(status="Active"), Row(review_status="Approved", published_revision=1), Row(
            documents_review_status="Approved", expiry_date="2027-01-01")

    def test_requires_actual_published_reviewed_valid_evidence(self):
        with module("capability_eligibility") as (api, frappe):
            frappe.db.get_value.return_value = True
            records = self.records()
            self.assertEqual(api._state(*records, None), "eligible")
            for index, changes, expected in (
                (0, dict(demo_only=1), "withdrawn"),
                (0, dict(reviewed_by=None), "withdrawn"),
                (0, dict(scope_effective_date=None), "withdrawn"),
                (0, dict(scope_effective_date="2027-01-01"), "withdrawn"),
                (1, dict(status="Superseded"), "superseded"),
                (2, dict(published_revision=0), "withdrawn"),
                (3, dict(documents_review_status="Historical Preview"), "revoked"),
                (3, dict(expiry_date=None), "withdrawn"),
                (3, dict(expiry_date="2026-11-06"), "expired"),
            ):
                with self.subTest(changes=changes):
                    values = list(self.records())
                    values[index].update(changes)
                    self.assertEqual(api._state(*values, None), expected)
            self.assertEqual(api._state(*self.records(), "revoked"), "revoked")


class EvidenceAndPermissions(unittest.TestCase):
    def test_original_pdf_and_positive_page_are_mandatory(self):
        with module("capability_eligibility") as (api, frappe):
            frappe.parse_json = json.loads
            api.source_version_verified = Mock(return_value=True)
            frappe.db.exists.return_value = True
            capability = Row(source_row="5")
            source = Row(source_file_url="/private/files/certificate.pdf",
                         structured_json=json.dumps({"items": [{"source_row": "5", "page": 2}]}))
            self.assertTrue(api.evidence_ready(capability, source))
            source.structured_json = json.dumps({"items": [{"source_row": "5", "page": 0}]})
            self.assertFalse(api.evidence_ready(capability, source))
            source.structured_json = json.dumps({"items": [{"source_row": "5", "page": 2}]})
            source.source_file_url = "/files/public.pdf"
            self.assertFalse(api.evidence_ready(capability, source))

    def test_reader_gate_rejects_other_users_and_administrators(self):
        with module("integration_access") as (api, frappe):
            frappe.conf["reli_lims_capability_reader_user"] = "reader@example.invalid"
            frappe.get_roles.return_value = ["LIMS Capability Reader"]
            frappe.session.user = "reader@example.invalid"
            api.require_capability_reader()
            for user in ("other@example.invalid", "Administrator", "Guest"):
                frappe.session.user = user
                with self.assertRaises(PermissionError):
                    api.require_capability_reader()

    def test_adapter_document_permission_has_native_ptype_signature(self):
        with module("integration_access") as (api, frappe):
            frappe.get_roles.return_value = ["LIMS Portal Adapter", "Mercur Integration"]
            frappe.db.exists.return_value = False
            self.assertFalse(api.document_permission(Row(name="OTHER-DOC"), ptype="read"))
            frappe.db.exists.return_value = True
            self.assertTrue(api.document_permission(Row(name="OWN-DOC"), ptype="read"))
            self.assertFalse(api.document_permission(Row(name="OWN-DOC"), ptype="delete"))
            frappe.session.user = "other@example.invalid"
            self.assertFalse(api.document_permission(Row(name="OWN-DOC"), ptype="read"))

    def test_reparse_never_reuses_approval_of_previous_parse(self):
        with module("portal_capabilities") as (api, frappe):
            document = Row(name="DOC-1", approved_structured_version="OLD-APPROVAL", selected_parse_run="OLD-PARSE",
                           status="Parsed", review_status="Approved", extraction_status="Approved")
            request = Row(document="DOC-1", parse_run="NEW-PARSE", previous_request="OLD-UPLOAD",
                          status="parsing", source=None, error_code=None, revision=2, save=Mock())
            frappe.get_doc = Mock(return_value=document)
            frappe.db.get_value.side_effect = lambda doctype, *a, **kw: (
                "OLD-PARSE" if doctype == "Document Approved Version" else "Succeeded")
            api._synchronize(request)
            self.assertEqual(request.status, "needs_confirmation")
            self.assertIsNone(request.source)
            self.assertEqual(request.revision, 3)


class FulfillmentCapacity(unittest.TestCase):
    def prepare(self, frappe, *, quote=10, ordered=4, requested=3):
        frappe.db.get_value.return_value = Row(parent="Q-1", qty=quote)
        def sql(query, *args, **kwargs):
            if "DISTINCT parent" in query:
                return ["Q-1"]
            if "tabSales Order Item" in query:
                return [(ordered,)]
            if "tabTest Request Item" in query:
                return [(requested,)]
            return []
        frappe.db.sql.side_effect = sql

    def test_partial_order_and_request_share_remaining_capacity(self):
        with module("quotation_origin") as (api, frappe):
            self.prepare(frappe)
            doc = Row(name="SO-new", items=[Row(quotation_item="LINE-1", qty=3)])
            api.validate_order_capacity(doc)
            doc.items[0].qty = 4
            with self.assertRaisesRegex(ValueError, "CAPACITY_CONFLICT"):
                api.validate_order_capacity(doc)
            queries = [call.args[0] for call in frappe.db.sql.call_args_list]
            self.assertTrue(any("tabQuotation`" in query and "FOR UPDATE" in query for query in queries))
            self.assertTrue(any("tabQuotation Item`" in query and "FOR UPDATE" in query for query in queries))

    def test_direct_request_subtracts_partial_order(self):
        with module("quotation_origin") as (api, frappe):
            self.prepare(frappe)
            row = Row(source_quotation="Q-1", source_quotation_item="LINE-1", requested_quantity=4)
            doc = Row(name="REQ-new", docstatus=0, items=[row])
            with self.assertRaisesRegex(ValueError, "CAPACITY_CONFLICT"):
                api.validate_line_capacity(row, doc)
            row.requested_quantity = 3
            api.validate_line_capacity(row, doc)

    def test_duplicate_rows_cannot_each_claim_full_balance(self):
        with module("quotation_origin") as (api, frappe):
            self.prepare(frappe)
            rows = [Row(source_quotation="Q-1", source_quotation_item="LINE-1", requested_quantity=2) for _ in range(2)]
            doc = Row(name="REQ-new", docstatus=0, items=rows)
            with self.assertRaisesRegex(ValueError, "CAPACITY_CONFLICT"):
                api.validate_line_capacity(rows[0], doc)


if __name__ == "__main__":
    unittest.main()
