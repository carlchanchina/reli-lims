"""Explicit, transactional conversion of a confirmed laboratory request."""
import frappe
from frappe import _
from reli_lims.i18n import scope_error_message

from reli_lims.request_scope import program_data, receipt_data, same_receipt
from reli_lims.services.request_files import copy_sample_photos
from reli_lims.validation import require_role


def create_project(request):
    """Called only inside the native request submission transaction."""
    frappe.get_doc('Customer', request.customer).check_permission('read')
    frappe.get_doc('Company', request.company).check_permission('read')
    project = frappe.get_doc(dict(doctype='Project',
        project_name=f'{request.name} - {request.title}', customer=request.customer,
        company=request.company, expected_end_date=request.delivery_date, status='Open')).insert()
    return project.name


def _confirmed_request(name):
    require_role('Lab Manager', 'Lab Engineer')
    request = frappe.get_doc('Test Request', name)
    request.check_permission('read')
    frappe.db.get_value('Test Request', name, 'name', for_update=True)
    request.reload()
    if request.docstatus != 1 or not request.project:
        frappe.throw(_('Confirm the testing request before receiving samples or making a program.'))
    frappe.get_doc('Project', request.project).check_permission('read')
    return request


@frappe.whitelist()
def receive_samples(request_name, receipts):
    request = _confirmed_request(request_name)
    receipts = frappe.parse_json(receipts) if isinstance(receipts, str) else receipts
    if not isinstance(receipts, list) or not receipts:
        frappe.throw(_('Select at least one sample to receive.'))
    rows = {r.sample_code: r for r in request.samples}
    seen, result = set(), []
    for receipt in receipts:
        if not isinstance(receipt, dict):
            frappe.throw(_('Invalid sample receipt.'))
        code = receipt.get('sample_code')
        if code not in rows or code in seen:
            frappe.throw(_('Select each sample from this request only once.'))
        seen.add(code)
        row = rows[code]
        try:
            values = receipt_data(row.as_dict(), receipt)
        except ValueError as exc:
            frappe.throw(scope_error_message(exc))
        frappe.get_doc('User', values['received_by']).check_permission('read')
        existing = frappe.db.get_value('Sample', {'request_sample_row': row.name}, 'name')
        if existing:
            sample = frappe.get_doc('Sample', existing)
            sample.check_permission('read')
            if sample.project != request.project or sample.test_request != request.name:
                frappe.throw(_('The received sample has inconsistent request provenance.'))
            # Repeating the same receipt is safe; different facts cannot overwrite it.
            if not same_receipt(sample.as_dict(), values):
                frappe.throw(_('This sample has already been received with different details.'))
        else:
            sample = frappe.get_doc(dict(doctype='Sample', project=request.project,
                test_request=request.name, request_sample_row=row.name, **values)).insert()
            copy_sample_photos(request, code, sample)
        result.append(sample.name)
    return result


@frappe.whitelist()
def make_test_program(request_name):
    request = _confirmed_request(request_name)
    existing = frappe.db.get_value('Test Program', {'test_request': request.name}, 'name')
    if existing:
        program = frappe.get_doc('Test Program', existing)
        program.check_permission('read')
        if program.project != request.project:
            frappe.throw(_('The program belongs to a different Project.'))
        return program.name
    samples = frappe.get_all('Sample', filters={'test_request': request.name},
                             fields=['name', 'request_sample_row', 'project'])
    by_row = {}
    for sample in samples:
        frappe.get_doc('Sample', sample.name).check_permission('read')
        if sample.project != request.project:
            frappe.throw(_('The received sample belongs to a different Project.'))
        by_row[sample.request_sample_row] = sample.name
    names = {r.sample_code: by_row[r.name] for r in request.samples if r.name in by_row}
    try:
        values = program_data(request.as_dict(), names)
    except ValueError as exc:
        frappe.throw(scope_error_message(exc))
    return frappe.get_doc(values).insert().name


@frappe.whitelist()
def get_receivable_samples(request_name):
    request = _confirmed_request(request_name)
    received = set(frappe.get_all('Sample', filters={'test_request': request.name},
                                 pluck='request_sample_row'))
    return [dict(sample_code=row.sample_code, product_name=row.product_name, quantity=row.quantity)
            for row in request.samples if row.name not in received]
