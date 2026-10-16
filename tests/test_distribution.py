import json
from pathlib import Path
import runpy
import unittest

ROOT = Path(__file__).resolve().parents[1]


class TestDistribution(unittest.TestCase):
    def test_launcher_entry_links_to_testing_center_and_packaged_logo(self):
        hooks = runpy.run_path(str(ROOT / "reli_lims/hooks.py"))
        entries = hooks.get("add_to_apps_screen", [])
        self.assertEqual(len(entries), 1, "Reli LIMS has no app launcher entry")
        entry = entries[0]
        self.assertEqual(entry["name"], "reli_lims")
        self.assertEqual(entry["route"], "/desk/reli-lims/testing-center")
        self.assertEqual(entry["has_permission"], "reli_lims.permissions.has_app_permission")
        prefix = "/assets/reli_lims/"
        self.assertTrue(entry["logo"].startswith(prefix))
        self.assertTrue((ROOT / "reli_lims/public" / entry["logo"][len(prefix):]).is_file())

    def test_role_fixtures_are_packaged_and_selected(self):
        hooks = runpy.run_path(str(ROOT / "reli_lims/hooks.py"))
        self.assertIn("fixtures", hooks, "Roles are not installed with the app")
        roles = json.loads((ROOT / "reli_lims/fixtures/role.json").read_text())
        self.assertEqual({r["role_name"] for r in roles},
                         {"Lab Manager", "Lab Engineer", "Lab Reviewer"})
        self.assertTrue(all(r["doctype"] == "Role" and r["desk_access"] == 1 for r in roles))
        self.assertEqual(hooks["fixtures"][0]["filters"][0][0:2], ["name", "in"])
        self.assertEqual(set(hooks["fixtures"][0]["filters"][0][2]),
                         {"Lab Manager", "Lab Engineer", "Lab Reviewer"})

    def test_workspace_only_links_to_available_erpnext_doctypes(self):
        path = ROOT / "reli_lims/reli_lims/workspace/testing_center/testing_center.json"
        self.assertTrue(path.exists(), "Testing Center is missing from the distribution")
        workspace = json.loads(path.read_text())
        self.assertEqual(workspace["module"], "Reli LIMS")
        self.assertEqual(workspace["public"], 1)
        self.assertEqual({r["role"] for r in workspace["roles"]},
                         {"Lab Manager", "Lab Engineer", "Lab Reviewer"})
        self.assertEqual({s["link_to"] for s in workspace["shortcuts"]}, {"Sample", "Test Program", "Test Standard", "Test Method", "Test Report", "Asset"})
        blocks = json.loads(workspace["content"])
        names = {s["label"] for s in workspace["shortcuts"]}
        self.assertTrue(all(b["data"]["shortcut_name"] in names
                            for b in blocks if b["type"] == "shortcut"))


if __name__ == "__main__":
    unittest.main()
