"""P4 transactional regression for native orders, mixed goods and equipment."""
import uuid
from unittest.mock import patch

import frappe
from reli_lims.tests import test_test_request
from frappe.utils import today, add_days

from reli_lims.sales_order_testing import accept_quotation, retry, order_scope


class TestP4OrdersEquipment(test_test_request.TestTestingRequest):
    def setUp(self):
        super().setUp()
        self.token = uuid.uuid4().hex[:8]
        self.project = frappe.get_doc(doctype="Test Project", project_name="P4 可靠性检测 " + self.token).insert()
        self.method.test_project = self.project.name
        self.method.save()
        self.testing = frappe.get_doc(doctype="Item", item_code="P4-T-" + self.token,
            item_name="P4 中文检测服务", item_group="All Item Groups", stock_uom="Nos",
            is_stock_item=0, is_sales_item=1, custom_reli_business_type="检测服务",
            custom_reli_test_project=self.project.name).insert()
        self.general = frappe.get_doc(doctype="Item", item_code="P4-S-" + self.token,
            item_name="P4 培训服务", item_group="All Item Groups", stock_uom="Nos",
            is_stock_item=0, custom_reli_business_type="普通服务").insert()
        self.goods = frappe.get_doc(doctype="Item", item_code="P4-G-" + self.token,
            item_name="P4 实物商品", item_group="All Item Groups", stock_uom="Nos",
            is_stock_item=1, custom_reli_business_type="实物商品").insert()

    def order(self, submit=True, testing_count=1):
        doc = frappe.get_doc(doctype="Sales Order", customer=self.customer.name, company=self.company.name,
            transaction_date=today(), delivery_date=add_days(today(), 7), currency="USD",
            selling_price_list="Standard Selling", items=[dict(item_code=self.testing.name, qty=1, rate=100,
                custom_reli_test_standard=self.standard.name, delivery_date=add_days(today(), 7)) for _ in range(testing_count)] + [
                dict(item_code=i.name, qty=1, rate=20, delivery_date=add_days(today(), 7)) for i in (self.general, self.goods)]).insert()
        if submit:
            doc.submit()
        return doc

    def request_for(self, order):
        return frappe.get_doc("Test Request", frappe.db.get_value("Test Request", {"sales_order": order.name}, "name"))

    def test_mixed_order_generates_only_testing_and_retry_is_idempotent(self):
        order = self.order()
        order.reload()
        self.assertEqual(order.custom_reli_generation_status, "已生成", order.custom_reli_generation_error)
        request = self.request_for(order)
        self.assertFalse(request.samples)
        self.assertEqual(len(request.items), 1)
        self.assertEqual(request.items[0].service_item, self.testing.name)
        self.assertEqual(request.items[0].source_sales_order_item, order.items[0].name)
        self.assertEqual(retry(order.name), [request.name])
        self.assertEqual(frappe.db.count("Test Request", {"sales_order": order.name}), 1)
        request.save()
        request.items = []
        with self.assertRaises(frappe.ValidationError):
            request.save()

    def test_failure_rolls_back_all_groups_and_can_retry(self):
        order = self.order(submit=False, testing_count=2)
        order.items[1].custom_reli_split_group = "第二实验室"
        order.save()
        original = frappe.get_doc
        def fail_second(*args, **kwargs):
            if args and isinstance(args[0], dict) and args[0].get("doctype") == "Test Request" and str(args[0].get("title") or "").endswith("第二实验室"):
                raise RuntimeError("P4 injected failure")
            return original(*args, **kwargs)
        with patch("reli_lims.sales_order_testing.frappe.get_doc", side_effect=fail_second):
            order.submit()
        order.reload()
        self.assertEqual(order.custom_reli_generation_status, "生成失败")
        self.assertFalse(frappe.db.exists("Test Request", {"sales_order": order.name}))
        self.assertEqual(len(retry(order.name)), 2)
        self.assertEqual(len(retry(order.name)), 2)

    def test_cancellation_and_duplicate_source_are_rejected(self):
        order = self.order()
        request = self.request_for(order)
        duplicate = frappe.copy_doc(request)
        with self.assertRaises(frappe.ValidationError):
            duplicate.insert()
        with self.assertRaises(frappe.ValidationError):
            order.cancel()

    def test_changed_order_flags_difference_without_overwriting_request(self):
        order = self.order()
        request = self.request_for(order)
        original = request.order_scope_snapshot
        from reli_lims.sales_order_testing import changed
        order.items[0].qty = 2
        changed(order)
        request.reload()
        self.assertTrue(request.order_difference)
        self.assertEqual(request.order_scope_snapshot, original)
        self.assertEqual(request.items[0].requested_quantity, 1)

    def test_order_without_testing_does_not_generate_request(self):
        order = self.order(submit=False)
        order.items = order.items[1:]
        order.save().submit()
        self.assertEqual(order.custom_reli_generation_status, "无需委托")
        self.assertFalse(frappe.db.exists("Test Request", {"sales_order": order.name}))

    def test_quotation_mapping_preserves_native_sources(self):
        quote = frappe.get_doc(doctype="Quotation", quotation_to="Customer", party_name=self.customer.name,
            company=self.company.name, transaction_date=today(), valid_till=add_days(today(), 10),
            currency="USD", selling_price_list="Standard Selling", items=[dict(item_code=i.name, qty=1, rate=100)
                for i in (self.testing, self.general, self.goods)]).insert().submit()
        accept_quotation(quote.name, "P4 SOFTWARE TEST customer accepted")
        from erpnext.selling.doctype.quotation.quotation import make_sales_order
        order = make_sales_order(quote.name)
        order.delivery_date = add_days(today(), 7)
        for row in order.items:
            row.delivery_date = order.delivery_date
        order.insert().submit()
        request = self.request_for(order)
        self.assertEqual(request.quotation, quote.name)
        self.assertEqual(len(request.items), 1)
        self.assertEqual(order.items[0].quotation_item, quote.items[0].name)

    def test_customer_print_projection_omits_internal_metadata(self):
        from reli_lims.document_output.mapping.quotation import build_context
        data = self.quotation.as_dict()
        data["items"][0].update(custom_reli_capability="PRIVATE-CAP", custom_reli_configuration={
            "conditions": {"duration": 15}, "snapshot": {"project_label": "中文项目", "standard_label": "公开标准",
                "source": "PRIVATE-SOURCE", "laboratory_cost": 999, "condition_schema": []}},
            description="PRIVATE-COST PRIVATE-SUPPLIER")
        context = build_context(data)
        text = str(context)
        for secret in ("PRIVATE-CAP", "PRIVATE-SOURCE", "PRIVATE-COST", "PRIVATE-SUPPLIER", "laboratory_cost"):
            self.assertNotIn(secret, text)
        self.assertIn("公开标准", text)

    def test_direct_order_allows_full_customer_review_and_intake(self):
        from reli_lims.customer_share import send_link, customer_confirm, lab_review, customer_save
        from reli_lims.services.test_request import receive_samples, make_test_program
        order = self.order()
        request = self.request_for(order)
        share = send_link(request.name, customer_email="p4@example.invalid")
        request.reload()
        with customer_save():
            request.customer_requirements = "P4 SOFTWARE TEST ONLY"
            request.contact_person = "P4 软件验收客户"
            request.contact_email = "p4@example.invalid"
            request.customer_declaration_confirmed = 1
            request.append("samples", dict(sample_code="S1", product_name="软件验收样品", quantity=1))
            request.save(ignore_permissions=True)
        self.assertEqual(request.sample_assignments[0].sample_code, "S1")
        customer_confirm(share["key"])
        lab_review(request.name)
        request.reload().submit()
        self.assertTrue(request.project)
        receive_samples(request.name, [dict(sample_code="S1", quantity=1, received_date=today(), received_by="Administrator")])
        program = frappe.get_doc("Test Program", make_test_program(request.name))
        self.assertEqual(program.items[0].test_project, self.project.name)

    def equipment(self):
        laboratory = frappe.get_doc(doctype="Laboratory Profile", mercur_seller_id="sel_p4_" + self.token,
            laboratory_name="P4 软件验收实验室 " + self.token, review_status="Approved").insert()
        account = frappe.db.get_value("Account", {"company": self.company.name, "account_type": "Fixed Asset", "is_group": 0}, "name")
        category = frappe.get_doc(doctype="Asset Category", asset_category_name="P4 " + self.token,
            non_depreciable_category=1, accounts=[dict(company_name=self.company.name, fixed_asset_account=account)]).insert()
        location = frappe.get_doc(doctype="Location", location_name="P4 实验室 " + self.token).insert()
        item = frappe.get_doc(doctype="Item", item_code="P4-ASSET-" + self.token, item_name="P4 自用试验台",
            item_group="All Item Groups", stock_uom="Nos", is_stock_item=0, is_fixed_asset=1,
            asset_category=category.name).insert()
        return frappe.get_doc(doctype="Asset", asset_name="P4 软件验收试验台", item_code=item.name,
            company=self.company.name, asset_category=category.name, asset_type="Existing Asset", asset_owner="Company",
            asset_quantity=1, purchase_date=today(), available_for_use_date=today(), location=location.name,
            net_purchase_amount=1000, purchase_amount=1000, calculate_depreciation=0,
            custom_reli_laboratory=laboratory.name, custom_reli_model="P4-MODEL", custom_reli_serial_no="P4-SERIAL",
            custom_reli_equipment_status="启用", custom_reli_calibration_until=add_days(today(), 30),
            custom_reli_scopes=[dict(test_project=self.project.name)]).insert()

    def test_equipment_qualification_and_execution_snapshot(self):
        from reli_lims.equipment import validate_execution, available
        asset = self.equipment()
        row = frappe._dict(name="new", test_project=self.project.name, asset=asset.name, status="Ready", equipment_snapshot=None)
        from types import SimpleNamespace
        program = SimpleNamespace(items=[row], get_doc_before_save=lambda: None)
        validate_execution(program)
        self.assertEqual(row.equipment_snapshot["asset_name"], asset.asset_name)
        self.assertEqual(available(self.project.name)["rows"][0].name, asset.name)
        self.assertEqual(available(self.project.name, text=asset.name)["rows"][0].name, asset.name)
        row.equipment_snapshot = None
        asset.custom_reli_calibration_until = add_days(today(), -1)
        asset.save()
        with self.assertRaises(frappe.ValidationError):
            validate_execution(program)
        asset.custom_reli_calibration_until = add_days(today(), 30)
        asset.custom_reli_equipment_status = "维护"
        asset.save()
        with self.assertRaises(frappe.ValidationError):
            validate_execution(program)
        asset.custom_reli_equipment_status = "启用"
        asset.save()
        row.status = "Running"
        validate_execution(program)
        stored = frappe._dict(row.copy())
        program.get_doc_before_save = lambda: SimpleNamespace(items=[stored])
        asset.asset_name = "设备后来改名"
        asset.save()
        row.status = "Completed"
        validate_execution(program)
        self.assertEqual(row.equipment_snapshot["asset_name"], "P4 软件验收试验台")
        row.equipment_snapshot = {"asset_name": "forged"}
        with self.assertRaises(frappe.ValidationError):
            validate_execution(program)

    def test_partial_customer_payload_preserves_native_date_values(self):
        import json
        from frappe.website.doctype.web_form import web_form as native
        from reli_lims.customer_share import accept, send_link
        order = self.order()
        request = self.request_for(order)
        share = send_link(request.name)
        with patch.object(native, "accept", return_value={"name": request.name}) as adapter:
            accept("customer-request", {"name": request.name, "customer_shipping_details": "P4 software test",
                "samples": [{"sample_code": "S1", "product_name": "P4 软件样品", "quantity": 1}]}, share["key"])
        payload = json.loads(adapter.call_args.args[1])
        self.assertEqual(payload["delivery_date"], str(request.delivery_date))
