"""Resolve the commercial party and the fulfillable scope of a quotation.

ERPNext quotations can be addressed to a Customer, a Lead, a Prospect or a
Frappe CRM Deal. Frappe CRM always creates ``quotation_to = "CRM Deal"``, so
``Quotation.customer`` does not exist there and ``party_name`` holds a deal.
The single deduplicated customer of that deal lives on the China enterprise
master data (``CRM Organization`` → ``China Enterprise Profile`` →
``China Enterprise Link``), which is why this module owns the resolution
instead of each caller guessing.

Only the fields needed for selection and consistency checks are read; amounts
stay behind the commercial boundary except for the explicit rate snapshot that
the request line keeps for fulfillment.
"""
import frappe
from frappe import _
from frappe.utils import flt

TESTING = "检测服务"
CRM_DEAL = "CRM Deal"


def _has_doctype(doctype):
    return bool(frappe.db.exists("DocType", doctype))


def _deal_sources():
    """Whether the CRM bridge tables this module relies on are available."""
    return (
        _has_doctype("CRM Deal")
        and _has_doctype("CRM Organization")
        and _has_doctype("China Enterprise Link")
    )


def _existing_customer(name):
    if not name:
        return None
    return frappe.db.get_value("Customer", name, "name")


def deal_customers(deals):
    """Map CRM deals to their resolved Customer in a bounded number of queries."""
    deals = [name for name in set(filter(None, deals)) if name]
    if not deals or not _deal_sources():
        return {}
    rows = frappe.db.sql(
        """select d.name, d.erpnext_customer, o.custom_cn_enterprise_profile as profile
        from `tabCRM Deal` d
        left join `tabCRM Organization` o on o.name = d.organization
        where d.name in %(deals)s""",
        {"deals": tuple(deals)},
        as_dict=True,
    )
    profiles = sorted({row.profile for row in rows if row.profile})
    linked = {}
    if profiles:
        for link in frappe.db.sql(
            """select enterprise_profile as profile, reference_name as customer
            from `tabChina Enterprise Link`
            where reference_doctype = 'Customer' and is_active = 1
              and enterprise_profile in %(profiles)s
            order by is_primary desc, modified desc""",
            {"profiles": tuple(profiles)},
            as_dict=True,
        ):
            linked.setdefault(link.profile, link.customer)
    legacy = {}
    for row in frappe.db.sql(
        """select name, crm_deal from `tabCustomer`
        where crm_deal in %(deals)s order by modified desc""",
        {"deals": tuple(deals)},
        as_dict=True,
    ):
        legacy.setdefault(row.crm_deal, row.name)
    resolved = {}
    for row in rows:
        customer = (
            (linked.get(row.profile) if row.profile else None)
            or legacy.get(row.name)
            or _existing_customer(row.erpnext_customer)
        )
        if customer and _existing_customer(customer):
            resolved[row.name] = customer
    return resolved


def quotation_customer(name):
    """The Customer behind a quotation, or None when it cannot be proven."""
    quote = frappe.db.get_value("Quotation", name, ["quotation_to", "party_name"], as_dict=True)
    if not quote:
        return None
    if quote.quotation_to == "Customer":
        return quote.party_name
    if quote.quotation_to != CRM_DEAL:
        return None
    organization = frappe.db.get_value("CRM Deal", quote.party_name, "organization")
    if organization:
        profile = frappe.db.get_value("CRM Organization", organization, "custom_cn_enterprise_profile")
        if profile and _has_doctype("China Enterprise Link"):
            linked = frappe.db.get_value(
                "China Enterprise Link",
                {"enterprise_profile": profile, "reference_doctype": "Customer", "is_active": 1},
                "reference_name",
                order_by="is_primary desc, modified desc",
            )
            if _existing_customer(linked):
                return linked
    return deal_customers([quote.party_name]).get(quote.party_name)


def deal_names_for_customer(customer):
    """CRM deals that resolve to this customer, used to filter quotation pickers."""
    if not customer or not _deal_sources():
        return []

    def pluck(query, values):
        return [row[0] for row in frappe.db.sql(query, values) if row and row[0]]

    deals = set()
    profiles = pluck(
        """select enterprise_profile from `tabChina Enterprise Link`
        where reference_doctype = 'Customer' and reference_name = %s and is_active = 1""",
        (customer,),
    )
    if profiles:
        deals.update(
            pluck(
                """select d.name from `tabCRM Deal` d
                join `tabCRM Organization` o on o.name = d.organization
                where o.custom_cn_enterprise_profile in %(profiles)s""",
                {"profiles": tuple(profiles)},
            )
        )
    deals.update(
        pluck(
            """select name from `tabCRM Deal` where erpnext_customer = %s""",
            (customer,),
        )
    )
    deals.update(
        pluck(
            """select crm_deal from `tabCustomer` where name = %s and ifnull(crm_deal, '') != ''""",
            (customer,),
        )
    )
    return sorted(deals)


def ordered_quantity(quotation_item):
    """Quantity already carried into submitted/draft sales orders."""
    return flt(
        frappe.db.sql(
            """select coalesce(sum(i.qty), 0) from `tabSales Order Item` i
            join `tabSales Order` so on so.name = i.parent
            where i.quotation_item = %s and so.docstatus < 2""",
            (quotation_item,),
        )[0][0]
    )


def requested_quantity(quotation_item, exclude_request=None):
    """Quantity already carried into testing requests that did not come from an order."""
    return flt(
        frappe.db.sql(
            """select coalesce(sum(i.requested_quantity), 0) from `tabTest Request Item` i
            join `tabTest Request` r on r.name = i.parent
            where i.source_quotation_item = %s and r.docstatus < 2
              and ifnull(i.source_sales_order_item, '') = ''
              and i.parent != %s""",
            (quotation_item, exclude_request or "\0"),
        )[0][0]
    )


def remaining_quantity(row, exclude_request=None):
    """Fulfillable quantity of one quotation line, never below zero."""
    used = ordered_quantity(row.name) + requested_quantity(row.name, exclude_request)
    return max(flt(row.qty) - flt(used), 0)


def is_testing_line(row):
    return row.get("custom_reli_business_type") == TESTING and bool(row.get("custom_reli_capability"))


def fulfillable_lines(quotation, exclude_request=None):
    """Detected testing-service lines that still have quantity left to fulfill.

    Ordinary services and stock items never reach the lab intake, and lines that
    are already fully ordered or requested are dropped instead of being offered
    again — that is the intent guard against duplicated fulfillment.
    """
    rows = frappe.db.sql(
        """select name, idx, item_code, item_name, qty, rate,
            custom_reli_business_type, custom_reli_capability, custom_reli_configuration,
            custom_reli_test_project
        from `tabQuotation Item`
        where parent = %s
        order by idx asc
        limit 500""",
        (quotation,),
        as_dict=True,
    )
    lines = []
    for row in rows:
        if not is_testing_line(row):
            continue
        if not row.get("custom_reli_configuration"):
            continue
        remaining = remaining_quantity(row, exclude_request)
        if remaining <= 0:
            continue
        line = dict(row)
        line["remaining_qty"] = remaining
        lines.append(line)
    return lines


def quotation_customer_map(rows):
    """Bulk variant of :func:`quotation_customer` for picker projections."""
    deals = [row.party_name for row in rows if row.quotation_to == CRM_DEAL]
    resolved = deal_customers(deals)
    return {
        row.name: row.party_name if row.quotation_to == "Customer" else resolved.get(row.party_name)
        for row in rows
    }


def fulfillable_exists_sql(alias="q"):
    """SQL predicate: the quotation still has a testing line with quantity left.

    Mirrors :func:`fulfillable_lines` so a picker never offers a quotation that
    would immediately come back empty, and never hides ordinary services or
    stock items as if they were lab work.
    """
    return f"""exists (
        select 1 from `tabQuotation Item` qi
        where qi.parent = {alias}.name
          and qi.custom_reli_business_type = '{TESTING}'
          and ifnull(qi.custom_reli_capability, '') != ''
          and ifnull(qi.custom_reli_configuration, '') not in ('', 'null', '{{}}')
          and qi.qty > (
            (select coalesce(sum(soi.qty), 0) from `tabSales Order Item` soi
             join `tabSales Order` so on so.name = soi.parent
             where soi.quotation_item = qi.name and so.docstatus < 2)
            + (select coalesce(sum(tri.requested_quantity), 0) from `tabTest Request Item` tri
               join `tabTest Request` tr on tr.name = tri.parent
               where tri.source_quotation_item = qi.name and tr.docstatus < 2
                 and ifnull(tri.source_sales_order_item, '') = '')
          )
    )"""


def validate_line_capacity(row, doc):
    """Server-side guard: a quotation line cannot be fulfilled beyond its quantity."""
    if not row.get("source_quotation_item") or row.get("source_sales_order_item"):
        return
    source = frappe.db.get_value(
        "Quotation Item",
        row.source_quotation_item,
        ["parent", "qty"],
        as_dict=True,
    )
    if not source or source.parent != row.source_quotation:
        frappe.throw(_("报价行来源无效。"))
    ordered = ordered_quantity(row.source_quotation_item)
    if ordered >= flt(source.qty):
        frappe.throw(_("该报价行已转销售订单，请从销售订单生成委托。"))
    requested = requested_quantity(row.source_quotation_item, exclude_request=doc.get("name") or "")
    if requested + flt(row.requested_quantity) > flt(source.qty) + 1e-6:
        frappe.throw(
            _("报价行 {0} 累计委托数量 {1} 超过报价数量 {2}。").format(
                row.source_quotation_item,
                flt(requested + flt(row.requested_quantity)),
                flt(source.qty),
            )
        )
