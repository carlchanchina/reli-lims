"""Run only on the designated acceptance site; all users are transactional."""
import uuid

import frappe
from frappe.tests import IntegrationTestCase


class TestLabPermissions(IntegrationTestCase):
    def setUp(self):
        super().setUp()
        self.users = {}
        for role in ('Lab Manager', 'Lab Engineer', 'Lab Reviewer'):
            self.users[role] = frappe.get_doc(
                doctype='User', email=f'lab-{uuid.uuid4().hex}@example.test',
                first_name=role, send_welcome_email=0, roles=[{'role': role}],
            ).insert().name

    def test_master_and_sample_permission_matrix(self):
        expectations = {
            'Lab Manager': {'Sample': (True, True, True), 'Test Standard': (True, True, True),
                            'Test Method': (True, True, True)},
            'Lab Engineer': {'Sample': (True, True, True), 'Test Standard': (True, False, False),
                             'Test Method': (True, False, False)},
            'Lab Reviewer': {'Sample': (True, False, False), 'Test Standard': (True, False, False),
                             'Test Method': (True, False, False)},
        }
        for role, doctypes in expectations.items():
            for doctype, expected in doctypes.items():
                with self.subTest(role=role, doctype=doctype):
                    actual = tuple(bool(frappe.has_permission(doctype, action, user=self.users[role]))
                                   for action in ('read', 'create', 'write'))
                    self.assertEqual(actual, expected)

    def test_lab_roles_do_not_grant_erpnext_equipment_access(self):
        for role, user in self.users.items():
            with self.subTest(role=role):
                self.assertFalse(frappe.has_permission('Asset', 'read', user=user))
        user = frappe.get_doc('User', self.users['Lab Engineer'])
        # ERPNext 16 grants Asset read access through Quality Manager.
        # Asset User is not a standard role in the supported installation.
        user.add_roles('Quality Manager', 'Projects User')
        self.assertTrue(frappe.has_permission('Asset', 'read', user=user.name))
        self.assertTrue(frappe.has_permission('Project', 'read', user=user.name))

    def test_report_delete_permission_is_manager_only(self):
        for role, user in self.users.items():
            with self.subTest(role=role):
                self.assertEqual(bool(frappe.has_permission('Test Report', 'delete', user=user)),
                                 role == 'Lab Manager')
