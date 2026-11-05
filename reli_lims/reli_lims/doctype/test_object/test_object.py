import frappe
from frappe import _
from frappe.model.document import Document

from reli_lims.reli_lims.doctype.test_project.test_project import project_key


class TestObject(Document):
    def validate(self):
        self.object_name = " ".join((self.object_name or "").split()).strip()
        self.normalized_name = project_key(self.object_name)
        if not self.normalized_name:
            frappe.throw(_("请输入检测对象名称。"))

        aliases = []
        seen_aliases = set()
        other_aliases = {}
        for other in frappe.get_all(
            "Test Object", fields=["name", "normalized_name", "aliases"],
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
                "Test Object", {"normalized_name": key, "name": ["!=", self.name]}, "name"
            )
            owner = other or other_aliases.get(key)
            if owner:
                frappe.throw(_("别名“{0}”已属于检测对象 {1}。").format(alias, owner))
            aliases.append(alias)
            seen_aliases.add(key)
        self.aliases = "\n".join(aliases)
