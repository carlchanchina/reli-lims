import json

import frappe
from frappe.tests import IntegrationTestCase


class TestInstallation(IntegrationTestCase):
    def test_module_and_roles_installed(self):
        self.assertTrue(frappe.db.exists("Module Def", "Reli LIMS"))
        for role in ("Lab Manager", "Lab Engineer", "Lab Reviewer"):
            self.assertEqual(frappe.db.get_value("Role", role, "desk_access"), 1)

    def test_workspace_installed_with_valid_shortcuts(self):
        workspace = frappe.get_doc("Workspace", "Testing Center")
        self.assertEqual(workspace.module, "Reli LIMS")
        self.assertEqual(workspace.public, 1)
        self.assertEqual({row.role for row in workspace.roles},
                         {"Lab Manager", "Lab Engineer", "Lab Reviewer"})
        self.assertTrue(json.loads(workspace.content))
        for shortcut in workspace.shortcuts:
            self.assertTrue(frappe.db.exists("DocType", shortcut.link_to))
