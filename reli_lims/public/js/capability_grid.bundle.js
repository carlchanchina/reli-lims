frappe.provide("reli_lims.capabilities");

function reli_capability_truncate(text, limit) {
    return text && text.length > limit ? `${text.slice(0, limit)}…` : text;
}

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

    // compact: 表单明细只展示摘要列，限制范围/实验室/来源等放进“查看详情”，避免横向过长。
    renderGrid(area, rows, {mode = "catalog", selected, actions, compact = false} = {}) {
        const selecting = Boolean(selected);
        // 报价与销售订单都按商业行展示数量、单位、单价。
        const commercial = mode === "quotation" || mode === "sales_order";
        const condition = row => row.condition_text || (selecting || mode === "catalog"
            ? (this.parse(row.condition_schema) || []).map(field => field.label).join("、") : "");
        const columns = [];
        if (selecting) {
            columns.push({label: "选择", html: (cell, row) => {
                $("<input type='checkbox'>").attr("aria-label", row.project_label || __("选择能力"))
                    .prop("checked", selected.has(row.name)).on("change", function () {
                        if (this.checked) selected.set(row.name, {capability_id: row.name, conditions: {}});
                        else selected.delete(row.name);
                    }).appendTo(cell);
            }});
        }
        columns.push(
            {label: "检测对象", value: row => row.test_object_label || row.product_scope},
            {label: "检测项目", value: row => row.project_label},
            {label: "检测依据（标准/方法）", value: row => row.standard_label},
            {label: "检测条件", value: row => compact ? reli_capability_truncate(condition(row), 36) : condition(row)},
        );
        if (compact) {
            if (commercial) {
                columns.push({label: "数量", value: row => row.qty}, {label: "单价", value: row => row.rate});
            }
            if (mode === "request") {
                columns.push({label: "样品", value: row => row.samples}, {label: "数量", value: row => row.qty});
            }
        } else {
            columns.push({label: "限制范围", value: row => row.limitation},
                {label: "实验室", value: row => row.laboratory_label});
            if (commercial) {
                columns.push({label: "服务商品", value: row => row.item_name},
                    {label: "数量", value: row => row.qty}, {label: "单位", value: row => row.uom},
                    {label: "单价", value: row => row.rate});
            }
            if (mode === "request") {
                columns.push({label: "样品", value: row => row.samples},
                    {label: "数量", value: row => row.qty}, {label: "备注", value: row => row.notes});
            }
        }
        columns.push({label: compact ? "详情" : "来源及详情", html: (cell, row) => {
            const detail = $("<details>").appendTo(cell);
            $("<summary>").text(__("查看详情")).appendTo(detail);
            const info = [row.industry, row.project_parameter, row.clause, row.status, row.source_row]
                .filter(Boolean).join(" · ");
            if (info) $("<p>").text(info).appendTo(detail);
            if (compact) {
                for (const [label, value] of [
                    ["完整检测条件", condition(row)], ["限制范围", row.limitation],
                    ["实验室", row.laboratory_label], ["服务商品", row.item_name], ["单位", row.uom],
                ]) {
                    if (value) $("<p>").text(`${label}：${value}`).appendTo(detail);
                }
            }
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
        }});

        const table = $("<table>").addClass("table table-bordered table-hover").appendTo(
            $("<div>").css("overflow-x", "auto").appendTo(area),
        );
        table.attr("aria-label", __("检测项目明细"))
            .css("min-width", compact ? "820px" : (mode === "catalog" ? "1050px" : "1350px"));
        const heading = $("<tr>").appendTo($("<thead>").appendTo(table));
        for (const column of columns) {
            $("<th scope='col'>").css("white-space", "nowrap").text(__(column.label)).appendTo(heading);
        }
        const body = $("<tbody>").appendTo(table);
        for (const row of rows) {
            const tr = $("<tr>").appendTo(body);
            for (const column of columns) {
                const cell = $("<td>").appendTo(tr);
                if (column.html) column.html(cell, row);
                else {
                    const value = column.value(row);
                    cell.text(value === undefined || value === null || value === "" ? "—" : value);
                }
            }
        }
        if (!rows.length) {
            $("<td>").attr("colspan", columns.length).text(__("没有匹配的检测项目"))
                .appendTo($("<tr>").appendTo(body));
        }
    },
});

reli_lims.capabilities.mount = async function (frm, mode) {
    // 报价单与销售订单共用同一套检测明细；委托单用 technical_configuration。
    const commercial = mode === "quotation" || mode === "sales_order";
    const items = frm.fields_dict.items?.$wrapper;
    if (!items) return;
    let wrapper = frm.fields_dict[commercial ? "custom_reli_details" : "reli_details"]?.$wrapper;
    if (!wrapper) {
        wrapper = items.next(".reli-capability-details");
        if (!wrapper.length) wrapper = $("<div class='reli-capability-details'>").insertAfter(items);
    }
    const configurationField = commercial ? "custom_reli_configuration" : "technical_configuration";
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
    const container = wrapper.closest(".frappe-control");
    wrapper.empty();
    // 没有检测能力行时不显示整块明细，选完检测服务后再自动出现。
    if (!lines.length) {
        container.hide();
        return;
    }
    container.show();
    $("<h5>").text(__("检测项目明细")).appendTo(wrapper);
    const rows = lines.map(line => {
        const config = this.parse(line[configurationField]);
        const view = {...details[config.capability_id], ...config.snapshot,
            condition_schema: config.snapshot?.condition_schema || details[config.capability_id]?.condition_schema};
        const assignments = (frm.doc.sample_assignments || []).filter(pair => pair.item_code === line.item_code);
        return {...view, line, config, liveDetails: details[config.capability_id], capability_id: config.capability_id,
            condition_text: this.conditionText(config.conditions, this.schema(view)),
            samples: assignments.map(pair => (frm.doc.samples || []).find(sample => sample.sample_code === pair.sample_code)
                ?.product_name || __("未命名样品")).join("、"),
            item_name: line.item_name, qty: commercial ? line.qty : line.requested_quantity,
            uom: line.uom, rate: line.rate, notes: line.notes};
    });
    this.renderGrid(wrapper, rows, {mode, compact: true, actions: (detail, row) => {
        if (frm.doc.docstatus !== 0 || !frm.perm?.[0]?.write) return;
        $("<button type='button' class='btn btn-default btn-xs'>").text(__("更新技术快照"))
            .on("click", async () => {
                const {message} = await frappe.call("reli_lims.capability_selection.configure", {
                    name: row.capability_id, conditions: row.config.conditions, mode,
                });
                await frappe.model.set_value(row.line.doctype, row.line.name, configurationField, message);
                if (mode === "request") await frappe.model.set_value(row.line.doctype, row.line.name, "test_condition",
                    this.conditionText(message.conditions, this.schema(message.snapshot)));
                frm.refresh_field("items");
                return this.mount(frm, mode);
            }).appendTo(detail);
        $("<button type='button' class='btn btn-default btn-xs'>").text(__("编辑检测条件"))
            .on("click", () => this.edit(row.liveDetails || row, row.config.conditions, async conditions => {
                const {message} = await frappe.call("reli_lims.capability_selection.configure", {
                    name: row.capability_id, conditions, mode,
                });
                await frappe.model.set_value(row.line.doctype, row.line.name, configurationField, message);
                if (mode === "request") await frappe.model.set_value(row.line.doctype, row.line.name, "test_condition",
                    this.conditionText(message.conditions, this.schema(message.snapshot)));
                frm.refresh_field("items");
                return this.mount(frm, mode);
            })).appendTo(detail);
        if (mode === "request") {
            $("<button type='button' class='btn btn-default btn-xs'>").text(__("关联样品"))
                .on("click", () => frm.script_manager.trigger("select_samples", row.line.doctype, row.line.name))
                .appendTo(detail);
        }
        $("<button type='button' class='btn btn-default btn-xs'>").text(commercial ? __("编辑数量、单位和单价") : __("编辑委托数量及备注"))
            .on("click", () => frm.fields_dict.items.grid.grid_rows_by_docname[row.line.name]?.toggle_view(true))
            .appendTo(detail);
    }});
};
