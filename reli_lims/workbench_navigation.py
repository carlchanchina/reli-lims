"""Native Workspace home, three business centers and compatible field presentation."""
from pathlib import Path
import frappe


def after_migrate():
    directory = Path(__file__).parent / "templates" / "workbench"
    values = {"html": (directory / "home.html").read_text(),
              "style": (directory / "home.css").read_text(),
              "script": (directory / "home.js").read_text(), "private": 0}
    name = "Reli Three Centers"
    if frappe.db.exists("Custom HTML Block", name):
        block = frappe.get_doc("Custom HTML Block", name)
        block.update(values)
        block.save(ignore_permissions=True)
    else:
        frappe.get_doc(dict(doctype="Custom HTML Block", name=name, **values)).insert(ignore_permissions=True)
    home = frappe.get_doc("Workspace", "Testing Center")
    home.set("custom_blocks", [{"custom_block_name": name, "label": name}])
    home.content = frappe.as_json([{"id": "reli-three-centers", "type": "custom_block",
                                  "data": {"custom_block_name": name, "col": 12}}])
    home.save(ignore_permissions=True)
    for field in ("custom_reli_test_method",):
        custom = frappe.db.get_value("Custom Field", {"dt": "Item", "fieldname": field}, "name")
        if custom:
            frappe.db.set_value("Custom Field", custom, {"hidden": 1, "read_only": 1}, update_modified=False)
    frappe.clear_cache()
