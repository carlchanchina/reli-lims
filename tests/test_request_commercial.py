import importlib
import sys
import types
import unittest
from unittest.mock import Mock, patch


class CommercialTests(unittest.TestCase):
    def setUp(self):
        self.f = types.ModuleType('frappe')
        self.f._ = lambda value: value
        self.f.throw = lambda message: (_ for _ in ()).throw(ValueError(message))
        self.q = types.SimpleNamespace(docstatus=1, quotation_to='Customer',
            party_name='C', company='CO', check_permission=Mock())
        self.o = types.SimpleNamespace(docstatus=1, customer='C', company='CO',
            items=[types.SimpleNamespace(prevdoc_docname='Q')], check_permission=Mock())
        self.f.get_doc = Mock(side_effect=lambda dt, name: self.q if dt == 'Quotation' else self.o)
        self.patcher = patch.dict(sys.modules, {'frappe': self.f})
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        sys.modules.pop('reli_lims.request_commercial', None)
        self.api = importlib.import_module('reli_lims.request_commercial')
        self.addCleanup(sys.modules.pop, 'reli_lims.request_commercial', None)
        class Request(dict):
            customer = 'C'
            company = 'CO'
        self.request = Request()

    def test_manual_request_needs_no_order(self):
        self.api.validate_commercial_links(self.request)
        self.f.get_doc.assert_not_called()

    def test_matching_submitted_sources_and_read_permission(self):
        self.request.update(quotation='Q', sales_order='SO')
        self.api.validate_commercial_links(self.request)
        self.q.check_permission.assert_called_with('read')
        self.o.check_permission.assert_called_with('read')

    def test_wrong_customer_company_or_status_rejected(self):
        self.request['quotation'] = 'Q'
        for field, value in [('party_name', 'OTHER'), ('company', 'OTHER'),
                             ('docstatus', 0), ('quotation_to', 'Lead')]:
            old = getattr(self.q, field)
            setattr(self.q, field, value)
            with self.assertRaises(ValueError): self.api.validate_commercial_links(self.request)
            setattr(self.q, field, old)

    def test_order_must_reference_selected_quotation(self):
        self.request.update(quotation='Q', sales_order='SO')
        self.o.items = []
        with self.assertRaises(ValueError): self.api.validate_commercial_links(self.request)

    def test_order_customer_and_status_checked(self):
        self.request['sales_order'] = 'SO'
        self.o.customer = 'OTHER'
        with self.assertRaises(ValueError): self.api.validate_commercial_links(self.request)
        self.o.customer = 'C'
        self.o.docstatus = 2
        with self.assertRaises(ValueError): self.api.validate_commercial_links(self.request)
