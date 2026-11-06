frappe.form.link_formatters.Item = ((original) => function (value, doc, ...args) {
    if (doc?.doctype === "Quotation Item" && doc.item_name) return frappe.utils.escape_html(doc.item_name);
    return original ? original.call(this, value, doc, ...args) : value;
})(frappe.form.link_formatters.Item);

frappe.ui.form.on("Quotation", {
    refresh(frm) {
        if (frm.doc.docstatus !== 0) return;
        frm.add_custom_button(__("选择检测服务"), async () => {
            await frappe.require("capability_grid.bundle.js");
            await frappe.require("capability_selector.bundle.js");
            return reli_lims.capabilities.open({
                mode: "quotation",
                async onSelect(selections) {
                    if (!selections.length) return;
                    const { message } = await frappe.call("reli_lims.capability_quotation.prepare_lines", { selections });
                    const [placeholder] = frm.doc.items || [];
                    if (frm.is_new() && frm.doc.items?.length === 1 && !placeholder.item_code &&
                        !placeholder.item_name && !placeholder.description && !placeholder.qty && !placeholder.rate) {
                        frm.clear_table("items");
                    }
                    for (const values of message) {
                        const row = frm.add_child("items", {
                            custom_reli_capability: values.custom_reli_capability, item_name: values.item_name,
                        });
                        await frappe.model.set_value(row.doctype, row.name, "item_code", values.item_code);
                        Object.assign(row, values);
                    }
                    frm.refresh_field("items");
                    frm.dirty();
                    await reli_lims.capabilities.mount(frm, "quotation");
                },
            });
        });
    },
});

frappe.ui.form.on("Quotation", {
    refresh(frm) {
        if (frm.is_new() || frm.doc.docstatus !== 1) return;
        frm.add_custom_button(__("创建销售订单"), () => frappe.model.open_mapped_doc({
            method: "erpnext.selling.doctype.quotation.quotation.make_sales_order", frm,
        }));
    },
});

frappe.ui.form.on("Quotation", {
    async refresh(frm) {
        await frappe.require("capability_grid.bundle.js");
        return reli_lims.capabilities.mount(frm, "quotation");
    },
});
