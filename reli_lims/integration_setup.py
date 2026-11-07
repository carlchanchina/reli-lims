"""Install narrow adapter permissions without assigning the role to any user."""
import frappe

ROLE = "LIMS Portal Adapter"


def after_migrate():
    from frappe.permissions import add_permission
    for role in (ROLE, "LIMS Capability Reader"):
        if not frappe.db.exists("Role", role):
            frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 0}).insert(ignore_permissions=True)
    for doctype in ("Item", "Capability Upload", "Laboratory Capability", "Laboratory Profile", "Incoming Document",
                    "Document Processing Run", "Document Extraction", "Document Approved Version", "Document Template", "Document Schema", "Document AI Provider"):
        if not frappe.db.exists("DocType", doctype):
            continue
        name = frappe.db.get_value("Custom DocPerm", {"parent": doctype, "role": ROLE, "permlevel": 0})
        if not name:
            name = add_permission(doctype, ROLE, ptype="read")
        if name and doctype in {"Incoming Document", "Document Processing Run", "Document Extraction", "Capability Upload"}:
            frappe.db.set_value("Custom DocPerm", name, "write", 1)
        frappe.clear_cache(doctype=doctype)

    from reli_lims.capability_eligibility import refresh_all
    refresh_all()
