"""Quotation lines keep the technical snapshot they were sold with.

Stage 1 batch 1: once a line is created, re-saving the quotation must never
re-read the live Laboratory Capability for the row's identity columns or text.
"""
import json
import uuid

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, today


class TestQuotationSnapshotFreeze(IntegrationTestCase):
    def setUp(self):
        super().setUp()
        token = uuid.uuid4().hex[:8]
        self.company = frappe.get_doc(dict(
            doctype="Company", company_name=f"快照公司 {token}", abbr=f"F{token[:5]}",
            default_currency="USD", country="United States", chart_of_accounts="Standard",
        )).insert()
        group = frappe.get_doc(dict(
            doctype="Customer Group", customer_group_name=f"快照组 {token}",
            parent_customer_group="All Customer Groups", is_group=0,
        )).insert()
        self.customer = frappe.get_doc(dict(
            doctype="Customer", customer_name=f"快照客户 {token}",
            customer_type="Company", customer_group=group.name, territory="All Territories",
        )).insert()
        self.project = frappe.get_doc(doctype="Test Project", project_name=f"快照检测 {token}").insert()
        self.project_b = frappe.get_doc(doctype="Test Project", project_name=f"改归类 {token}").insert()
        self.standard = frappe.get_doc(dict(
            doctype="Test Standard", standard_code=f"S-{token}", title="Snapshot standard",
            version="1", basis_type="国家标准", status="Active",
        )).insert()
        self.standard_b = frappe.get_doc(dict(
            doctype="Test Standard", standard_code=f"SB-{token}", title="Other standard",
            version="1", basis_type="国家标准", status="Active",
        )).insert()
        self.object = frappe.get_doc(dict(
            doctype="Test Object", object_name=f"快照对象 {token}", category="轨道交通",
        )).insert()
        self.object_b = frappe.get_doc(dict(
            doctype="Test Object", object_name=f"其他对象 {token}", category="轨道交通",
        )).insert()
        self.laboratory = frappe.get_doc(dict(
            doctype="Laboratory Profile", mercur_seller_id=f"sel_fz_{token}",
            laboratory_name=f"快照实验室 {token}", review_status="Approved",
        )).insert()
        self.capability = frappe.get_doc(dict(
            doctype="Laboratory Capability", laboratory=self.laboratory.name,
            test_project=self.project.name, test_object=self.object.name,
            test_standard=self.standard.name, capability_scope="SNAPSHOT ONLY",
            limitation="只测:容积≤1m³,温度≤+175°C",
            condition_schema=frappe.as_json([
                dict(key="hold_minutes", label="保持时间（分钟）", type="number"),
            ]),
        )).insert()
        for status in ("已确认", "已发布"):
            self.capability.status = status
            self.capability.save()
        self.item = frappe.get_doc(dict(
            doctype="Item", item_code=f"FZ-{token}", item_name="快照检测服务",
            item_group="All Item Groups", stock_uom="Nos", is_stock_item=0, is_sales_item=1,
            custom_reli_business_type="检测服务", custom_reli_test_project=self.project.name,
        )).insert()

    def lines(self, conditions=None):
        from reli_lims.capability_quotation import prepare_lines
        result = prepare_lines([dict(
            capability_id=self.capability.name,
            conditions=dict(hold_minutes=30) if conditions is None else conditions,
            item_code=self.item.name,
        )])
        result[0]["rate"] = 100
        return result

    def quotation(self, lines):
        return frappe.get_doc(dict(
            doctype="Quotation", quotation_to="Customer", party_name=self.customer.name,
            company=self.company.name, transaction_date=today(),
            valid_till=add_days(today(), 30), currency="USD",
            selling_price_list="Standard Selling", items=lines,
        )).insert()

    # --- provenance -------------------------------------------------------
    def test_prepare_lines_freezes_the_configuration(self):
        config = self.lines()[0]["custom_reli_configuration"]
        self.assertTrue(config.get("snapshot_at"))
        self.assertEqual(config["snapshot"]["test_project"], self.project.name)
        self.assertEqual(config["snapshot"]["test_object"], self.object.name)
        self.assertEqual(config["conditions"], {"hold_minutes": 30.0})

    # --- identity columns never follow the live capability -----------------
    def test_resave_keeps_columns_when_capability_is_reclassified(self):
        quote = self.quotation(self.lines())
        row = quote.items[0]
        self.assertEqual(row.custom_reli_test_project, self.project.name)

        # Simulates an administrator re-classifying the capability later.
        frappe.db.set_value("Laboratory Capability", self.capability.name, {
            "test_project": self.project_b.name,
            "test_object": self.object_b.name,
            "test_standard": self.standard_b.name,
        })
        quote.reload()
        quote.save()

        row = quote.items[0]
        self.assertEqual(row.custom_reli_test_project, self.project.name)
        self.assertEqual(row.custom_reli_test_object, self.object.name)
        self.assertEqual(row.custom_reli_test_standard, self.standard.name)
        self.assertEqual(row.item_name, self.project.project_name)
        stored = frappe.parse_json(row.custom_reli_configuration)
        self.assertEqual(stored["snapshot"]["test_project"], self.project.name)

    # --- text and conditions stay frozen ----------------------------------
    def test_resave_keeps_description_when_capability_text_changes(self):
        quote = self.quotation(self.lines())
        before = quote.items[0].description
        frappe.db.set_value("Laboratory Capability", self.capability.name, {
            "limitation": "只测:容积≤72m³,温度≤+100°C",
            "capability_scope": "REWRITTEN SCOPE",
        })
        quote.reload()
        quote.save()
        self.assertEqual(quote.items[0].description, before)

    def test_condition_edit_is_validated_against_the_frozen_schema(self):
        quote = self.quotation(self.lines())
        config = frappe.parse_json(quote.items[0].custom_reli_configuration)
        config["conditions"] = {"hold_minutes": 45}
        quote.items[0].custom_reli_configuration = json.dumps(config)
        quote.save()
        stored = frappe.parse_json(quote.items[0].custom_reli_configuration)
        self.assertEqual(stored["conditions"], {"hold_minutes": 45.0})
        self.assertIn("45", quote.items[0].description)
        self.assertEqual(stored["snapshot"]["test_project"], self.project.name)

    def test_unknown_condition_key_is_rejected_after_freeze(self):
        quote = self.quotation(self.lines())
        config = frappe.parse_json(quote.items[0].custom_reli_configuration)
        config["conditions"] = {"hold_minutes": 30, "rewritten_schema": 1}
        quote.items[0].custom_reli_configuration = json.dumps(config)
        with self.assertRaises(frappe.ValidationError):
            quote.save()

    # --- submission gate still needs a published capability ---------------
    def test_submission_requires_published_capability(self):
        quote = self.quotation(self.lines())
        frappe.db.set_value("Laboratory Capability", self.capability.name, {"published": 0})
        with self.assertRaises(frappe.ValidationError):
            quote.submit()

    # --- legacy rows: never fabricate history ------------------------------
    def legacy_quote(self):
        legacy = {"schema_version": 1, "capability_id": self.capability.name, "conditions": {}}
        line = dict(
            item_code=self.item.name, qty=1, rate=100,
            custom_reli_capability=self.capability.name,
            custom_reli_configuration=json.dumps(legacy),
        )
        return self.quotation([line])

    def test_legacy_row_is_marked_pending_instead_of_invented(self):
        quote = self.legacy_quote()
        stored = frappe.parse_json(quote.items[0].custom_reli_configuration)
        self.assertEqual(stored.get("snapshot_state"), "pending_manual_confirmation")
        self.assertNotIn("snapshot", stored)
        self.assertNotIn("snapshot_repair", stored)
        # Identity columns must stay empty rather than be guessed from the live capability.
        self.assertFalse(quote.items[0].custom_reli_test_project)
        with self.assertRaises(frappe.ValidationError):
            quote.submit()

    def test_legacy_row_can_be_confirmed_by_a_human(self):
        from reli_lims.capability_quotation import confirm_legacy_snapshot
        quote = self.legacy_quote()
        result = confirm_legacy_snapshot(
            quote.name, quote.items[0].name, self.project.name, self.object.name,
            self.standard.name, note="核对原始合同",
        )
        quote.reload()
        stored = frappe.parse_json(quote.items[0].custom_reli_configuration)
        self.assertEqual(stored["snapshot_state"] if "snapshot_state" in stored else None, None)
        self.assertEqual(stored["snapshot_source"], "manual_confirmation")
        self.assertEqual(stored["snapshot"]["test_project"], self.project.name)
        self.assertEqual(stored["snapshot"]["test_object"], self.object.name)
        self.assertEqual(stored["confirmed_by"], result["confirmed_by"])
        self.assertTrue(stored.get("live_capability_modified") is not None)
        self.assertEqual(quote.items[0].custom_reli_test_project, self.project.name)
        quote.submit()

    def test_order_row_restores_snapshot_from_its_quotation_line(self):
        from reli_lims.capability_quotation import _restore_from_upstream
        quote = self.quotation(self.lines())
        restored = _restore_from_upstream(
            frappe._dict(quotation_item=quote.items[0].name), {"schema_version": 1})
        self.assertIsNotNone(restored)
        self.assertEqual(restored["snapshot_restored_from"], quote.items[0].name)
        self.assertEqual(restored["snapshot"]["test_project"], self.project.name)
        self.assertIsNone(_restore_from_upstream(frappe._dict(), {"schema_version": 1}))

    # --- empty frozen schema is not a wildcard ----------------------------
    def test_empty_schema_accepts_only_the_hist_original_text(self):
        capability = frappe.get_doc(dict(
            doctype="Laboratory Capability", laboratory=self.laboratory.name,
            test_project=self.project.name, test_object=self.object.name,
            test_standard=self.standard.name, capability_scope="NO TEMPLATE",
        )).insert()
        for status in ("已确认", "已发布"):
            capability.status = status
            capability.save()
        from reli_lims.capability_selection import build_configuration
        config = build_configuration(capability.name, {"original_text": "按协议 30min"}, "quotation", freeze=True)
        config["snapshot"]["condition_schema"] = []
        line = dict(
            item_code=self.item.name, qty=1, rate=100,
            custom_reli_capability=capability.name,
            custom_reli_test_project=self.project.name,
            custom_reli_test_object=self.object.name,
            custom_reli_test_standard=self.standard.name,
            custom_reli_configuration=json.dumps(config),
        )
        quote = self.quotation([line])

        edited = frappe.parse_json(quote.items[0].custom_reli_configuration)
        edited["conditions"] = {"original_text": "按协议 45min"}
        quote.items[0].custom_reli_configuration = json.dumps(edited)
        quote.save()
        self.assertEqual(frappe.parse_json(quote.items[0].custom_reli_configuration)["conditions"],
                         {"original_text": "按协议 45min"})

        invalid = frappe.parse_json(quote.items[0].custom_reli_configuration)
        invalid["conditions"] = {"hold_minutes": 30}
        quote.items[0].custom_reli_configuration = json.dumps(invalid)
        with self.assertRaises(frappe.ValidationError):
            quote.save()

    # --- the snapshot itself is immutable --------------------------------
    def test_snapshot_member_edit_is_rejected(self):
        quote = self.quotation(self.lines())
        config = frappe.parse_json(quote.items[0].custom_reli_configuration)
        config["snapshot"]["test_project"] = self.project_b.name
        config["snapshot"]["limitation"] = "改写后的限制"
        quote.items[0].custom_reli_configuration = json.dumps(config)
        with self.assertRaises(frappe.ValidationError):
            quote.save()

    def test_snapshot_removal_is_rejected(self):
        quote = self.quotation(self.lines())
        config = frappe.parse_json(quote.items[0].custom_reli_configuration)
        config.pop("snapshot")
        quote.items[0].custom_reli_configuration = json.dumps(config)
        with self.assertRaises(frappe.ValidationError):
            quote.save()
