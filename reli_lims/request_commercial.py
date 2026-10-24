"""Optional links to ERPNext commercial facts; never create commercial documents."""
import frappe
from frappe import _


def validate_commercial_links(request):
    quotation = request.get('quotation')
    sales_order = request.get('sales_order')
    if quotation:
        doc = frappe.get_doc('Quotation', quotation)
        doc.check_permission('read')
        if doc.docstatus != 1 or doc.quotation_to != 'Customer':
            frappe.throw(_('请选择已提交且面向客户的报价单。'))
        if doc.party_name != request.customer or doc.company != request.company:
            frappe.throw(_('报价单与委托单位或公司不一致。'))
    if sales_order:
        doc = frappe.get_doc('Sales Order', sales_order)
        doc.check_permission('read')
        if doc.docstatus != 1:
            frappe.throw(_('请选择已提交的销售订单。'))
        if doc.customer != request.customer or doc.company != request.company:
            frappe.throw(_('销售订单与委托单位或公司不一致。'))
        if quotation:
            sources = {row.prevdoc_docname for row in doc.items if row.prevdoc_docname}
            if quotation not in sources:
                frappe.throw(_('销售订单未引用所选报价单，请核对商业来源。'))
