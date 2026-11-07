"""商业来源校验：实验室角色不持有报价/销售订单 DocPerm，只能读有界字段。

这组测试锁定"读投影、不读整单"的设计：校验只取状态、客户、公司，
不再调用 Quotation / Sales Order 的 check_permission。
"""
import importlib
import sys
import types
import unittest
from unittest.mock import Mock, patch


class CommercialTests(unittest.TestCase):
    def setUp(self):
        self.f = types.ModuleType('frappe')
        self.f._ = lambda value: value
        self.f.throw = lambda message, exc=None: (_ for _ in ()).throw(ValueError(message))
        self.quotation = {'docstatus': 1, 'quotation_to': 'Customer',
                          'party_name': 'C', 'company': 'CO'}
        self.order = {'docstatus': 1, 'customer': 'C', 'company': 'CO'}
        self.lines = [{'prevdoc_docname': 'Q'}]

        def get_value(doctype, name, fields=None, as_dict=False):
            if doctype == 'Quotation':
                return types.SimpleNamespace(**self.quotation)
            if doctype == 'Sales Order':
                return types.SimpleNamespace(**self.order)
            return None

        self.f.whitelist = lambda *args, **kwargs: (lambda fn: fn)
        self.f.get_roles = lambda user=None: ["Lab Manager"]
        self.f.session = types.SimpleNamespace(user=" Administrator")
        self.f.db = types.SimpleNamespace(get_value=Mock(side_effect=get_value))
        def get_all(doctype, **kwargs):
            if doctype != 'Sales Order Item':
                return []
            field = kwargs.get('pluck')
            return [row[field] for row in self.lines] if field else list(self.lines)

        self.f.get_all = Mock(side_effect=get_all)
        self.f.get_doc = Mock(side_effect=AssertionError('不应读取整张商业单据'))
        share_stub = types.ModuleType('reli_lims.customer_share')
        share_stub.in_customer_save = lambda: False
        sales_stub = types.ModuleType('reli_lims.sales_order_testing')
        sales_stub.quotation_customer = lambda name: self.quotation.get('party_name') if self.quotation.get('quotation_to') == 'Customer' else None
        self.patcher = patch.dict(sys.modules, {'frappe': self.f,
                                                'reli_lims.sales_order_testing': sales_stub,
                                                'reli_lims.customer_share': share_stub})
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        for module in ('reli_lims.request_commercial', 'reli_lims.commercial_access'):
            sys.modules.pop(module, None)
            self.addCleanup(sys.modules.pop, module, None)
        self.api = importlib.import_module('reli_lims.request_commercial')

        class Request(dict):
            customer = 'C'
            company = 'CO'

        self.request = Request()

    def test_manual_request_needs_no_order(self):
        self.api.validate_commercial_links(self.request)
        self.f.db.get_value.assert_not_called()

    def test_matching_submitted_sources_pass_without_docperm(self):
        self.request.update(quotation='Q', sales_order='SO')
        self.api.validate_commercial_links(self.request)
        self.f.get_doc.assert_not_called()

    def test_quotation_projection_never_reads_whole_document(self):
        self.request['quotation'] = 'Q'
        self.api.validate_commercial_links(self.request)
        fields = self.f.db.get_value.call_args[0][2]
        self.assertNotIn('grand_total', fields)
        self.assertEqual(set(fields), {'docstatus', 'quotation_to', 'party_name', 'company'})

    def test_wrong_customer_company_or_status_rejected(self):
        self.request['quotation'] = 'Q'
        for field, value in [('party_name', 'OTHER'), ('company', 'OTHER'),
                             ('docstatus', 0), ('quotation_to', 'Lead')]:
            original = self.quotation[field]
            self.quotation[field] = value
            with self.assertRaises(ValueError):
                self.api.validate_commercial_links(self.request)
            self.quotation[field] = original

    def test_missing_quotation_is_rejected(self):
        self.request['quotation'] = 'Q'
        self.f.db.get_value = Mock(return_value=None)
        with self.assertRaises(ValueError):
            self.api.validate_commercial_links(self.request)

    def test_order_must_reference_selected_quotation(self):
        self.request.update(quotation='Q', sales_order='SO')
        self.lines = []
        with self.assertRaises(ValueError):
            self.api.validate_commercial_links(self.request)

    def test_order_customer_and_status_checked(self):
        self.request['sales_order'] = 'SO'
        self.order['customer'] = 'OTHER'
        with self.assertRaises(ValueError):
            self.api.validate_commercial_links(self.request)
        self.order['customer'] = 'C'
        self.order['docstatus'] = 2
        with self.assertRaises(ValueError):
            self.api.validate_commercial_links(self.request)
