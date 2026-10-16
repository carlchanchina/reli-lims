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
