"""Persisted qualification events. Commercial approval remains with Bridge."""
import hashlib
import json
import re
from datetime import datetime, timezone

import frappe
from frappe.utils import getdate, now_datetime, today
from reli_lims.integration_access import require_bridge, require_capability_reader, check_laboratory

EVENT = "Capability Eligibility Event"


def _state(capability, standard, laboratory, source, source_state):
    if source_state:
        return source_state
    if (capability.status != "已发布" or not capability.published
            or capability.get("demo_only") or not capability.get("reviewed_by")):
        return "withdrawn"
    if not source or source.documents_review_status != "Approved":
        return "revoked"
    if laboratory.review_status != "Approved" or not laboratory.get("published_revision"):
        return "withdrawn"
    if standard.status != "Active":
        return "superseded" if standard.status == "Superseded" else "withdrawn"
    current = getdate(today())
    if standard.get("effective_date") and getdate(standard.effective_date) > current:
        return "withdrawn"
    # CNAS/CMA evidence must have a proven start and expiry. Unknown means ineligible.
    start = capability.get("scope_effective_date")
    expiry = source.get("expiry_date")
    if capability.accreditation_type in {"CNAS", "CMA"} and (
            not capability.certificate_no or not start or not expiry):
        return "withdrawn"
    if start and getdate(start) > current:
        return "withdrawn"
    if expiry and getdate(expiry) < current:
        return "expired"
    if not frappe.db.get_value("Test Project", capability.test_project, "active"):
        return "withdrawn"
    return "eligible"


def source_version_verified(source):
    if not frappe.db.exists("DocType", "Document Approved Version"):
        return False
    document = (source.documents_source_id or "").rsplit(":", 1)[0]
    version = frappe.db.get_value("Document Approved Version", {
        "document": document, "version": source.documents_version, "version_type": "Structured"},
        ["structured_json", "payload_hash", "approved_by"], as_dict=True)
    if not version or not version.approved_by:
        return False
    from wekona_documents.services.approval import payload_hash
    return (frappe.parse_json(source.structured_json) == frappe.parse_json(version.structured_json)
            and payload_hash(version.structured_json) == version.payload_hash
            and frappe.db.get_value("Incoming Document", document, "source_file") == source.source_file_url)


def evidence_ready(capability, source):
    if not source or not (source.get("source_file_url") or "").startswith("/private/files/"):
        return False
    if not source.source_file_url.lower().endswith(".pdf"):
        return False
    if not frappe.db.exists("File", {"file_url": source.source_file_url, "is_private": 1}):
        return False
    if not source_version_verified(source):
        return False
    payload = frappe.parse_json(source.structured_json)
    if not isinstance(payload, dict):
        return False
    for index, row in enumerate(payload.get("items") or [], 1):
        if not isinstance(row, dict) or str(row.get("source_row") or index) != str(capability.source_row):
            continue
        pages = row.get("source_pages") or row.get("pages") or [row.get("page") or row.get("source_page")]
        if not isinstance(pages, list):
            pages = [pages]
        return bool(pages) and all(type(page) is int and page > 0 for page in pages)
    return False


def projection(capability):
    standard = frappe.get_doc("Test Standard", capability.test_standard)
    laboratory = frappe.get_doc("Laboratory Profile", capability.laboratory)
    source = frappe.get_doc("Capability Source", capability.source) if capability.source else None
    status = frappe.get_all("Capability Source Status", filters={"source": capability.source},
                            fields=["state"], order_by="name desc", limit_page_length=1) if source else []
    state = _state(capability, standard, laboratory, source, status[0].state if status else None)
    if state == "eligible" and not evidence_ready(capability, source):
        state = "withdrawn"
    return {
        "capabilityId": capability.name,
        "laboratoryId": capability.laboratory,
        "sellerId": laboratory.mercur_seller_id,
        "testProjectId": capability.test_project or "",
        "testObjectId": capability.test_object or "",
        "standard": {"id": standard.name, "code": standard.standard_code or "",
                     "edition": standard.version or "", "status": (standard.status or "Draft").lower()},
        "method": capability.test_method or "",
        "scope": capability.capability_scope or "",
        "limitations": capability.limitation or "",
        "source": {"id": source.name if source else "", "documentId": source.documents_source_id.rsplit(":", 1)[0] if source else "",
                   "version": str(source.documents_version or "") if source else "",
                   "row": str(capability.source_row or "")},
        "accreditation": {"type": capability.accreditation_type, "certificate": capability.certificate_no or "",
                          "validFrom": str(capability.scope_effective_date) if capability.scope_effective_date else None,
                          "validUntil": str(source.expiry_date) if source and source.expiry_date else None},
        "review": {"state": "approved" if capability.get("reviewed_by") else "pending",
                   "reference": capability.name + ":" + str(capability.get("reviewed_on") or "")},
        "state": state,
    }


def refresh(name):
    # A common per-capability lock serializes the event revision under callbacks/readers.
    frappe.db.sql("SELECT name FROM `tabLaboratory Capability` WHERE name=%s FOR UPDATE", name)
    capability = frappe.get_doc("Laboratory Capability", name)
    payload = projection(capability)
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"),
                                       ensure_ascii=False).encode()).hexdigest()
    previous = frappe.get_all(EVENT, filters={"capability": name}, fields=["name", "revision", "payload_hash", "snapshot"],
                              order_by="name desc", limit_page_length=1)
    if previous and previous[0].payload_hash == digest:
        return frappe.parse_json(previous[0].snapshot)
    event = frappe.get_doc({"doctype": EVENT, "capability": name,
                           "revision": (previous[0].revision if previous else 0) + 1,
                           "payload_hash": digest})
    event.set_new_name()
    payload.update(revision=event.revision, eventId="reli-lims:" + event.name,
                   modifiedAt=datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"))
    event.snapshot = json.dumps(payload, ensure_ascii=False)
    event.insert(ignore_permissions=True)
    if payload["state"] != "eligible" and previous:
        frappe.enqueue("reli_lims.capability_eligibility.notify_bridge", capability_ids=[name],
                       enqueue_after_commit=True)
    return payload


def changed(doc, method=None):
    if not frappe.db.table_exists(EVENT):
        return
    if doc.doctype == "Laboratory Capability":
        names = [doc.name]
    else:
        field = {"Test Standard": "test_standard", "Laboratory Profile": "laboratory",
                 "Capability Source": "source", "Test Project": "test_project"}.get(doc.doctype)
        if not field:
            return
        names = frappe.get_all("Laboratory Capability", filters={field: doc.name}, pluck="name", order_by="name")
    for name in names:
        refresh(name)


def refresh_all():
    for name in frappe.get_all("Laboratory Capability", pluck="name", order_by="name"):
        refresh(name)


def list_events(cursor=None, limit=100):
    require_capability_reader()
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        frappe.throw("INVALID_SCHEMA")
    if not 1 <= limit <= 100 or (cursor and not re.fullmatch(r"ELIG-[0-9]{12,}", cursor)):
        frappe.throw("INVALID_SCHEMA")
    filters = {"name": [">", cursor]} if cursor else {}
    rows = frappe.get_all(EVENT, filters=filters, fields=["name", "snapshot"],
                          order_by="name", limit_page_length=limit + 1)
    return {"schemaVersion": 2, "items": [frappe.parse_json(row.snapshot) for row in rows[:limit]],
            "nextCursor": rows[limit-1].name if len(rows) > limit else None}


def get_current(capability_ids):
    require_capability_reader()
    if isinstance(capability_ids, str):
        capability_ids = frappe.parse_json(capability_ids)
    if (not isinstance(capability_ids, list) or not 1 <= len(capability_ids) <= 100
            or any(not isinstance(name, str) or not 1 <= len(name) <= 140 for name in capability_ids)):
        frappe.throw("INVALID_SCHEMA")
    return [refresh(name) for name in sorted(set(capability_ids))]


@frappe.whitelist(methods=["POST"])
def invalidate_source(source_name, state, reason):
    if not set(frappe.get_roles()).intersection({"Lab Manager", "System Manager"}):
        frappe.throw("FORBIDDEN", frappe.PermissionError)
    source = frappe.get_doc("Capability Source", source_name)
    source.check_permission("read")
    check_laboratory(source.laboratory)
    if state not in {"revoked", "superseded"} or not isinstance(reason, str) or not 4 <= len(reason.strip()) <= 2000:
        frappe.throw("INVALID_SCHEMA")
    frappe.get_doc({"doctype": "Capability Source Status", "source": source_name,
                    "state": state, "reason": reason.strip(), "actor": frappe.session.user}).insert(ignore_permissions=True)
    changed(source)
    return {"sourceId": source_name, "state": state}


def notify_bridge(capability_ids):
    """Notify through Bridge's existing retry journal under its scoped identity."""
    user = frappe.session.user
    try:
        frappe.set_user(frappe.conf.get("reli_lims_portal_bridge_user") or "Guest")
        require_bridge()
        from mercur_erpnext_bridge.capability_publication import invalidate_capabilities
        invalidate_capabilities(capability_ids)
    finally:
        frappe.set_user(user)
