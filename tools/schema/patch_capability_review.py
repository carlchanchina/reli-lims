"""一次性结构脚本：为 CNAS 能力审核工作流补字段与审核日志子表。

保留 JSON 的原始缩进（indent=2, 不排序键），避免整文件重排。
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCTYPES = ROOT / "reli_lims" / "reli_lims" / "doctype"

CAPABILITY = DOCTYPES / "laboratory_capability" / "laboratory_capability.json"
LOG_DOCTYPE = DOCTYPES / "capability_review_log"


def dump(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_child():
    LOG_DOCTYPE.mkdir(parents=True, exist_ok=True)
    (LOG_DOCTYPE / "__init__.py").write_text("", encoding="utf-8")
    doc = {
        "actions": [],
        "autoname": "hash",
        "creation": "2026-11-05 23:50:00.000000",
        "doctype": "DocType",
        "editable_grid": 1,
        "engine": "InnoDB",
        "field_order": [
            "action",
            "from_status",
            "to_status",
            "column_break_actor",
            "actor",
            "actor_role",
            "at",
            "section_break_note",
            "note",
        ],
        "fields": [
            {
                "fieldname": "action",
                "fieldtype": "Select",
                "in_list_view": 1,
                "label": "审核动作",
                "options": "提交审核\n审核通过\n退回补充\n发布\n停用",
                "reqd": 1,
            },
            {
                "fieldname": "from_status",
                "fieldtype": "Data",
                "in_list_view": 1,
                "label": "原状态",
                "read_only": 1,
            },
            {
                "fieldname": "to_status",
                "fieldtype": "Data",
                "in_list_view": 1,
                "label": "新状态",
                "read_only": 1,
            },
            {"fieldname": "column_break_actor", "fieldtype": "Column Break"},
            {
                "fieldname": "actor",
                "fieldtype": "Link",
                "in_list_view": 1,
                "label": "操作人",
                "options": "User",
                "read_only": 1,
            },
            {
                "fieldname": "actor_role",
                "fieldtype": "Data",
                "label": "操作角色",
                "read_only": 1,
            },
            {
                "fieldname": "at",
                "fieldtype": "Datetime",
                "in_list_view": 1,
                "label": "操作时间",
                "read_only": 1,
            },
            {"fieldname": "section_break_note", "fieldtype": "Section Break"},
            {
                "fieldname": "note",
                "fieldtype": "Small Text",
                "label": "审核意见",
            },
        ],
        "index_web_pages_for_search": 0,
        "istable": 1,
        "links": [],
        "modified": "2026-11-05 23:50:00.000000",
        "modified_by": "Administrator",
        "module": "Reli LIMS",
        "name": "Capability Review Log",
        "owner": "Administrator",
        "permissions": [],
        "sort_field": "creation",
        "sort_order": "DESC",
        "states": [],
    }
    dump(LOG_DOCTYPE / "capability_review_log.json", doc)


def patch_capability():
    data = json.loads(CAPABILITY.read_text(encoding="utf-8"))

    existing = {field["fieldname"] for field in data["fields"]}
    additions = [
        {"fieldname": "review_section", "fieldtype": "Section Break",
         "label": "CNAS 审核与发布", "collapsible": 1},
        {"fieldname": "demo_only", "fieldtype": "Check", "label": "演示能力（非认可）",
         "default": "0",
         "description": "勾选后该能力仅用于开发/演示，不计入 CNAS 认可范围，对外必须标注为非认可。"},
        {"fieldname": "scope_evidence_section", "fieldtype": "Column Break"},
        {"fieldname": "reviewed_by", "fieldtype": "Link", "label": "审核人",
         "options": "User", "read_only": 1},
        {"fieldname": "reviewed_on", "fieldtype": "Datetime", "label": "审核时间",
         "read_only": 1},
        {"fieldname": "published_by", "fieldtype": "Link", "label": "发布人",
         "options": "User", "read_only": 1},
        {"fieldname": "published_on", "fieldtype": "Datetime", "label": "发布时间",
         "read_only": 1},
        {"fieldname": "review_note", "fieldtype": "Small Text", "label": "最新审核意见",
         "read_only": 1},
        {"fieldname": "review_log_section", "fieldtype": "Section Break",
         "label": "审核记录"},
        {"fieldname": "review_log", "fieldtype": "Table", "label": "审核记录",
         "options": "Capability Review Log", "read_only": 1},
    ]
    for field in additions:
        if field["fieldname"] not in existing:
            data["fields"].append(field)

    order = data["field_order"]
    new_names = [field["fieldname"] for field in additions if field["fieldname"] not in order]
    if new_names:
        anchor = order.index("published") + 1 if "published" in order else len(order)
        order[anchor:anchor] = new_names

    for field in data["fields"]:
        if field["fieldname"] == "accreditation_type":
            options = field.get("options", "").splitlines()
            if "演示（非认可）" not in options:
                field["options"] = "\n".join(options + ["演示（非认可）"])
        if field["fieldname"] == "status":
            field["in_standard_filter"] = 1
        if field["fieldname"] == "laboratory":
            field["in_standard_filter"] = 1

    roles = {perm["role"] for perm in data["permissions"]}
    if "Lab Engineer" not in roles:
        data["permissions"].append({"role": "Lab Engineer", "read": 1, "print": 1, "report": 1})

    dump(CAPABILITY, data)


if __name__ == "__main__":
    build_child()
    patch_capability()
    print("capability schema patched")
