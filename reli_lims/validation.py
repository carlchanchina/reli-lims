import frappe
from frappe import _


def require_role(*roles):
    if frappe.session.user != 'Administrator' and not set(roles).intersection(frappe.get_roles()):
        frappe.throw(_('You are not authorized for this laboratory action.'), frappe.PermissionError)


def validate_transition(previous, current, states):
    if previous == current:
        return
    if current not in states.get(previous, ()):
        frappe.throw(_('Invalid status transition: {0} → {1}.').format(previous, current))


def field_values(doc, excluded=()):
    """Compare persisted business fields while ignoring Frappe bookkeeping."""
    values = {"name": doc.name} if doc.meta.istable else {}
    for field in doc.meta.fields:
        if field.fieldname in excluded or field.fieldtype in ('Section Break', 'Column Break', 'HTML', 'Button'):
            continue
        value = doc.get(field.fieldname)
        if field.fieldtype in ('Table', 'Table MultiSelect'):
            values[field.fieldname] = [field_values(row) for row in value or []]
        else:
            values[field.fieldname] = str(value) if value is not None else None
    return values
