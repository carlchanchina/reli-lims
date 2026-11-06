"""ERPNext Quotation snapshot; monetary values come from ERPNext calculations."""
import json

import frappe

from .common import context, plain, text
from ..registry import TEMPLATES


def service_display(row):
    name = row.get('item_name')
    if row.get('custom_reli_test_project'):
        name = frappe.db.get_value(
            'Test Project', row.get('custom_reli_test_project'), 'project_name'
        ) or name
    name = name or row.get('item_code')
    if not row.get('custom_reli_capability'):
        return name
    from reli_lims.capability_quotation import description
    config = row.get('custom_reli_configuration')
    if isinstance(config, str):
        config = json.loads(config)
    technical = plain(description(config)) if config else plain(row.get('description'))
    return '\n'.join(filter(None, [text(name), technical]))


def build_context(doc):
    currency = text(doc.get('currency'))
    money = lambda key: f"{text(doc.get(key))} {currency}".strip()
    fields = [('客户', doc.get('customer_name') or doc.get('party_name')),
              ('报价日期', doc.get('transaction_date')), ('有效期', doc.get('valid_till')),
              ('报价公司', doc.get('company')), ('币种', currency),
              ('承诺交期', doc.get('custom_reli_delivery_date')),
              ('明细合计', money('total')), ('净额', money('net_total')),
              ('税费', money('total_taxes_and_charges')), ('价税合计', money('grand_total'))]
    rows = [[i, service_display(r), r.get('uom'), r.get('rate'), r.get('qty'), r.get('amount')]
            for i, r in enumerate(doc.get('items') or [], 1)]
    result = context('检测报价单', doc, fields, TEMPLATES['Quotation'].columns, rows,
                     notice='已取消' if doc.get('docstatus') == 2 else ('草稿' if doc.get('docstatus', 0) == 0 else '报价单输出副本'))
    result.update(customer=text(doc.get('customer_name') or doc.get('party_name')),
                  contact=text(doc.get('contact_display')), address=plain(doc.get('address_display')),
                  phone=text(doc.get('contact_mobile') or doc.get('contact_phone')),
                  company=text(doc.get('company')), company_address=plain(doc.get('company_address_display')),
                  date=text(doc.get('transaction_date')), currency=currency,
                  total=doc.get('grand_total') or 0, terms=plain(doc.get('terms')),
                  totals='；'.join(f'{label}：{value}' for label, value in fields[7:]))
    return result
