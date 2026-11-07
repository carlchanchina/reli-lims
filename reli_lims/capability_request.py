"""Copy technical selections into the existing Test Request draft and preserve provenance."""
import frappe

from reli_lims.capability_selection import build_configuration


def to_request_item(config):
    snapshot = config["snapshot"]
    capability = frappe.db.get_value(
        "Laboratory Capability", config.get("capability_id"),
        ["test_project", "test_object", "test_method", "test_standard"], as_dict=True,
    ) or {}
    test_project = snapshot.get("test_project") or capability.get("test_project")
    test_object = snapshot.get("test_object") or capability.get("test_object")
    test_method = snapshot.get("test_method") or capability.get("test_method")
    test_standard = snapshot.get("test_standard") or capability.get("test_standard")
    labels = {field["key"]: field["label"] for field in snapshot.get("condition_schema", [])}
    return {
        "test_project": test_project, "test_object": test_object,
        "test_method": test_method, "standard": test_standard,
        "test_condition": "；".join(f"{labels[key]}：{value}" if key in labels else f"{key}: {value}" for key, value in config["conditions"].items()),
        "capability": config["capability_id"], "technical_configuration": config,
    }


@frappe.whitelist(methods=["POST"])
def prepare_items(selections):
    if not (frappe.has_permission("Test Request", "create") or frappe.has_permission("Test Request", "write")):
        frappe.throw("没有委托编辑权限。", frappe.PermissionError)
    selections = frappe.parse_json(selections)
    if not isinstance(selections, list) or not 1 <= len(selections) <= 30:
        frappe.throw("请一次选择 1 至 30 条能力。")
    return [to_request_item(build_configuration(
        row["capability_id"], row.get("conditions", {}), "request",
    )) for row in selections]


@frappe.whitelist()
def quotation_items(name, customer=None, company=None):
    """把报价的**可履约检测服务行**转成委托行草稿。

    支持 ERPNexT 原生客户报价与 Frappe CRM 创建的商机报价：CRM 报价的
    ``party_name`` 是商机，必须经企业主档解析出唯一客户后才允许导入。
    普通服务、实物商品、已全部下单或已全部转委托的行一律不返回。
    """
    from reli_lims.commercial_access import quotation_facts
    from reli_lims.quotation_origin import fulfillable_lines, quotation_customer

    if not frappe.has_permission("Test Request", "create"):
        frappe.throw("没有创建委托权限。", frappe.PermissionError)
    # 实验室角色不持有 Quotation 的 DocPerm，改读有界投影：编号、客户、公司、
    # 行号、数量与技术快照；不返回价格与税额。
    quote = quotation_facts(name)
    if not quote:
        frappe.throw("报价单不存在。")
    if quote.docstatus == 2:
        frappe.throw("请选择有效客户报价。")
    if quote.quotation_to not in ("Customer", "CRM Deal"):
        frappe.throw("请选择客户或 CRM 商机来源的报价。")
    if quote.docstatus == 0 and not (frappe.local.site == "carl" and frappe.conf.developer_mode):
        frappe.throw("请先提交报价。")
    resolved_customer = quotation_customer(name)
    if not resolved_customer:
        frappe.throw("无法从该报价解析出唯一客户。CRM 商机报价须先关联企业主档并建立客户身份。")
    if not frappe.db.exists("Customer", resolved_customer):
        frappe.throw("报价关联的客户不存在或已删除，请先核对客户主档。")
    if customer and customer != resolved_customer:
        frappe.throw("报价客户与当前委托客户不一致。")
    if company and quote.company and company != quote.company:
        frappe.throw("报价公司与当前委托公司不一致。")
    items = []
    for row in fulfillable_lines(name):
        configuration = frappe.parse_json(row.get("custom_reli_configuration"))
        if not isinstance(configuration, dict) or not configuration:
            continue
        items.append(dict(
            to_request_item(configuration),
            source_quotation=quote_name(name, quote),
            source_quotation_item=row["name"],
            quoted_quantity=row["qty"],
            requested_quantity=row["remaining_qty"],
        ))
    if not items:
        frappe.throw("该报价没有可履约的检测服务行：已全部下单或已转委托，或只剩普通服务与实物商品。")
    return {"customer": resolved_customer, "company": quote.company,
            "quotation": quote_name(name, quote), "items": items}


def quote_name(name, quote):
    """Draft quotations are only linkable in developer previews."""
    return name if quote.docstatus == 1 else None


def validate(doc, method=None):
    previous = doc.get_doc_before_save()
    old_rows = {row.name: row for row in previous.items} if previous else {}
    for row in doc.items:
        if not row.capability:
            if row.technical_configuration or ((row.source_quotation or row.source_quotation_item) and not row.get("source_sales_order_item")):
                frappe.throw("技术快照和报价来源须关联检测能力。")
            continue
        old = old_rows.get(row.name)
        config = frappe.parse_json(row.technical_configuration)
        if not isinstance(config, dict) or config.get("capability_id") != row.capability:
            frappe.throw("委托能力和技术快照不一致。")
        if row.source_quotation or row.source_quotation_item:
            if not row.source_quotation or not row.source_quotation_item:
                frappe.throw("请同时保留报价单和报价行来源。")
            from reli_lims.commercial_access import quotation_facts, quotation_line
            from reli_lims.quotation_origin import validate_line_capacity
            from reli_lims.sales_order_testing import quotation_customer
            quote = quotation_facts(row.source_quotation)
            if not quote:
                frappe.throw("来源报价不存在。")
            # CRM 来源报价的 party_name 是商机，客户需按企业主档解析。
            expected_customer = quotation_customer(row.source_quotation)
            if (quote.docstatus == 2 or not expected_customer
                    or expected_customer != doc.customer or quote.company != doc.company):
                frappe.throw("来源报价与委托客户或公司不一致。")
            original = quotation_line(row.source_quotation_item)
            if not original or original.parent != row.source_quotation or not original.custom_reli_capability:
                frappe.throw("报价行来源无效。")
            quoted = frappe.parse_json(original.custom_reli_configuration)
            if config != quoted and (not old or config != frappe.parse_json(old.technical_configuration)):
                config = build_configuration(row.capability, config.get("conditions", {}), "request")
            row.quoted_quantity = original.qty
            # 价格快照只在服务端落库，不进入实验室视角的报价投影。
            row.quoted_rate = original.rate
            # 同一报价行不能被多张委托重复履约。
            validate_line_capacity(row, doc)
            row.quotation_difference = int(
                config != quoted or row.test_method != quoted["snapshot"]["test_method"]
                or row.standard != quoted["snapshot"]["test_standard"]
                or (row.test_condition or "") != to_request_item(quoted)["test_condition"]
                or (row.requested_quantity or 0) != original.qty
            )
        else:
            if not old or config != frappe.parse_json(old.technical_configuration):
                config = build_configuration(row.capability, config.get("conditions", {}), "request")
            row.quotation_difference = 0
        if row.test_method != config["snapshot"]["test_method"] or row.standard != config["snapshot"]["test_standard"]:
            frappe.throw("请通过能力选择器更改方法或标准，保留报价来源。")
        capability = frappe.get_doc("Laboratory Capability", row.capability)
        if not row.test_project:
            row.test_project = capability.test_project
        if not row.test_object:
            row.test_object = capability.test_object
        if row.test_project != capability.test_project:
            frappe.throw("委托检测项目与所选实验室能力不一致，请重新选择能力。")
        if row.test_object and capability.test_object and row.test_object != capability.test_object:
            frappe.throw("委托检测对象与所选实验室能力不一致，请重新选择能力。")
        row.technical_configuration = config
        if doc.docstatus == 1:
            if not capability.published or capability.status != "已发布":
                frappe.throw("检测能力须审核发布后才能正式受理。")


@frappe.whitelist()
def execution_items(request):
    doc = frappe.get_doc("Test Request", request)
    doc.check_permission("read")
    if doc.docstatus != 1:
        frappe.throw("正式受理后才能读取履约条件。")
    return [{"item_code": row.item_code, "test_project": row.test_project, "test_object": row.test_object,
             "configuration": frappe.parse_json(row.technical_configuration),
             "samples": [link.sample_code for link in doc.sample_assignments if link.item_code == row.item_code]}
            for row in doc.items if row.capability]
