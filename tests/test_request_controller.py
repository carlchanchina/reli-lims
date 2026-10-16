"""Controller unit checks; Frappe lifecycle persistence is covered separately on a test site."""
from pathlib import Path
import runpy
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch


class Rejected(Exception):
    pass


def load_controller():
    frappe = ModuleType('frappe')
    frappe._ = lambda text: text
    def reject(message):
        raise Rejected(message)
    frappe.throw = reject
    document = ModuleType('frappe.model.document')
    document.Document = object
    modules = {'frappe': frappe, 'frappe.model.document': document,
               'frappe.utils': SimpleNamespace(now_datetime=lambda:None),
               'reli_lims.services.request_files': SimpleNamespace(validate_photos=lambda doc:None),
               'reli_lims.validation': SimpleNamespace(require_role=lambda *args:None)}
    with patch.dict(sys.modules, modules):
        namespace = runpy.run_path(str(Path(__file__).resolve().parents[1] /
            'reli_lims/reli_lims/doctype/test_request/test_request.py'))
    return namespace['TestRequest']


class TestConfirmedFreeze(unittest.TestCase):
    def test_update_after_submit_is_rejected_even_without_validate(self):
        cls = load_controller()
        with self.assertRaises(Rejected):
            cls().before_update_after_submit()


class TestInvoiceHeading(unittest.TestCase):
    def test_same_applicant_ignores_stale_invoice_customer(self):
        cls = load_controller()
        namespace = cls.validate.__globals__
        calls = []
        namespace['frappe'].get_doc = lambda dt, name: SimpleNamespace(check_permission=lambda action: calls.append(name))
        namespace['frappe'].db = SimpleNamespace(get_value=lambda *args: 'Current Customer')
        namespace['validate_scope'] = lambda data: None
        doc = cls()
        values = dict(customer='CURRENT', company='LAB',payer_same_as_customer=1,
                      payer_customer='REVOKED', report_same_as_customer=0, items=[])
        doc.get = lambda key: values.get(key)
        doc.as_dict = lambda: values
        doc.get_doc_before_save = lambda: None
        for key, value in values.items(): setattr(doc,key,value)
        doc.validate()
        self.assertNotIn('REVOKED',calls)
        self.assertEqual(doc.payer_customer,'CURRENT')
