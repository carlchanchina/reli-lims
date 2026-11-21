import json

import frappe
from frappe.tests.utils import FrappeTestCase

WORKSPACE = "Commercial Intake Center"
C360_LABEL = "客户 360"
C360_ROUTE = "/crm-customer-360"


class TestCommercialCustomer360Entry(FrappeTestCase):
	"""商务中心只负责入口；数据仍由 wekona_china 的客户 360 服务提供。"""

	def setUp(self):
		super().setUp()
		if not frappe.db.exists("Workspace", WORKSPACE):
			self.skipTest("Commercial Intake Center workspace is not installed")
		self.workspace = frappe.get_doc("Workspace", WORKSPACE)

	def test_shortcut_opens_existing_customer360_page(self):
		row = next((s for s in self.workspace.shortcuts if s.label == C360_LABEL), None)
		self.assertIsNotNone(row, "商务中心缺少「客户 360」入口")
		self.assertEqual(row.type, "URL")
		self.assertEqual((row.url or "").strip(), C360_ROUTE)

	def test_entry_is_visible_on_the_workspace_page(self):
		content = json.loads(self.workspace.content or "[]")
		blocks = {block.get("id"): block for block in content}
		self.assertIn("commercial-c360-s0", blocks)
		shortcut = blocks["commercial-c360-s0"]["data"]["shortcut_name"]
		self.assertEqual(shortcut, C360_LABEL)
		labels = {s.label for s in self.workspace.shortcuts}
		self.assertIn(shortcut, labels)

	def test_workspace_roles_can_read_the_page(self):
		"""The page itself enforces login and CRM permissions; here we only make
		sure the entry is exposed to the commercial roles, not to everyone."""
		self.assertEqual(self.workspace.public, 1)
		roles = {row.role for row in self.workspace.roles}
		self.assertTrue(roles & {"Sales User", "Sales Manager", "Lab Manager"})
