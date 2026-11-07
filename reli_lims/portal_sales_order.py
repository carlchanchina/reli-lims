"""Internal adapter called only after the Bridge validates portal scope/evidence.

No whitelisted customer endpoint and no role escalation. ERPNext remains the
commercial document owner. The Bridge stores pre/post fingerprints and receipts
in the same request transaction as these writes.
"""
import frappe
import json
from reli_lims.integration_access import require_bridge
from reli_lims.sales_order_testing import quotation_customer


def _quotation(name, expected_customer, expected_company):
    require_bridge()
    quote = frappe.get_doc("Quotation", name, for_update=True)
    if (quote.docstatus != 1 or quotation_customer(name) != expected_customer
            or quote.company != expected_company):
        frappe.throw("SCOPE_MISMATCH", frappe.PermissionError)
    return quote


def accept_for_portal(name, customer_contact, expected_customer, expected_company, actor_id):
    quote = _quotation(name, expected_customer, expected_company)
    if not isinstance(actor_id, str) or not 1 <= len(actor_id) <= 140:
        frappe.throw("INVALID_SCHEMA")
    # The native method validates status/expiry and writes only its audit fields.
    # Its write check is granted for this single in-memory document operation.
    original = quote.flags.ignore_permissions
    quote.flags.ignore_permissions = True
    try:
        # Pass this locked document through a private helper instead of granting
        # the service role general Quotation write rights.
        from reli_lims.sales_order_testing import record_customer_acceptance
        record_customer_acceptance(quote, customer_contact)
    finally:
        quote.flags.ignore_permissions = original
    audit = frappe.get_doc({"doctype": "Quotation Portal Acceptance", "quotation": name,
        "actor_id": actor_id, "customer": expected_customer, "company": expected_company,
        "accepted_by": customer_contact, "accepted_at": frappe.utils.now_datetime()})
    audit.insert(ignore_permissions=True)
    return {"name": name, "acceptedBy": customer_contact,
            "acceptedAt": str(audit.accepted_at)}


def make_for_portal(name, expected_customer, expected_company):
    quote = _quotation(name, expected_customer, expected_company)
    if not frappe.db.exists("Quotation Portal Acceptance", {"quotation": name}):
        frappe.throw("COMMERCIAL_APPROVAL_REQUIRED")
    from erpnext.selling.doctype.quotation.quotation import _make_sales_order, validate_quotation_expiry
    validate_quotation_expiry(quote.name)
    order = _make_sales_order(quote.name, ignore_permissions=True)
    if not order.items:
        frappe.throw("CAPACITY_CONFLICT")
    order.insert(ignore_permissions=True)
    return order


def bind_request_for_portal(name, expected_customer, expected_company, fields):
    """Bind native draft items to their exact accepted quotation rows and balance."""
    quote = _quotation(name, expected_customer, expected_company)
    from reli_lims.capability_request import to_request_item
    from reli_lims.quotation_origin import lock_quotation_lines, remaining_quantity
    lock_quotation_lines([row.name for row in quote.items])
    rows = []
    for index, row in enumerate(quote.items, 1):
        config = frappe.parse_json(row.get("custom_reli_configuration"))
        if row.get("custom_reli_business_type") != "检测服务":
            continue
        if not row.get("custom_reli_capability") or not isinstance(config, dict):
            frappe.throw("CAPABILITY_INELIGIBLE")
        remaining = remaining_quantity(row)
        if remaining <= 0:
            continue
        rows.append(dict(to_request_item(config), item_code="Q" + str(index),
            source_quotation=quote.name, source_quotation_item=row.name,
            quoted_quantity=row.qty, requested_quantity=remaining))
    if not rows:
        frappe.throw("CAPACITY_CONFLICT")
    result = dict(fields, customer=expected_customer, company=expected_company,
                  quotation=quote.name, items=rows)
    codes = {row["item_code"] for row in rows}
    result["sample_assignments"] = [row for row in result.get("sample_assignments", [])
                                    if row.get("item_code") in codes]
    return result


def apply_inquiry_scope(fields, reference):
    """Use the native single-capability row without inventing multi-scope pricing."""
    require_bridge()
    refs = reference.get("capabilityReferences") or []
    if len(refs) != 1 or len(fields.get("items") or []) != 1:
        raise ValueError("TECHNICAL_APPROVAL_REQUIRED")
    groups = reference.get("requiredGroups") or []
    if groups and any(not any(member.get("id") == refs[0].get("id")
                             and member.get("revision") == refs[0].get("revision")
                             for member in group.get("any_of", [])) for group in groups):
        raise ValueError("TECHNICAL_APPROVAL_REQUIRED")
    from reli_lims.capability_eligibility import get_current
    qualification = get_current([refs[0]["id"]])[0]
    scope = reference.get("scopeSnapshot") or {}
    standards = scope.get("standards") or []
    expected_standard = {key: qualification["standard"][key] for key in ("id", "code", "edition")}
    if (qualification["state"] != "eligible" or qualification["revision"] != refs[0].get("revision")
            or qualification["laboratoryId"] != reference.get("laboratoryId")
            or qualification["sellerId"] != reference.get("sellerId")
            or standards != [expected_standard] or scope.get("range") != qualification["scope"]
            or (scope.get("limitations") or "") != qualification["limitations"]):
        raise ValueError("TECHNICAL_APPROVAL_REQUIRED")
    from reli_lims.capability_selection import build_configuration
    from reli_lims.capability_quotation import service_item
    capability = frappe.get_doc("Laboratory Capability", refs[0]["id"])
    row = dict(fields["items"][0])
    linked_item = frappe.db.get_value("Item", row.get("item_code"),
        ["custom_reli_test_project", "custom_reli_business_type"], as_dict=True)
    if (not linked_item or linked_item.custom_reli_test_project != capability.test_project
            or linked_item.custom_reli_business_type != "检测服务"):
        raise ValueError("TECHNICAL_APPROVAL_REQUIRED")
    previous_item = frappe.flags.get("reli_lims_portal_item")
    frappe.flags.reli_lims_portal_item = row.get("item_code")
    try:
        item = service_item(capability, row.get("item_code"))
    finally:
        frappe.flags.reli_lims_portal_item = previous_item
    if item.name != reference.get("itemCode"):
        raise ValueError("TECHNICAL_APPROVAL_REQUIRED")
    config = build_configuration(capability.name, {}, "quotation")
    result = dict(fields)
    row.update(custom_reli_capability=capability.name, custom_reli_configuration=json.dumps(config, ensure_ascii=False),
               custom_reli_test_project=capability.test_project, custom_reli_test_object=capability.test_object,
               custom_reli_test_standard=capability.test_standard, custom_reli_business_type="检测服务")
    result["items"] = [row]
    return result
