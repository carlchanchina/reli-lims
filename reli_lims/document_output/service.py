"""Authorized source → mapping → file template → renderer → private attachment."""
import re
import frappe

from .registry import get_template, MIME_TYPES
from .mapping import quotation, commission, test_report


def source_document(doctype: str, name: str, output_format: str = 'pdf'):
    doc = frappe.get_doc(doctype, name)
    doc.check_permission('read')
    doc.check_permission('print')
    if output_format == 'xlsx':
        doc.check_permission('export')
    doc.apply_fieldlevel_read_permissions()
    return doc


def label_items(data):
    cache = {}
    for row in data.get('items') or []:
        for field, doctype, display in (('test_method', 'Test Method', 'method_name'),
                                         ('standard', 'Test Standard', 'full_name')):
            name = row.get(field)
            if not name:
                continue
            key = (doctype, name)
            if key not in cache:
                linked = frappe.get_doc(doctype, name)
                linked.check_permission('read')
                linked.apply_fieldlevel_read_permissions()
                cache[key] = linked.as_dict().get(display) or name
            row[field + '_label'] = cache[key]
    return data


def build_context(doc):
    data = doc.as_dict()
    if doc.doctype == 'Quotation':
        return quotation.build_context(data)
    if doc.doctype == 'Test Request':
        return commission.build_context(label_items(data))
    program = source_document('Test Program', data.get('test_program'))
    return test_report.build_context(data, label_items(program.as_dict()))


def render_document(spec, context: dict, output_format: str) -> bytes:
    from .renderers import pdf_renderer, docx_renderer, xlsx_renderer
    renderer = {'pdf': pdf_renderer, 'docx': docx_renderer, 'xlsx': xlsx_renderer}[output_format]
    return renderer.render(spec, context)


def generate_document(doctype: str, name: str, template: str | None = None,
                      output_format: str = 'pdf') -> dict:
    spec = get_template(doctype, template)
    if output_format not in spec.formats:
        raise ValueError('不支持的输出格式。')
    doc = source_document(doctype, name, output_format)
    context = build_context(doc)
    content = render_document(spec, context, output_format)
    safe_name = re.sub(r'[^\w.\-\u4e00-\u9fff]', '_', name)[:100]
    filename = f'{spec.title}-{safe_name}.{output_format}'
    from frappe.utils.file_manager import save_file
    file = save_file(filename, content, doctype, name, is_private=1)
    return dict(file_name=file.file_name, file_url=file.file_url, file_id=file.name,
                mime_type=MIME_TYPES[output_format], template=spec.title, output_format=output_format)
