"""Standard selection displays its native title without changing linked IDs."""
import json
from pathlib import Path
import unittest


class StandardDisplayTests(unittest.TestCase):
    def test_title_search_and_list_expose_code_name_and_version(self):
        root = Path(__file__).resolve().parents[1]
        meta = json.loads((root/'reli_lims/reli_lims/doctype/test_standard/test_standard.json').read_text())
        self.assertEqual(meta['title_field'], 'full_name')
        self.assertEqual(meta['show_title_field_in_link'], 1)
        self.assertTrue({'standard_code', 'title', 'version'}.issubset(meta['search_fields'].split(',')))
        fields = {f['fieldname']: f for f in meta['fields']}
        for name in ('standard_code', 'title', 'version'):
            self.assertEqual(fields[name]['in_list_view'], 1)
        self.assertEqual(meta['autoname'], 'format:STD-{#####}')
        self.assertEqual(fields['status']['default'], 'Draft')
        self.assertEqual(fields['status']['options'], 'Active\nSuperseded\nDraft')
