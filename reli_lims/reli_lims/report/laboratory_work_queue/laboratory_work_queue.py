"""Native task report: parent permissions first, then child-row assignment scope."""
import frappe
from frappe import _

VIEWS = {
    '我的待执行': {'Lab Engineer', 'Lab Manager'},
    '我的进行中': {'Lab Engineer', 'Lab Manager'},
    '我的待补结果': {'Lab Engineer', 'Lab Manager'},
    '待复核结果': {'Lab Reviewer', 'Lab Manager'},
    '待分配任务': {'Lab Manager'},
}


def select_rows(rows, view, user):
    result = []
    for row in rows:
        status = row.get('status')
        mine = row.get('engineer') == user
        include = {
            '我的待执行': mine and status in ('Pending', 'Ready'),
            '我的进行中': mine and status == 'Running',
            '我的待补结果': mine and status == 'Running' and (
                not row.get('result') or not row.get('conclusion')),
            '待复核结果': status == 'Completed',
            '待分配任务': not row.get('engineer') and status in ('Pending', 'Ready'),
        }.get(view, False)
        if include:
            result.append(row)
    return result


def execute(filters=None):
    filters = frappe._dict(filters or {})
    roles = set(frappe.get_roles())
    view = filters.get('view') or ('待分配任务' if 'Lab Manager' in roles else
                                 '待复核结果' if 'Lab Reviewer' in roles else '我的待执行')
    if view not in VIEWS or not roles.intersection(VIEWS[view]):
        frappe.throw(_('没有权限查看此任务队列。'), frappe.PermissionError)
    # Never accept an engineer/user supplied by the browser as identity.
    parent_filters = {'status': ['!=', 'Cancelled']}
    if filters.get('test_program'):
        parent_filters['name'] = filters.test_program
    parents = frappe.get_list('Test Program', filters=parent_filters,
                             pluck='name', limit_page_length=501, order_by='name')
    if len(parents) > 500:
        frappe.throw(_('可见方案超过500个，请先指定试验方案。'))
    rows = frappe.get_all('Test Program Item', filters={
        'parent': ['in', parents], 'parenttype': 'Test Program', 'parentfield': 'items'},
        fields=['parent', 'item_code', 'test_method', 'standard', 'engineer', 'status',
                'result', 'conclusion', 'planned_start', 'planned_end'],
        order_by='parent, idx', limit_page_length=0) if parents else []
    data = select_rows(rows, view, frappe.session.user)
    columns = [
        {'fieldname': 'parent', 'label': _('试验方案'), 'fieldtype': 'Link', 'options': 'Test Program', 'width': 170},
        {'fieldname': 'item_code', 'label': _('检测项目编号'), 'fieldtype': 'Data', 'width': 120},
        {'fieldname': 'test_method', 'label': _('检测项目'), 'fieldtype': 'Link', 'options': 'Test Method', 'width': 150},
        {'fieldname': 'standard', 'label': _('执行标准'), 'fieldtype': 'Link', 'options': 'Test Standard', 'width': 150},
        {'fieldname': 'engineer', 'label': _('工程师'), 'fieldtype': 'Link', 'options': 'User', 'width': 160},
        {'fieldname': 'status', 'label': _('状态'), 'fieldtype': 'Data', 'width': 100},
        {'fieldname': 'planned_end', 'label': _('计划结束'), 'fieldtype': 'Datetime', 'width': 160},
    ]
    # Internal result/conclusion determine the queue but are not exposed as columns.
    return columns, [{key: row.get(key) for key in
                     ('parent', 'item_code', 'test_method', 'standard', 'engineer', 'status', 'planned_end')}
                    for row in data]
