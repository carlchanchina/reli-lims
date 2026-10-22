import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import today

from reli_lims.validation import field_values, require_role, validate_transition


TRANSITIONS = {'Draft': ('Review',), 'Review': ('Approved',),
               'Approved': ('Issued',), 'Issued': ()}


class TestReport(Document):
    def validate(self):
        previous = self.get_doc_before_save()
        validate_transition(previous.status if previous else 'Draft', self.status, TRANSITIONS)
        program = frappe.get_doc('Test Program', self.test_program)
        source = program.get('test_request')
        if self.test_request and self.test_request != source:
            frappe.throw(_('报告的来源委托单必须与检测方案一致。'))
        self.test_request = source
        if self.project != program.project:
            frappe.throw(_('报告与检测方案必须属于同一项目。'))
        self.customer = frappe.db.get_value('Project', self.project, 'customer')
        if previous and previous.status == 'Approved':
            if field_values(self, ('status', 'issued_date', 'pdf_file')) != field_values(previous, ('status', 'issued_date', 'pdf_file')):
                frappe.throw(_('已批准报告的内容不能修改。'))
            if self.pdf_file != previous.pdf_file:
                require_role('Lab Manager')
        if previous and previous.status in ('Issued', 'Revised'):
            if field_values(self, ('status',)) != field_values(previous, ('status',)):
                frappe.throw(_('已签发报告不能修改，请建立新的报告版本。'))
            if self.status != previous.status:
                require_role('Lab Manager')
        if self.status != 'Draft':
            if program.status == 'Cancelled' or not program.items or any(row.status != 'Reviewed' for row in program.items):
                frappe.throw(_('报告编制完成或签发前，所有检测项目必须完成复核。'))
            if not (self.overall_conclusion or '').strip():
                frappe.throw(_('请填写总体结论。'))
        if self.status == 'Approved' and (not previous or previous.status != 'Approved'):
            require_role('Lab Reviewer', 'Lab Manager')
            self.reviewer = frappe.session.user
            self.approver = frappe.session.user  # legacy audit compatibility; no third approval step
        if self.status == 'Issued' and (not previous or previous.status != 'Issued'):
            require_role('Lab Manager')
            if not self.reviewer or not self.pdf_file:
                frappe.throw(_('已批准报告须有审核人和最终 PDF 才能签发。'))
            if not frappe.db.exists('File', {'file_url': self.pdf_file, 'is_private': 1,
                                             'attached_to_doctype': 'Test Report', 'attached_to_name': self.name}):
                frappe.throw(_('签发前请将最终 PDF 作为本报告的私有附件上传。'))
            if not self.pdf_file.lower().endswith('.pdf'):
                frappe.throw(_('最终报告文件必须为 PDF。'))
            self.issued_date = today()
        elif previous:
            self.issued_date = previous.issued_date
        else:
            self.issued_date = None

    def on_trash(self):
        if self.status in ('Issued', 'Revised'):
            frappe.throw(_('已签发或已修订的报告不能删除。'))
