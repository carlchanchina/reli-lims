"""Server-to-server Mercur bridge and reviewed laboratory directory."""

import json
import re

import frappe
from frappe import _
from frappe.utils import now_datetime

DOCTYPE = "Laboratory Profile"
INTEGRATION_ROLE = "Mercur Integration"


def _require_integration():
    if frappe.session.user == "Guest" or INTEGRATION_ROLE not in frappe.get_roles():
        frappe.throw(_("Mercur integration role required"), frappe.PermissionError)


def _require_reviewer():
    if frappe.session.user == "Guest" or not set(frappe.get_roles()).intersection(
        {"Lab Reviewer", "System Manager"}
    ):
        frappe.throw(_("Laboratory reviewer role required"), frappe.PermissionError)


def _require_directory_reader():
    if frappe.session.user == "Guest" or "Laboratory Directory Reader" not in frappe.get_roles():
        frappe.throw(_("Laboratory directory reader role required"), frappe.PermissionError)


def _seller_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"sel_[A-Za-z0-9_]{1,96}", value):
        frappe.throw(_("Invalid Mercur seller ID"))
    return value


def _lock_profile(seller_id):
    frappe.db.sql("SELECT name FROM `tabLaboratory Profile` WHERE name = %s FOR UPDATE", (seller_id,))


def _text(value, label, limit=2000, required=False):
    if not isinstance(value, str):
        frappe.throw(_("{0} must be text").format(_(label)))
    value = value.strip()
    if len(value) > limit or (required and not value):
        frappe.throw(_("Invalid {0}").format(_(label)))
    return value


def _items(value, label, limit=30):
    if not isinstance(value, list) or len(value) > limit:
        frappe.throw(_("Invalid {0}").format(_(label)))
    return [_text(item, label, 300, required=True) for item in value]


def _normalize(profile):
    if isinstance(profile, str):
        profile = json.loads(profile)
    if not isinstance(profile, dict):
        frappe.throw(_("Invalid laboratory profile"))
    certificates = profile.get("certificates", [])
    if not isinstance(certificates, list) or len(certificates) > 20:
        frappe.throw(_("Invalid certificates"))
    clean_certificates = []
    for certificate in certificates:
        if not isinstance(certificate, dict):
            frappe.throw(_("Invalid certificate"))
        clean_certificates.append({
            "name": _text(certificate.get("name"), "certificate name", 150, True),
            "scope": _text(certificate.get("scope", ""), "certificate scope", 1000),
            "valid_until": _text(certificate.get("valid_until", ""), "certificate expiry", 20),
        })
    response_hours = profile.get("response_hours")
    if not isinstance(response_hours, int) or isinstance(response_hours, bool) or not 1 <= response_hours <= 720:
        frappe.throw(_("Response hours must be between 1 and 720"))
    return {
        "name": _text(profile.get("name"), "laboratory name", 150, True),
        "city": _text(profile.get("city"), "city", 100, True),
        "introduction": _text(profile.get("introduction"), "introduction", 4000, True),
        "response_hours": response_hours,
        "capabilities": _items(profile.get("capabilities", []), "capabilities"),
        "equipment": _items(profile.get("equipment", []), "equipment"),
        "standards": _items(profile.get("standards", []), "standards"),
        "industries": _items(profile.get("industries", []), "industries"),
        "cases": _items(profile.get("cases", []), "cases"),
        "certificates": clean_certificates,
    }


def _decode(value):
    return json.loads(value) if isinstance(value, str) and value else value or None


@frappe.whitelist(methods=["GET"])
def get_vendor_profile(seller_id):
    _require_integration()
    seller_id = _seller_id(seller_id)
    if not frappe.db.exists(DOCTYPE, seller_id):
        return {"seller_id": seller_id, "status": "Draft", "draft": None, "published": None, "revision": 0}
    doc = frappe.get_doc(DOCTYPE, seller_id)
    return {
        "seller_id": seller_id,
        "status": doc.review_status,
        "draft": _decode(doc.draft_json),
        "published": _decode(doc.published_json),
        "revision": doc.draft_revision or 0,
        "review_note": doc.review_note,
    }


@frappe.whitelist(methods=["POST"])
def submit_vendor_profile(seller_id, profile, expected_revision):
    _require_integration()
    seller_id = _seller_id(seller_id)
    clean = _normalize(profile)
    if frappe.db.exists(DOCTYPE, seller_id):
        _lock_profile(seller_id)
        doc = frappe.get_doc(DOCTYPE, seller_id)
    else:
        doc = frappe.get_doc({"doctype": DOCTYPE, "mercur_seller_id": seller_id})
    if (doc.draft_revision or 0) != int(expected_revision):
        frappe.throw(_("Profile changed; reload before submitting"))
    doc.laboratory_name = clean["name"]
    doc.draft_json = frappe.as_json(clean)
    doc.draft_revision = (doc.draft_revision or 0) + 1
    doc.review_status = "Pending"
    doc.submitted_at = now_datetime()
    doc.review_note = None
    if doc.is_new():
        doc.insert(ignore_permissions=True)
    else:
        doc.save(ignore_permissions=True)
    return {"seller_id": seller_id, "status": "Pending", "revision": doc.draft_revision}


@frappe.whitelist(methods=["POST"])
def review_profile(seller_id, revision, approve, note=""):
    _require_reviewer()
    seller_id = _seller_id(seller_id)
    _lock_profile(seller_id)
    doc = frappe.get_doc(DOCTYPE, seller_id)
    if doc.review_status != "Pending" or doc.draft_revision != int(revision):
        frappe.throw(_("Profile changed since review began; reload it"))
    approved = approve in (True, 1, "1", "true", "True")
    if approved:
        doc.published_json = doc.draft_json
        doc.published_revision = doc.draft_revision
        doc.review_status = "Approved"
    else:
        doc.review_status = "Rejected"
    doc.review_note = _text(note, "review note", 1000)
    doc.reviewed_at = now_datetime()
    doc.reviewed_by = frappe.session.user
    doc.save(ignore_permissions=True)
    return {"seller_id": seller_id, "status": doc.review_status, "published_revision": doc.published_revision or 0}


@frappe.whitelist(methods=["GET"])
def list_published_profiles():
    _require_directory_reader()
    rows = frappe.get_all(
        DOCTYPE,
        filters={"published_revision": [">", 0]},
        fields=["mercur_seller_id", "published_json", "published_revision"],
        limit_page_length=500,
    )
    return [
        {"seller_id": row.mercur_seller_id, "profile": _decode(row.published_json), "revision": row.published_revision}
        for row in rows
    ]
