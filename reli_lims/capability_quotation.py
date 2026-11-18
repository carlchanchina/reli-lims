"""ERPNext quotation adapter for shared capability configurations."""
import hashlib

import frappe

from reli_lims.capability_selection import build_configuration, is_dev_preview, normalize_conditions


def after_migrate():
    from reli_lims.capability_catalog import ensure_custom_fields
    ensure_custom_fields()


def service_item(capability, item_code=None):
    project = capability.test_project or frappe.db.get_value(
        "Test Method", capability.test_method, "test_project"
    )
    if not project:
        frappe.throw("检测能力尚未关联统一检测项目，请先完成归类。")
    project_label = frappe.db.get_value("Test Project", project, "project_name")
    if not item_code:
        existing = frappe.get_all(
            "Item", filters={"custom_reli_test_project": project, "is_stock_item": 0,
                             "is_sales_item": 1, "disabled": 0},
            pluck="name", order_by="name asc", limit_page_length=1,
        )
        item_code = existing[0] if existing else None
    if not item_code:
        item_code = "RELI-SVC-" + hashlib.sha256(project.encode()).hexdigest()[:16].upper()
        if not frappe.db.exists("Item", item_code):
            if not frappe.has_permission("Item", "create"):
                frappe.throw("请选择已有服务商品，或请有权限的人员创建。", frappe.PermissionError)
            group = frappe.db.exists("Item Group", "Services")
            uom = frappe.db.exists("UOM", "Nos")
            if not group or not uom:
                frappe.throw("请先配置服务商品分组与计量单位。")
            frappe.get_doc({
                "doctype": "Item", "item_code": item_code,
                "item_name": project_label,
                "item_group": group, "stock_uom": uom, "is_stock_item": 0, "is_sales_item": 1,
                "custom_reli_test_project": project, "custom_reli_business_type": "检测服务",
            }).insert()
    item = frappe.get_doc("Item", item_code)
    item.check_permission("read")
    if item.disabled or item.is_stock_item or not item.is_sales_item:
        frappe.throw("请选择已启用的非库存销售服务。")
    if item.get("custom_reli_service_capability") not in (None, "", capability.name):
        if item.get("custom_reli_test_project") != project:
            frappe.throw("商品关联的检测能力或检测项目不一致。")
    if item.get("custom_reli_test_project") not in (None, "", project):
        frappe.throw("商品关联的统一检测项目不一致。")
    if item.get("custom_reli_business_type") in ("普通服务", "实物商品"):
        frappe.throw("所选商品已归类为普通服务或实物商品，请选择检测服务商品。")
    if not item.get("custom_reli_test_project") or not item.get("custom_reli_business_type"):
        item.check_permission("write")
        item.custom_reli_test_project = project
        item.custom_reli_business_type = "检测服务"
        item.save()
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
        config = build_configuration(selection["capability_id"], selection.get("conditions", {}), "quotation", freeze=True)
        capability = frappe.get_doc("Laboratory Capability", config["capability_id"])
        item = service_item(capability, selection.get("item_code"))
        project_label = frappe.db.get_value("Test Project", capability.test_project, "project_name")
        result.append({"item_code": item.name, "item_name": project_label, "uom": item.stock_uom,
                       "description": description(config), "qty": 1,
                       "custom_reli_capability": capability.name,
                       "custom_reli_test_project": capability.test_project,
                       "custom_reli_test_object": capability.test_object,
                       "custom_reli_test_standard": capability.test_standard,
                       "custom_reli_configuration": config})
    return result


def description(config):
    snapshot = config["snapshot"]
    labels = {field["key"]: field["label"] for field in snapshot.get("condition_schema", [])}
    conditions = "，".join(f"{labels.get(key, key)}：{value}" for key, value in config["conditions"].items())
    text = "；".join(filter(None, [snapshot.get("product_scope"), snapshot.get("project_label"),
                                  snapshot.get("standard_label"), conditions, snapshot.get("limitation")]))
    return frappe.utils.escape_html(text)


FROZEN_COLUMNS = (
    ("custom_reli_test_project", "test_project"),
    ("custom_reli_test_object", "test_object"),
    ("custom_reli_test_standard", "test_standard"),
)


def _snapshot(config):
    return (config.get("snapshot") or {}) if isinstance(config, dict) else {}


def apply_snapshot(row, config):
    """Make the stored snapshot the only source of the row's identity columns.

    The columns are rewritten from the frozen snapshot, never from the live
    Laboratory Capability, so re-saving an old quotation cannot re-classify it.
    """
    snapshot = _snapshot(config)
    for row_field, snapshot_field in FROZEN_COLUMNS:
        if snapshot.get(snapshot_field):
            row.set(row_field, snapshot.get(snapshot_field))
    label = snapshot.get("project_label")
    if label:
        row.item_name = label


def _repair_legacy(row, config):
    """One-off repair for rows whose config was created outside the adapter.

    Legacy rows have no snapshot at all; building one once is the only path that
    still reads the live capability, and it is marked so it can be audited.
    """
    capability = frappe.get_doc("Laboratory Capability", row.custom_reli_capability)
    rebuilt = build_configuration(
        capability.name, config.get("conditions") or {}, "quotation", freeze=True,
    )
    rebuilt["snapshot_repair"] = 1
    row.custom_reli_configuration = rebuilt
    return rebuilt


def _sync_conditions(row, config, old_config):
    """Apply operator condition edits against the frozen schema, not the live one."""
    if old_config is not None and old_config.get("conditions") == config.get("conditions"):
        return config
    schema = _snapshot(config).get("condition_schema") or []
    if not schema:
        return config
    normalized = normalize_conditions(schema, config.get("conditions") or {})
    config = dict(config, conditions=normalized)
    row.custom_reli_configuration = config
    row.description = description(config)
    return config


def _validate_item(row, config):
    item = frappe.get_doc("Item", row.item_code)
    item.check_permission("read")
    if item.disabled or item.is_stock_item or not item.is_sales_item:
        frappe.throw("请选择已启用的非库存销售服务。")
    if item.get("custom_reli_business_type") in ("普通服务", "实物商品"):
        frappe.throw("所选商品已归类为普通服务或实物商品，请选择检测服务商品。")
    expected = _snapshot(config).get("test_project") or row.get("custom_reli_test_project")
    if item.get("custom_reli_test_project") and expected and item.get("custom_reli_test_project") != expected:
        frappe.throw("商品关联的统一检测项目与报价快照不一致。")


def _validate_submission(row, previous_status):
    capability = frappe.db.get_value(
        "Laboratory Capability", row.custom_reli_capability, ["published", "status"], as_dict=True,
    )
    if previous_status == 1:
        # Already-submitted documents keep their commercial fact even if the master changed.
        return
    if not capability:
        frappe.throw("检测能力已不存在，无法提交报价。")
    if not capability.published or capability.status != "已发布":
        frappe.throw("检测能力须审核发布后才可提交正式报价。")
    if not row.rate or row.rate < 0:
        frappe.throw("检测服务缺少有效单价。")


def validate(doc, method=None):
    previous = doc.get_doc_before_save()
    previous_rows = {row.name: row for row in previous.items} if previous else {}
    previous_status = previous.docstatus if previous else 0
    for row in doc.items:
        if not row.get("custom_reli_capability"):
            continue
        config = frappe.parse_json(row.custom_reli_configuration)
        old_row = previous_rows.get(row.name)
        old_config = frappe.parse_json(old_row.custom_reli_configuration) if old_row else None
        if not isinstance(config, dict) or config.get("capability_id") != row.custom_reli_capability:
            frappe.throw("报价能力和技术条件快照不一致。")
        if not config.get("snapshot"):
            config = _repair_legacy(row, config)
        config = _sync_conditions(row, config, old_config)
        apply_snapshot(row, config)
        if row.item_code and (old_row is None or old_row.item_code != row.item_code):
            _validate_item(row, config)
        if doc.docstatus == 1:
            _validate_submission(row, previous_status)
