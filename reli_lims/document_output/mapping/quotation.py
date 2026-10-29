"""ERPNext Quotation snapshot; monetary values come from ERPNext calculations."""
from .common import context, plain, text
from ..registry import TEMPLATES


def build_context(doc):
    currency = text(doc.get('currency'))
    money = lambda key: f"{text(doc.get(key))} {currency}".strip()
    fields = [('客户', doc.get('customer_name') or doc.get('party_name')),
              ('报价日期', doc.get('transaction_date')), ('有效期', doc.get('valid_till')),
              ('报价公司', doc.get('company')), ('币种', currency),
              ('明细合计', money('total')), ('净额', money('net_total')),
              ('税费', money('total_taxes_and_charges')), ('价税合计', money('grand_total'))]
    rows = [[i, r.get('item_name') or r.get('item_code'), r.get('uom'), r.get('rate'), r.get('qty'), r.get('amount')]
            for i, r in enumerate(doc.get('items') or [], 1)]
    result = context('检测报价单', doc, fields, TEMPLATES['Quotation'].columns, rows,
                     notice='已取消' if doc.get('docstatus') == 2 else ('草稿' if doc.get('docstatus', 0) == 0 else '报价单输出副本'))
    result.update(customer=text(doc.get('customer_name') or doc.get('party_name')),
                  contact=text(doc.get('contact_display')), address=plain(doc.get('address_display')),
                  phone=text(doc.get('contact_mobile') or doc.get('contact_phone')),
                  company=text(doc.get('company')), company_address=plain(doc.get('company_address_display')),
                  date=text(doc.get('transaction_date')), currency=currency,
                  total=doc.get('grand_total') or 0, terms=plain(doc.get('terms')),
                  totals='；'.join(f'{label}：{value}' for label, value in fields[5:]))
    return result
