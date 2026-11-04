frappe.provide("reli_lims.capabilities");

reli_lims.capabilities.open = function ({ mode = "catalog", onSelect }) {
    const selected = new Map();
    let offset = 0;
    let generation = 0;
    const dimensions = [
        ["industry", "行业"], ["product", "产品及检测对象"], ["project", "项目及参数"],
        ["standard", "标准"], ["method", "方法"],
    ];
    const dialog = new frappe.ui.Dialog({
        title: __("检测能力选择"),
        size: "extra-large",
        fields: [
            { fieldtype: "Data", fieldname: "search", label: __("搜索"), onchange: refresh },
            ...dimensions.map(([key, label]) => ({
                fieldtype: key === "standard" || key === "method" ? "Link" : "Data",
                options: { standard: "Test Standard", method: "Test Method" }[key],
                fieldname: key, label: __(label), onchange: refresh,
            })),
            { fieldtype: "HTML", fieldname: "results" },
        ],
        primary_action_label: __("使用所选能力"),
        primary_action: async () => {
            await onSelect?.([...selected.values()]);
            dialog.hide();
        },
    });

    function refresh() {
        offset = 0;
        return render();
    }

    async function render() {
        const current = ++generation;
        const filters = Object.fromEntries(dimensions.map(([key]) => [key, dialog.get_value(key)]));
        const { message } = await frappe.call("reli_lims.capability_selection.search", {
            mode, text: dialog.get_value("search"), facets: filters, offset,
        });
        if (current !== generation) return;
        const area = dialog.fields_dict.results.$wrapper.empty();
        for (const row of message.rows) {
            const detail = $("<details>").appendTo(area);
            $("<summary>").text([row.product_scope, row.method_label, row.standard_label].filter(Boolean).join(" · ")).appendTo(detail);
            $("<p>").text([row.industry, row.project_parameter, row.laboratory_label, row.limitation, row.status].filter(Boolean).join(" · ")).appendTo(detail);
            const conditions = selected.get(row.name)?.conditions || {};
            for (const field of (typeof row.condition_schema === "string" ? JSON.parse(row.condition_schema) : row.condition_schema || [])) {
                const label = $("<label>").addClass("d-block").text(field.label).appendTo(detail);
                const input = field.type === "select" ? $("<select>") : $("<input>").attr("type", field.type === "number" ? "number" : "text");
                if (field.type === "select") {
                    $("<option>").val("").appendTo(input);
                    for (const option of field.options || []) $("<option>").val(option).text(option).appendTo(input);
                }
                input.val(conditions[field.key] ?? "").on("change", () => { conditions[field.key] = input.val(); }).appendTo(label);
            }
            if (onSelect) {
                $("<input type='checkbox'>").prop("checked", selected.has(row.name)).on("change", function () {
                    if (this.checked) selected.set(row.name, { capability_id: row.name, conditions });
                    else selected.delete(row.name);
                }).appendTo($("<label>").text(__("选择 ")).appendTo(detail));
            }
        }
        if (!message.rows.length) $("<p>").text(__("没有匹配能力")).appendTo(area);
        if (offset > 0) $("<button class='btn btn-default'>").text(__("上一页")).on("click", () => { offset -= 30; render(); }).appendTo(area);
        if (message.has_more) $("<button class='btn btn-default'>").text(__("下一页")).on("click", () => { offset += 30; render(); }).appendTo(area);
    }
    dialog.show();
    if (!onSelect) dialog.get_primary_btn().hide();
    return render();
};
