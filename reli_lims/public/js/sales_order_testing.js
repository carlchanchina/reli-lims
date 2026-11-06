frappe.form.link_formatters.Item = ((original) => function (value, doc, ...args) {
    if (doc?.doctype === "Sales Order Item" && doc.item_name) return frappe.utils.escape_html(doc.item_name);
    return original ? original.call(this, value, doc, ...args) : value;
})(frappe.form.link_formatters.Item);

frappe.ui.form.on("Sales Order", {
    refresh(frm) {
        frm.fields_dict.items.grid.update_docfield_property("item_code", "label", __("商品／服务"));
        if (frm.is_new()) return;
        for (const name of new Set((frm.doc.items || []).map(row => row.prevdoc_docname).filter(Boolean))) {
            frm.add_custom_button(__("来源报价") + " " + name, () => frappe.set_route("Form", "Quotation", name));
        }
        if (frm.doc.docstatus === 1 && frappe.model.can_write("Sales Order")) {
            frm.add_custom_button(__("重试生成检测委托"), async () => {
                await frappe.call("reli_lims.sales_order_testing.retry", {name: frm.doc.name});
                await frm.reload_doc();
            });
        }
        const host = frm.fields_dict.custom_reli_requests?.$wrapper;
        if (!host) return;
        host.empty();
        frappe.call("reli_lims.sales_order_testing.requests", {name: frm.doc.name}).then(({message}) => {
            for (const row of message || []) {
                $("<button type='button' class='btn btn-default btn-sm mr-2 mb-2'>")
                    .text(`${row.title} · ${row.business_stage || (row.docstatus ? __("已受理") : __("草稿待补充"))}`)
                    .on("click", () => frappe.set_route("Form", "Test Request", row.name)).appendTo(host);
                if (row.order_difference) $("<p class='text-warning'>").text(row.order_difference).appendTo(host);
            }
        });
    },
});
