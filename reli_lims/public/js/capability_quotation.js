frappe.form.link_formatters.Item = ((original) => function (value, doc, ...args) {
    if (doc?.doctype === "Quotation Item" && doc.item_name && doc.custom_reli_capability) return frappe.utils.escape_html(doc.item_name);
    return original ? original.call(this, value, doc, ...args) : value;
})(frappe.form.link_formatters.Item);

frappe.ui.form.on("Quotation", {
    refresh(frm) {
        if (frm.doc.docstatus !== 0) return;
        frm.add_custom_button(__("选择检测服务"), async () => {
            await frappe.require("/assets/reli_lims/js/capability_grid.js");
            await frappe.require("/assets/reli_lims/js/capability_selector.js");
            return reli_lims.capabilities.open({
                mode: "quotation",
                async onSelect(selections) {
                    if (!selections.length) return;
                    const { message } = await frappe.call("reli_lims.capability_quotation.prepare_lines", { selections });
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
        if (frm.is_new() || frm.doc.docstatus === 2 || !frm.doc.items?.some(row => row.custom_reli_capability)) return;
        frm.add_custom_button(__("发起检测委托"), async () => {
            const { message } = await frappe.call("reli_lims.capability_request.quotation_items", { name: frm.doc.name });
            await frappe.new_doc("Test Request", {}, doc => {
                doc.customer = message.customer;
                doc.company = message.company;
                if (message.quotation) doc.quotation = message.quotation;
                for (const [index, values] of message.items.entries()) {
                    Object.assign(frappe.model.add_child(doc, "Test Request Item", "items"), values,
                        { item_code: `CAP-${index + 1}` });
                }
            });
        });
    },
});

frappe.ui.form.on("Quotation", {
    async refresh(frm) {
        await frappe.require("/assets/reli_lims/js/capability_grid.js");
        return reli_lims.capabilities.mount(frm, "quotation");
    },
});
