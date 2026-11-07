"""Optional links to ERPNext commercial facts; never create commercial documents."""
import frappe
from frappe import _


def validate_commercial_links(request):
    from reli_lims.commercial_access import quotation_facts, sales_order_facts
    from reli_lims.customer_share import in_customer_save
    # 客户链接只读商业来源；来源一致性仍校验，但不再要求客户具备内部读取权限。
    # 实验室角色不持有 Quotation / Sales Order 的 DocPerm（避免连带销售写入权），
    # 因此这里只读取校验必需的四个字段，不读金额与明细。
    check_permission = not in_customer_save()
    quotation = request.get('quotation')
    sales_order = request.get('sales_order')
    if quotation:
        from reli_lims.sales_order_testing import quotation_customer
        doc = quotation_facts(quotation)
        if not doc:
            frappe.throw(_('报价单不存在。'))
        # Frappe CRM 生成的报价单 quotation_to = "CRM Deal"，客户由企业主档解析。
        if doc.docstatus != 1 or doc.quotation_to not in ('Customer', 'CRM Deal'):
            frappe.throw(_('请选择已提交且面向客户的报价单。'))
        expected_customer = quotation_customer(quotation)
        if not expected_customer or expected_customer != request.customer or doc.company != request.company:
            frappe.throw(_('报价单与委托单位或公司不一致。'))
    if sales_order:
        doc = sales_order_facts(sales_order)
        if not doc:
            frappe.throw(_('销售订单不存在。'))
        if doc.docstatus != 1:
            frappe.throw(_('请选择已提交的销售订单。'))
        if doc.customer != request.customer or doc.company != request.company:
            frappe.throw(_('销售订单与委托单位或公司不一致。'))
        if quotation:
            from reli_lims.commercial_access import quotation_lines
            sources = {name for name in quotation_lines(sales_order) if name}
            if quotation not in sources:
                frappe.throw(_('销售订单未引用所选报价单，请核对商业来源。'))
