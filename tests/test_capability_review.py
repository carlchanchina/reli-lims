"""能力审核工作流的纯逻辑测试（不依赖 Frappe 运行时）。

注意：本文件与 test_customer_share 共用一份 `frappe` 桩。桩必须是两者的超集，
并且幂等（已存在时只补缺失属性），否则两个模块同时运行会互相踩踏。
"""
import importlib
import sys
import types
import unittest
from datetime import datetime, timedelta


def _install_frappe_stub():
    frappe = sys.modules.get("frappe")
    if frappe is None or not hasattr(frappe, "__version__"):
        frappe = types.ModuleType("frappe")
        frappe.__version__ = "16.0.0-stub"
        sys.modules["frappe"] = frappe

    class ValidationError(Exception):
        pass

    class PermissionError_(Exception):
        pass

    def throw(message, exc=None):
        raise (exc or ValidationError)(message)

    def whitelist(*args, **kwargs):
        def decorator(fn):
            return fn
        if args and callable(args[0]):
            return args[0]
        return decorator

    defaults = {
        "flags": {},
        "local": types.SimpleNamespace(request=None),
        "_": lambda text, *a, **k: text,
        "throw": throw,
        "whitelist": whitelist,
        "ValidationError": ValidationError,
        "PermissionError": PermissionError_,
        "session": types.SimpleNamespace(user="Administrator"),
        "get_roles": lambda user=None: ["Lab Manager"],
        "get_all": lambda *a, **k: [],
        "get_doc": lambda *a, **k: None,
        "get_meta": lambda doctype: types.SimpleNamespace(fields=[]),
        "has_permission": lambda *a, **k: True,
    }
    for key, value in defaults.items():
        if not hasattr(frappe, key):
            setattr(frappe, key, value)
    if not hasattr(frappe, "db"):
        frappe.db = types.SimpleNamespace(exists=lambda *a: False, count=lambda *a, **k: 0,
                                          get_value=lambda *a, **k: None,
                                          set_value=lambda *a, **k: None)

    utils = sys.modules.get("frappe.utils")
    if utils is None or not hasattr(utils, "__name__"):
        utils = types.ModuleType("frappe.utils")
        sys.modules["frappe.utils"] = utils
    for key, value in {
        "now_datetime": lambda: datetime(2026, 11, 5, 12, 0, 0),
        "get_datetime": lambda value: value,
        "add_days": lambda value, days: value + timedelta(days=days),
        "add_to_date": lambda value, **kwargs: value + timedelta(**kwargs),
        "cint": lambda value: int(value or 0),
    }.items():
        if not hasattr(utils, key):
            setattr(utils, key, value)
    frappe.utils = utils

    if "frappe.rate_limiter" not in sys.modules:
        rate_limiter = types.ModuleType("frappe.rate_limiter")
        rate_limiter.rate_limit = lambda **kwargs: (lambda fn: fn)
        sys.modules["frappe.rate_limiter"] = rate_limiter
    return frappe


class PublishBlockersTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frappe = _install_frappe_stub()
        sys.modules.pop("reli_lims.capability_review", None)
        cls.module = importlib.import_module("reli_lims.capability_review")

    def doc(self, **overrides):
        base = dict(
            name="CAP-TEST", status="已确认", demo_only=0, accreditation_type="CNAS",
            certificate_no="CNAS L1234", scope_effective_date="2026-01-01",
            capability_scope="低温贮存 -40℃", limitation="仅限整机，不含电池",
            test_project="TPR-1", test_standard="STD-1", reviewed_by="reviewer@example.com",
        )
        base.update(overrides)
        return base

    def test_complete_cnas_capability_is_publishable(self):
        self.assertEqual(self.module.publish_blockers(self.doc()), [])

    def test_cnas_without_certificate_is_blocked(self):
        problems = self.module.publish_blockers(self.doc(certificate_no=""))
        self.assertTrue(any("证书编号" in text for text in problems))

    def test_cnas_without_effective_date_is_blocked(self):
        problems = self.module.publish_blockers(self.doc(scope_effective_date=None))
        self.assertTrue(any("生效日期" in text for text in problems))

    def test_unreviewed_capability_is_blocked(self):
        problems = self.module.publish_blockers(self.doc(reviewed_by=None))
        self.assertTrue(any("尚未经过审核" in text for text in problems))

    def test_draft_status_is_blocked(self):
        problems = self.module.publish_blockers(self.doc(status="待确认"))
        self.assertTrue(any("已确认" in text for text in problems))

    def test_demo_must_be_marked_as_non_accredited(self):
        problems = self.module.publish_blockers(
            self.doc(demo_only=1, accreditation_type="CNAS", certificate_no="DEMO-ONLY"))
        self.assertTrue(any("演示（非认可）" in text for text in problems))

    def test_demo_requires_demo_certificate(self):
        problems = self.module.publish_blockers(
            self.doc(demo_only=1, accreditation_type=self.module.DEMO, certificate_no="L1234"))
        self.assertTrue(any("DEMO" in text for text in problems))

    def test_demo_with_proper_marking_is_publishable(self):
        problems = self.module.publish_blockers(
            self.doc(demo_only=1, accreditation_type=self.module.DEMO,
                     certificate_no="DEMO-ONLY", scope_effective_date=None))
        self.assertEqual(problems, [])

    def test_missing_scope_or_limitation_is_blocked(self):
        self.assertTrue(self.module.publish_blockers(self.doc(capability_scope="")))
        self.assertTrue(self.module.publish_blockers(self.doc(limitation="")))


class BatchLimitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frappe = _install_frappe_stub()
        sys.modules.pop("reli_lims.capability_review", None)
        cls.module = importlib.import_module("reli_lims.capability_review")

    def test_batch_over_limit_is_rejected(self):
        names = [f"CAP-{index:05d}" for index in range(51)]
        with self.assertRaises(Exception) as context:
            self.module._names(names)
        self.assertIn("50", str(context.exception))

    def test_duplicates_are_collapsed(self):
        self.assertEqual(self.module._names(["CAP-1", "CAP-1", "CAP-2"]), ["CAP-1", "CAP-2"])

    def test_empty_selection_is_rejected(self):
        with self.assertRaises(Exception):
            self.module._names([])

    def test_json_string_selection_is_accepted(self):
        self.assertEqual(self.module._names('["CAP-1"]'), ["CAP-1"])

    def test_note_short_text_is_rejected(self):
        with self.assertRaises(Exception):
            self.module._note("好")

    def test_note_is_trimmed(self):
        self.assertEqual(self.module._note("  退回补充设备条件  "), "退回补充设备条件")


if __name__ == "__main__":
    unittest.main()
