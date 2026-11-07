frappe.form.link_formatters.Item = ((original) => function (value, doc, ...args) {
    if (doc?.doctype === "Sales Order Item" && doc.item_name) return frappe.utils.escape_html(doc.item_name);
    return original ? original.call(this, value, doc, ...args) : value;
})(frappe.form.link_formatters.Item);

frappe.ui.form.on("Sales Order", {
    async refresh(frm) {
        frm.fields_dict.items.grid.update_docfield_property("item_code", "label", __("商品／服务"));
        // 原生报价转订单不会带出 Quotation 的承诺交期，而行级“交付日期”在界面上已隐藏。
        // 若不在前端补齐，ERPNext 的必填校验会让映射出来的订单无法保存。
        if (frm.is_new() && !frm.doc.customer) {
            const source = (frm.doc.items || []).map(row => row.prevdoc_docname).find(Boolean);
            if (source) {
                const { message } = await frappe.call("reli_lims.sales_order_testing.resolve_quotation_customer", { name: source });
                if (message) await frm.set_value("customer", message);
            }
        }
        if (frm.is_new() && !frm.doc.delivery_date) {
            const sources = [...new Set((frm.doc.items || []).map(row => row.prevdoc_docname).filter(Boolean))];
            const dates = [];
            for (const name of sources) {
                const { message } = await frappe.db.get_value("Quotation", name, "custom_reli_delivery_date");
                if (message?.custom_reli_delivery_date) dates.push(message.custom_reli_delivery_date);
            }
            if (dates.length) {
                dates.sort();
                await frm.set_value("delivery_date", dates[0]);
                let changed = false;
                (frm.doc.items || []).forEach(row => {
                    if (!row.delivery_date) { row.delivery_date = dates[0]; changed = true; }
                });
                if (changed) frm.refresh_field("items");
            }
        }
        // 直接开单：不经过报价也能选检测服务，行为和报价单的“选择检测服务”一致。
        if (frm.doc.docstatus === 0) {
            frm.add_custom_button(__("选择检测服务"), async () => {
                await frappe.require("capability_grid.bundle.js");
                await frappe.require("capability_selector.bundle.js");
                return reli_lims.capabilities.open({
                    mode: "sales_order",
                    async onSelect(selections) {
                        if (!selections.length) return;
                        const { message } = await frappe.call("reli_lims.sales_order_testing.prepare_lines", { selections });
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
                            if (frm.doc.delivery_date) row.delivery_date = frm.doc.delivery_date;
                        }
                        frm.refresh_field("items");
                        frm.dirty();
                        await reli_lims.capabilities.mount(frm, "sales_order");
                    },
                });
            });
        }
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

frappe.ui.form.on("Sales Order", {
    async refresh(frm) {
        await frappe.require("capability_grid.bundle.js");
        return reli_lims.capabilities.mount(frm, "sales_order");
    },
});
