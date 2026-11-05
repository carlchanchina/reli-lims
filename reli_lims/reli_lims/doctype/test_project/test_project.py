import json
import unicodedata

import frappe
from frappe import _
from frappe.model.document import Document


def project_key(value):
    return " ".join(unicodedata.normalize("NFKC", value or "").split()).casefold()


def validate_condition_template(value):
    if not value:
        return []
    template = json.loads(value) if isinstance(value, str) else value
    if not isinstance(template, list):
        frappe.throw(_("检测条件模板必须是字段数组。"))
    seen = set()
    for index, field in enumerate(template, start=1):
        if not isinstance(field, dict):
            frappe.throw(_("检测条件模板第 {0} 项必须是对象。").format(index))
        key = str(field.get("key") or "").strip()
        label = str(field.get("label") or "").strip()
        fieldtype = field.get("type")
        if not key or not label:
            frappe.throw(_("检测条件模板第 {0} 项缺少 key 或 label。").format(index))
        if key in seen:
            frappe.throw(_("检测条件模板的 key 不能重复。"))
        if fieldtype not in {"text", "number", "select"}:
            frappe.throw(_("检测条件模板第 {0} 项类型无效。").format(index))
        if fieldtype == "select" and (
            not isinstance(field.get("options"), list) or not field["options"]
        ):
            frappe.throw(_("下拉条件必须提供选项。"))
        seen.add(key)
    return template


class TestProject(Document):
    def validate(self):
        self.project_name = (self.project_name or "").strip()
        self.normalized_name = project_key(self.project_name)
        if not self.normalized_name:
            frappe.throw(_("请输入项目中文名称。"))

        aliases = []
        seen_aliases = set()
        other_aliases = {}
        for other in frappe.get_all(
            "Test Project", fields=["name", "normalized_name", "aliases"],
            filters={"name": ["!=", self.name]},
        ):
            for alias in (other.aliases or "").splitlines():
                key = project_key(alias)
                if key:
                    other_aliases[key] = other.name
        for value in (self.aliases or "").splitlines():
            alias = " ".join(value.split()).strip()
            key = project_key(alias)
            if not key or key == self.normalized_name or key in seen_aliases:
                continue
            other = frappe.db.get_value(
                "Test Project", {"normalized_name": key, "name": ["!=", self.name]}, "name"
            )
            owner = other or other_aliases.get(key)
            if owner:
                frappe.throw(_("别名“{0}”已属于检测项目 {1}。").format(alias, owner))
            aliases.append(alias)
            seen_aliases.add(key)
        self.aliases = "\n".join(aliases)
        self.condition_template = json.dumps(
            validate_condition_template(self.condition_template), ensure_ascii=False
        )
        self._validate_relations()

    def _validate_relations(self):
        standards, objects = set(), set()
        for row in self.standards:
            if not row.test_standard:
                frappe.throw(_("检测依据行不能为空。"))
            if row.test_standard in standards:
                frappe.throw(_("同一检测依据不能重复关联。"))
            standards.add(row.test_standard)
        for row in self.objects:
            if not row.test_object:
                frappe.throw(_("检测对象行不能为空。"))
            if row.test_object in objects:
                frappe.throw(_("同一检测对象不能重复关联。"))
            objects.add(row.test_object)
