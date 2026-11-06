frappe.ui.form.on("Quotation", {
    refresh(frm) {
        if (frm.doc.docstatus !== 1 || frm.doc.quotation_to !== "Customer" || !frappe.model.can_write("Quotation")) return;
        frm.add_custom_button(__("记录客户接受"), () => frappe.prompt([
            {fieldname: "customer_contact", fieldtype: "Data", label: __("客户接受人／凭据说明"), reqd: 1},
        ], async values => {
            await frappe.call("reli_lims.sales_order_testing.accept_quotation", {name: frm.doc.name, ...values});
            await frm.reload_doc();
        }));
    },
});
