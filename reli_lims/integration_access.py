"""Narrow service identity and laboratory scope for integration adapters."""
import frappe


def require_bridge():
    expected = frappe.conf.get("reli_lims_portal_bridge_user")
    if (not expected or frappe.session.user != expected
            or frappe.session.user in {"Guest", "Administrator"}
            or not {"Mercur Integration", "LIMS Portal Adapter"}.issubset(frappe.get_roles())):
        frappe.throw("FORBIDDEN", frappe.PermissionError)


def laboratory_scope(laboratory, user=None):
    user = user or frappe.session.user
    if user == "Administrator" or "System Manager" in frappe.get_roles(user):
        return True
    return bool(frappe.db.exists("User Permission", {
        "user": user, "allow": "Laboratory Profile", "for_value": laboratory,
    }))


def check_laboratory(laboratory):
    if not laboratory_scope(laboratory):
        frappe.throw("SCOPE_MISMATCH", frappe.PermissionError)


def capability_permission(doc, user=None, ptype=None):
    user = user or frappe.session.user
    roles = set(frappe.get_roles(user))
    if (user == frappe.conf.get("reli_lims_portal_bridge_user")
            and "Mercur Integration" in roles and ptype == "read"):
        return any(binding.get("laboratory_id") == doc.laboratory
                   for binding in (frappe.conf.get("reli_lims_portal_laboratories") or []))
    if user == "Administrator" or "System Manager" in roles:
        return True
    allowed_roles = {"Lab Manager", "Lab Reviewer"} if ptype in {"read", "write", "report", "export", "print"} else {"Lab Manager"}
    return bool(roles.intersection(allowed_roles)) and laboratory_scope(doc.laboratory, user)


def capability_query(user=None):
    user = user or frappe.session.user
    if user == "Administrator" or "System Manager" in frappe.get_roles(user):
        return ""
    labs = frappe.get_all("User Permission", filters={"user": user,
        "allow": "Laboratory Profile"}, pluck="for_value")
    values = ",".join(frappe.db.escape(lab) for lab in labs) or "NULL"
    return f"`tabLaboratory Capability`.`laboratory` IN ({values})"


def document_permission(doc, user=None, ptype=None):
    # Other roles continue through the native Documents permissions.
    user = user or frappe.session.user
    if user != frappe.conf.get("reli_lims_portal_bridge_user"):
        return "LIMS Portal Adapter" not in frappe.get_roles(user)
    if ptype not in {"read", "write"}:
        return False
    return bool(frappe.db.exists("Capability Upload", {"document": doc.name}))


def source_permission(doc, user=None, ptype=None):
    return capability_permission(doc, user, ptype)


def source_query(user=None):
    return capability_query(user).replace("tabLaboratory Capability", "tabCapability Source")


def upload_permission(doc, user=None, ptype=None):
    user = user or frappe.session.user
    if user == frappe.conf.get("reli_lims_portal_bridge_user"):
        return ptype in {"read", "write"}
    return "LIMS Portal Adapter" not in frappe.get_roles(user)


def document_run_permission(doc, user=None, ptype=None):
    user = user or frappe.session.user
    if user != frappe.conf.get("reli_lims_portal_bridge_user"):
        return "LIMS Portal Adapter" not in frappe.get_roles(user)
    return ptype in {"read", "write"} and bool(frappe.db.exists(
        "Capability Upload", {"document": doc.incoming_document}))


def document_config_permission(doc, user=None, ptype=None):
    user = user or frappe.session.user
    if user != frappe.conf.get("reli_lims_portal_bridge_user"):
        return "LIMS Portal Adapter" not in frappe.get_roles(user)
    if ptype != "read":
        return False
    fields = {"Document Template": "reli_lims_cnas_extraction_profile",
              "Document AI Provider": "reli_lims_cnas_ai_provider"}
    if doc.doctype == "Document Schema":
        profile = frappe.conf.get("reli_lims_cnas_extraction_profile")
        schema = frappe.db.get_value("Document Template", profile, "source_schema") if profile else None
        return bool(schema and doc.name == schema)
    return doc.name == frappe.conf.get(fields[doc.doctype])


def profile_permission(doc, user=None, ptype=None):
    return capability_permission(frappe._dict(laboratory=doc.name), user, ptype)


def profile_query(user=None):
    return capability_query(user).replace("`tabLaboratory Capability`.`laboratory`", "`tabLaboratory Profile`.`name`")


def document_query(user=None):
    user = user or frappe.session.user
    if "LIMS Portal Adapter" not in frappe.get_roles(user):
        return ""
    if user != frappe.conf.get("reli_lims_portal_bridge_user"):
        return "1=0"
    return "`tabIncoming Document`.`name` IN (SELECT document FROM `tabCapability Upload` WHERE ifnull(document,'')!='')"


def run_query(user=None):
    condition = document_query(user)
    return condition.replace("`tabIncoming Document`.`name`", "incoming_document")


def config_query(user=None):
    user = user or frappe.session.user
    if "LIMS Portal Adapter" in frappe.get_roles(user):
        # Config records are accessed directly by their pinned names, never listed.
        return "1=0"
    return ""


def require_capability_reader():
    user = frappe.session.user
    if (user == frappe.conf.get("reli_lims_capability_reader_user")
            and user not in {"Guest", "Administrator"}
            and "LIMS Capability Reader" in frappe.get_roles()):
        return
    require_bridge()


def item_permission(doc, user=None, ptype=None):
    user = user or frappe.session.user
    if "LIMS Portal Adapter" not in frappe.get_roles(user):
        return True
    return (user == frappe.conf.get("reli_lims_portal_bridge_user") and ptype == "read"
            and doc.name == frappe.flags.get("reli_lims_portal_item"))


def approved_version_permission(doc, user=None, ptype=None):
    user = user or frappe.session.user
    if user != frappe.conf.get("reli_lims_portal_bridge_user"):
        return "LIMS Portal Adapter" not in frappe.get_roles(user)
    return ptype == "read" and bool(frappe.db.exists("Capability Upload", {"document": doc.document}))


def approved_version_query(user=None):
    return document_query(user).replace("`tabIncoming Document`.`name`", "document")
