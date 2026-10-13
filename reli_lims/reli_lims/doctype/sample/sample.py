import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class Sample(Document):
    def validate(self):
        if not self.project:
            frappe.throw(_("A Sample must belong to a Project."))
        if flt(self.quantity) <= 0:
            frappe.throw(_("Sample quantity must be greater than zero."))
        self.customer = frappe.db.get_value("Project", self.project, "customer")
