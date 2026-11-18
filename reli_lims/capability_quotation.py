"""ERPNext quotation adapter for shared capability configurations."""
import hashlib

import frappe

from reli_lims.capability_selection import (
    DEFAULT_CONDITION, assert_snapshot_immutable, build_configuration, is_dev_preview,
    normalize_conditions,
)


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


PENDING_CONFIRMATION = "pending_manual_confirmation"


def _restore_from_upstream(row, config):
    """Adopt the snapshot of the quotation line an order row was mapped from.

    This is the only tolerated automatic reconstruction: it copies a snapshot
    that was already frozen elsewhere, never the current capability master.
    """
    source_name = row.get("quotation_item")
    if not source_name:
        return None
    source = frappe.db.get_value("Quotation Item", source_name, "custom_reli_configuration")
    source_config = frappe.parse_json(source) if source else None
    if not isinstance(source_config, dict) or not _snapshot(source_config):
        return None
    restored = dict(source_config)
    restored["snapshot_restored_from"] = source_name
    return restored


def _mark_pending(row, config):
    """Legacy rows get an explicit pending state instead of invented history.

    The live capability may already have been re-classified, so rebuilding a
    snapshot from it would fabricate a technical fact the customer never bought.
    """
    config = dict(config)
    config["snapshot_state"] = PENDING_CONFIRMATION
    config.setdefault(
        "snapshot_note",
        "该行早于快照机制创建；系统不会用当前实验室能力重建历史快照，需人工确认后提交。",
    )
    row.custom_reli_configuration = config
    return config


def _sync_conditions(row, config, old_config):
    """Apply operator condition edits against the frozen schema, not the live one."""
    if old_config is not None and old_config.get("conditions") == config.get("conditions"):
        return config
    # A frozen empty schema only permits the historical free-text condition;
    # it is not a wildcard for arbitrary keys.
    schema = _snapshot(config).get("condition_schema") or DEFAULT_CONDITION
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


def _validate_submission(row, previous_status, config):
    if previous_status == 1:
        # Already-submitted documents keep their commercial fact even if the master changed.
        return
    if (config or {}).get("snapshot_state") == PENDING_CONFIRMATION:
        frappe.throw("该报价行缺少历史技术快照，请先完成人工确认再提交正式报价。")
    capability = frappe.db.get_value(
        "Laboratory Capability", row.custom_reli_capability, ["published", "status"], as_dict=True,
    )
    if not capability:
        frappe.throw("检测能力已不存在，无法提交报价。")
    if not capability.published or capability.status != "已发布":
        frappe.throw("检测能力须审核发布后才可提交正式报价。")
    if not row.rate or row.rate < 0:
        frappe.throw("检测服务缺少有效单价。")


@frappe.whitelist(methods=["POST"])
def confirm_legacy_snapshot(quotation, row, test_project, test_object, test_standard, note=None):
    """Explicit, audited replacement for the old silent repair.

    A human states which project/object/standard the historical line actually
    referred to; the system records who confirmed it, when, and which live
    capability version was used to fill the descriptive fields.
    """
    doc = frappe.get_doc("Quotation", quotation)
    doc.check_permission("write")
    if doc.docstatus != 0:
        frappe.throw("仅草稿报价可以人工确认历史快照。")
    target = next((item for item in doc.items if item.name == row), None)
    if not target or not target.get("custom_reli_capability"):
        frappe.throw("报价行不存在，或不是检测服务行。")
    config = frappe.parse_json(target.custom_reli_configuration) or {}
    if _snapshot(config):
        frappe.throw("该报价行已有技术快照，无需人工确认。")
    for doctype, name in (
        ("Test Project", test_project), ("Test Object", test_object), ("Test Standard", test_standard),
    ):
        if not frappe.db.exists(doctype, name):
            frappe.throw(f"{doctype} 不存在：{name}")
    capability = frappe.get_doc("Laboratory Capability", target.custom_reli_capability)
    rebuilt = build_configuration(capability.name, config.get("conditions") or {}, "quotation", freeze=True)
    rebuilt["snapshot"].update({
        "test_project": test_project,
        "test_object": test_object,
        "test_standard": test_standard,
        "project_label": frappe.db.get_value("Test Project", test_project, "project_name"),
        "test_object_label": frappe.db.get_value("Test Object", test_object, "object_name"),
        "standard_label": frappe.db.get_value("Test Standard", test_standard, "full_name"),
    })
    rebuilt.pop("snapshot_state", None)
    rebuilt.pop("snapshot_note", None)
    rebuilt["snapshot_source"] = "manual_confirmation"
    rebuilt["confirmed_by"] = frappe.session.user
    rebuilt["confirmed_at"] = frappe.utils.now()
    rebuilt["confirmed_note"] = note
    rebuilt["live_capability_modified"] = str(capability.modified or "")
    target.flags.allow_snapshot_change = True
    target.custom_reli_configuration = rebuilt
    target.custom_reli_test_project = test_project
    target.custom_reli_test_object = test_object
    target.custom_reli_test_standard = test_standard
    doc.save()
    return {"row": target.name, "snapshot_at": rebuilt["snapshot_at"],
            "confirmed_by": rebuilt["confirmed_by"]}


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
        if old_config:
            # Conditions may change; the sold technical fact may not.
            assert_snapshot_immutable(old_config, config, row)
        frozen = bool(_snapshot(config))
        if not frozen:
            restored = _restore_from_upstream(row, config)
            if restored:
                config = restored
                row.custom_reli_configuration = config
                frozen = True
            else:
                config = _mark_pending(row, config)
        if frozen:
            config = _sync_conditions(row, config, old_config)
            apply_snapshot(row, config)
        if row.item_code and (old_row is None or old_row.item_code != row.item_code):
            _validate_item(row, config)
        if doc.docstatus == 1:
            _validate_submission(row, previous_status, config)
