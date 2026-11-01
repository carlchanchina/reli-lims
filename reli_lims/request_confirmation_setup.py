"""Idempotent additions to native Test Request; no parallel business DocType."""
FIELDS = [
 {'fieldname':'customer_requirements','label':'客户需求说明','fieldtype':'Small Text'},
 {'fieldname':'customer_expected_tests','label':'客户期望检测项目','fieldtype':'Small Text'},
 {'fieldname':'customer_reference_standards','label':'客户参考标准','fieldtype':'Small Text'},
 {'fieldname':'customer_declared_conditions','label':'客户声明试验条件','fieldtype':'Small Text'},
 {'fieldname':'customer_shipping_details','label':'客户送样信息','fieldtype':'Small Text'},
 {'fieldname':'execution_company','label':'执行公司','fieldtype':'Link','options':'Company'},
 {'fieldname':'lab_intake_notes','label':'受理信息','fieldtype':'Small Text'},
 {'fieldname':'customer_confirmation_state','label':'客户确认状态','fieldtype':'Select','options':'Draft\nAwaiting Customer Confirmation\nCustomer Confirmed\nNeeds Reconfirmation\nAccepted','default':'Draft','read_only':1},
 {'fieldname':'customer_confirmed_by','label':'客户确认人','fieldtype':'Data','read_only':1},
 {'fieldname':'customer_confirmed_at','label':'客户确认时间','fieldtype':'Datetime','read_only':1},
 {'fieldname':'customer_confirmation_fingerprint','label':'客户确认版本','fieldtype':'Data','read_only':1},
]

FILE_FIELDS = [
    {'fieldname': 'reli_customer_visible', 'label': '客户可见委托附件',
     'fieldtype': 'Check', 'default': '0', 'read_only': 1},
]
FILE_HOOKS = {
    'validate': 'reli_lims.request_confirmation.validate_file_visibility',
    **{event: 'reli_lims.request_confirmation.file_changed'
       for event in ('after_insert', 'on_update', 'after_delete')},
}


def _custom_fields():
    return {'Test Request': FIELDS, 'File': FILE_FIELDS}


def _native_links():
    import json
    from pathlib import Path
    schema = json.loads((Path(__file__).parent / 'reli_lims' / 'doctype' /
                         'test_request' / 'test_request.json').read_text())
    return [field for field in schema['fields']
            if field['fieldname'] in ('quotation', 'sales_order')]


def _check_fields(doctype, fields, existing_only=False):
    import frappe
    meta = frappe.get_meta(doctype)
    errors = []
    for expected in fields:
        name = expected['fieldname']
        actual = meta.get_field(name)
        if not actual:
            if not existing_only:
                errors.append(f'{doctype}.{name}: missing')
            continue
        keys = ('fieldtype', 'options') if existing_only else (
            'fieldtype', 'options', 'read_only', 'reqd', 'default', 'no_copy')
        for key in keys:
            if key not in expected and key not in ('reqd', 'read_only'):
                continue
            value = expected.get(key, 0)
            current = actual.get(key)
            if key in ('read_only', 'reqd', 'no_copy'):
                matches = bool(current) == bool(value)
            else:
                matches = str(current or '') == str(value or '')
            if not matches:
                errors.append(f'{doctype}.{name}: incompatible {key}')
    return errors


def verify_schema():
    """Read-only deployment gate; never repairs metadata or business records."""
    import frappe
    errors = []
    for doctype, fields in _custom_fields().items():
        errors.extend(_check_fields(doctype, fields))
    links = _native_links()
    if len(links) != 2:
        errors.append('Test Request: native commercial link declarations missing')
    errors.extend(_check_fields('Test Request', links))
    file_hooks = frappe.get_hooks('doc_events', app_name='reli_lims').get('File', {})
    for event, handler in FILE_HOOKS.items():
        configured = file_hooks.get(event, [])
        if isinstance(configured, str):
            configured = [configured]
        if handler not in configured:
            errors.append(f'File.{event}: missing hook {handler}')
            continue
        try:
            if not callable(frappe.get_attr(handler)):
                errors.append(f'File.{event}: handler is not callable')
        except (ImportError, AttributeError) as error:
            errors.append(f'File.{event}: {error}')
    permissions = frappe.get_meta('Test Request').permissions
    if not any(row.get('role') == 'Lab Manager' and row.get('submit') for row in permissions):
        errors.append('Test Request: Lab Manager submit permission missing')
    if errors:
        frappe.throw('V1 schema readiness failed: ' + '; '.join(errors))
    return {'confirmation_fields': len(FIELDS), 'commercial_links': len(links),
            'file_visibility': True, 'file_hooks': len(FILE_HOOKS),
            'lab_manager_submit': True}


def after_migrate():
    import frappe
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
    conflicts = []
    for doctype, fields in _custom_fields().items():
        conflicts.extend(_check_fields(doctype, fields, existing_only=True))
    if conflicts:
        frappe.throw('V1 schema storage conflict: ' + '; '.join(conflicts))
    create_custom_fields({'Test Request': [dict(field, insert_after='report_requirements') for field in FIELDS],
                          'File': FILE_FIELDS}, update=True)
    verify_schema()
