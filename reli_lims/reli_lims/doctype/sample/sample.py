import frappe
from frappe import _
from reli_lims.i18n import scope_error_message
from frappe.model.document import Document
from reli_lims.request_scope import positive_number
from reli_lims.request_provenance import validate_sample_source
from reli_lims.validation import validate_transition


class Sample(Document):
    def validate(self):
        if not self.project:
            frappe.throw(_('样品必须关联项目。'))
        try:
            positive_number(self.quantity, "Sample quantity")
        except ValueError as exc:
            frappe.throw(scope_error_message(exc))
        previous = self.get_doc_before_save()
        validate_sample_source(self, previous)
        validate_transition(previous.status if previous else 'Received', self.status, {
            'Received': ('Testing', 'Retained', 'Returned', 'Disposed'),
            'Testing': ('Completed', 'Returned', 'Disposed'),
            'Completed': ('Retained', 'Returned', 'Disposed'),
            'Retained': ('Returned', 'Disposed'), 'Returned': (), 'Disposed': ()})
        if previous and previous.project != self.project and frappe.db.exists('Test Program Sample', {'sample': self.name}):
            frappe.throw(_('已分配检测方案的样品不能更改所属项目。'))
        self.customer = frappe.db.get_value("Project", self.project, "customer")
