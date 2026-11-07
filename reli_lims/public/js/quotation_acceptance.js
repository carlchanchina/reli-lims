frappe.ui.form.on("Quotation", {
    refresh(frm) {
        frm.fields_dict.items.grid.update_docfield_property("item_code", "label", __("商品／服务"));
        // Frappe CRM 生成的报价单 quotation_to 是 "CRM Deal"，客户由企业主档解析。
        if (frm.doc.docstatus !== 1 || !["Customer", "CRM Deal"].includes(frm.doc.quotation_to) ||
            !frappe.model.can_write("Quotation")) return;
        frm.add_custom_button(__("记录客户接受"), () => frappe.prompt([
            {fieldname: "customer_contact", fieldtype: "Data", label: __("客户接受人／凭据说明"), reqd: 1},
        ], async values => {
            await frappe.call("reli_lims.sales_order_testing.accept_quotation", {name: frm.doc.name, ...values});
            await frm.reload_doc();
        }));
    },
});
