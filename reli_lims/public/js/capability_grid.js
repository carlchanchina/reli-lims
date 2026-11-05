frappe.provide("reli_lims.capabilities");

Object.assign(reli_lims.capabilities, {
    parse(value) {
        return typeof value === "string" ? JSON.parse(value) : value;
    },

    schema(row) {
        const schema = this.parse(row.condition_schema) || [];
        return schema.length ? schema : [{key: "original_text", label: "检测条件原文", type: "text"}];
    },

    conditionText(values, schema) {
        const labels = Object.fromEntries(schema.map(field => [field.key, field.label]));
        return Object.entries(values || {}).filter(([, value]) => value !== "" && value != null)
            .map(([key, value]) => `${labels[key] || key}：${value}`).join("；");
    },

    edit(row, values, apply) {
        const fields = this.schema(row).map(field => ({
            fieldname: field.key, label: field.label, reqd: field.required ? 1 : 0,
            fieldtype: {number: "Float", select: "Select"}[field.type] || "Small Text",
            options: field.type === "select" ? ["", ...field.options].join("\n") : undefined,
            default: values[field.key],
        }));
        const dialog = new frappe.ui.Dialog({
            title: __("编辑检测条件"), fields, primary_action_label: __("应用"),
            primary_action: async (conditions) => {
                await apply(conditions);
                dialog.hide();
            },
        });
        dialog.show();
    },

    renderGrid(area, rows, {mode = "catalog", selected, actions} = {}) {
        const selecting = Boolean(selected);
        const headers = ["检测对象", "检测项目", "检测依据（标准/方法）", "检测条件", "限制范围", "实验室"];
        if (mode === "quotation") headers.push("服务商品", "数量", "单位", "单价");
        if (mode === "request") headers.push("样品", "数量", "备注");
        if (selecting) headers.unshift("选择");
        headers.push("来源及详情");
        const table = $("<table>").addClass("table table-bordered table-hover").appendTo(
            $("<div>").css("overflow-x", "auto").appendTo(area),
        );
        table.attr("aria-label", __("检测项目明细")).css("min-width", mode === "catalog" ? "1050px" : "1350px");
        const heading = $("<tr>").appendTo($("<thead>").appendTo(table));
        headers.forEach(label => $("<th scope='col'>").css("white-space", "nowrap").text(__(label)).appendTo(heading));
        const body = $("<tbody>").appendTo(table);
        for (const row of rows) {
            const tr = $("<tr>").appendTo(body);
            const cell = value => $("<td>").text(value ?? "—").appendTo(tr);
            if (selecting) {
                $("<input type='checkbox'>").attr("aria-label", row.project_label || __("选择能力"))
                    .prop("checked", selected.has(row.name)).on("change", function () {
                        if (this.checked) selected.set(row.name, {capability_id: row.name, conditions: {}});
                        else selected.delete(row.name);
                    }).appendTo(cell(""));
            }
            const template = this.parse(row.condition_schema);
            const condition = row.condition_text || (selecting || mode === "catalog"
                ? (template || []).map(field => field.label).join("、") : "");
            for (const field of ["test_object_label", "project_label", "standard_label",
                "condition_text", "limitation", "laboratory_label"]) {
                const value = field === "condition_text" ? condition : row[field];
                cell(value || (field === "test_object_label" ? row.product_scope : "—"));
            }
            if (mode === "quotation") ["item_name", "qty", "uom", "rate"].forEach(key => cell(row[key]));
            if (mode === "request") ["samples", "qty", "notes"].forEach(key => cell(row[key]));
            const detail = $("<details>").appendTo(cell(""));
            $("<summary>").text(__("查看详情")).appendTo(detail);
            const info = [row.industry, row.project_parameter, row.method_label ? __("兼容方法") + `: ${row.method_label}` : "",
                row.method_code, row.clause, row.status, row.source_row]
                .filter(Boolean).join(" · ");
            if (info) $("<p>").text(info).appendTo(detail);
            for (const [doctype, name, label] of [
                ["Test Project", row.test_project, "查看检测项目"],
                ["Test Object", row.test_object, "查看检测对象"],
                ["Laboratory Capability", row.capability_id || (mode === "catalog" && row.name), "查看原始能力"],
                ["Capability Source", row.source, "查看导入来源"],
                ["Laboratory Profile", row.laboratory, "查看实验室"],
            ]) {
                if (name) $("<button type='button' class='btn btn-default btn-xs'>").text(__(label))
                    .on("click", () => frappe.set_route("Form", doctype, name)).appendTo(detail);
            }
            actions?.(detail, row);
        }
        if (!rows.length) $("<td>").attr("colspan", headers.length).text(__("没有匹配的检测项目"))
            .appendTo($("<tr>").appendTo(body));
    },
});

reli_lims.capabilities.mount = async function (frm, mode) {
    const quote = mode === "quotation";
    const items = frm.fields_dict.items?.$wrapper;
    if (!items) return;
    let wrapper = frm.fields_dict[quote ? "custom_reli_details" : "reli_details"]?.$wrapper;
    if (!wrapper) {
        wrapper = items.next(".reli-capability-details");
        if (!wrapper.length) wrapper = $("<div class='reli-capability-details'>").insertAfter(items);
    }
    const configurationField = quote ? "custom_reli_configuration" : "technical_configuration";
    const generation = Symbol();
    wrapper.data("reli-generation", generation);
    const lines = (frm.doc.items || []).filter(line => line[configurationField]);
    const names = [...new Set(lines.map(line => this.parse(line[configurationField]).capability_id))];
    const details = {};
    for (let index = 0; index < names.length; index += 100) {
        const {message} = await frappe.call("reli_lims.capability_selection.line_details", {
            names: names.slice(index, index + 100),
        });
        Object.assign(details, message);
    }
    if (wrapper.data("reli-generation") !== generation) return;
    wrapper.empty();
    $("<h5>").text(__("检测项目明细")).appendTo(wrapper);
    const rows = lines.map(line => {
        const config = this.parse(line[configurationField]);
        const view = {...config.snapshot, ...details[config.capability_id],
            condition_schema: config.snapshot?.condition_schema || details[config.capability_id]?.condition_schema};
        const assignments = (frm.doc.sample_assignments || []).filter(pair => pair.item_code === line.item_code);
        return {...view, line, config, liveDetails: details[config.capability_id], capability_id: config.capability_id,
            condition_text: this.conditionText(config.conditions, this.schema(view)),
            samples: assignments.map(pair => (frm.doc.samples || []).find(sample => sample.sample_code === pair.sample_code)
                ?.product_name || __("未命名样品")).join("、"),
            item_name: line.item_name, qty: quote ? line.qty : line.requested_quantity,
            uom: line.uom, rate: line.rate, notes: line.notes};
    });
    this.renderGrid(wrapper, rows, {mode, actions: (detail, row) => {
        if (frm.doc.docstatus !== 0 || !frm.perm?.[0]?.write) return;
        $("<button type='button' class='btn btn-default btn-xs'>").text(__("编辑检测条件"))
            .on("click", () => this.edit(row.liveDetails || row, row.config.conditions, async conditions => {
                const {message} = await frappe.call("reli_lims.capability_selection.configure", {
                    name: row.capability_id, conditions, mode,
                });
                await frappe.model.set_value(row.line.doctype, row.line.name, configurationField, message);
                if (!quote) await frappe.model.set_value(row.line.doctype, row.line.name, "test_condition",
                    this.conditionText(message.conditions, this.schema(message.snapshot)));
                frm.refresh_field("items");
                return this.mount(frm, mode);
            })).appendTo(detail);
        if (!quote) {
            $("<button type='button' class='btn btn-default btn-xs'>").text(__("关联样品"))
                .on("click", () => frm.script_manager.trigger("select_samples", row.line.doctype, row.line.name))
                .appendTo(detail);
        }
        $("<button type='button' class='btn btn-default btn-xs'>").text(quote ? __("编辑数量、单位和单价") : __("编辑委托数量及备注"))
            .on("click", () => frm.fields_dict.items.grid.grid_rows_by_docname[row.line.name]?.toggle_view(true))
            .appendTo(detail);
    }});
};
