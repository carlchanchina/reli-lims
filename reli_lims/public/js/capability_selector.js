frappe.provide("reli_lims.capabilities");

reli_lims.capabilities.open = function ({ mode = "catalog", onSelect, source }) {
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
            mode, source, text: dialog.get_value("search"), facets: filters, offset,
        });
        if (current !== generation) return;
        const area = dialog.fields_dict.results.$wrapper.empty();
        reli_lims.capabilities.renderGrid(area, message.rows, {
            selected: onSelect ? selected : null,
            actions: onSelect ? (detail, row) => {
                $("<button type='button' class='btn btn-default btn-xs'>").text(__("编辑条件并选中"))
                    .on("click", () => reli_lims.capabilities.edit(row, selected.get(row.name)?.conditions || {}, conditions => {
                        selected.set(row.name, {capability_id: row.name, conditions});
                        return render();
                    })).appendTo(detail);
            } : null,
        });
        $("<p>").text(__("第 {0} 页 · 当前 {1} 条 · 已选 {2} 条",
            [offset / 30 + 1, message.rows.length, selected.size])).appendTo(area);
        if (offset > 0) $("<button class='btn btn-default'>").text(__("上一页")).on("click", () => { offset -= 30; render(); }).appendTo(area);
        if (message.has_more) $("<button class='btn btn-default'>").text(__("下一页")).on("click", () => { offset += 30; render(); }).appendTo(area);
    }
    dialog.show();
    if (!onSelect) dialog.get_primary_btn().hide();
    return render();
};
