"""能力审核工作流的纯逻辑测试（不依赖 Frappe 运行时）。"""
import importlib
import sys
import types
import unittest


def _install_frappe_stub():
    frappe = types.ModuleType("frappe")

    class ValidationError(Exception):
        pass

    class PermissionError_(Exception):
        pass

    def throw(message, exc=None):
        raise (exc or ValidationError)(message)

    frappe._ = lambda text, *args, **kwargs: text
    frappe.throw = throw
    frappe.ValidationError = ValidationError
    frappe.PermissionError = PermissionError_
    frappe.session = types.SimpleNamespace(user="Administrator")
    frappe.get_roles = lambda user=None: ["Lab Manager"]
    frappe.whitelist = lambda *args, **kwargs: (lambda fn: fn)
    utils = types.ModuleType("frappe.utils")
    utils.now_datetime = lambda: None
    utils.get_datetime = lambda value: value
    frappe.utils = utils
    sys.modules["frappe"] = frappe
    sys.modules["frappe.utils"] = utils
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
