"""Company resolution belongs to the controller, not a self-referencing default."""
import json
from pathlib import Path
import unittest


class RequestMetadataTest(unittest.TestCase):
    def test_company_does_not_fetch_nonexistent_company_column(self):
        root = Path(__file__).resolve().parents[1]
        schema = json.loads((root/'reli_lims/reli_lims/doctype/test_request/test_request.json').read_text())
        company = next(field for field in schema['fields'] if field['fieldname'] == 'company')
        self.assertFalse(company.get('default'))
        self.assertEqual(company['options'], 'Company')
