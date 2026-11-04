"""Shared technical selection contract for Desk and later document adapters."""
import json
import math

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


def is_dev_preview():
    return frappe.local.site == "carl" and bool(frappe.conf.developer_mode)


def eligibility(mode):
    if mode not in {"quotation", "request", "execution", "catalog"}:
        frappe.throw("未知的能力选择模式。")
    if mode == "catalog" or (mode in {"quotation", "request"} and is_dev_preview()):
        return {"status": ["!=", "已停用"]}
    return {"status": "已发布", "published": 1}


@frappe.whitelist()
def search(mode="catalog", text=None, facets=None, offset=0, source=None):
    if mode == "execution":
        frappe.throw("履约条件须从已确认委托读取。")
    filters = eligibility(mode)
    if source:
        frappe.get_doc("Capability Source", source).check_permission("read")
        filters["source"] = source
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
                           fields=FIELDS + ["source", "source_row"], order_by="name asc", start=max(0, int(offset)), page_length=31)
    for row in rows[:30]:
        row.update(labels(row))
    return {"rows": rows[:30], "has_more": len(rows) > 30}


def labels(row):
    method, notes = frappe.get_cached_value("Test Method", row.get("test_method"),
                                            ["method_name", "notes"]) or (None, None)
    prefix = "CNAS Workbench "
    method_code = notes[len(prefix):] if notes and notes.startswith(prefix) else ""
    if method and method_code:
        method = method.removesuffix(f" [{method_code}]")
    return {
        "method_label": method,
        "method_code": method_code,
        "standard_label": frappe.get_cached_value("Test Standard", row.get("test_standard"), "full_name"),
        "laboratory_label": frappe.get_cached_value("Laboratory Profile", row.get("laboratory"), "laboratory_name"),
        "project_label": method or row.get("project_parameter"),
    }


@frappe.whitelist()
def line_details(names):
    names = frappe.parse_json(names)
    if not isinstance(names, list) or len(names) > 100:
        frappe.throw("请一次查询不超过 100 个检测项目。")
    return {row.name: dict(row, **labels(row)) for row in frappe.get_list(
        "Laboratory Capability", filters={"name": ["in", names]}, fields=FIELDS + ["source", "source_row"],
        page_length=100,
    )} if names else {}


@frappe.whitelist(methods=["POST"])
def configure(name, conditions, mode):
    return build_configuration(name, frappe.parse_json(conditions), mode)


def build_configuration(name, conditions, mode):
    if mode not in {"catalog", "quotation", "request"}:
        frappe.throw("履约条件须从已确认委托读取。")
    capability = frappe.get_doc("Laboratory Capability", name)
    capability.check_permission("read")
    if mode != "catalog" and not is_dev_preview() and (capability.status != "已发布" or not capability.published):
        frappe.throw("能力尚未发布。")
    schema = frappe.parse_json(capability.condition_schema) or []
    if not schema:
        schema = [{"key": "original_text", "type": "text", "label": "检测条件原文"}]
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
            if not math.isfinite(value):
                frappe.throw("请输入有限数值。")
        elif field["type"] == "select" and value not in field.get("options", []):
            frappe.throw(f"无效的{field['label']}。")
        if field["type"] == "text" and (not isinstance(value, str) or len(value) > 2000):
            frappe.throw("检测条件文本须为 2000 字以内。")
        normalized[key] = value
    snapshot = {field: capability.get(field) for field in FIELDS if field != "condition_schema"}
    snapshot.update(labels(capability))
    snapshot.update(source=capability.source, source_row=capability.source_row, condition_schema=schema)
    return {"schema_version": 1, "capability_id": name, "conditions": normalized,
            "snapshot": json.loads(frappe.as_json(snapshot))}
