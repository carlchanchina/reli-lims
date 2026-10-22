"""Validate optional links from execution records back to confirmed intake."""
import frappe
from frappe import _


def confirmed_source(name, project):
    request = frappe.get_doc('Test Request', name)
    request.check_permission('read')
    if request.docstatus != 1 or request.project != project:
        frappe.throw(_('来源委托单必须已确认，并且属于同一项目。'))
    return request


def validate_sample_source(sample, previous):
    if previous and any(sample.get(key) != previous.get(key)
                        for key in ('test_request', 'request_sample_row')):
        frappe.throw(_('已有样品不能更改来源委托信息。'))
    if not sample.test_request and not sample.request_sample_row:
        return
    if not sample.test_request or not sample.request_sample_row:
        frappe.throw(_('必须同时填写来源委托单和委托样品行。'))
    request = confirmed_source(sample.test_request, sample.project)
    source = next((r for r in request.samples if r.name == sample.request_sample_row), None)
    if not source:
        frappe.throw(_('来源样品行不属于本委托单。'))
    if not previous and any(str(sample.get(key) or '') != str(source.get(key) or '')
                            for key in ('product_name', 'model', 'dimensions')):
        frappe.throw(_('收样记录必须保留委托时声明的产品、型号和尺寸。'))
    if not previous and float(sample.get('weight_kg') or 0) != float(source.get('weight_kg') or 0):
        frappe.throw(_('收样记录必须保留委托时声明的重量。'))


def validate_program_source(program, previous):
    if previous and program.test_request != previous.test_request:
        frappe.throw(_('已有检测方案不能更改来源委托单。'))
    if not program.test_request:
        return
    confirmed_source(program.test_request, program.project)
    for row in program.samples:
        if frappe.db.get_value('Sample', row.sample, 'test_request') != program.test_request:
            frappe.throw(_('方案样品必须来自所选委托单。'))
