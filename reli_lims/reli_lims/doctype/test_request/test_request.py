import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

from reli_lims.request_scope import validate_scope
from reli_lims.services.request_files import validate_photos
from reli_lims.validation import require_role


class TestRequest(Document):
    def validate(self):
        try:
            validate_scope(self.as_dict())
        except ValueError as exc:
            frappe.throw(str(exc))
        previous = self.get_doc_before_save()
        for key in ('project', 'confirmed_by', 'confirmed_on'):
            if str(self.get(key) or '') != str((previous.get(key) if previous else None) or ''):
                frappe.throw(_('Confirmation fields cannot be edited directly.'))
        for dt, name in (('Customer', self.customer), ('Company', self.company)):
            frappe.get_doc(dt, name).check_permission('read')
        if self.get('payer_same_as_customer'):
            self.payer_customer = self.customer
        if self.get('payer_customer'):
            frappe.get_doc('Customer', self.payer_customer).check_permission('read')
        if self.get('report_same_as_customer'):
            self.report_company = frappe.db.get_value('Customer', self.customer, 'customer_name')
            self.report_address = self.get('applicant_address')
        assignments = self.get('sample_assignments') or []
        for row in self.items:
            row.applicable_sample_codes = ', '.join(pair.sample_code for pair in assignments
                                                    if pair.item_code == row.item_code)
        validate_photos(self)

    def before_submit(self):
        require_role('Lab Manager')
        # Lock before side effects; native submit also checks modification/docstatus.
        stored = frappe.db.get_value('Test Request', self.name,
                                     ['docstatus', 'project'], as_dict=True, for_update=True)
        if not stored or stored.docstatus != 0 or stored.project:
            frappe.throw(_('This request has already been confirmed.'))

    def on_submit(self):
        from reli_lims.services.test_request import create_project
        project = create_project(self)
        self.db_set({'project': project, 'confirmed_by': frappe.session.user,
                     'confirmed_on': now_datetime()}, update_modified=False)

    def before_update_after_submit(self):
        frappe.throw(_("Confirmed testing request content is frozen."))

    def before_cancel(self):
        frappe.throw(_('Confirmed testing requests cannot be cancelled in this version.'))

    def on_trash(self):
        if self.docstatus:
            frappe.throw(_('Confirmed testing requests cannot be deleted.'))
