"""实验室角色读取商业单据的**有界投影**。

背景：委托受理要引用客户、报价单、销售订单，但实验室内勤/工程师不该为了"能选到报价"
被授予 Sales User（那会连带取得报价、销售订单的写入权）。Frappe 的自定义权限会整体
覆盖原生权限，不能用来"只加一条 read"。因此这里只暴露选择与校验必需的最少字段，
写入、金额明细、其它客户的单据一律不返回。

约定：
  * 仅实验室角色可调用；
  * 返回字段固定，不接受调用方指定字段；
  * 报价/销售订单只返回已提交单据，且必须属于所选客户与公司。
"""
import frappe
from frappe import _

LAB_ROLES = ("Lab Manager", "Lab Engineer", "Lab Reviewer", "System Manager")


def _require_lab():
    if frappe.session.user == "Administrator":
        return
    if not set(LAB_ROLES).intersection(set(frappe.get_roles())):
        frappe.throw(_("没有权限读取商业单据。"), frappe.PermissionError)


def _like(txt):
    return f"%{(txt or '').strip()}%"


def _filters(filters):
    """Link 字段的 filters 从 HTTP 进来是 JSON 字符串，表单内调用是 dict。"""
    if isinstance(filters, str):
        return frappe.parse_json(filters) or {}
    return filters or {}


@frappe.whitelist()
def customer_query(doctype, txt, searchfield, start, page_len, filters):
    """客户选择器：只返回编号与客户名称。"""
    _require_lab()
    filters = _filters(filters)
    company = filters.get("company")
    conditions = {}
    if company:
        conditions["company"] = company
    rows = frappe.get_all(
        "Customer",
        filters=conditions,
        or_filters=[["name", "like", _like(txt)], ["customer_name", "like", _like(txt)]],
        fields=["name", "customer_name"],
        order_by="modified desc",
        limit_start=int(start or 0),
        limit_page_length=int(page_len or 20),
    )
    return [[row.name, row.customer_name or row.name] for row in rows]


@frappe.whitelist()
def quotation_query(doctype, txt, searchfield, start, page_len, filters):
    """报价选择器：已提交、属于该客户/公司，且仍有可履约检测服务行。

    客户来源既可以是原生 ``quotation_to = "Customer"``，也可以是 Frappe CRM
    创建的 ``quotation_to = "CRM Deal"``。后者按企业主档解析出客户后再匹配，
    绝不因为 ``quotation_to`` 是 CRM 商机就放行。
    """
    from reli_lims.quotation_origin import (
        CRM_DEAL,
        deal_names_for_customer,
        fulfillable_exists_sql,
        quotation_customer_map,
    )

    _require_lab()
    filters = _filters(filters)
    conditions = ["q.docstatus = 1", "q.quotation_to in ('Customer', 'CRM Deal')"]
    params = {
        "start": int(start or 0),
        "page_len": int(page_len or 20),
    }
    if filters.get("company"):
        conditions.append("q.company = %(company)s")
        params["company"] = filters["company"]
    if filters.get("customer"):
        customer = filters["customer"]
        params["customer"] = customer
        deals = deal_names_for_customer(customer)
        if deals:
            params["deals"] = tuple(deals)
            conditions.append(
                "((q.quotation_to = 'Customer' and q.party_name = %(customer)s)"
                f" or (q.quotation_to = '{CRM_DEAL}' and q.party_name in %(deals)s))"
            )
        else:
            conditions.append("(q.quotation_to = 'Customer' and q.party_name = %(customer)s)")
    if (txt or "").strip():
        conditions.append("q.name like %(txt)s")
        params["txt"] = _like(txt)
    conditions.append(fulfillable_exists_sql("q"))
    rows = frappe.db.sql(
        f"""select q.name, q.transaction_date, q.quotation_to, q.party_name
        from `tabQuotation` q
        where {" and ".join(conditions)}
        order by q.transaction_date desc, q.name desc
        limit %(start)s, %(page_len)s""",
        params,
        as_dict=True,
    )
    customers = quotation_customer_map(rows)
    return [
        [row.name, f"{row.name}｜{row.transaction_date}｜{customers.get(row.name) or row.party_name}"]
        for row in rows
    ]


@frappe.whitelist()
def sales_order_query(doctype, txt, searchfield, start, page_len, filters):
    """销售订单选择器：只返回已提交、且属于该客户/公司的单据编号与日期。"""
    _require_lab()
    filters = _filters(filters)
    conditions = {"docstatus": 1}
    if filters.get("customer"):
        conditions["customer"] = filters["customer"]
    if filters.get("company"):
        conditions["company"] = filters["company"]
    rows = frappe.get_all(
        "Sales Order",
        filters=conditions,
        or_filters=[["name", "like", _like(txt)]],
        fields=["name", "transaction_date", "customer"],
        order_by="transaction_date desc",
        limit_start=int(start or 0),
        limit_page_length=int(page_len or 20),
    )
    return [[row.name, f"{row.name}｜{row.transaction_date}｜{row.customer}"] for row in rows]


def quotation_facts(name):
    """校验用事实：状态、客户、公司；不读取金额与明细。"""
    return frappe.db.get_value("Quotation", name, ["docstatus", "quotation_to", "party_name", "company"],
                               as_dict=True)


def quotation_detail(name):
    """把报价转成委托时所需的最少字段：行号、数量、能力与技术快照。

    实验室内勤要按报价行生成委托行，绕不开这部分数据；这里只取技术配置与数量，
    不返回价格、折扣、税额等商业信息。
    """
    facts = quotation_facts(name)
    if not facts:
        return None
    items = frappe.get_all(
        "Quotation Item",
        filters={"parent": name},
        fields=["name", "qty", "custom_reli_capability", "custom_reli_configuration"],
        order_by="idx asc",
        limit_page_length=500,
    )
    return {
        "name": name,
        "party_name": facts.party_name,
        "company": facts.company,
        "docstatus": facts.docstatus,
        "quotation_to": facts.quotation_to,
        "items": [dict(row) for row in items],
    }


def quotation_line(name):
    """单条报价行：能力、技术快照与单价（仅服务端校验与快照使用）。"""
    return frappe.db.get_value("Quotation Item", name,
                               ["parent", "qty", "rate", "custom_reli_capability",
                                "custom_reli_configuration"],
                               as_dict=True)


def sales_order_facts(name):
    return frappe.db.get_value("Sales Order", name, ["docstatus", "customer", "company"], as_dict=True)


def quotation_lines(name):
    """销售订单引用了哪些报价单（只读引用字段，不读行明细）。"""
    return frappe.get_all("Sales Order Item", filters={"parent": name},
                          pluck="prevdoc_docname", limit_page_length=500)
