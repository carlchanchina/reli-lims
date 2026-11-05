for (const [doctype, key] of [["Test Method", "method_label"], ["Test Standard", "standard_label"]]) {
    const original = frappe.form.link_formatters[doctype];
    frappe.form.link_formatters[doctype] = function (value, doc, ...args) {
        if (doc?.doctype === "Test Request Item" && doc.technical_configuration) {
            const config = typeof doc.technical_configuration === "string"
                ? JSON.parse(doc.technical_configuration) : doc.technical_configuration;
            if (config.snapshot?.[key]) return frappe.utils.escape_html(config.snapshot[key]);
        }
        return original ? original.call(this, value, doc, ...args) : value;
    };
}

frappe.provide("reli_lims.requests");

reli_lims.requests.add_items = function (frm, items) {
    const [placeholder] = frm.doc.items || [];
    if (frm.is_new() && frm.doc.items?.length === 1 && !placeholder.test_project && !placeholder.test_object &&
        !placeholder.test_method && !placeholder.standard &&
        !placeholder.test_condition && !placeholder.notes && !placeholder.capability &&
        !(frm.doc.sample_assignments || []).some(pair => pair.item_code === placeholder.item_code)) {
        frm.clear_table("items");
    }
    const samples = frm.doc.samples || [];
    const codes = new Set((frm.doc.items || []).map(row => row.item_code));
    let index = 1;
    for (const values of items) {
        while (codes.has(`CAP-${index}`)) index += 1;
        const row = frm.add_child("items", {
            ...values, item_code: `CAP-${index++}`,
        });
        if (samples.length === 1 && samples[0].sample_code) {
            frm.add_child("sample_assignments", {
                item_code: row.item_code, sample_code: samples[0].sample_code,
            });
        }
    }
    frm.refresh_field("items");
    frm.refresh_field("sample_assignments");
    frm.dirty();
    reli_lims.capabilities.mount(frm, "request");
};

reli_lims.requests.import_quote = async function (frm, name) {
    const { message } = await frappe.call("reli_lims.capability_request.quotation_items", { name });
    if (!message.items.length) return frappe.msgprint(__("这张报价没有检测条件快照。"));
    if ((frm.doc.customer && frm.doc.customer !== message.customer) ||
        (frm.doc.company && frm.doc.company !== message.company)) {
        return frappe.msgprint(__("报价客户或公司与当前委托不一致。"));
    }
    await frm.set_value({
        customer: message.customer, company: message.company, quotation: message.quotation || frm.doc.quotation,
    });
    const existing = new Set((frm.doc.items || []).map(row => row.source_quotation_item).filter(Boolean));
    reli_lims.requests.add_items(frm, message.items.filter(row => !existing.has(row.source_quotation_item)));
};

frappe.ui.form.on("Test Request", {
    refresh(frm) {
        if (frm.doc.docstatus !== 0) return;
        frm.add_custom_button(__("选择检测能力"), async () => {
            await frappe.require("capability_grid.bundle.js");
            await frappe.require("/assets/reli_lims/js/capability_selector.js");
            return reli_lims.capabilities.open({
                mode: "request",
                async onSelect(selections) {
                    if (!selections.length) return;
                    const { message } = await frappe.call("reli_lims.capability_request.prepare_items", { selections });
                    reli_lims.requests.add_items(frm, message);
                },
            });
        });
        frm.add_custom_button(__("从报价导入项目"), () => frappe.prompt(
            [{ fieldtype: "Link", options: "Quotation", fieldname: "quotation", label: __("报价"), reqd: 1 }],
            values => reli_lims.requests.import_quote(frm, values.quotation),
            __("从报价导入项目"),
        ));
        if (frm.is_new() && frappe.route_options?.reli_source_quotation) {
            const name = frappe.route_options.reli_source_quotation;
            delete frappe.route_options.reli_source_quotation;
            reli_lims.requests.import_quote(frm, name);
        }
    },
});

frappe.ui.form.on("Test Request", {
    async refresh(frm) {
        await frappe.require("capability_grid.bundle.js");
        return reli_lims.capabilities.mount(frm, "request");
    },
});
