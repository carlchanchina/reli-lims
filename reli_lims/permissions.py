import frappe


def has_app_permission():
    """Keep the launcher aligned with the app's existing read permissions."""
    return bool(frappe.has_permission("Sample", "read"))
