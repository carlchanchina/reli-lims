"""Repeatable V1 schema readiness; the native DocType JSON stays authoritative."""
import importlib
import json
from pathlib import Path
import runpy
import sys
import types
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]


class Meta:
    def __init__(self, fields=(), permissions=()):
        self.fields = {f['fieldname']: dict(f) for f in fields}
        self.permissions = list(permissions)

    def get_field(self, name):
        return self.fields.get(name)


class SchemaMigrationTests(unittest.TestCase):
    def setUp(self):
        self.api = importlib.import_module('reli_lims.request_confirmation_setup')
        native = json.loads((ROOT/'reli_lims/reli_lims/doctype/test_request/test_request.json').read_text())
        self.meta = {'Test Request': Meta(native['fields'], native['permissions']), 'File': Meta()}
        self.hooks = runpy.run_path(str(ROOT/'reli_lims/hooks.py'))['doc_events']
        self.frappe = types.ModuleType('frappe')
        self.frappe.get_meta = Mock(side_effect=lambda dt: self.meta[dt])
        self.frappe.get_hooks = Mock(return_value=self.hooks)
        self.frappe.get_attr = Mock(return_value=lambda: None)
        self.frappe.throw = Mock(side_effect=lambda message: (_ for _ in ()).throw(RuntimeError(message)))
        self.custom = types.ModuleType('frappe.custom.doctype.custom_field.custom_field')
        self.custom.create_custom_fields = Mock(side_effect=self.apply)
        self.patcher = patch.dict(sys.modules, {'frappe': self.frappe,
            'frappe.custom.doctype.custom_field.custom_field': self.custom})
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def apply(self, fields, update):
        self.assertTrue(update)
        for dt, rows in fields.items():
            self.meta[dt].fields.update({row['fieldname']: dict(row) for row in rows})

    def test_upgrade_and_replay_preserve_schema_and_native_links(self):
        self.api.after_migrate()
        first = {dt: dict(meta.fields) for dt, meta in self.meta.items()}
        self.api.after_migrate()
        self.assertEqual(first, {dt: meta.fields for dt, meta in self.meta.items()})
        self.assertEqual(len(self.api.FIELDS), 11)
        self.assertEqual(self.api.verify_schema()['confirmation_fields'], 11)
        self.assertEqual(self.meta['Test Request'].get_field('quotation')['options'], 'Quotation')
        self.assertEqual(self.meta['Test Request'].get_field('sales_order')['options'], 'Sales Order')
        self.assertEqual(self.meta['File'].get_field('reli_customer_visible')['read_only'], 1)

    def test_conflicting_storage_type_fails_before_any_upsert(self):
        self.meta['Test Request'].fields['customer_confirmation_fingerprint'] = {
            'fieldname': 'customer_confirmation_fingerprint', 'fieldtype': 'Int'}
        with self.assertRaisesRegex(RuntimeError, 'customer_confirmation_fingerprint'):
            self.api.after_migrate()
        self.custom.create_custom_fields.assert_not_called()

    def test_readiness_rejects_missing_or_incompatible_native_commercial_link(self):
        self.api.after_migrate()
        for replacement in (None, {'fieldname': 'quotation', 'fieldtype': 'Data'}):
            with self.subTest(replacement=replacement):
                self.meta['Test Request'].fields['quotation'] = replacement
                with self.assertRaisesRegex(RuntimeError, 'quotation'):
                    self.api.verify_schema()

    def test_file_visibility_cannot_become_customer_writable(self):
        self.api.after_migrate()
        self.meta['File'].fields['reli_customer_visible']['read_only'] = 0
        with self.assertRaisesRegex(RuntimeError, 'reli_customer_visible'):
            self.api.verify_schema()

    def test_missing_file_hook_or_unresolvable_handler_rejects_readiness(self):
        self.api.after_migrate()
        original = self.hooks['File'].pop('validate')
        with self.assertRaisesRegex(RuntimeError, 'File.validate'):
            self.api.verify_schema()
        self.hooks['File']['validate'] = original
        self.frappe.get_attr.side_effect = ImportError('handler unavailable')
        with self.assertRaisesRegex(RuntimeError, 'handler unavailable'):
            self.api.verify_schema()

    def test_lab_manager_submit_permission_is_required(self):
        self.api.after_migrate()
        self.meta['Test Request'].permissions = []
        with self.assertRaisesRegex(RuntimeError, 'Lab Manager'):
            self.api.verify_schema()

    def test_existing_drafts_do_not_gain_new_mandatory_fields(self):
        self.api.after_migrate()
        for field in self.api.FIELDS:
            self.assertFalse(self.meta['Test Request'].get_field(field['fieldname']).get('reqd'))
