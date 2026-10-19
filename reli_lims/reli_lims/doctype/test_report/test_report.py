import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import today

from reli_lims.validation import field_values, require_role, validate_transition


TRANSITIONS = {'Draft': ('Engineering Complete',), 'Engineering Complete': ('Review',),
               'Review': ('Approved',), 'Approved': ('Issued',), 'Issued': ('Revised',), 'Revised': ()}


class TestReport(Document):
    def validate(self):
        previous = self.get_doc_before_save()
        validate_transition(previous.status if previous else 'Draft', self.status, TRANSITIONS)
        program = frappe.get_doc('Test Program', self.test_program)
        source = program.get('test_request')
        if self.test_request and self.test_request != source:
            frappe.throw(_('The report request must match its Test Program.'))
        self.test_request = source
        if self.project != program.project:
            frappe.throw(_('Report and program must belong to the same Project.'))
        self.customer = frappe.db.get_value('Project', self.project, 'customer')
        if previous and previous.status == 'Approved':
            if field_values(self, ('status', 'issued_date', 'pdf_file')) != field_values(previous, ('status', 'issued_date', 'pdf_file')):
                frappe.throw(_("Approved report content cannot change."))
            if self.pdf_file != previous.pdf_file:
                require_role('Lab Manager')
        if previous and previous.status in ('Issued', 'Revised'):
            if field_values(self, ('status',)) != field_values(previous, ('status',)):
                frappe.throw(_('Issued report content is immutable; create a new report version.'))
            if self.status != previous.status:
                require_role('Lab Manager')
        if self.status != 'Draft':
            if program.status == 'Cancelled' or not program.items or any(row.status != 'Reviewed' for row in program.items):
                frappe.throw(_('All program items must be Reviewed before report completion or issue.'))
            if not (self.overall_conclusion or '').strip():
                frappe.throw(_('An overall conclusion is required.'))
        if self.status == 'Approved' and (not previous or previous.status != 'Approved'):
            require_role('Lab Manager')
            if not self.reviewer:
                frappe.throw(_('Assign a reviewer before approval.'))
            self.approver = frappe.session.user
        if self.status == 'Issued' and (not previous or previous.status != 'Issued'):
            require_role('Lab Manager')
            if not self.approver or not self.pdf_file:
                frappe.throw(_('Approved reports need an approver and PDF before issue.'))
            if not frappe.db.exists('File', {'file_url': self.pdf_file, 'is_private': 1,
                                             'attached_to_doctype': 'Test Report', 'attached_to_name': self.name}):
                frappe.throw(_('Attach the final PDF as a private file to this report before issue.'))
            if not self.pdf_file.lower().endswith('.pdf'):
                frappe.throw(_('The final report file must be a PDF.'))
            self.issued_date = today()
        elif previous:
            self.issued_date = previous.issued_date
        else:
            self.issued_date = None

    def on_trash(self):
        if self.status in ('Issued', 'Revised'):
            frappe.throw(_('Issued or revised reports cannot be deleted.'))
