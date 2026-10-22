import frappe
from frappe import _
from reli_lims.i18n import scope_error_message
from frappe.model.document import Document
from frappe.utils import now_datetime

from reli_lims.request_scope import validate_scope
from reli_lims.services.request_files import validate_photos
from reli_lims.validation import require_role


class TestRequest(Document):
    def validate(self):
        if not self.company:
            self.company = frappe.defaults.get_user_default('Company') or frappe.defaults.get_global_default('company')
        if not self.company:
            companies = frappe.get_list('Company', pluck='name', page_length=2)
            if len(companies) == 1:
                self.company = companies[0]
        if not self.company:
            frappe.throw(_('请先设置默认公司，再创建检测委托单。'))
        try:
            validate_scope(self.as_dict())
        except ValueError as exc:
            frappe.throw(scope_error_message(exc))
        previous = self.get_doc_before_save()
        for key in ('project', 'confirmed_by', 'confirmed_on'):
            if str(self.get(key) or '') != str((previous.get(key) if previous else None) or ''):
                frappe.throw(_('确认记录字段不能直接修改。'))
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
            frappe.throw(_('本委托单已经确认，请勿重复确认。'))

    def on_submit(self):
        from reli_lims.services.test_request import create_project
        project = create_project(self)
        self.db_set({'project': project, 'confirmed_by': frappe.session.user,
                     'confirmed_on': now_datetime()}, update_modified=False)

    def before_update_after_submit(self):
        frappe.throw(_('已确认的检测委托内容不可修改。'))

    def before_cancel(self):
        frappe.throw(_('当前版本不支持取消已确认的检测委托单。'))

    def on_trash(self):
        if self.docstatus:
            frappe.throw(_('已确认的检测委托单不能删除。'))
