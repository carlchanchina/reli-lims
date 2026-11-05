import uuid
from pathlib import Path

import frappe
from frappe.tests import IntegrationTestCase

from reli_lims import business_relations
from reli_lims.patches.p161_legacy_dictionary_cleanup import _cleanup


class TestBusinessRelations(IntegrationTestCase):
    def setUp(self):
        super().setUp()
        suffix = uuid.uuid4().hex[:10]
        self.standard = frappe.get_doc(
            doctype="Test Standard", standard_code=f"GB/T REL-{suffix}",
            title="关联关系试验方法", version="2026",
            basis_type="国家标准", status="Active",
        ).insert()
        self.test_object = frappe.get_doc(
            doctype="Test Object", object_name=f"关联关系检测对象 {suffix}",
            category="轨道交通",
        ).insert()
        self.project = frappe.get_doc(
            doctype="Test Project", project_name=f"关联关系检测项目 {suffix}",
            category="力学试验", classification_status="已归类",
            standards=[{"test_standard": self.standard.name}],
            objects=[{"test_object": self.test_object.name}],
        ).insert()
        self.laboratory = frappe.get_doc(
            doctype="Laboratory Profile", mercur_seller_id=f"sel_rel_{suffix}",
            laboratory_name=f"关联关系实验室 {suffix}", review_status="Approved",
        ).insert()
        self.capability = frappe.get_doc(
            doctype="Laboratory Capability", laboratory=self.laboratory.name,
            test_project=self.project.name, test_object=self.test_object.name,
            test_standard=self.standard.name, product_scope=self.test_object.object_name,
            capability_scope=f"关联能力范围 {suffix}", limitation="原始限制说明",
        ).insert()
        item_group = frappe.db.get_value("Item Group", {"is_group": 0}, "name") or "All Item Groups"
        self.item = frappe.get_doc(
            doctype="Item", item_code=f"RELI-REL-{suffix}",
            item_name=self.project.project_name, item_group=item_group, stock_uom="Nos",
            is_stock_item=0, is_sales_item=1,
            custom_reli_test_project=self.project.name,
            custom_reli_service_capability=self.capability.name,
        ).insert()

    def test_retired_detection_project_has_no_business_link(self):
        meta = frappe.get_meta("Item")
        self.assertIsNone(meta.get_field("custom_reli_detection_project"))
        self.assertFalse(frappe.db.has_column("Item", "custom_reli_detection_project"))
        self.assertFalse(frappe.db.has_column("Laboratory Capability", "detection_project"))
        self.assertFalse(frappe.get_all(
            "Custom Field", filters={"options": "Detection Project"}, limit_page_length=0,
        ))
        self.assertFalse(frappe.db.exists("DocType", "Detection Project"))

    def test_item_with_unified_project_opens_and_saves(self):
        item = frappe.get_doc("Item", self.item.name)
        self.assertEqual(item.custom_reli_test_project, self.project.name)
        item.description = "关联关系回归测试"
        item.save()
        self.assertEqual(
            frappe.db.get_value("Item", item.name, "custom_reli_test_project"),
            self.project.name,
        )

    def test_object_has_reverse_project_standard_capability_and_item_views(self):
        data = business_relations.test_object_relations(self.test_object.name)

        self.assertEqual([row["name"] for row in data["projects"]], [self.project.name])
        self.assertEqual([row["name"] for row in data["standards"]], [self.standard.name])
        self.assertEqual([row["name"] for row in data["capabilities"]], [self.capability.name])
        self.assertEqual([row["name"] for row in data["items"]], [self.item.name])
        self.assertEqual(data["counts"]["laboratories"], 1)

    def test_project_has_service_item_and_capability_views(self):
        data = business_relations.test_project_relations(self.project.name)

        self.assertEqual([row["name"] for row in data["objects"]], [self.test_object.name])
        self.assertEqual([row["name"] for row in data["standards"]], [self.standard.name])
        self.assertEqual([row["name"] for row in data["capabilities"]], [self.capability.name])
        self.assertEqual([row["name"] for row in data["items"]], [self.item.name])

    def test_standard_has_reverse_project_capability_and_item_views(self):
        data = business_relations.test_standard_relations(self.standard.name)

        self.assertEqual([row["name"] for row in data["projects"]], [self.project.name])
        self.assertEqual([row["name"] for row in data["capabilities"]], [self.capability.name])
        self.assertEqual([row["name"] for row in data["items"]], [self.item.name])

    def test_item_returns_project_context(self):
        data = business_relations.item_relations(self.item.name)

        self.assertEqual(data["project"]["name"], self.project.name)
        self.assertEqual(data["counts"]["objects"], 1)
        self.assertEqual(data["counts"]["standards"], 1)
        self.assertEqual(data["counts"]["capabilities"], 1)
        self.assertEqual(data["counts"]["service_items"], 1)

    def test_service_item_translation_overrides_suite_label(self):
        translations = Path(frappe.get_app_path("reli_lims")) / "translations" / "zh.csv"
        content = translations.read_text()
        self.assertIn("Item,服务商品", content)
        self.assertIn("Items,服务商品", content)

    def test_global_relation_asset_uses_built_url(self):
        includes = frappe.get_hooks("app_include_js") or []
        self.assertIn("business_relations.bundle.js", includes)
        asset = Path(frappe.get_app_path("reli_lims")) / "public/js/business_relations.bundle.js"
        self.assertTrue(asset.is_file())

    def test_legacy_cleanup_is_idempotent_without_touching_business_data(self):
        before = (
            frappe.db.count("Test Project"), frappe.db.count("Test Object"),
            frappe.db.count("Test Standard"), frappe.db.count("Laboratory Capability"),
        )
        self.assertEqual(_cleanup(), {"items": 0, "capabilities": 0})
        self.assertEqual(_cleanup(), {"items": 0, "capabilities": 0})
        after = (
            frappe.db.count("Test Project"), frappe.db.count("Test Object"),
            frappe.db.count("Test Standard"), frappe.db.count("Laboratory Capability"),
        )
        self.assertEqual(before, after)
