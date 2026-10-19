import frappe
from frappe import _
from reli_lims.i18n import scope_error_message
from frappe.model.document import Document
from reli_lims.request_scope import positive_number
from reli_lims.request_provenance import validate_sample_source


class Sample(Document):
    def validate(self):
        if not self.project:
            frappe.throw(_("A Sample must belong to a Project."))
        try:
            positive_number(self.quantity, "Sample quantity")
        except ValueError as exc:
            frappe.throw(scope_error_message(exc))
        previous = self.get_doc_before_save()
        validate_sample_source(self, previous)
        if previous and previous.project != self.project and frappe.db.exists('Test Program Sample', {'sample': self.name}):
            frappe.throw(_("A sample assigned to a Test Program cannot change Project."))
        self.customer = frappe.db.get_value("Project", self.project, "customer")
