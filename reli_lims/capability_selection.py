"""Shared technical selection contract for Desk and later document adapters."""
import json
import math

import frappe

FACETS = {
    "project": "test_project",
    "object": "test_object",
    "standard": "test_standard",
    "laboratory": "laboratory",
    "industry": "industry",
    "status": "status",
    "method": "test_method",
}
FIELDS = ["name", "test_project", "test_object", "laboratory", "test_method", "test_standard", "industry",
          "product_scope", "project_parameter", "capability_scope", "clause",
          "limitation", "scope_effective_date", "condition_schema", "status"]
DEFAULT_CONDITION = [{"key": "original_text", "type": "text", "label": "检测条件原文"}]


def is_dev_preview():
    return frappe.local.site == "carl" and bool(frappe.conf.developer_mode)


def eligibility(mode):
    if mode not in {"quotation", "request", "execution", "catalog"}:
        frappe.throw("未知的能力选择模式。")
    if mode == "catalog" or (mode in {"quotation", "request"} and is_dev_preview()):
        return {"status": ["!=", "已停用"]}
    return {"status": "已发布", "published": 1}


def _search_terms(term):
    term = f"%{str(term)[:100]}%"
    matching = [
        [field, "like", term]
        for field in ("product_scope", "project_parameter", "capability_scope", "limitation", "industry")
    ]
    for doctype, field, fields in (
        ("Test Project", "test_project", ("project_name", "aliases", "category")),
        ("Test Object", "test_object", ("object_name", "category", "aliases")),
        ("Test Standard", "test_standard", ("standard_code", "title", "full_name")),
        ("Laboratory Profile", "laboratory", ("laboratory_name",)),
        ("Test Method", "test_method", ("method_name", "category")),
    ):
        names = frappe.get_list(
            doctype,
            filters={fields[0]: ["like", term]},
            or_filters=[[fieldname, "like", term] for fieldname in fields[1:]],
            pluck="name",
            limit_page_length=100,
        )
        if names:
            matching.append([field, "in", names])
    return matching


def effective_schema(row):
    schema = frappe.parse_json(row.get("condition_schema")) if row.get("condition_schema") else []
    if not schema and row.get("test_project"):
        template = frappe.get_cached_value("Test Project", row.get("test_project"), "condition_template")
        schema = frappe.parse_json(template) if template else []
    return schema or DEFAULT_CONDITION


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
        if key == "status" and mode != "catalog":
            frappe.throw("只能在目录中按审核状态筛选。")
        if value:
            filters[FACETS[key]] = str(value)[:140]
    matching = _search_terms(text) if text else None
    rows = frappe.get_list(
        "Laboratory Capability", filters=filters, or_filters=matching,
        fields=FIELDS + ["source", "source_row"], order_by="name asc",
        start=max(0, int(offset)), page_length=31,
    )
    for row in rows[:30]:
        row.update(labels(row))
        row["condition_schema"] = effective_schema(row)
    return {"rows": rows[:30], "has_more": len(rows) > 30}


def labels(row):
    method, notes = (
        frappe.get_cached_value("Test Method", row.get("test_method"), ["method_name", "notes"])
        if row.get("test_method") else (None, None)
    )
    prefix = "CNAS Workbench "
    method_code = notes[len(prefix):] if notes and notes.startswith(prefix) else ""
    if method and method_code:
        method = method.removesuffix(f" [{method_code}]")
    project = frappe.get_cached_value("Test Project", row.get("test_project"), "project_name") if row.get("test_project") else None
    test_object = frappe.get_cached_value("Test Object", row.get("test_object"), "object_name") if row.get("test_object") else None
    return {
        "method_label": method,
        "method_code": method_code,
        "standard_label": frappe.get_cached_value("Test Standard", row.get("test_standard"), "full_name") if row.get("test_standard") else None,
        "laboratory_label": frappe.get_cached_value("Laboratory Profile", row.get("laboratory"), "laboratory_name") if row.get("laboratory") else None,
        "project_label": project or method or row.get("project_parameter"),
        "test_object_label": test_object or row.get("product_scope"),
    }


@frappe.whitelist()
def line_details(names):
    names = frappe.parse_json(names)
    if not isinstance(names, list) or len(names) > 100:
        frappe.throw("请一次查询不超过 100 个检测项目。")
    rows = frappe.get_list(
        "Laboratory Capability", filters={"name": ["in", names]},
        fields=FIELDS + ["source", "source_row"], page_length=100,
    ) if names else []
    result = {}
    for row in rows:
        row.update(labels(row))
        row["condition_schema"] = effective_schema(row)
        result[row.name] = row
    return result


@frappe.whitelist(methods=["POST"])
def configure(name, conditions, mode):
    return build_configuration(name, frappe.parse_json(conditions), mode)


def build_configuration(name, conditions, mode):
    if mode not in {"catalog", "quotation", "request"}:
        frappe.throw("履约条件须从已确认委托读取。")
    capability = frappe.get_doc("Laboratory Capability", name)
    capability.check_permission("read")
    if mode != "catalog" and not is_dev_preview() and (
        capability.status != "已发布" or not capability.published
    ):
        frappe.throw("能力尚未发布。")
    schema = effective_schema(capability.as_dict())
    if not isinstance(conditions, dict) or set(conditions) - {field["key"] for field in schema}:
        frappe.throw("检测条件不符合能力或项目模板。")
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
        elif field["type"] == "text" and (not isinstance(value, str) or len(value) > 2000):
            frappe.throw("检测条件文本须为 2000 字以内。")
        normalized[key] = value
    snapshot = {field: capability.get(field) for field in FIELDS if field != "condition_schema"}
    snapshot.update(labels(capability.as_dict()))
    snapshot.update(source=capability.source, source_row=capability.source_row, condition_schema=schema)
    return {"schema_version": 1, "capability_id": name, "conditions": normalized,
            "snapshot": json.loads(frappe.as_json(snapshot))}
