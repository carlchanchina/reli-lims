"""P1.6.1: remove retired Detection Project links after verified mapping."""
import frappe
from frappe import _

from reli_lims.reli_lims.doctype.test_project.test_project import project_key


def _has_table(table):
    return bool(frappe.db.sql("show tables like %s", (table,)))


def _legacy_project_targets():
    if not _has_table("tabDetection Project"):
        return {}
    projects = frappe.get_all("Test Project", fields=["name", "project_name"])
    by_key = {project_key(row.project_name): row.name for row in projects}
    return {
        row.name: by_key.get(project_key(row.project_name))
        for row in frappe.db.sql(
            "select name, project_name from `tabDetection Project`", as_dict=True
        )
    }


def _verify_legacy_mapping():
    targets = _legacy_project_targets()
    unresolved = []

    if frappe.db.has_column("Item", "custom_reli_detection_project"):
        for row in frappe.get_all(
            "Item",
            filters={"custom_reli_detection_project": ["is", "set"]},
            fields=["name", "custom_reli_detection_project", "custom_reli_test_project"],
            limit_page_length=0,
        ):
            expected = targets.get(row.custom_reli_detection_project)
            if not expected or row.custom_reli_test_project != expected:
                unresolved.append(
                    "Item {0}: {1} -> {2}".format(
                        row.name, row.custom_reli_detection_project,
                        row.custom_reli_test_project or "未映射",
                    )
                )

    if frappe.db.has_column("Laboratory Capability", "detection_project"):
        for row in frappe.get_all(
            "Laboratory Capability",
            filters={"detection_project": ["is", "set"]},
            fields=["name", "detection_project", "test_project"],
            limit_page_length=0,
        ):
            expected = targets.get(row.detection_project)
            if not expected or row.test_project != expected:
                unresolved.append(
                    "Laboratory Capability {0}: {1} -> {2}".format(
                        row.name, row.detection_project, row.test_project or "未映射",
                    )
                )

    if unresolved:
        preview = "\n".join(unresolved[:20])
        frappe.throw(_("旧检测项目关联尚未全部映射，已停止清理：\n{0}").format(preview))

    return {
        "items": frappe.db.count(
            "Item", {"custom_reli_detection_project": ["is", "set"]}
        ) if frappe.db.has_column("Item", "custom_reli_detection_project") else 0,
        "capabilities": frappe.db.count(
            "Laboratory Capability", {"detection_project": ["is", "set"]}
        ) if frappe.db.has_column("Laboratory Capability", "detection_project") else 0,
    }


def _delete_link_metadata():
    for row in frappe.get_all(
        "Custom Field",
        filters={"options": "Detection Project"},
        fields=["name"],
        limit_page_length=0,
    ):
        frappe.delete_doc("Custom Field", row.name, ignore_permissions=True, force=True)

    for row in frappe.get_all(
        "Property Setter",
        filters={"value": "Detection Project"},
        fields=["name"],
        limit_page_length=0,
    ):
        frappe.delete_doc("Property Setter", row.name, ignore_permissions=True, force=True)

    for doctype in ("Workspace Link", "Workspace Shortcut"):
        for row in frappe.get_all(
            doctype,
            filters={"link_to": "Detection Project"},
            fields=["name"],
            limit_page_length=0,
        ):
            frappe.delete_doc(doctype, row.name, ignore_permissions=True, force=True)


def _drop_orphan_capability_column():
    if frappe.db.has_column("Laboratory Capability", "detection_project"):
        frappe.db.sql_ddl("alter table `tabLaboratory Capability` drop column `detection_project`")


def execute():
    counts = _verify_legacy_mapping()
    _delete_link_metadata()
    _drop_orphan_capability_column()
    frappe.clear_cache()
    frappe.logger("reli_lims").info(
        "P1.6.1 removed retired Detection Project links: items=%s capabilities=%s",
        counts["items"], counts["capabilities"],
    )
