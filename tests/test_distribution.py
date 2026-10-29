import json
from pathlib import Path
import runpy
import unittest

ROOT = Path(__file__).resolve().parents[1]


class TestDistribution(unittest.TestCase):
    def test_role_fixtures_are_packaged_and_selected(self):
        hooks = runpy.run_path(str(ROOT / "reli_lims/hooks.py"))
        self.assertIn("fixtures", hooks, "Roles are not installed with the app")
        roles = json.loads((ROOT / "reli_lims/fixtures/role.json").read_text())
        desk_roles = {"Lab Manager", "Lab Engineer", "Lab Reviewer"}
        integration_roles = {"Mercur Integration", "Laboratory Directory Reader"}
        expected_roles = desk_roles | integration_roles
        self.assertEqual({r["role_name"] for r in roles}, expected_roles)
        self.assertTrue(all(r["doctype"] == "Role" for r in roles))
        self.assertTrue(all(r["desk_access"] == int(r["role_name"] in desk_roles) for r in roles))
        self.assertEqual(hooks["fixtures"][0]["filters"][0][0:2], ["name", "in"])
        self.assertEqual(set(hooks["fixtures"][0]["filters"][0][2]), expected_roles)

    def test_workspace_only_links_to_available_erpnext_doctypes(self):
        path = ROOT / "reli_lims/reli_lims/workspace/testing_center/testing_center.json"
        self.assertTrue(path.exists(), "Testing Center is missing from the distribution")
        workspace = json.loads(path.read_text())
        self.assertEqual(workspace["module"], "Reli LIMS")
        self.assertEqual(workspace["public"], 1)
        self.assertEqual({r["role"] for r in workspace["roles"]},
                         {"Lab Manager", "Lab Engineer", "Lab Reviewer"})
        self.assertEqual({s["link_to"] for s in workspace["shortcuts"]}, {"Test Request", "Test Program", "Test Report", "Sample", "Customer", "Quotation", "Sales Order"})
        self.assertEqual(len(workspace['shortcuts']), 9)
        self.assertEqual(len(workspace['number_cards']), 6)
        self.assertTrue({'Project', 'Task', 'Asset', 'Contact', 'Address', 'Test Method', 'Test Standard', 'Sales Invoice', 'Payment Entry'} <=
                        {link.get('link_to') for link in workspace['links']})
        blocks = json.loads(workspace["content"])
        card_labels = {row['label'] for row in workspace['number_cards']}
        self.assertEqual({b['data']['number_card_name'] for b in blocks if b['type'] == 'number_card'}, card_labels,
                         'Frappe workspace blocks resolve Number Cards by the row display label')
        names = {s["label"] for s in workspace["shortcuts"]}
        self.assertTrue(all(b["data"]["shortcut_name"] in names
                            for b in blocks if b["type"] == "shortcut"))


if __name__ == "__main__":
    unittest.main()
