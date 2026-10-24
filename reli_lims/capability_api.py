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
        standard_name = frappe.db.get_value("Test Standard", {"standard_code": standard}, "name") or (
            standard if frappe.db.exists("Test Standard", standard) else None
        )
        if not method_name or not standard_name:
            skipped.append({"row": index, "reason": "无法匹配现有检测项目或检测标准"})
            continue

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
                "test_method": method_name,
                "test_standard": standard_name,
                "product_scope": item.get("product_scope"),
                "capability_scope": item.get("capability_scope") or item.get("scope") or _("待补充"),
                "limitation": item.get("limitation"),
                "accreditation_type": item.get("accreditation_type") or source.source_type,
                "certificate_no": item.get("certificate_no") or source.certificate_no,
                "source": source.name,
                "source_row": str(item.get("source_row") or index),
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
    _require_role("Lab Manager", "Lab Reviewer", "System Manager")
    doc = frappe.get_doc("Laboratory Capability", name)
    if doc.status not in {"待确认", "已确认"}:
        frappe.throw(_("当前状态不能确认。"))
    doc.status = "已确认"
    doc.save()
    return doc.name


@frappe.whitelist(methods=["POST"])
def publish_capability(name):
    _require_role("Lab Manager", "System Manager")
    doc = frappe.get_doc("Laboratory Capability", name)
    if doc.status != "已确认":
        frappe.throw(_("只有已确认的能力才能发布。"))
    doc.status = "已发布"
    doc.save()
    return get_public_capability(doc.name)


@frappe.whitelist(methods=["POST"])
def unpublish_capability(name):
    _require_role("Lab Manager", "System Manager")
    doc = frappe.get_doc("Laboratory Capability", name)
    if doc.status != "已发布":
        frappe.throw(_("当前能力未发布。"))
    doc.status = "已确认"
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
        "test_method": doc.test_method,
        "test_standard": doc.test_standard,
        "product_scope": doc.product_scope,
        "capability_scope": doc.capability_scope,
        "limitation": doc.limitation,
        "accreditation_type": doc.accreditation_type,
        "certificate_no": doc.certificate_no,
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
