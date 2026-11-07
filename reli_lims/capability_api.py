import json

import frappe
from frappe import _
from frappe.utils import now_datetime


def _require_role(*roles):
    if not set(roles).intersection(set(frappe.get_roles())):
        frappe.throw(_("没有权限执行此操作。"), frappe.PermissionError)


def _load_items(source):
    payload = source.structured_json
    if isinstance(payload, str):
        payload = json.loads(payload)
    if isinstance(payload, dict):
        items = payload.get("items", [])
    else:
        items = payload
    if not isinstance(items, list):
        frappe.throw(_("审核后结构化结果必须包含能力数组。"))
    return items


@frappe.whitelist(methods=["POST"])
def import_capability_source(source_name):
    _require_role("Lab Manager", "System Manager")
    source = frappe.get_doc("Capability Source", source_name)
    if source.documents_review_status != "Approved":
        frappe.throw(_("只有 Documents 已审核通过的来源可以导入。"))

    source.check_permission("read")
    source.check_permission("write")
    source.validate()
    frappe.db.sql("SELECT name FROM `tabCapability Source` WHERE name=%s FOR UPDATE", source.name)
    items = _load_items(source)
    created = []
    skipped = []

    for index, item in enumerate(items, start=1):
        method = item.get("test_method") or item.get("test_method_name")
        standard = item.get("test_standard") or item.get("standard_name") or item.get("standard_code")
        if not method or not standard:
            skipped.append({"row": index, "reason": "缺少检测项目或检测标准"})
            continue

        method_name = frappe.db.get_value("Test Method", {"method_name": method}, "name") or (
            method if frappe.db.exists("Test Method", method) else None
        )
        standard_name = standard if frappe.db.exists("Test Standard", standard) else None
        if not standard_name:
            standard_filters = {"standard_code": standard}
            if item.get("standard_version") or item.get("version"):
                standard_filters["version"] = item.get("standard_version") or item.get("version")
            matches = frappe.get_all("Test Standard", filters=standard_filters, pluck="name", limit_page_length=2)
            if len(matches) > 1:
                skipped.append({"row": index, "reason": "STANDARD_AMBIGUOUS"})
                continue
            standard_name = matches[0] if matches else None
        if not method_name or not standard_name:
            skipped.append({"row": index, "reason": "无法匹配现有检测项目或检测标准"})
            continue
        test_project = item.get("test_project") or frappe.db.get_value("Test Method", method_name, "test_project")
        if test_project and not frappe.db.exists("Test Project", test_project):
            test_project = frappe.db.get_value("Test Project", {"project_name": test_project}, "name")
        if not test_project:
            skipped.append({"row": index, "reason": "无法匹配统一检测项目"})
            continue
        test_object = item.get("test_object") or frappe.db.get_value(
            "Test Object", {"object_name": item.get("product_scope")}, "name"
        )
        if test_object and not frappe.db.exists("Test Object", test_object):
            test_object = frappe.db.get_value("Test Object", {"object_name": test_object}, "name")

        existing = frappe.db.exists(
            "Laboratory Capability",
            {
                "laboratory": source.laboratory,
                "source": source.name,
                "source_row": str(item.get("source_row") or index),
            },
        )
        if existing:
            created.append(existing)
            continue

        doc = frappe.get_doc(
            {
                "doctype": "Laboratory Capability",
                "laboratory": source.laboratory,
                "test_project": test_project,
                "test_object": test_object,
                "test_method": method_name,
                "test_standard": standard_name,
                "product_scope": item.get("product_scope"),
                "capability_scope": item.get("capability_scope") or item.get("scope") or _("待补充"),
                "limitation": item.get("limitation"),
                "accreditation_type": item.get("accreditation_type") or source.source_type,
                "certificate_no": item.get("certificate_no") or source.certificate_no,
                "source": source.name,
                "source_row": str(item.get("source_row") or index),
                "condition_schema": item.get("condition_schema"),
                "status": "待确认",
                "remarks": item.get("remarks"),
            }
        )
        doc.insert()
        created.append(doc.name)

    source.import_status = "部分导入" if skipped and created else ("失败" if skipped and not created else "已导入")
    source.imported_at = now_datetime() if created else None
    source.save()
    return {"created": created, "skipped": skipped, "status": source.import_status}


@frappe.whitelist(methods=["POST"])
def confirm_capability(name):
    """单条审核入口；内部走批量工作流，保证每条都有审核记录。"""
    from reli_lims.capability_review import review

    _require_role("Lab Manager", "Lab Reviewer", "System Manager")
    result = review([name], "approve", note=_("单条审核通过"))
    return result["done"][0] if result["done"] else name


@frappe.whitelist(methods=["POST"])
def publish_capability(name):
    """单条发布入口；演示能力在单条操作里显式允许（界面可见、审计可查）。"""
    from reli_lims.capability_review import publish

    _require_role("Lab Manager", "System Manager")
    doc = frappe.get_doc("Laboratory Capability", name)
    result = publish([name], note=_("单条发布"), include_demo=bool(doc.get("demo_only")))
    return get_public_capability(result["published"][0])


@frappe.whitelist(methods=["POST"])
def unpublish_capability(name):
    from reli_lims.capability_review import _log

    _require_role("Lab Manager", "System Manager")
    doc = frappe.get_doc("Laboratory Capability", name)
    if doc.status != "已发布":
        frappe.throw(_("当前能力未发布。"))
    doc.check_permission("write")
    doc.status = "已确认"
    _log(doc, "退回补充", "已发布", _("取消发布"))
    doc.save()
    return doc.name


@frappe.whitelist(allow_guest=True)
def get_public_capability(name):
    doc = frappe.get_doc("Laboratory Capability", name)
    if doc.status != "已发布" or not doc.published:
        frappe.throw(_("该能力尚未发布。"), frappe.PermissionError)
    return {
        "id": doc.name,
        "laboratory": doc.laboratory,
        "test_project": doc.test_project,
        "test_object": doc.test_object,
        "test_method": doc.test_method,
        "test_standard": doc.test_standard,
        "product_scope": doc.product_scope,
        "capability_scope": doc.capability_scope,
        "limitation": doc.limitation,
        "accreditation_type": doc.accreditation_type,
        "certificate_no": doc.certificate_no,
        "demo_only": bool(doc.get("demo_only")),
        "scope_effective_date": str(doc.get("scope_effective_date") or ""),
    }


@frappe.whitelist(allow_guest=True)
def list_public_capabilities(laboratory=None):
    """Bounded, explicit public projection; never expose source JSON or files."""
    filters = {"status": "已发布", "published": 1}
    if laboratory:
        filters["laboratory"] = laboratory
    names = frappe.get_all("Laboratory Capability", filters=filters,
                           pluck="name", order_by="name", limit_page_length=100)
    return [get_public_capability(name) for name in names]


@frappe.whitelist(methods=["GET"])
def list_bridge_eligibility(cursor=None, limit=100):
    from reli_lims.capability_eligibility import list_events
    return list_events(cursor, limit)


@frappe.whitelist(methods=["POST"])
def get_bridge_eligibility(capability_ids):
    from reli_lims.capability_eligibility import get_current
    return get_current(capability_ids)
