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
        from reli_lims.customer_share import (customer_scope_errors, in_customer_save,
                                              prepare_customer_rows)
        customer_links = in_customer_save()
        if customer_links:
            # 客户链接保存：新增样品行没有内部编号，先补号再校验。
            prepare_customer_rows(self)
        if not self.company:
            self.company = frappe.defaults.get_user_default('Company') or frappe.defaults.get_global_default('company')
        if not self.company:
            companies = frappe.get_list('Company', pluck='name', page_length=2)
            if len(companies) == 1:
                self.company = companies[0]
        if not self.company:
            frappe.throw(_('请先设置默认公司，再创建检测委托单。'))
        if self.get('customer') and not self.get('customer_display_name'):
            self.customer_display_name = frappe.db.get_value('Customer', self.customer, 'customer_name')
        try:
            if customer_links:
                # 客户可以先保存未完成草稿，只拦会破坏数据结构的输入。
                errors = customer_scope_errors(self.as_dict())
                if errors:
                    frappe.throw(' '.join(errors))
            else:
                validate_scope(self.as_dict())
        except ValueError as exc:
            frappe.throw(scope_error_message(exc))
        previous = self.get_doc_before_save()
        for key in ('project', 'confirmed_by', 'confirmed_on'):
            if str(self.get(key) or '') != str((previous.get(key) if previous else None) or ''):
                frappe.throw(_('确认记录字段不能直接修改。'))
        if not customer_links:
            # 客户链接读取的客户/公司由 Web Form Request.doc_values 固定，
            # 不能再用实验室内部角色的读取权限作为保存前提。
            for dt, name in (('Customer', self.customer), ('Company', self.company)):
                frappe.get_doc(dt, name).check_permission('read')
        if self.get('payer_same_as_customer'):
            self.payer_customer = self.customer
        if self.get('payer_customer') and not customer_links:
            frappe.get_doc('Customer', self.payer_customer).check_permission('read')
        if self.get('report_same_as_customer'):
            self.report_company = frappe.db.get_value('Customer', self.customer, 'customer_name')
            self.report_address = self.get('applicant_address')
        assignments = self.get('sample_assignments') or []
        for row in self.items:
            row.applicable_sample_codes = ', '.join(pair.sample_code for pair in assignments
                                                    if pair.item_code == row.item_code)
        from reli_lims.request_commercial import validate_commercial_links
        validate_commercial_links(self)
        validate_photos(self)
        from reli_lims.request_confirmation import validate_confirmation
        validate_confirmation(self)

    @frappe.whitelist(methods=['POST'])
    def request_customer_confirmation(self):
        from reli_lims.request_confirmation import await_customer
        await_customer(self)

    @frappe.whitelist(methods=['POST'])
    def share_customer_attachment(self, file_id: str):
        from reli_lims.request_confirmation import share_customer_attachment
        return share_customer_attachment(self, file_id)

    @frappe.whitelist(methods=['POST'])
    def send_customer_fill_link(self, expires_days=7, customer_email=None, note=None):
        from reli_lims.customer_share import send_link
        return send_link(self.name, expires_days=expires_days, customer_email=customer_email, note=note)

    @frappe.whitelist(methods=['POST'])
    def revoke_customer_fill_link(self):
        from reli_lims.customer_share import revoke_link
        return revoke_link(self.name)

    @frappe.whitelist(methods=['POST'])
    def review_customer_fill(self, approve=1, note=None):
        from reli_lims.customer_share import lab_review
        return lab_review(self.name, approve=approve, note=note)

    def before_submit(self):
        require_role('Lab Manager')
        # Lock before side effects; native submit also checks modification/docstatus.
        stored = frappe.db.get_value('Test Request', self.name,
                                     ['docstatus', 'project'], as_dict=True, for_update=True)
        if not stored or stored.docstatus != 0 or stored.project:
            frappe.throw(_('本委托单已经确认，请勿重复确认。'))
        from reli_lims.request_submission import validate_submission
        validate_submission(self, stored)

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
