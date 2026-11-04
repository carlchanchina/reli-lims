"""Copy technical selections into the existing Test Request draft and preserve provenance."""
import frappe

from reli_lims.capability_selection import build_configuration


def to_request_item(config):
    snapshot = config["snapshot"]
    return {
        "test_method": snapshot["test_method"], "standard": snapshot["test_standard"],
        "test_condition": "；".join(f"{key}: {value}" for key, value in config["conditions"].items()),
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
def quotation_items(name):
    quote = frappe.get_doc("Quotation", name)
    quote.check_permission("read")
    if not frappe.has_permission("Test Request", "create"):
        frappe.throw("没有创建委托权限。", frappe.PermissionError)
    if quote.docstatus == 2 or quote.quotation_to != "Customer":
        frappe.throw("请选择有效客户报价。")
    if quote.docstatus == 0 and not (frappe.local.site == "carl" and frappe.conf.developer_mode):
        frappe.throw("请先提交报价。")
    items = []
    for row in quote.items:
        configuration = frappe.parse_json(row.custom_reli_configuration)
        if not configuration:
            continue
        items.append(dict(to_request_item(configuration), source_quotation=quote.name,
                          source_quotation_item=row.name, quoted_quantity=row.qty,
                          requested_quantity=row.qty))
    return {"customer": quote.party_name, "company": quote.company,
            "quotation": quote.name if quote.docstatus == 1 else None, "items": items}


def validate(doc, method=None):
    previous = doc.get_doc_before_save()
    old_rows = {row.name: row for row in previous.items} if previous else {}
    for row in doc.items:
        if not row.capability:
            if row.source_quotation or row.source_quotation_item or row.technical_configuration:
                frappe.throw("技术快照和报价来源须关联检测能力。")
            continue
        old = old_rows.get(row.name)
        config = frappe.parse_json(row.technical_configuration)
        if not isinstance(config, dict) or config.get("capability_id") != row.capability:
            frappe.throw("委托能力和技术快照不一致。")
        if row.source_quotation or row.source_quotation_item:
            if not row.source_quotation or not row.source_quotation_item:
                frappe.throw("请同时保留报价单和报价行来源。")
            quote = frappe.get_doc("Quotation", row.source_quotation)
            if not old or (old.source_quotation, old.source_quotation_item) != (row.source_quotation, row.source_quotation_item):
                quote.check_permission("read")
            if quote.docstatus == 2 or quote.party_name != doc.customer or quote.company != doc.company:
                frappe.throw("来源报价与委托客户或公司不一致。")
            original = next((item for item in quote.items if item.name == row.source_quotation_item), None)
            if not original or not original.custom_reli_capability:
                frappe.throw("报价行来源无效。")
            quoted = frappe.parse_json(original.custom_reli_configuration)
            if config != quoted and (not old or config != frappe.parse_json(old.technical_configuration)):
                config = build_configuration(row.capability, config.get("conditions", {}), "request")
            row.quoted_quantity = original.qty
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
        row.technical_configuration = config
        if doc.docstatus == 1:
            capability = frappe.get_doc("Laboratory Capability", row.capability)
            if not capability.published or capability.status != "已发布":
                frappe.throw("检测能力须审核发布后才能正式受理。")


@frappe.whitelist()
def execution_items(request):
    doc = frappe.get_doc("Test Request", request)
    doc.check_permission("read")
    if doc.docstatus != 1:
        frappe.throw("正式受理后才能读取履约条件。")
    return [{"item_code": row.item_code, "configuration": frappe.parse_json(row.technical_configuration),
             "samples": [link.sample_code for link in doc.sample_assignments if link.item_code == row.item_code]}
            for row in doc.items if row.capability]
