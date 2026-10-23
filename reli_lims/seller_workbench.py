"""Private read projection used only after the ERP bridge authorizes an order."""
import frappe

from reli_lims.progress import STAGES


def request_summary(request_name, company):
    request = frappe.get_doc('Test Request', request_name)
    request.check_permission('read')
    if request.company != company:
        frappe.throw('委托单不属于已授权的执行公司。', frappe.PermissionError)
    project_name = request.project if request.docstatus == 1 else None
    received = set()
    if project_name:
        project = frappe.get_doc('Project', project_name)
        project.check_permission('read')
        if project.company != company or project.customer != request.customer:
            frappe.throw('委托单与项目的归属不一致。', frappe.PermissionError)
        received = set(frappe.get_all('Sample', filters={
            'test_request': request.name, 'project': project_name,
        }, pluck='request_sample_row', limit_page_length=0))
    elif request.docstatus == 1:
        frappe.throw('已确认委托单缺少关联项目。')
    stage = '已取消' if request.docstatus == 2 else (
        '待确认' if request.docstatus == 0 else request.business_stage)
    if stage not in (*STAGES, '已取消'):
        frappe.throw('委托单履约阶段无效，请联系实验室核查。')
    expected = {row.name for row in request.samples}
    return {
        'request': request.name, 'title': request.title, 'docstatus': request.docstatus,
        'project': project_name, 'stage': stage,
        'delivery_date': str(request.delivery_date) if request.delivery_date else None,
        'updated_at': str(request.modified), 'declared_samples': len(expected),
        'received_samples': len(expected.intersection(received)),
    }
