"""Laboratory qualification on ERPNext Asset, with execution-time evidence."""
import frappe
from frappe.utils import getdate, today, now_datetime


def validate_asset(doc, method=None):
    if not doc.get("custom_reli_laboratory"):
        if doc.get("custom_reli_scopes"):
            frappe.throw("请先选择设备所属实验室。")
        return
    if doc.get("asset_owner") not in (None, "", "Company"):
        frappe.throw("实验室自用设备必须为公司资产。")
    seen = set()
    for row in doc.custom_reli_scopes:
        pair = (row.test_project, row.capability)
        if pair in seen:
            frappe.throw("设备检测项目与能力关联重复。")
        seen.add(pair)
        if row.capability:
            cap = frappe.db.get_value("Laboratory Capability", row.capability,
                ["laboratory", "test_project"], as_dict=True)
            if not cap or cap.laboratory != doc.custom_reli_laboratory or cap.test_project != row.test_project:
                frappe.throw("设备适用能力必须属于同一实验室和检测项目。")


def snapshot(asset):
    return dict(asset=asset.name, asset_name=asset.asset_name,
        model=asset.custom_reli_model, serial_no=asset.custom_reli_serial_no,
        laboratory=asset.custom_reli_laboratory, location=asset.location,
        state=asset.custom_reli_equipment_status, asset_status=asset.status,
        calibration_until=str(asset.custom_reli_calibration_until or ""),
        parameters=asset.custom_reli_parameters, captured_at=str(now_datetime()))


def validate_execution(doc, method=None):
    previous = doc.get_doc_before_save()
    old_rows = {r.name: r for r in previous.items} if previous else {}
    for row in doc.items:
        old = old_rows.get(row.name)
        stored = frappe.parse_json(old.get("equipment_snapshot")) if old else None
        if frappe.parse_json(row.get("equipment_snapshot")) != stored:
            frappe.throw("执行设备快照由系统记录，不能直接修改。")
        if old and old.status in ("Running", "Completed", "Reviewed"):
            continue
        if not row.asset:
            row.equipment_snapshot = None
            continue
        asset = frappe.get_doc("Asset", row.asset)
        asset.check_permission("read")
        if not asset.get("custom_reli_laboratory"):
            # Existing unmanaged Asset references remain compatible.
            if not stored:
                row.equipment_snapshot = snapshot(asset)
            continue
        scopes = asset.custom_reli_scopes or []
        if not any(s.test_project == row.test_project and (not s.capability or s.capability == row.capability) for s in scopes):
            frappe.throw("所选设备不适用于当前检测项目或实验室能力。")
        if row.capability and frappe.db.get_value("Laboratory Capability", row.capability, "laboratory") != asset.custom_reli_laboratory:
            frappe.throw("执行设备与所选能力必须属于同一实验室。")
        if row.status in ("Ready", "Running"):
            if asset.docstatus == 2 or asset.custom_reli_equipment_status != "启用" or asset.status in ("Sold", "Scrapped", "In Maintenance", "Out of Order"):
                frappe.throw("设备已停用、维护或不可用，不能开始试验。")
            if not asset.custom_reli_calibration_until or getdate(asset.custom_reli_calibration_until) < getdate(today()):
                frappe.throw("设备校准／检定已到期或未填写，不能开始试验。")
        if not stored or not old or old.asset != row.asset or row.status == "Running":
            row.equipment_snapshot = snapshot(asset)


@frappe.whitelist()
def available(test_project, capability=None, text=None, start=0):
    frappe.get_doc("Test Project", test_project).check_permission("read")
    names = frappe.get_all("Laboratory Equipment Scope", filters={"test_project": test_project, "parenttype": "Asset"},
        fields=["parent", "capability"])
    selected = [r.parent for r in names if not capability or not r.capability or r.capability == capability]
    if not selected:
        return {"rows": [], "has_more": False}
    filters = {"name": ["in", selected], "docstatus": ["!=", 2],
        "custom_reli_equipment_status": "启用", "custom_reli_calibration_until": [">=", today()],
        "status": ["not in", ["Sold", "Scrapped", "In Maintenance", "Out of Order"]]}
    or_filters = [[key, "like", f"%{str(text)[:100]}%"] for key in ("asset_name", "custom_reli_model", "custom_reli_serial_no")] if text else None
    rows = frappe.get_list("Asset", filters=filters, or_filters=or_filters,
        fields=["name", "asset_name", "custom_reli_model", "custom_reli_laboratory", "location", "custom_reli_calibration_until"],
        order_by="asset_name asc, name asc", start=max(0, int(start)), page_length=21)
    return {"rows": rows[:20], "has_more": len(rows) > 20}


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def asset_query(doctype, txt, searchfield, start, page_len, filters):
    filters = frappe.parse_json(filters) if isinstance(filters, str) else filters
    result = available(filters["test_project"], filters.get("capability"), txt, start)
    return [[r.name, r.asset_name, r.custom_reli_model, r.custom_reli_laboratory] for r in result["rows"]]
