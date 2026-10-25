"""Disposable-site permission checks; users are rolled back with each test."""
import json
import uuid

import frappe
from frappe.tests import IntegrationTestCase

from reli_lims.reli_lims.report.laboratory_work_queue.laboratory_work_queue import execute, VIEWS


class TestWorkspacePermissions(IntegrationTestCase):
    def setUp(self):
        super().setUp()
        frappe.set_user('Administrator')
        self.users = {}
        for role in ('Lab Engineer', 'Lab Reviewer', 'Lab Manager'):
            self.users[role] = frappe.get_doc(dict(
                doctype='User', email=f'workspace-{uuid.uuid4().hex}@example.test',
                first_name='Workspace test', send_welcome_email=0,
                roles=[{'role': role}],
            )).insert().name
        self.addCleanup(frappe.set_user, 'Administrator')

    def test_queue_role_matrix_uses_real_users(self):
        for role, user in self.users.items():
            frappe.set_user(user)
            for view, allowed in VIEWS.items():
                with self.subTest(role=role, view=view):
                    if role in allowed:
                        columns, data = execute({'view': view})
                        self.assertTrue(columns)
                        if view.startswith('我的'):
                            self.assertTrue(all(row['engineer'] == user for row in data))
                    else:
                        with self.assertRaises(frappe.PermissionError):
                            execute({'view': view})

    def test_guest_cannot_query_internal_tasks(self):
        frappe.set_user('Guest')
        for view in VIEWS:
            with self.assertRaises(frappe.PermissionError):
                execute({'view': view})

    def test_roles_do_not_gain_submit_or_integration_access(self):
        for role, user in self.users.items():
            self.assertEqual(bool(frappe.has_permission('Test Request', 'submit', user=user)),
                             role == 'Lab Manager')
            self.assertFalse(frappe.has_permission('User', 'create', user=user))
            self.assertNotIn('System Manager', frappe.get_roles(user))
            self.assertNotIn('Mercur Integration', frappe.get_roles(user))

    def test_number_cards_match_permission_filtered_lists(self):
        from frappe.desk.doctype.number_card.number_card import get_result
        from frappe.utils import today

        workspace = frappe.get_doc('Workspace', 'Testing Center')
        self.assertEqual(len(workspace.number_cards), 10)
        for role, user in self.users.items():
            frappe.set_user(user)
            for row in workspace.number_cards:
                with self.subTest(role=role, card=row.number_card_name):
                    card = frappe.get_doc('Number Card', row.number_card_name)
                    filters = json.loads(card.filters_json or '[]')
                    for dt, field, operator, expression in json.loads(card.dynamic_filters_json or '[]'):
                        self.assertIn(expression, ('frappe.session.user', 'frappe.datetime.get_today()'))
                        value = user if expression == 'frappe.session.user' else today()
                        filters.append([dt, field, operator, value])
                    expected = len(frappe.get_list(card.document_type, filters=filters,
                                                  pluck='name', limit_page_length=0))
                    actual = get_result(card.as_dict(), filters)
                    self.assertEqual(actual, expected)
