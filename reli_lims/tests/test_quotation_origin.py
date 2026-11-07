"""CRM-origin quotations must reach the lab without widening the commercial boundary."""
import uuid

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, today

from reli_lims import capability_request, commercial_access
from reli_lims.quotation_origin import fulfillable_lines, quotation_customer

ALPHABET = "0123456789ABCDEFGHJKLMNPQRTUWXY"
WEIGHTS = (1, 3, 9, 27, 19, 26, 16, 17, 20, 29, 25, 13, 8, 24, 10, 30, 28)


def uscc(seed):
    """Deterministic, checksum-valid unified social credit code for fixtures."""
    prefix = ("91320594" + seed).upper().ljust(17, "0")[:17]
    total = sum(ALPHABET.index(char) * weight for char, weight in zip(prefix, WEIGHTS))
    return prefix + ALPHABET[(31 - total % 31) % 31]


class TestQuotationOrigin(IntegrationTestCase):
    def setUp(self):
        super().setUp()
        self.token = uuid.uuid4().hex[:8]
        self.company = frappe.get_doc(dict(doctype="Company", company_name=f"报价来源 {self.token}",
            abbr=f"Q{self.token[:5]}", default_currency="USD", country="United States",
            chart_of_accounts="Standard")).insert()
        group = frappe.get_doc(dict(doctype="Customer Group",
            customer_group_name=f"报价来源组 {self.token}", parent_customer_group="All Customer Groups",
            is_group=0)).insert()
        self.customer = frappe.get_doc(dict(doctype="Customer", customer_name=f"报价来源客户 {self.token}",
            customer_type="Company", customer_group=group.name, territory="All Territories")).insert()
        self.method = frappe.get_doc(dict(doctype="Test Method", method_name=f"报价来源 {self.token}")).insert()
        self.standard = frappe.get_doc(dict(doctype="Test Standard", standard_code=f"Q-{self.token}",
            title="Quotation origin standard", version="1", status="Active")).insert()
        self.project = frappe.get_doc(
            doctype="Test Project", project_name="报价来源检测 " + self.token
        ).insert()
        self.method.test_project = self.project.name
        self.method.save()
        self.testing = frappe.get_doc(
            doctype="Item", item_code="QT-" + self.token, item_name="报价来源检测服务",
            item_group="All Item Groups", stock_uom="Nos", is_stock_item=0, is_sales_item=1,
            custom_reli_business_type="检测服务", custom_reli_test_project=self.project.name,
        ).insert()
        self.general = frappe.get_doc(
            doctype="Item", item_code="QG-" + self.token, item_name="报价来源培训服务",
            item_group="All Item Groups", stock_uom="Nos", is_stock_item=0,
            custom_reli_business_type="普通服务",
        ).insert()
        self.goods = frappe.get_doc(
            doctype="Item", item_code="QW-" + self.token, item_name="报价来源实物商品",
            item_group="All Item Groups", stock_uom="Nos", is_stock_item=1,
            custom_reli_business_type="实物商品",
        ).insert()

    def capability_quote_lines(self, *, rate=100):
        """真实能力 → 报价行草稿，保留技术快照。"""
        from reli_lims.capability_quotation import prepare_lines
        from reli_lims.capability_selection import build_configuration

        token = uuid.uuid4().hex[:8]
        laboratory = frappe.get_doc(
            doctype="Laboratory Profile", mercur_seller_id=f"sel_qt_{token}",
            laboratory_name=f"报价来源实验室 {token}", review_status="Approved",
        ).insert()
        capability = frappe.get_doc(
            doctype="Laboratory Capability", laboratory=laboratory.name,
            test_project=self.project.name, test_method=self.method.name,
            test_standard=self.standard.name, capability_scope="QUOTATION ORIGIN ONLY",
            condition_schema=frappe.as_json([dict(key="hold_minutes", label="保持时间（分钟）", type="number")]),
        ).insert()
        for status in ("已确认", "已发布"):
            capability.status = status
            capability.save()
        config = build_configuration(capability.name, {"hold_minutes": 30}, "quotation")
        lines = prepare_lines([dict(capability_id=capability.name,
            conditions=config["conditions"], item_code=self.testing.name)])
        lines[0]["rate"] = rate
        return capability, config, lines
    def quote(self, lines, *, party_type="Customer", party=None):
        return frappe.get_doc(
            doctype="Quotation",
            quotation_to=party_type,
            party_name=party or self.customer.name,
            company=self.company.name,
            transaction_date=today(),
            valid_till=add_days(today(), 30),
            currency="USD",
            selling_price_list="Standard Selling",
            custom_reli_delivery_date=add_days(today(), 12),
            items=lines,
        ).insert().submit()

    def crm_quote(self, lines, *, customer=None):
        """CRM 商机 → 企业主档 → 客户身份 → 报价，完整走官方三层模型。"""
        token = uuid.uuid4().hex[:8]
        organization = frappe.get_doc(
            doctype="CRM Organization", organization_name=f"报价来源企业 {token}"
        ).insert()
        profile = frappe.get_doc(
            doctype="China Enterprise Profile",
            enterprise_name=organization.name,
            source_type="手工",
            verification_status="未核验",
            unified_social_credit_code=uscc(token),
        ).insert()
        organization.custom_cn_enterprise_profile = profile.name
        organization.save()
        deal = frappe.get_doc(
            doctype="CRM Deal", organization=organization.name, status="Qualification"
        ).insert()
        if customer:
            frappe.get_doc(
                doctype="China Enterprise Link",
                enterprise_profile=profile.name,
                reference_doctype="Customer",
                reference_name=customer,
                relationship_type="客户",
                is_active=1,
                is_primary=1,
            ).insert()
        return self.quote(lines, party_type="CRM Deal", party=deal.name), deal, organization, profile

    def mixed_lines(self):
        """检测服务 + 普通服务 + 实物商品，用于验证实验室只看到检测行。"""
        _capability, _config, lines = self.capability_quote_lines(rate=250)
        return lines + [
            dict(item_code=self.general.name, qty=1, rate=20),
            dict(item_code=self.goods.name, qty=1, rate=20),
        ]

    def request_from(self, payload):
        items = [
            dict(row, item_code=f"CAP-{index}")
            for index, row in enumerate(payload["items"], 1)
        ]
        return frappe.get_doc(
            dict(
                doctype="Test Request",
                title="报价来源导入 " + uuid.uuid4().hex[:6],
                customer=payload["customer"],
                company=payload["company"],
                request_date=today(),
                delivery_date=add_days(today(), 7),
                quotation=payload["quotation"],
                samples=[dict(sample_code="S1", product_name="报价来源样品", quantity=1)],
                items=items,
                sample_assignments=[dict(item_code=row["item_code"], sample_code="S1") for row in items],
            )
        ).insert()

    def choices(self, customer=None):
        rows = commercial_access.quotation_query(
            "Quotation", None, None, 0, 50, {"customer": customer, "company": self.company.name}
        )
        return {row[0]: row[1] for row in rows}

    # ---------------------------------------------------------------- customer source

    def test_customer_quotation_imports_only_fulfillable_testing_lines(self):
        quote = self.quote(self.mixed_lines())

        payload = capability_request.quotation_items(quote.name)

        self.assertEqual(payload["customer"], self.customer.name)
        self.assertEqual(payload["quotation"], quote.name)
        self.assertEqual(len(payload["items"]), 1, "普通服务与实物商品不得进入实验室委托")
        row = payload["items"][0]
        self.assertEqual(row["capability"], quote.items[0].custom_reli_capability)
        self.assertEqual(row["requested_quantity"], 1)
        self.assertEqual(row["quoted_quantity"], 1)
        self.assertNotIn("rate", row, "实验室视角不返回价格，但服务端保留快照")
        self.assertIn(quote.name, self.choices(self.customer.name))

    # --------------------------------------------------------------------- crm source

    def test_crm_deal_quotation_resolves_customer_and_is_selectable(self):
        quote, deal, organization, profile = self.crm_quote(self.mixed_lines(), customer=self.customer.name)

        self.assertEqual(quotation_customer(quote.name), self.customer.name)
        payload = capability_request.quotation_items(quote.name)
        self.assertEqual(payload["customer"], self.customer.name)
        self.assertEqual(payload["company"], self.company.name)
        self.assertEqual(len(payload["items"]), 1)

        labels = self.choices(self.customer.name)
        self.assertIn(quote.name, labels)
        self.assertEqual(labels[quote.name].split("｜")[-1], self.customer.name)

        other = frappe.get_doc(
            doctype="Customer",
            customer_name="非本企业 " + uuid.uuid4().hex[:6],
            customer_type="Company",
            customer_group=self.customer.customer_group,
            territory="All Territories",
        ).insert()
        self.assertNotIn(quote.name, self.choices(other.name))
        with self.assertRaises(frappe.ValidationError):
            capability_request.quotation_items(quote.name, customer=other.name)

    def test_crm_deal_without_enterprise_link_is_rejected(self):
        quote, _deal, _organization, _profile = self.crm_quote(self.mixed_lines())

        self.assertIsNone(quotation_customer(quote.name))
        with self.assertRaises(frappe.ValidationError) as caught:
            capability_request.quotation_items(quote.name)
        self.assertIn("企业主档", str(caught.exception))
        self.assertNotIn(quote.name, self.choices(self.customer.name))

    # ------------------------------------------------------------------- duplications

    def test_import_keeps_price_snapshot_and_blocks_over_quantity(self):
        quote = self.quote(self.mixed_lines())
        payload = capability_request.quotation_items(quote.name)
        request = self.request_from(payload)

        row = frappe.get_doc("Test Request", request.name).items[0]
        self.assertEqual(row.quoted_rate, 250)
        self.assertEqual(row.quoted_quantity, 1)
        self.assertEqual(row.source_quotation, quote.name)
        self.assertEqual(row.source_quotation_item, quote.items[0].name)

        self.assertEqual(fulfillable_lines(quote.name), [], "已转委托的行不得再次出现")
        with self.assertRaises(frappe.ValidationError):
            capability_request.quotation_items(quote.name)
        with self.assertRaises(frappe.ValidationError) as caught:
            self.request_from(payload)
        self.assertIn("超过报价数量", str(caught.exception))

    def test_ordered_line_is_hidden_from_the_lab_picker(self):
        from erpnext.selling.doctype.quotation.quotation import make_sales_order
        from reli_lims.sales_order_testing import accept_quotation

        quote = self.quote(self.mixed_lines())
        accept_quotation(quote.name, "报价来源回归客户接受")
        order = make_sales_order(quote.name)
        order.delivery_date = add_days(today(), 12)
        for line in order.items:
            line.delivery_date = order.delivery_date
        order.insert()

        self.assertEqual(fulfillable_lines(quote.name), [])
        self.assertNotIn(quote.name, self.choices(self.customer.name))
        with self.assertRaises(frappe.ValidationError) as caught:
            capability_request.quotation_items(quote.name)
        self.assertIn("可履约的检测服务行", str(caught.exception))
