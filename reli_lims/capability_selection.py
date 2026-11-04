"""Shared technical selection contract for Desk and later document adapters."""
import json

import frappe

FACETS = {
    "industry": "industry",
    "product": "product_scope",
    "project": "project_parameter",
    "standard": "test_standard",
    "method": "test_method",
}
FIELDS = ["name", "laboratory", "test_method", "test_standard", "industry",
          "product_scope", "project_parameter", "capability_scope", "clause",
          "limitation", "scope_effective_date", "condition_schema", "status"]


def eligibility(mode):
    if mode not in {"quotation", "request", "execution", "catalog"}:
        frappe.throw("未知的能力选择模式。")
    if mode == "catalog":
        return {"status": ["!=", "已停用"]}
    return {"status": "已发布", "published": 1}


@frappe.whitelist()
def search(mode="catalog", text=None, facets=None, offset=0):
    if mode == "execution":
        frappe.throw("履约条件须从已确认委托读取。")
    filters = eligibility(mode)
    values = frappe.parse_json(facets) if isinstance(facets, str) else facets
    for key, value in (values or {}).items():
        if key not in FACETS:
            frappe.throw("未知的能力筛选条件。")
        if value:
            filters[FACETS[key]] = str(value)[:140]
    matching = None
    if text:
        term = f"%{str(text)[:100]}%"
        matching = [[field, "like", term] for field in (
            "industry", "product_scope", "project_parameter", "capability_scope", "limitation")]
        for doctype, field, title in (
            ("Test Method", "test_method", "method_name"),
            ("Test Standard", "test_standard", "standard_code"),
        ):
            names = frappe.get_list(doctype, filters={title: ["like", term]}, pluck="name", limit_page_length=100)
            if names:
                matching.append([field, "in", names])
    rows = frappe.get_list("Laboratory Capability", filters=filters, or_filters=matching,
                           fields=FIELDS, order_by="name asc", start=max(0, int(offset)), page_length=31)
    for row in rows[:30]:
        row["method_label"] = frappe.get_cached_value("Test Method", row.test_method, "method_name")
        row["standard_label"] = frappe.get_cached_value("Test Standard", row.test_standard, "full_name")
        row["laboratory_label"] = frappe.get_cached_value("Laboratory Profile", row.laboratory, "laboratory_name")
    return {"rows": rows[:30], "has_more": len(rows) > 30}


def build_configuration(name, conditions, mode):
    if mode not in {"catalog", "quotation", "request"}:
        frappe.throw("履约条件须从已确认委托读取。")
    capability = frappe.get_doc("Laboratory Capability", name)
    capability.check_permission("read")
    if mode != "catalog" and (capability.status != "已发布" or not capability.published):
        frappe.throw("能力尚未发布。")
    schema = frappe.parse_json(capability.condition_schema) or []
    if not isinstance(conditions, dict) or set(conditions) - {field["key"] for field in schema}:
        frappe.throw("检测条件不符合能力配置。")
    normalized = {}
    for field in schema:
        key = field["key"]
        value = conditions.get(key)
        if value is None or value == "":
            if field.get("required"):
                frappe.throw(f"请输入{field['label']}。")
            continue
        if field["type"] == "number":
            value = float(value)
            if not __import__("math").isfinite(value):
                frappe.throw("请输入有限数值。")
        elif field["type"] == "select" and value not in field.get("options", []):
            frappe.throw(f"无效的{field['label']}。")
        normalized[key] = value
    snapshot = {field: capability.get(field) for field in FIELDS if field != "condition_schema"}
    snapshot.update(source=capability.source, source_row=capability.source_row)
    return {"schema_version": 1, "capability_id": name, "conditions": normalized,
            "snapshot": json.loads(frappe.as_json(snapshot))}
