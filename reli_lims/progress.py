"""One overall business stage; internal execution states stay independent."""

STAGES = ('待确认', '待收样', '已收样', '待试验', '试验中', '待报告', '报告审核', '已完成')


def business_stage(docstatus, expected, received, item_states, report_states):
    if docstatus != 1:
        return '待确认'
    if received < expected:
        return '待收样'
    if not item_states:
        return '已收样'
    if any(state in ('Running', 'Completed', 'Reviewed') for state in item_states):
        if any(state != 'Reviewed' for state in item_states):
            return '试验中'
    else:
        return '待试验'
    if 'Issued' in report_states:
        return '已完成'
    if any(state in ('Review', 'Approved') for state in report_states):
        return '报告审核'
    return '待报告'


def overdue(stage, delivery_date, current_date, docstatus=1):
    return int(docstatus != 2 and stage != '已完成' and bool(delivery_date)
               and str(delivery_date)[:10] < str(current_date))


def refresh_request(name):
    """Only server lifecycle hooks call this; no privileged public API."""
    import frappe
    frappe.db.get_value('Test Request', name, 'name', for_update=True)
    request = frappe.get_doc('Test Request', name)
    received = frappe.get_all('Sample', filters={'test_request': name}, pluck='request_sample_row')
    expected = {row.name for row in request.samples}
    programs = frappe.get_all('Test Program', filters={'test_request': name, 'status': ['!=', 'Cancelled']}, pluck='name')
    states = frappe.get_all('Test Program Item', filters={'parent': ['in', programs],
        'parenttype': 'Test Program'}, pluck='status') if programs else []
    reports = frappe.get_all('Test Report', filters={'test_program': ['in', programs]}, pluck='status') if programs else []
    stage = business_stage(request.docstatus, len(expected), len(expected.intersection(received)), states, reports)
    # A report for one program must not complete other unfinished/unreported programs.
    if stage == '已完成' and any(not frappe.db.exists('Test Report', {'test_program': p, 'status': 'Issued'}) for p in programs):
        stage = '待报告'
    values = dict(business_stage=stage,
        overdue_status='超期' if overdue(stage, request.delivery_date, frappe.utils.today(), request.docstatus) else '',
        sample_summary='、'.join(row.product_name or '' for row in request.samples)[:140],
        test_summary='、'.join(dict.fromkeys(frappe.db.get_value('Test Method', row.test_method, 'method_name') or row.test_method for row in request.items))[:140])
    frappe.db.set_value('Test Request', name, values, update_modified=False)


def update_progress(doc, method=None):
    import frappe
    name = doc.name if doc.doctype == 'Test Request' else doc.get('test_request')
    if name and frappe.db.exists('Test Request', name):
        refresh_request(name)


def refresh_all():
    import frappe
    for name in frappe.get_all('Test Request', pluck='name'):
        refresh_request(name)
