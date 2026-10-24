"""Run on a disposable Frappe test site, never on production."""
import frappe
from frappe.tests import IntegrationTestCase

from reli_lims.capability_api import (
    confirm_capability, get_public_capability, import_capability_source,
    list_public_capabilities, publish_capability, unpublish_capability,
)
from reli_lims.demo_capabilities import seed_demo_capabilities


class TestLaboratoryCapability(IntegrationTestCase):
    def setUp(self):
        frappe.set_user('Administrator')
        self.demo = seed_demo_capabilities()

    def tearDown(self):
        frappe.set_user('Administrator')

    def test_demo_and_import_are_idempotent(self):
        self.assertEqual(seed_demo_capabilities(), self.demo)
        first = import_capability_source(self.demo['source'])
        second = import_capability_source(self.demo['source'])
        self.assertEqual(first['created'], second['created'])
        self.assertEqual(len(first['created']), 2)
        self.assertEqual(frappe.db.count('Laboratory Capability',
                         {'source': self.demo['source']}), 2)

    def test_source_must_be_approved(self):
        source = frappe.get_doc('Capability Source', self.demo['source'])
        source.documents_review_status = 'Revoked'
        with self.assertRaises(frappe.ValidationError):
            source.save()

    def test_source_cannot_cross_laboratories(self):
        cap = frappe.get_doc('Laboratory Capability',
                            {'source': self.demo['source'], 'source_row': '1'})
        cap.laboratory = 'sel_other_lab'
        with self.assertRaises(frappe.ValidationError):
            cap.validate()

    def test_publish_unpublish_and_public_projection(self):
        name = frappe.db.get_value('Laboratory Capability',
                                   {'source': self.demo['source'], 'source_row': '1'})
        confirm_capability(name)
        publish_capability(name)
        self.assertEqual(get_public_capability(name)['id'], name)
        self.assertIn(name, [row['id'] for row in list_public_capabilities(self.demo['laboratory'])])
        unpublish_capability(name)
        with self.assertRaises(frappe.PermissionError):
            get_public_capability(name)
        self.assertNotIn(name, [row['id'] for row in list_public_capabilities(self.demo['laboratory'])])
