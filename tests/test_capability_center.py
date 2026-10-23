"""Service/controller regressions runnable without a bench database."""
import importlib
import sys
import types
import unittest
from unittest.mock import Mock, patch


class CapabilityTests(unittest.TestCase):
    def setUp(self):
        f = types.ModuleType('frappe')
        f._ = lambda message: message
        f.PermissionError = PermissionError
        f.throw = lambda message, error=ValueError: (_ for _ in ()).throw(error(message))
        f.whitelist = lambda **kwargs: lambda fn: fn
        f.get_roles = lambda: ['Lab Manager']
        f.db = Mock()
        f.db.exists.return_value = 'CAP-existing'
        f.db.get_value.return_value = 'MASTER'
        self.source = types.SimpleNamespace(name='SRC', laboratory='LAB',
            documents_review_status='Approved', structured_json={'items': [
                {'test_method': '低温', 'standard_code': 'STD', 'source_row': '1'}]},
            check_permission=Mock(), validate=Mock(), save=Mock())
        self.cap = types.SimpleNamespace(name='CAP', laboratory='LAB', source=None,
            status='待确认', published=0, get_doc_before_save=lambda: None)
        f.get_doc = Mock(return_value=self.source)
        f.get_all = Mock(return_value=[])
        utils = types.ModuleType('frappe.utils')
        utils.now_datetime = lambda: 'now'
        model = types.ModuleType('frappe.model.document')
        model.Document = object
        self.patch = patch.dict(sys.modules, {'frappe': f, 'frappe.utils': utils,
                                             'frappe.model.document': model})
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.f = f
        modules = ['reli_lims.capability_api',
                   'reli_lims.reli_lims.doctype.laboratory_capability.laboratory_capability']
        for name in modules:
            sys.modules.pop(name, None)
            self.addCleanup(sys.modules.pop, name, None)
        self.api = importlib.import_module(modules[0])
        self.controller = importlib.import_module(modules[1]).LaboratoryCapability

    def test_only_approved_import(self):
        self.source.documents_review_status = 'Draft'
        with self.assertRaises(ValueError):
            self.api.import_capability_source('SRC')

    def test_repeat_import_reuses_existing(self):
        for _ in range(2):
            self.assertEqual(self.api.import_capability_source('SRC')['created'], ['CAP-existing'])
        self.assertEqual(self.f.get_doc.call_count, 2)

    def test_cross_lab_source_rejected(self):
        self.cap.source = 'SRC'
        self.cap.laboratory = 'OTHER'
        with self.assertRaises(ValueError):
            self.controller.validate(self.cap)

    def test_direct_publish_requires_confirmation(self):
        self.cap.status = '已发布'
        with self.assertRaises(ValueError):
            self.controller.validate(self.cap)

    def test_publish_and_unpublish(self):
        self.cap.status = '已确认'
        self.cap.get_doc_before_save = lambda: types.SimpleNamespace(status='已确认', get=lambda key: None)
        self.cap.get = lambda key: None
        self.cap.status = '已发布'
        self.controller.validate(self.cap)
        self.assertEqual(self.cap.published, 1)
        self.cap.get_doc_before_save = lambda: types.SimpleNamespace(status='已发布', get=lambda key: None)
        self.cap.status = '已确认'
        self.controller.validate(self.cap)
        self.assertEqual(self.cap.published, 0)

    def test_reviewer_cannot_publish_directly(self):
        self.f.get_roles = lambda: ['Lab Reviewer']
        self.cap.status = '已发布'
        self.cap.get_doc_before_save = lambda: types.SimpleNamespace(status='已确认')
        with self.assertRaises(PermissionError):
            self.controller.validate(self.cap)

    def test_public_projection_filters_and_denies_unpublished(self):
        self.f.get_doc.return_value = self.cap
        with self.assertRaises(PermissionError):
            self.api.get_public_capability('CAP')
        self.assertEqual(self.api.list_public_capabilities(), [])
        self.assertEqual(self.f.get_all.call_args.kwargs['filters'],
                         {'status': '已发布', 'published': 1})
