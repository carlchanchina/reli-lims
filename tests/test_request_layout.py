import json
from pathlib import Path
import unittest

BASE = Path(__file__).resolve().parents[1] / 'reli_lims/reli_lims/doctype'


def meta(name):
    return json.loads((BASE / name / f'{name}.json').read_text())


class TestRequestLayout(unittest.TestCase):
    def test_three_business_tabs_and_no_separate_assignment_editor(self):
        fields = meta('test_request')['fields']
        self.assertEqual([f['label'] for f in fields if f['fieldtype'] == 'Tab Break'],
                         ['Client Information', 'Sample Information', 'Test Information'])
        self.assertTrue(next(f for f in fields if f['fieldname'] == 'sample_assignments')['hidden'])
        names = {f['fieldname'] for f in fields}
        self.assertTrue({'applicant_address', 'contact_person', 'contact_phone', 'contact_email',
                         'report_same_as_customer', 'report_company', 'report_address',
                         'payer_same_as_customer', 'payer_customer', 'report_format', 'test_purpose',
                         'sample_return', 'fixture_required', 'fixture_provider',
                         'subcontract_consent', 'method_choice_consent', 'result_judgment'} <= names)

    def test_item_selection_and_sample_measurements(self):
        item = {f['fieldname']: f for f in meta('test_request_item')['fields']}
        self.assertEqual(item['select_samples']['fieldtype'], 'Button')
        self.assertTrue(item['applicable_sample_codes']['read_only'])
        for doctype in ('test_request_sample', 'sample'):
            fields = {f['fieldname']: f for f in meta(doctype)['fields']}
            self.assertIn('weight_kg', fields)
