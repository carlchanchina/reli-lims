frappe.ui.form.on("Quotation", {
    refresh(frm) {
        if (frm.doc.docstatus !== 0) return;
        frm.add_custom_button(__("选择检测服务"), async () => {
            await frappe.require("/assets/reli_lims/js/capability_selector.js");
            return reli_lims.capabilities.open({
                mode: "quotation",
                async onSelect(selections) {
                    if (!selections.length) return;
                    const { message } = await frappe.call("reli_lims.capability_quotation.prepare_lines", { selections });
                    for (const values of message) {
                        const row = frm.add_child("items");
                        await frappe.model.set_value(row.doctype, row.name, "item_code", values.item_code);
                        Object.assign(row, values);
                    }
                    frm.refresh_field("items");
                    frm.dirty();
                },
            });
        });
    },
});
