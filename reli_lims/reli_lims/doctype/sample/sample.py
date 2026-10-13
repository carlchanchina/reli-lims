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
        previous = self.get_doc_before_save()
        if previous and previous.project != self.project and frappe.db.exists('Test Program Sample', {'sample': self.name}):
            frappe.throw(_("A sample assigned to a Test Program cannot change Project."))
        self.customer = frappe.db.get_value("Project", self.project, "customer")
