"""V2 Unified Workspace command center: links must point to real pages only."""
import json
import os
from pathlib import Path

import frappe
from frappe.tests import IntegrationTestCase

from reli_lims.hooks import app_home
from reli_lims.v2_setup import (
    CENTER_SHORTCUTS,
    COMMAND_CENTER,
    WORKSPACE_JSON,
    install_v2_command_center,
    is_editor_route,
    user_route,
    verify_targets,
    workspace_name_from_url,
)


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

    def test_four_center_shortcuts_use_user_routes_not_editor(self):
        install_v2_command_center()
        definition = self._definition()
        shortcuts = {s["label"]: s["url"] for s in definition["shortcuts"]}
        self.assertEqual(list(shortcuts), list(CENTER_SHORTCUTS))
        self.assertEqual(
            [block["data"]["shortcut_name"] for block in json.loads(definition["content"])
             if block["type"] == "shortcut"],
            list(CENTER_SHORTCUTS),
        )
        for label, name in CENTER_SHORTCUTS.items():
            with self.subTest(center=label):
                self.assertTrue(frappe.db.exists("Workspace", name), f"missing workspace: {name}")
                expected = user_route(name)
                self.assertEqual(shortcuts[label], expected, f"{label} shortcut is stale")
                # A Workspace editor page is not a user dashboard: reject it explicitly.
                self.assertFalse(is_editor_route(shortcuts[label]), f"{label} points at the editor")
                # On this Frappe line get_url() returns the editor route, so a
                # shortcut equal to it would open the editor instead of the page.
                self.assertNotEqual(
                    shortcuts[label],
                    frappe.get_doc("Workspace", name).get_url(),
                    f"{label} still uses the Workspace editor route",
                )

    def test_verify_targets_rejects_editor_routes(self):
        install_v2_command_center()
        report = verify_targets()
        self.assertEqual(report["missing"], [])
        for row in report["shortcuts"]:
            with self.subTest(shortcut=row["label"]):
                self.assertTrue(row["matches_user_route"], row)
                self.assertFalse(row["is_editor_route"], row)
                self.assertEqual(row["url"], row["expected_url"])

    def test_url_resolution_distinguishes_editor_from_user_page(self):
        # The editor route never resolves, even for an existing workspace.
        self.assertIsNone(workspace_name_from_url("/desk/workspace/Wekona%20Documents"))
        self.assertIsNone(workspace_name_from_url("/desk/workspace/RELI%20LIMS%20V2"))
        # The real user route does resolve.
        self.assertEqual(
            workspace_name_from_url(user_route("Wekona Documents")), "Wekona Documents"
        )
        self.assertEqual(
            workspace_name_from_url(user_route("Commercial Intake Center")),
            "Commercial Intake Center",
        )

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

    def test_center_navigation_and_roles(self):
        workspace_root = Path(WORKSPACE_JSON).parent.parent
        for center in ("commercial_intake_center", "laboratory_capability_center", "testing_fulfillment_center"):
            with self.subTest(center=center):
                definition = json.loads((workspace_root / center / f"{center}.json").read_text(encoding="utf-8"))
                shortcuts = {row["label"]: row for row in definition["shortcuts"]}
                self.assertEqual(shortcuts["返回 RELI LIMS V2"]["url"], app_home)
                self.assertEqual(app_home, user_route(COMMAND_CENTER))
                self.assertFalse(is_editor_route(app_home), "app_home must not be the editor route")
                for block in json.loads(definition["content"]):
                    if block["type"] == "shortcut":
                        self.assertIn(block["data"]["shortcut_name"], shortcuts)
                if center == "commercial_intake_center":
                    self.assertEqual([row["label"] for row in shortcuts.values() if row.get("link_to") == "Sales Order"], ["销售订单"])
                if center == "laboratory_capability_center":
                    self.assertIn("Lab Engineer", {row["role"] for row in definition["roles"]})
