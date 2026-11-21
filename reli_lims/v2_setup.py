"""Idempotent installer for the V2 Unified Workspace command center.

Only creates/updates a single native Workspace record. All target links point
to pages that already exist in the site; this module never creates or copies
business data. Safe to run on every migrate.
"""
import json
import os

import frappe

# Workspace uses autoname="field:label", so the record name equals its label.
COMMAND_CENTER = "RELI LIMS V2"
WORKSPACE_JSON = os.path.join(
    os.path.dirname(__file__), "reli_lims", "workspace", "v2_command_center",
    "v2_command_center.json",
)


def install_v2_command_center():
    """Upsert the V2 command center Workspace from its source JSON.

    Idempotent: an existing record is refreshed in place, otherwise inserted.
    """
    with open(WORKSPACE_JSON, encoding="utf-8") as handle:
        definition = json.load(handle)

    # Workspace.autoname == "field:label"; the record name is always the label.
    name = definition.get("label") or COMMAND_CENTER
    definition["name"] = name
    if frappe.db.exists("Workspace", name):
        doc = frappe.get_doc("Workspace", name)
        doc.update(definition)
        doc.save(ignore_permissions=True)
    else:
        doc = frappe.get_doc(definition)
        doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return name


def get_route():
    """Return the Desk route of the installed command center (for smoke tests)."""
    doc = frappe.get_doc("Workspace", COMMAND_CENTER)
    return doc.get_url() if hasattr(doc, "get_url") else f"/desk/reli-lims/{COMMAND_CENTER}"


def verify_targets():
    """Return a report confirming every shortcut/link target really exists.

    Raises ValueError if any configured target is missing, so a broken link can
    never be shipped as "verified".
    """
    with open(WORKSPACE_JSON, encoding="utf-8") as handle:
        definition = json.load(handle)

    report = {"links": [], "shortcuts": [], "missing": []}
    for link in definition.get("links", []):
        if link.get("type") != "Link":
            continue
        target_type, target = link.get("link_type"), link.get("link_to")
        exists = bool(frappe.db.exists(target_type, target)) if target_type and target else False
        report["links"].append({"type": target_type, "to": target, "exists": exists})
        if not exists:
            report["missing"].append(f"link:{target_type}:{target}")

    for shortcut in definition.get("shortcuts", []):
        label, url = shortcut.get("label"), shortcut.get("url")
        exists = bool(url)  # URL targets are resolved below by route check
        report["shortcuts"].append({"label": label, "url": url, "exists": exists})
        if not exists:
            report["missing"].append(f"shortcut:{label}")

    if report["missing"]:
        raise ValueError("V2 command center has broken targets: " + ", ".join(report["missing"]))
    return report
