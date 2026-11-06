"""Native pre-submit guard; Project creation remains in the existing on_submit."""
def confirmation_error(data, current, missing, states=('Customer Confirmed', 'Lab Reviewed')):
    if data.get('docstatus') != 0:
        return '只能正式受理未提交的检测委托。'
    if data.get('customer_confirmation_state') not in states:
        return '请先取得当前委托内容的客户确认。'
    if not data.get('customer_confirmed_by') or not data.get('customer_confirmed_at') or data.get('customer_confirmation_fingerprint') != current:
        return '客户确认已失效，请客户重新确认。'
    if missing:
        return '客户委托资料不完整：' + ', '.join(missing)


def validate_submission(doc, stored):
    import frappe
    from reli_lims.request_confirmation import current_fingerprint, confirmation_blockers
    from reli_lims.request_commercial import validate_commercial_links
    # During native before_submit the in-memory docstatus is already 1;
    # the locked database row must still be Draft.
    from reli_lims.customer_share import LEGACY_SUBMITTABLE_STATES, SUBMITTABLE_STATES, has_share
    data=doc.as_dict();data['docstatus']=stored.docstatus
    # 走客户共同填写的委托必须完成实验室审核；未启用该流程的历史委托保持原行为。
    request_name = doc.get('name') if hasattr(doc, 'get') else getattr(doc, 'name', None)
    states = SUBMITTABLE_STATES if request_name and has_share(request_name) else LEGACY_SUBMITTABLE_STATES
    error=confirmation_error(data,current_fingerprint(doc),confirmation_blockers(doc),states)
    if error:frappe.throw(error)
    validate_commercial_links(doc)
    customer=frappe.get_doc('Customer',doc.customer)
    company=frappe.get_doc('Company',doc.company)
    if customer.get('disabled') or company.get('disabled'):
        frappe.throw('委托单位或公司已停用，不能正式受理。')
    if not doc.get('quotation') and not doc.get('sales_order'):
        frappe.throw('正式受理必须关联有效的原生客户报价或销售订单。')
    quotation=frappe.get_doc('Quotation',doc.quotation) if doc.get('quotation') else {}
    if quotation.get('status') in ('Lost','Expired','Cancelled','Closed') or (quotation.get('valid_till') and str(quotation.valid_till)[:10]<frappe.utils.today()):
        frappe.throw('报价已失效，请内部复核商业来源。')

    validate_execution_scope(doc)


def validate_execution_scope(doc):
    """Only formal intake requires active technical masters; drafts stay editable."""
    import frappe
    projects, methods, standards = set(), set(), set()
    for item in doc.items:
        project, method, standard = item.get('test_project'), item.get('test_method'), item.get('standard')
        if not (project or method) or not standard:
            frappe.throw('请内部补齐检测项目和标准后再正式受理。')
        if project:
            projects.add(project)
        if method:
            methods.add(method)
        standards.add(standard)
    if not projects and not methods:
        frappe.throw('请内部补齐检测项目和标准后再正式受理。')
    for name in sorted(methods):
        method = frappe.db.get_value('Test Method', name, ['active', 'test_project'], as_dict=True, for_update=True)
        if not method:
            frappe.throw('兼容检测项目不存在，不能正式受理。')
        if method.get('test_project'):
            projects.add(method['test_project'])
        elif method.get('active') != 1:
            frappe.throw('兼容检测项目未启用，不能正式受理。')
    for name in sorted(projects):
        project = frappe.db.get_value('Test Project', name, ['active'], as_dict=True, for_update=True)
        if not project or project.get('active') != 1:
            frappe.throw('检测项目未启用，不能正式受理。')
    for name in sorted(standards):
        standard = frappe.db.get_value('Test Standard', name, ['status'], as_dict=True, for_update=True)
        if not standard or standard.get('status') != 'Active':
            frappe.throw('检测标准尚未审核启用，请实验室负责人确认适用标准后再正式受理。')
