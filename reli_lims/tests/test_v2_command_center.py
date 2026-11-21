"""V2 Unified Workspace command center: links must point to real pages only."""
import json
import os

import frappe
from frappe.tests import IntegrationTestCase

from reli_lims.v2_setup import COMMAND_CENTER, WORKSPACE_JSON, install_v2_command_center, verify_targets


class TestV2CommandCenter(IntegrationTestCase):
    def _definition(self):
        with open(WORKSPACE_JSON, encoding="utf-8") as handle:
            return json.load(handle)

    def test_install_is_idempotent_and_creates_one_record(self):
        install_v2_command_center()
        install_v2_command_center()
        names = frappe.get_all("Workspace", filters={"name": COMMAND_CENTER}, pluck="name")
        self.assertEqual(names, [COMMAND_CENTER])

    def test_all_link_targets_exist(self):
        install_v2_command_center()
        report = verify_targets()
        self.assertEqual(report["missing"], [])
        for link in report["links"]:
            with self.subTest(link=link):
                self.assertTrue(link["exists"], f"broken link: {link}")

    def test_four_center_shortcuts_point_to_real_workspace_routes(self):
        install_v2_command_center()
        definition = self._definition()
        shortcuts = {s["label"]: s["url"] for s in definition["shortcuts"]}
        workspace_names = {
            "商务中心": "Commercial Intake Center",
            "能力中心": "Laboratory Capability Center",
            "履约中心": "Testing Fulfillment Center",
            "文档中心": "Wekona Documents",
        }
        self.assertEqual(set(shortcuts), set(workspace_names))
        # Each URL must equal the real get_url() of an existing Workspace, so a
        # route-format change can never silently ship a dead link.
        for label, name in workspace_names.items():
            with self.subTest(center=label):
                self.assertTrue(frappe.db.exists("Workspace", name), f"missing workspace: {name}")
                real_url = frappe.get_doc("Workspace", name).get_url()
                self.assertEqual(shortcuts[label], real_url, f"{label} shortcut is stale")

    def test_role_gate_matches_existing_workspaces(self):
        definition = self._definition()
        roles = {r["role"] for r in definition["roles"]}
        self.assertIn("Lab Manager", roles)
        self.assertIn("System Manager", roles)

    def test_no_fabricated_data_blocks(self):
        definition = self._definition()
        # V2 command center is navigation only: no charts/cards/quick lists.
        self.assertEqual(definition["charts"], [])
        self.assertEqual(definition["number_cards"], [])
        self.assertEqual(definition["quick_lists"], [])
