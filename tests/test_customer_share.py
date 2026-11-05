import json
import base64
import sys
import types
import unittest
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class StubThrow(Exception):
    def __init__(self, message, exception=None):
        super().__init__(message)
        self.exception = exception


def _install_frappe_stub():
    if "frappe" in sys.modules and getattr(sys.modules["frappe"], "__version__", None):
        return

    frappe = types.ModuleType("frappe")
    frappe.__version__ = "16.0.0-stub"
    frappe.flags = {}
    frappe.session = types.SimpleNamespace(user="Guest")
    frappe.local = types.SimpleNamespace(request=None)
    frappe._ = lambda message, *args, **kwargs: message

    def throw(message, exception=None):
        raise StubThrow(message, exception)

    def whitelist(*args, **kwargs):
        def decorator(fn):
            return fn
        if args and callable(args[0]):
            return args[0]
        return decorator

    frappe.throw = throw
    frappe.whitelist = whitelist
    frappe.PermissionError = type("PermissionError", (Exception,), {})
    frappe.get_all = lambda *args, **kwargs: []
    frappe.get_doc = lambda *args, **kwargs: None
    frappe.get_meta = lambda doctype: types.SimpleNamespace(fields=[])
    frappe.db = types.SimpleNamespace(exists=lambda *args: False)
    frappe.utils = types.SimpleNamespace(
        add_days=lambda value, days: value + timedelta(days=days),
        add_to_date=lambda value, **kwargs: value + timedelta(**kwargs),
        cint=lambda value: int(value or 0),
        get_datetime=lambda value: value,
        now_datetime=lambda: datetime(2026, 11, 5, 12, 0, 0),
    )
    rate_limiter = types.ModuleType("frappe.rate_limiter")
    rate_limiter.rate_limit = lambda **kwargs: (lambda fn: fn)
    sys.modules["frappe"] = frappe
    sys.modules["frappe.utils"] = frappe.utils
    sys.modules["frappe.rate_limiter"] = rate_limiter


_install_frappe_stub()

from reli_lims import (customer_share, customer_share_setup, request_confirmation,  # noqa: E402
                       request_confirmation_setup)
from reli_lims import request_submission  # noqa: E402


class FakeShare:
    def __init__(self, name="WFR-1", key="key-1", expires_on=None, revoked=0, bound="REQ-1"):
        self.name = name
        self.key = key
        self.expires_on = expires_on
        self.reli_revoked = revoked
        self.references = [types.SimpleNamespace(link_name=bound)]
        self.reli_customer_email = "buyer@example.com"
        self.docs = {"reli_revoked": revoked, "reli_use_count": 0}

    def get(self, fieldname, default=None):
        if hasattr(self, fieldname):
            return getattr(self, fieldname)
        return self.docs.get(fieldname, default)


class AuthorizeTest(unittest.TestCase):
    def setUp(self):
        self.share = FakeShare(expires_on=datetime(2026, 11, 12, 12, 0, 0))
        frappe = sys.modules["frappe"]
        self.original = (frappe.get_all, frappe.get_doc, frappe.db.exists,
                         frappe.utils.now_datetime)
        frappe.get_all = lambda doctype, **kwargs: [{"name": self.share.name}]
        frappe.get_doc = lambda doctype, name, **kwargs: self.share
        frappe.db.exists = lambda doctype, name=None: name in ("REQ-1", "REQ-2")
        frappe.utils.now_datetime = lambda: datetime(2026, 11, 5, 12, 0, 0)

    def tearDown(self):
        frappe = sys.modules["frappe"]
        (frappe.get_all, frappe.get_doc, frappe.db.exists,
         frappe.utils.now_datetime) = self.original

    def test_valid_link_binds_exactly_one_request(self):
        share, bound = customer_share.authorize("key-1", "REQ-1")
        self.assertIs(share, self.share)
        self.assertEqual(bound, "REQ-1")

    def test_cross_request_access_is_rejected(self):
        with self.assertRaises(StubThrow):
            customer_share.authorize("key-1", "REQ-2")

    def test_unknown_key_is_rejected(self):
        sys.modules["frappe"].get_all = lambda doctype, **kwargs: []
        with self.assertRaises(StubThrow):
            customer_share.authorize("guessed-key", "REQ-1")

    def test_revoked_link_is_rejected(self):
        self.share.reli_revoked = 1
        with self.assertRaises(StubThrow):
            customer_share.authorize("key-1", "REQ-1")

    def test_expired_link_is_rejected(self):
        self.share.expires_on = datetime(2026, 11, 4, 12, 0, 0)
        with self.assertRaises(StubThrow):
            customer_share.authorize("key-1", "REQ-1")

    def test_non_string_key_is_rejected(self):
        with self.assertRaises(StubThrow):
            customer_share.authorize(None, "REQ-1")


class CustomerDraftRulesTest(unittest.TestCase):
    def test_new_sample_row_receives_sequential_code(self):
        doc = types.SimpleNamespace(samples=[{"sample_code": "S1"}])
        payload = {"samples": [{"sample_code": "S1", "product_name": "A"}, {"product_name": "B"}]}
        filled = customer_share.fill_new_sample_codes(payload, doc)
        self.assertEqual([row["sample_code"] for row in filled["samples"]], ["S1", "S2"])

    def test_incomplete_draft_is_allowed_but_broken_structure_is_not(self):
        self.assertEqual(customer_share.customer_scope_errors(
            {"samples": [{"sample_code": "S1", "product_name": ""}]}), [])
        self.assertTrue(customer_share.customer_scope_errors({"samples": []}))
        self.assertTrue(customer_share.customer_scope_errors(
            {"samples": [{"sample_code": "", "product_name": "A"}]}))
        self.assertTrue(customer_share.customer_scope_errors(
            {"samples": [{"sample_code": "S1", "quantity": 0}]}))
        self.assertTrue(customer_share.customer_scope_errors(
            {"samples": [{"sample_code": "S1", "quantity": "abc"}]}))

    def test_confirmed_draft_cannot_be_edited_by_customer(self):
        for state in ("Awaiting Lab Review", "Lab Reviewed", "Customer Confirmed"):
            doc = types.SimpleNamespace(docstatus=0, customer_confirmation_state=state)
            with self.assertRaises(StubThrow):
                customer_share._assert_customer_editable(doc)
        submitted = types.SimpleNamespace(docstatus=1, customer_confirmation_state="Draft")
        with self.assertRaises(StubThrow):
            customer_share._assert_customer_editable(submitted)
        editable = types.SimpleNamespace(docstatus=0, customer_confirmation_state="Awaiting Customer Confirmation")
        customer_share._assert_customer_editable(editable)

    def test_customer_save_sentinel_is_scoped(self):
        self.assertFalse(customer_share.in_customer_save())
        with customer_share.customer_save():
            self.assertTrue(customer_share.in_customer_save())
        self.assertFalse(customer_share.in_customer_save())


class ShareDiffTest(unittest.TestCase):
    def setUp(self):
        self.frappe = sys.modules["frappe"]
        self.frappe.get_meta = lambda doctype: types.SimpleNamespace(fields=[
            types.SimpleNamespace(fieldname="contact_person", label="联系人"),
            types.SimpleNamespace(fieldname="delivery_date", label="要求完成日期"),
            types.SimpleNamespace(fieldname="samples", label="委托样品"),
            types.SimpleNamespace(fieldname="items", label="检测项目"),
        ])

    def test_only_changed_fields_are_recorded(self):
        before = {"contact_person": "张三", "delivery_date": "2026-11-15", "samples": [], "items": []}
        after = {"contact_person": "李四", "delivery_date": "2026-11-15", "samples": [], "items": []}
        self.assertEqual(customer_share.diff(before, after), ["联系人"])

    def test_row_level_changes_are_named(self):
        before = {"contact_person": "", "delivery_date": "", "items": [],
                  "samples": [{"name": "r1", "product_name": "A", "quantity": 1.0}]}
        after = {"contact_person": "", "delivery_date": "", "items": [],
                 "samples": [{"name": "r1", "product_name": "A", "quantity": 3}]}
        changed = customer_share.diff(before, after)
        self.assertEqual(len(changed), 1)
        self.assertIn("委托样品", changed[0])

    def test_row_count_change_is_recorded(self):
        before = {"contact_person": "", "delivery_date": "", "items": [], "samples": []}
        after = {"contact_person": "", "delivery_date": "", "items": [],
                 "samples": [{"name": "r1", "product_name": "A"}]}
        self.assertTrue(any("行数" in item for item in customer_share.diff(before, after)))


class ExecutionScopeGateTest(unittest.TestCase):
    """真实 CNAS 发布校验不允许被客户端流程放宽。"""

    def setUp(self):
        self.frappe = sys.modules["frappe"]
        self.original = self.frappe.db

    def tearDown(self):
        self.frappe.db = self.original

    def _doc(self):
        return types.SimpleNamespace(items=[{"test_project": "TPR-1", "test_method": None,
                                            "standard": "STD-1"}])

    def _with_standard(self, status):
        def get_value(doctype, name=None, fields=None, as_dict=False, for_update=False):
            return {"status": status} if doctype == "Test Standard" else {"active": 1}
        self.frappe.db = types.SimpleNamespace(get_value=get_value, exists=lambda *a, **k: True,
                                               count=lambda *a, **k: 0)

    def test_draft_standard_blocks_formal_acceptance(self):
        self._with_standard("Draft")
        with self.assertRaises(StubThrow) as context:
            request_submission.validate_execution_scope(self._doc())
        self.assertIn("检测标准", str(context.exception))

    def test_active_standard_passes_scope_check(self):
        self._with_standard("Active")
        request_submission.validate_execution_scope(self._doc())


class AuditEventDeclarationTest(unittest.TestCase):
    def setUp(self):
        self.meta = json.loads((
            ROOT / "reli_lims/reli_lims/doctype/test_request_share_event/test_request_share_event.json"
        ).read_text())
        self.options = next(field["options"] for field in self.meta["fields"]
                            if field["fieldname"] == "event").split("\n")
        self.source = (ROOT / "reli_lims/customer_share.py").read_text()

    def test_every_logged_event_is_a_declared_select_option(self):
        for event in ("发送客户填写链接", "撤销客户填写链接", "客户打开链接", "客户保存",
                      "客户确认提交", "实验室审核通过", "实验室退回补充"):
            self.assertIn(event, self.options, f"审计下拉缺少事件：{event}")
            self.assertIn(event, self.source, f"代码未使用事件：{event}")

    def test_audit_records_actor_ip_and_time(self):
        for field in ("actor_type", "actor_ip", "event_time", "changed_fields", "web_form_request"):
            self.assertIn(field, [row["fieldname"] for row in self.meta["fields"]])


class AttachmentLimitTest(unittest.TestCase):
    PNG = base64.b64encode(
        bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
                      "0000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082")
    ).decode()

    def test_valid_png_is_accepted(self):
        content, extension = customer_share.decode_attachment(f"data:image/png;base64,{self.PNG}")
        self.assertEqual(extension, "png")
        self.assertTrue(content.startswith(b"\x89PNG"))

    def test_oversize_attachment_is_rejected(self):
        oversized = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"0" * (customer_share.MAX_ATTACHMENT_BYTES + 1)).decode()
        with self.assertRaises(StubThrow):
            customer_share.decode_attachment(f"data:image/png;base64,{oversized}")

    def test_disallowed_mime_is_rejected(self):
        for mime in ("text/plain", "application/zip", "image/svg+xml", "application/octet-stream"):
            with self.assertRaises(StubThrow):
                customer_share.decode_attachment(f"data:{mime};base64,{self.PNG}")

    def test_content_must_match_declared_type(self):
        spoofed = base64.b64encode(b"<script>alert(1)</script>").decode()
        with self.assertRaises(StubThrow):
            customer_share.decode_attachment(f"data:image/png;base64,{spoofed}")
        with self.assertRaises(StubThrow):
            customer_share.decode_attachment(f"data:application/pdf;base64,{self.PNG}")

    def test_empty_and_malformed_are_rejected(self):
        with self.assertRaises(StubThrow):
            customer_share.decode_attachment("data:image/png;base64,")
        with self.assertRaises(StubThrow):
            customer_share.decode_attachment("not-a-data-url")
        with self.assertRaises(StubThrow):
            customer_share.decode_attachment("data:image/png;base64,!!!!")


class SubmissionGateTest(unittest.TestCase):
    def test_lab_review_is_required_after_customer_link_flow(self):
        data = dict(docstatus=0, customer_confirmation_state="Customer Confirmed",
                    customer_confirmation_fingerprint="a" * 64,
                    customer_confirmed_by="buyer", customer_confirmed_at="2026-11-05")
        self.assertIsNone(request_submission.confirmation_error(data, "a" * 64, []))
        self.assertTrue(request_submission.confirmation_error(
            data, "a" * 64, [], customer_share.SUBMITTABLE_STATES))
        data["customer_confirmation_state"] = "Lab Reviewed"
        self.assertIsNone(request_submission.confirmation_error(
            data, "a" * 64, [], customer_share.SUBMITTABLE_STATES))


class WebFormFieldSafetyTest(unittest.TestCase):
    def setUp(self):
        self.meta = json.loads((ROOT / "reli_lims/reli_lims/doctype/test_request/test_request.json").read_text())
        self.fields = {df["fieldname"]: df for df in self.meta["fields"]}
        for extra in request_confirmation_setup.FIELDS + customer_share_setup.REQUEST_FIELDS:
            self.fields.setdefault(extra["fieldname"], extra)
        self.child_meta = {
            "samples": json.loads((ROOT / "reli_lims/reli_lims/doctype/test_request_sample/test_request_sample.json").read_text()),
        }

    def test_share_form_never_exposes_link_or_master_code_fields(self):
        for row in customer_share_setup.WEB_FORM_FIELDS:
            if "fieldname" not in row or row["fieldtype"] in ("Section Break", "Column Break"):
                continue
            field = self.fields.get(row["fieldname"])
            self.assertIsNotNone(field, f"未在 Test Request 定义的字段：{row['fieldname']}")
            self.assertEqual(field["fieldtype"], row["fieldtype"],
                             f"字段类型不一致：{row['fieldname']}")
            self.assertNotEqual(field["fieldtype"], "Link",
                                f"客户表单不能暴露 Link 字段：{row['fieldname']}")

    def test_share_form_excludes_internal_tables_and_fields(self):
        names = {row.get("fieldname") for row in customer_share_setup.WEB_FORM_FIELDS}
        for forbidden in ("items", "sample_assignments", "photos", "customer", "company",
                          "quotation", "sales_order", "customer_confirmed_by",
                          "customer_confirmation_fingerprint", "lab_reviewed_by"):
            self.assertNotIn(forbidden, names)

    def test_sample_table_columns_are_not_links(self):
        names = {row.get("fieldname") for row in customer_share_setup.WEB_FORM_FIELDS}
        self.assertIn("samples", names)
        for df in self.child_meta["samples"]["fields"]:
            if df.get("in_list_view"):
                self.assertNotEqual(df["fieldtype"], "Link",
                                    f"样品子表列不能是 Link：{df['fieldname']}")

    def test_confirmation_review_states_are_declared(self):
        for state in ("Awaiting Lab Review", "Lab Reviewed"):
            self.assertIn(state, customer_share_setup.STATE_OPTIONS.split("\n"))


class ConfirmationCoverageTest(unittest.TestCase):
    def test_customer_attachment_participates_in_fingerprint(self):
        self.assertIn("customer_attachment", request_confirmation.TECHNICAL_FIELDS)
        data = {"customer_attachment": "/private/files/a.pdf"}
        other = {"customer_attachment": "/private/files/b.pdf"}
        self.assertNotEqual(request_confirmation.fingerprint(data, []),
                            request_confirmation.fingerprint(other, []))

    def test_lab_review_fields_are_protected(self):
        for field in ("lab_reviewed_by", "lab_reviewed_at"):
            self.assertIn(field, request_confirmation.PROTECTED)

    def test_technical_details_cover_every_fingerprint_field(self):
        details = request_confirmation.technical_details({})
        labels = {row["label"] for row in details}
        self.assertIn("客户补充附件", labels)


if __name__ == "__main__":
    unittest.main()
