import uuid

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import today


class TestMasters(IntegrationTestCase):
    def setUp(self):
        super().setUp()
        for doctype in ('Sample', 'Test Standard', 'Test Method'):
            self.assertTrue(frappe.db.exists('DocType', doctype), f'{doctype} is not installed')
        suffix = uuid.uuid4().hex[:10]
        self.company = frappe.get_doc(doctype='Company', company_name=f'Lab {suffix}',
                                      abbr=f'L{suffix}', default_currency='USD', country='United States',
                                      chart_of_accounts='Standard').insert()
        self.customer = frappe.get_doc(doctype='Customer', customer_name=f'Lab {suffix}', customer_type='Company').insert()
        self.project = frappe.get_doc(doctype='Project', project_name=f'Lab {suffix}', customer=self.customer.name, company=self.company.name).insert()

    def sample(self, **values):
        return frappe.get_doc(dict(doctype='Sample', project=self.project.name,
                                   received_date=today(), quantity=1, **values))

    def test_sample_derives_customer_and_has_unique_number(self):
        first = self.sample(customer=None).insert()
        second = self.sample().insert()
        self.assertEqual(first.customer, self.customer.name)
        self.assertNotEqual(first.name, second.name)
        first.customer = None
        first.save()
        self.assertEqual(first.customer, self.customer.name)

    def test_sample_requires_project(self):
        doc = self.sample()
        doc.project = None
        with self.assertRaises(frappe.ValidationError):
            doc.insert()

    def test_sample_rejects_nonpositive_quantity(self):
        for quantity in (0, -1):
            doc = self.sample()
            doc.quantity = quantity
            with self.assertRaises(frappe.ValidationError):
                doc.insert()

    def test_sample_clears_customer_for_project_without_customer(self):
        self.project.customer = None
        self.project.save()
        doc = self.sample(customer=self.customer.name).insert()
        self.assertFalse(doc.customer)

    def test_standard_versions_are_distinct(self):
        first = frappe.get_doc(doctype='Test Standard', standard_code='LAB-A', title='Low Temperature', version='2008').insert()
        second = frappe.get_doc(doctype='Test Standard', standard_code='LAB-A', title='Low Temperature', version='2026').insert()
        self.assertNotEqual(first.name, second.name)
        self.assertEqual(first.full_name, 'LAB-A:2008 — Low Temperature')

    def test_method_default_standard_is_optional_and_reusable(self):
        standard = frappe.get_doc(doctype='Test Standard', standard_code='LAB-B', title='Test Basis', version='2026').insert()
        first = frappe.get_doc(doctype='Test Method', method_name='Low Temperature').insert()
        self.assertFalse(first.default_standard)
        first.default_standard = standard.name
        first.save()
        second = frappe.get_doc(doctype='Test Method', method_name='High Temperature', default_standard=standard.name).insert()
        self.assertEqual(first.default_standard, second.default_standard)

    def test_sample_return_is_final_and_cannot_skip_to_testing_complete(self):
        sample = frappe.get_doc(doctype='Sample', project=self.project.name, quantity=1,
            received_date=today()).insert()
        sample.status = 'Completed'
        with self.assertRaises(frappe.ValidationError):
            sample.save()
        sample.reload()
        sample.status = 'Returned'
        sample.save()
        sample.status = 'Testing'
        with self.assertRaises(frappe.ValidationError):
            sample.save()
