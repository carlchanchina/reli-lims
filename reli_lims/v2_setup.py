"""Idempotent installer for the V2 Unified Workspace command center.

Only creates/updates a single native Workspace record. All target links point
to pages that already exist in the site; this module never creates or copies
business data. Safe to run on every migrate.
"""
import json
import os
from urllib.parse import urlparse

import frappe

# Workspace uses autoname="field:label", so the record name equals its label.
COMMAND_CENTER = "RELI LIMS V2"
WORKSPACE_JSON = os.path.join(
    os.path.dirname(__file__), "reli_lims", "workspace", "v2_command_center",
    "v2_command_center.json",
)

# The four home-page entries and the Workspace each one opens. The real Desk
# route is derived from these (never hard-coded a second time).
CENTER_SHORTCUTS = {
    "1 · 商务中心": "Commercial Intake Center",
    "2 · 能力中心": "Laboratory Capability Center",
    "3 · 履约中心": "Testing Fulfillment Center",
    "4 · 文档中心": "Wekona Documents",
}

# On this Frappe line ``/desk/workspace/<Name>`` opens the Workspace *editor*
# (the "build" form), not the dashboard a user works in. Shortcuts must never
# point there.
EDITOR_ROUTE_PREFIX = "/desk/workspace/"


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


def shell_slug_for(workspace_name):
    """URL segment of the app shell a workspace lives under.

    Desk routes are ``/desk/<shell>/<page>``. The shell is the Sidebar record
    whose title matches the workspace module, so its slug is what the router
    actually uses instead of the module's Python name.
    """
    module = frappe.get_doc("Workspace", workspace_name).module
    return frappe.utils.slug(module)


def user_route(workspace_name):
    """The Desk route a user opens for this workspace dashboard."""
    return f"/desk/{shell_slug_for(workspace_name)}/{frappe.utils.slug(workspace_name)}"


def is_editor_route(url):
    """True for the Workspace editor route, which is never a valid shortcut."""
    if not url:
        return False
    return urlparse(url).path.startswith(EDITOR_ROUTE_PREFIX)


def get_route():
    """Return the user-facing route of the installed command center."""
    return user_route(COMMAND_CENTER)


def route_report():
    """Return real user routes for the command center and its four targets."""
    names = [COMMAND_CENTER, *CENTER_SHORTCUTS.values()]
    lines = []
    for name in names:
        if frappe.db.exists("Workspace", name):
            lines.append(f"{name} => {user_route(name)}")
        else:
            lines.append(f"{name} => MISSING")
    return "\n".join(lines)


def workspace_name_from_url(url):
    """Resolve a shortcut URL back to the Workspace it opens.

    Only real user routes resolve. The editor route and anything unknown return
    ``None`` so a shortcut pointing at the editor can never validate.
    """
    if not url or is_editor_route(url):
        return None
    path = urlparse(url).path.rstrip("/")
    for label, name in CENTER_SHORTCUTS.items():
        if frappe.db.exists("Workspace", name) and path == user_route(name):
            return name
    return None


def verify_targets():
    """Return a report confirming every shortcut/link target really exists.

    A shortcut passes only when its URL is the workspace's real user route and
    every shortcut is listed in CENTER_SHORTCUTS. The Workspace editor route is
    explicitly rejected. Raises ValueError on any broken target.
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
        workspace_name = CENTER_SHORTCUTS.get(label)
        exists = bool(workspace_name) and bool(frappe.db.exists("Workspace", workspace_name))
        expected = user_route(workspace_name) if exists else None
        report["shortcuts"].append(
            {
                "label": label,
                "url": url,
                "workspace": workspace_name,
                "expected_url": expected,
                "exists": exists,
                "is_editor_route": is_editor_route(url),
                "matches_user_route": bool(expected) and url == expected,
            }
        )
        if not exists:
            report["missing"].append(f"shortcut:{label}:workspace-missing")
        elif is_editor_route(url):
            report["missing"].append(f"shortcut:{label}:points-at-editor")
        elif url != expected:
            report["missing"].append(f"shortcut:{label}:{url}!={expected}")

    if report["missing"]:
        raise ValueError("V2 command center has broken targets: " + ", ".join(report["missing"]))
    return report
