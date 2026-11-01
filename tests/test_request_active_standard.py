"""Execution readiness is enforced only at formal native submission."""
import sys
import types
import unittest
from unittest.mock import Mock, patch


class ActiveStandardTests(unittest.TestCase):
    def setUp(self):
        self.frappe = types.ModuleType('frappe')
        self.rows = {'Test Method': {'active': 1}, 'Test Standard': {'status': 'Active'}}
        self.frappe.db = types.SimpleNamespace(get_value=Mock(side_effect=lambda dt, name, fields, **kw: self.rows[dt]))
        self.frappe.throw = Mock(side_effect=lambda message: (_ for _ in ()).throw(ValueError(message)))
        self.doc = types.SimpleNamespace(items=[{'test_method': 'MTH-TEST', 'standard': 'STD-TEST'}])
        self.patcher = patch.dict(sys.modules, {'frappe': self.frappe})
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def test_active_standard_and_method_pass_with_locked_reads(self):
        from reli_lims.request_submission import validate_execution_scope
        validate_execution_scope(self.doc)
        self.assertEqual(self.frappe.db.get_value.call_count, 2)
        for call in self.frappe.db.get_value.call_args_list:
            self.assertTrue(call.kwargs['for_update'])

    def test_draft_superseded_or_missing_standard_cannot_submit(self):
        from reli_lims.request_submission import validate_execution_scope
        for row in ({'status': 'Draft'}, {'status': 'Superseded'}, None):
            with self.subTest(row=row):
                self.rows['Test Standard'] = row
                with self.assertRaisesRegex(ValueError, '标准'):
                    validate_execution_scope(self.doc)

    def test_inactive_or_missing_method_cannot_submit(self):
        from reli_lims.request_submission import validate_execution_scope
        for row in ({'active': 0}, None):
            with self.subTest(row=row):
                self.rows['Test Method'] = row
                with self.assertRaisesRegex(ValueError, '检测项目'):
                    validate_execution_scope(self.doc)

    def test_missing_technical_reference_cannot_submit(self):
        from reli_lims.request_submission import validate_execution_scope
        self.doc.items = [{'test_method': 'MTH-TEST'}]
        with self.assertRaisesRegex(ValueError, '标准'):
            validate_execution_scope(self.doc)

    def test_repeated_items_do_not_repeat_master_locks(self):
        from reli_lims.request_submission import validate_execution_scope
        self.doc.items *= 10
        validate_execution_scope(self.doc)
        self.assertEqual(self.frappe.db.get_value.call_count, 2)

    def test_native_submission_invokes_active_master_guard(self):
        from reli_lims import request_submission as api
        data = dict(docstatus=1, customer_confirmation_state='Customer Confirmed',
                    customer_confirmation_fingerprint='a'*64, customer_confirmed_by='customer',
                    customer_confirmed_at='2026-11-01', quotation='QUOTE-FIXTURE')
        self.doc.as_dict = lambda: dict(data)
        self.doc.get = data.get
        self.doc.customer = 'CUSTOMER-FIXTURE'
        self.doc.company = 'COMPANY-FIXTURE'
        self.doc.quotation = data['quotation']
        self.frappe.get_doc = Mock(side_effect=lambda dt, name: {'status': 'Submitted', 'disabled': 0})
        self.frappe.utils = types.SimpleNamespace(today=lambda: '2026-11-01')
        modules = {'reli_lims.request_confirmation': types.SimpleNamespace(
            current_fingerprint=lambda doc: 'a'*64, confirmation_blockers=lambda doc: []),
            'reli_lims.request_commercial': types.SimpleNamespace(validate_commercial_links=lambda doc: None)}
        with patch.dict(sys.modules, modules), patch.object(api, 'validate_execution_scope') as gate:
            api.validate_submission(self.doc, types.SimpleNamespace(docstatus=0))
        gate.assert_called_once_with(self.doc)
