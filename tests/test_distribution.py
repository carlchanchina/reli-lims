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
        self.assertEqual(workspace['label'], '工作台首页')
        self.assertEqual(workspace['number_cards'], [])
        fulfillment = json.loads((ROOT / 'reli_lims/reli_lims/workspace/testing_fulfillment_center/testing_fulfillment_center.json').read_text())
        self.assertEqual(len(fulfillment['number_cards']), 6)
        self.assertEqual([row['label'] for row in fulfillment['shortcuts']],
                         ['检测委托单', '样品', '试验方案', '试验记录', '检测报告'])
        sidebar = json.loads((ROOT / 'reli_lims/reli_lims/sidebar/reli_lims/reli_lims.json').read_text())
        centers = [row for row in sidebar['items'] if row.get('link_type') == 'Workspace']
        self.assertEqual([row['label'] for row in centers],
                         ['工作台首页', '商业接单中心', '检测履约中心', '实验室能力中心'])
        self.assertNotIn('Test Method', {row.get('link_to') for row in sidebar['items']})



if __name__ == "__main__":
    unittest.main()
