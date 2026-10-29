"""Cross-DocType output endpoints; no guest access or arbitrary template paths."""
import frappe
from .registry import get_template
from .service import source_document, generate_document as generate


@frappe.whitelist(methods=['POST'])
def generate_document(doctype: str, name: str, template: str | None = None,
                      output_format: str = 'pdf') -> dict:
    return generate(doctype, name, template, output_format)


@frappe.whitelist(methods=['GET', 'POST'])
def get_templates(doctype: str, name: str) -> list:
    spec = get_template(doctype)
    source_document(doctype, name)
    return [dict(name=spec.key, label=spec.title, formats=list(spec.formats), default_format='pdf')]
