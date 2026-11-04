"""ERPNext quotation adapter for shared capability configurations."""
import hashlib

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from reli_lims.capability_selection import build_configuration, is_dev_preview


def after_migrate():
    create_custom_fields({
        "Quotation": [{"fieldname": "custom_reli_details", "label": "检测项目明细",
                       "fieldtype": "HTML", "insert_after": "items"}],
        "Quotation Item": [
            {"fieldname": "custom_reli_capability", "label": "检测能力", "fieldtype": "Link",
             "options": "Laboratory Capability", "insert_after": "description", "read_only": 1},
            {"fieldname": "custom_reli_configuration", "label": "检测条件快照", "fieldtype": "JSON",
             "insert_after": "custom_reli_capability", "read_only": 1},
        ],
        "Item": [
            {"fieldname": "custom_reli_service_capability", "label": "能力目录生成来源", "fieldtype": "Link",
             "options": "Laboratory Capability", "insert_after": "custom_reli_test_method", "read_only": 1},
        ],
    }, update=False)


def service_item(capability, item_code=None):
    if not item_code:
        item_code = "RELI-SVC-" + hashlib.sha256(capability.name.encode()).hexdigest()[:16].upper()
        if not frappe.db.exists("Item", item_code):
            if not frappe.has_permission("Item", "create"):
                frappe.throw("请选择已有服务商品，或请有权限的人员创建。", frappe.PermissionError)
            group = frappe.db.exists("Item Group", "Services")
            uom = frappe.db.exists("UOM", "Nos")
            if not group or not uom:
                frappe.throw("请先配置服务商品分组与计量单位。")
            frappe.get_doc({
                "doctype": "Item", "item_code": item_code,
                "item_name": frappe.db.get_value("Test Method", capability.test_method, "method_name"),
                "item_group": group, "stock_uom": uom, "is_stock_item": 0, "is_sales_item": 1,
                "custom_reli_service_capability": capability.name,
                "custom_reli_test_method": capability.test_method,
            }).insert()
    item = frappe.get_doc("Item", item_code)
    item.check_permission("read")
    if item.disabled or item.is_stock_item or not item.is_sales_item:
        frappe.throw("请选择已启用的非库存销售服务。")
    if item.get("custom_reli_service_capability") not in (None, "", capability.name):
        frappe.throw("商品关联的能力不一致。")
    return item


@frappe.whitelist(methods=["POST"])
def prepare_lines(selections):
    if not (frappe.has_permission("Quotation", "create") or frappe.has_permission("Quotation", "write")):
        frappe.throw("没有报价权限。", frappe.PermissionError)
    selections = frappe.parse_json(selections)
    if not isinstance(selections, list) or not 1 <= len(selections) <= 30:
        frappe.throw("请一次选择 1 至 30 条能力。")
    result = []
    for selection in selections:
        config = build_configuration(selection["capability_id"], selection.get("conditions", {}), "quotation")
        capability = frappe.get_doc("Laboratory Capability", config["capability_id"])
        item = service_item(capability, selection.get("item_code"))
        result.append({"item_code": item.name, "item_name": item.item_name, "uom": item.stock_uom,
                       "description": description(config), "qty": 1,
                       "custom_reli_capability": capability.name, "custom_reli_configuration": config})
    return result


def description(config):
    snapshot = config["snapshot"]
    labels = {field["key"]: field["label"] for field in snapshot.get("condition_schema", [])}
    conditions = "，".join(f"{labels.get(key, key)}：{value}" for key, value in config["conditions"].items())
    text = "；".join(filter(None, [snapshot.get("product_scope"), snapshot.get("project_label"),
                                  snapshot.get("standard_label"), conditions, snapshot.get("limitation")]))
    return frappe.utils.escape_html(text)


def validate(doc, method=None):
    previous = doc.get_doc_before_save()
    previous_rows = {row.name: row for row in previous.items} if previous else {}
    for row in doc.items:
        if not row.get("custom_reli_capability"):
            continue
        config = frappe.parse_json(row.custom_reli_configuration)
        old_row = previous_rows.get(row.name)
        old_config = frappe.parse_json(old_row.custom_reli_configuration) if old_row else None
        if not isinstance(config, dict) or config.get("capability_id") != row.custom_reli_capability:
            frappe.throw("报价能力和技术条件快照不一致。")
        if config != old_config:
            config = build_configuration(
                row.custom_reli_capability, config.get("conditions", {}), "quotation",
            )
            row.custom_reli_configuration = config
            row.description = description(config)
        capability = frappe.get_doc("Laboratory Capability", row.custom_reli_capability)
        if not (old_row and old_row.item_code == row.item_code and old_config == config):
            item = service_item(capability, row.item_code)
            if item.get("custom_reli_service_capability") != capability.name and not is_dev_preview():
                frappe.throw("请审核商品与检测能力的关联。")
        if doc.docstatus == 1:
            if not capability.published or capability.status != "已发布":
                frappe.throw("检测能力须审核发布后才可提交正式报价。")
            if not row.rate or row.rate < 0:
                frappe.throw("检测服务缺少有效单价。")
