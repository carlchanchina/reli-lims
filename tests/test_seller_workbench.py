import importlib
import sys
import types
import unittest
from unittest.mock import Mock, patch


class RequestSummaryTest(unittest.TestCase):
    def setUp(self):
        self.f = types.ModuleType('frappe')
        self.f.PermissionError = PermissionError
        self.f.throw = lambda message, error=ValueError: (_ for _ in ()).throw(error(message))
        self.request = types.SimpleNamespace(name='REQ-1', company='Company A', customer='CUST-A',
            title='高温检测', docstatus=1, project='PROJ-1', business_stage='待收样',
            delivery_date='2026-12-01', modified='2026-10-23 12:00:00',
            check_permission=Mock(), samples=[types.SimpleNamespace(name='ROW-1')])
        self.project = types.SimpleNamespace(company='Company A', customer='CUST-A', check_permission=Mock())
        self.f.get_doc = lambda dt, name: self.request if dt == 'Test Request' else self.project
        self.f.get_all = Mock(return_value=[])
        self.patch = patch.dict(sys.modules, {'frappe': self.f})
        self.patch.start(); self.addCleanup(self.patch.stop)
        sys.modules.pop('reli_lims.seller_workbench', None)
        self.api = importlib.import_module('reli_lims.seller_workbench')

    def test_summary_omits_private_notes_files_and_contacts(self):
        data = self.api.request_summary('REQ-1', 'Company A')
        self.assertEqual(data['request'], 'REQ-1')
        self.assertEqual(data['stage'], '待收样')
        self.assertEqual(set(data), {'request','title','docstatus','project','stage','delivery_date','updated_at','declared_samples','received_samples'})
        self.request.check_permission.assert_called_with('read')
        self.project.check_permission.assert_called_with('read')

    def test_wrong_company_or_changed_project_is_denied(self):
        with self.assertRaises(PermissionError): self.api.request_summary('REQ-1', 'Company B')
        self.project.customer = 'OTHER'
        with self.assertRaises(PermissionError): self.api.request_summary('REQ-1', 'Company A')

    def test_cancelled_and_draft_do_not_disclose_project(self):
        self.request.docstatus = 2
        data = self.api.request_summary('REQ-1', 'Company A')
        self.assertEqual(data['stage'], '已取消')
        self.assertIsNone(data['project'])
        self.request.docstatus = 0
        self.assertEqual(self.api.request_summary('REQ-1', 'Company A')['stage'], '待确认')

    def test_received_count_only_uses_rows_from_this_request(self):
        self.f.get_all.return_value = ['ROW-1', 'ROW-1', 'FOREIGN']
        data = self.api.request_summary('REQ-1', 'Company A')
        self.assertEqual(data['received_samples'], 1)
        filters = self.f.get_all.call_args.kwargs['filters']
        self.assertEqual(filters, {'test_request': 'REQ-1', 'project': 'PROJ-1'})

    def test_unknown_stage_is_not_reported_as_completed(self):
        self.request.business_stage = 'Unexpected'
        with self.assertRaises(ValueError): self.api.request_summary('REQ-1', 'Company A')

if __name__ == '__main__': unittest.main()
