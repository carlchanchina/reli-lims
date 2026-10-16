"""Validate optional links from execution records back to confirmed intake."""
import frappe
from frappe import _


def confirmed_source(name, project):
    request = frappe.get_doc('Test Request', name)
    request.check_permission('read')
    if request.docstatus != 1 or request.project != project:
        frappe.throw(_('The source request must be confirmed and belong to the same Project.'))
    return request


def validate_sample_source(sample, previous):
    if previous and any(sample.get(key) != previous.get(key)
                        for key in ('test_request', 'request_sample_row')):
        frappe.throw(_('An existing sample cannot change its request provenance.'))
    if not sample.test_request and not sample.request_sample_row:
        return
    if not sample.test_request or not sample.request_sample_row:
        frappe.throw(_('Both request and source sample row are required.'))
    request = confirmed_source(sample.test_request, sample.project)
    source = next((r for r in request.samples if r.name == sample.request_sample_row), None)
    if not source:
        frappe.throw(_('The source sample row does not belong to this request.'))
    if not previous and any(str(sample.get(key) or '') != str(source.get(key) or '')
                            for key in ('product_name', 'model', 'dimensions')):
        frappe.throw(_('New received samples must retain the declared product, model and dimensions.'))


def validate_program_source(program, previous):
    if previous and program.test_request != previous.test_request:
        frappe.throw(_('An existing program cannot change its source request.'))
    if not program.test_request:
        return
    confirmed_source(program.test_request, program.project)
    for row in program.samples:
        if frappe.db.get_value('Sample', row.sample, 'test_request') != program.test_request:
            frappe.throw(_('Program samples must originate from the selected request.'))
