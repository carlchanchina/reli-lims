"""Native Workspace home, three business centers and compatible field presentation."""
from pathlib import Path
import frappe

# 三中心 + 首页是唯一的公开入口。label 决定侧边栏文案，name 决定路由，
# 因此 name 保持不变，只统一 label/title/顺序/可见性。
CENTER_WORKSPACES = (
    ("Testing Center", "工作台首页", 1.0),
    ("Commercial Intake Center", "商业接单中心", 2.0),
    ("Testing Fulfillment Center", "检测履约中心", 3.0),
    ("Laboratory Capability Center", "实验室能力中心", 4.0),
)


def enforce_workspaces():
    """把四个入口收敛为唯一形态，并隐藏历史遗留的重复工作区。"""
    canonical = {name for name, _, _ in CENTER_WORKSPACES}
    for name, label, sequence in CENTER_WORKSPACES:
        if not frappe.db.exists("Workspace", name):
            frappe.throw(f"缺少工作区 {name}，请检查模块安装是否完整。")
        current = frappe.db.get_value("Workspace", name,
                                      ["label", "title", "sequence_id", "is_hidden", "public"],
                                      as_dict=True)
        changes = {}
        if (current.get("label") or "") != label:
            changes["label"] = label
        if (current.get("title") or "") != label:
            changes["title"] = label
        if float(current.get("sequence_id") or 0) != sequence:
            changes["sequence_id"] = sequence
        if current.get("is_hidden"):
            changes["is_hidden"] = 0
        if not current.get("public"):
            changes["public"] = 1
        if changes:
            frappe.db.set_value("Workspace", name, changes, update_modified=False)
    for row in frappe.get_all("Workspace", filters={"module": "Reli LIMS"},
                              fields=["name", "label", "is_hidden"], limit_page_length=0):
        if row.name not in canonical and not row.is_hidden:
            # 重复入口不删除（保留历史链接可用），只在侧边栏隐藏。
            frappe.db.set_value("Workspace", row.name, {"is_hidden": 1}, update_modified=False)


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
    # Workspace.save() 会用 name 回写 label，因此中文标签必须在保存之后收敛。
    enforce_workspaces()
    frappe.clear_cache()
