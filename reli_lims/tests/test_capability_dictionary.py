import uuid

import frappe
from frappe.tests import IntegrationTestCase

from reli_lims import capability_catalog
from reli_lims.capability_request import to_request_item
from reli_lims.capability_selection import search


class TestCapabilityDictionary(IntegrationTestCase):
    def setUp(self):
        super().setUp()
        suffix = uuid.uuid4().hex[:10]
        self.project = frappe.get_doc(
            doctype="Test Project", project_name=f"统一低温试验 {suffix}",
            category="气候环境试验", classification_status="已归类",
            condition_template='[{"key":"temperature","label":"温度","type":"number"}]',
        ).insert()
        self.other_project = frappe.get_doc(
            doctype="Test Project", project_name=f"统一振动试验 {suffix}",
            category="力学试验",
        ).insert()
        self.test_object = frappe.get_doc(
            doctype="Test Object", object_name=f"受控检测对象 {suffix}",
            category="轨道交通",
        ).insert()
        self.standard_one = frappe.get_doc(
            doctype="Test Standard", standard_code=f"GB/T T{suffix}", title="低温试验方法",
            version="2026", basis_type="国家标准", status="Active",
        ).insert()
        self.standard_two = frappe.get_doc(
            doctype="Test Standard", standard_code=f"TB/T T{suffix}", title="振动试验方法",
            version="2026", basis_type="行业标准", status="Active",
        ).insert()
        self.method = frappe.get_doc(
            doctype="Test Method", method_name=f"兼容方法 {suffix}", test_project=self.project.name,
        ).insert()
        self.laboratory_one = frappe.get_doc(
            doctype="Laboratory Profile", mercur_seller_id=f"sel_{suffix}",
            laboratory_name=f"实验室甲 {suffix}", review_status="Approved",
        ).insert()
        self.laboratory_two = frappe.get_doc(
            doctype="Laboratory Profile", mercur_seller_id=f"sel_other_{suffix}",
            laboratory_name=f"实验室乙 {suffix}", review_status="Approved",
        ).insert()

        self.capability_one = self.capability(self.laboratory_one, self.standard_one)
        self.capability_two = self.capability(self.laboratory_two, self.standard_two)

    def capability(self, laboratory, standard, **values):
        return frappe.get_doc(dict(
            doctype="Laboratory Capability", laboratory=laboratory.name,
            test_project=self.project.name, test_object=self.test_object.name,
            test_method=self.method.name, test_standard=standard.name,
            product_scope=self.test_object.object_name, capability_scope="受控范围",
            condition_schema='[{"key":"original_text","label":"检测条件原文","type":"text"}]',
            **values,
        )).insert()

    def test_multiple_laboratories_and_standards_share_one_project(self):
        counts = capability_catalog._project_counts(self.project.name)
        self.assertEqual(counts["cap_count"], 2)
        self.assertEqual(counts["laboratory_count"], 2)
        self.assertEqual(counts["standard_count"], 2)
        standards = {row.test_standard for row in frappe.get_doc("Test Project", self.project.name).standards}
        self.assertEqual(standards, {self.standard_one.name, self.standard_two.name})

    def test_one_standard_can_serve_multiple_projects(self):
        other = frappe.get_doc("Test Project", self.other_project.name)
        other.append("standards", {"test_standard": self.standard_one.name})
        other.save()
        owners = frappe.get_all(
            "Test Project Standard", filters={"test_standard": self.standard_one.name},
            pluck="parent", distinct=True,
        )
        self.assertGreaterEqual(set(owners), {self.project.name, self.other_project.name})

    def test_capability_search_supports_four_business_dimensions(self):
        facets = {
            "project": self.project.name,
            "object": self.test_object.name,
            "standard": self.standard_one.name,
            "laboratory": self.laboratory_one.name,
        }
        result = search(mode="catalog", facets=facets)
        self.assertEqual([row.name for row in result["rows"]], [self.capability_one.name])
        for key, value in facets.items():
            row = search(mode="catalog", facets={key: value})["rows"]
            self.assertTrue(any(item.name == self.capability_one.name for item in row), key)

    def test_service_item_reuses_the_project_level_service(self):
        group = frappe.db.get_value("Item Group", {"is_group": 0}, "name") or "All Item Groups"
        item = frappe.get_doc(
            doctype="Item", item_code=f"RELI-TEST-{uuid.uuid4().hex[:12]}",
            item_name=self.project.project_name, item_group=group, stock_uom="Nos",
            is_stock_item=0, is_sales_item=1, custom_reli_test_project=self.project.name,
        ).insert()
        from reli_lims.capability_quotation import service_item
        self.assertEqual(service_item(self.capability_one, item.name).name, item.name)

        from reli_lims.capability_quotation import prepare_lines
        lines = prepare_lines([{"capability_id": self.capability_one.name, "item_code": item.name}])
        self.assertEqual(lines[0]["item_name"], self.project.project_name)
        self.assertEqual(lines[0]["custom_reli_test_project"], self.project.name)

    def test_legacy_snapshot_backfills_unified_project_without_mutation(self):
        legacy = {
            "schema_version": 1, "capability_id": self.capability_one.name, "conditions": {},
            "snapshot": {
                "test_method": self.method.name, "test_standard": self.standard_one.name,
                "method_label": self.method.method_name, "standard_label": self.standard_one.full_name,
                "condition_schema": [{"key": "original_text", "label": "检测条件原文", "type": "text"}],
            },
        }
        before = frappe.as_json(legacy)
        row = to_request_item(legacy)
        self.assertEqual(row["test_project"], self.project.name)
        self.assertEqual(row["test_object"], self.test_object.name)
        self.assertEqual(frappe.as_json(legacy), before)

    def test_legacy_method_maps_to_the_unified_project(self):
        method = frappe.get_doc(
            doctype="Test Method", method_name=f"仅兼容方法 {uuid.uuid4().hex[:8]}",
            test_project=self.project.name,
        ).insert()
        capability = self.capability(
            self.laboratory_one, self.standard_one, test_method=method.name, test_project=None,
        )
        self.assertEqual(capability.test_project, self.project.name)
