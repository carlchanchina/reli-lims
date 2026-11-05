frappe.provide("reli_lims.capabilities");

reli_lims.capabilities.open = function ({ mode = "catalog", onSelect, source }) {
    const selected = new Map();
    let offset = 0;
    let generation = 0;
    const dimensions = [
        ["project", "检测项目", "Test Project"],
        ["object", "检测对象", "Test Object"],
        ["standard", "检测依据（标准/方法）", "Test Standard"],
        ["laboratory", "实验室", "Laboratory Profile"],
    ];
    const fields = [
        { fieldtype: "Data", fieldname: "search", label: __("搜索"), onchange: refresh },
        ...dimensions.map(([key, label, options]) => ({
            fieldtype: "Link", options, fieldname: key, label: __(label), onchange: refresh,
        })),
    ];
    if (mode === "catalog") {
        fields.push({
            fieldtype: "Select", fieldname: "status", label: __("审核状态"),
            options: ["", "待确认", "已确认", "已发布", "已停用"].join("\n"), onchange: refresh,
        });
    }
    fields.push({ fieldtype: "HTML", fieldname: "results" });

    const dialog = new frappe.ui.Dialog({
        title: __(onSelect ? "选择实验室能力" : "实验室能力明细"),
        size: "extra-large",
        fields,
        primary_action_label: __("使用所选能力"),
        primary_action: async () => {
            if (!selected.size) {
                frappe.msgprint(__("请至少选择一条实验室能力。"));
                return;
            }
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
        const filters = Object.fromEntries(
            [...dimensions.map(([key]) => [key, dialog.get_value(key)]), ["status", dialog.get_value("status")]],
        );
        const { message } = await frappe.call("reli_lims.capability_selection.search", {
            mode, source, text: dialog.get_value("search"), facets: filters, offset,
        });
        if (current !== generation) return;
        const area = dialog.fields_dict.results.$wrapper.empty();
        reli_lims.capabilities.renderGrid(area, message.rows, {
            selected: onSelect ? selected : null,
            actions: onSelect ? (detail, row) => {
                $("<button type='button' class='btn btn-default btn-xs'>").text(__("编辑条件并选中"))
                    .on("click", () => reli_lims.capabilities.edit(
                        row, selected.get(row.name)?.conditions || {}, conditions => {
                            selected.set(row.name, { capability_id: row.name, conditions });
                            return render();
                        },
                    )).appendTo(detail);
            } : null,
        });
        $("<p class='text-muted'>").text(__("第 {0} 页 · 当前 {1} 条 · 已选 {2} 条",
            [offset / 30 + 1, message.rows.length, selected.size])).appendTo(area);
        const pager = $("<div class='mt-2'>").appendTo(area);
        if (offset > 0) {
            $("<button type='button' class='btn btn-default btn-sm'>").text(__("上一页"))
                .on("click", () => { offset -= 30; render(); }).appendTo(pager);
        }
        if (message.has_more) {
            $("<button type='button' class='btn btn-default btn-sm ml-2'>").text(__("下一页"))
                .on("click", () => { offset += 30; render(); }).appendTo(pager);
        }
        if (onSelect) dialog.get_primary_btn().prop("disabled", selected.size === 0);
    }

    dialog.show();
    if (!onSelect) dialog.get_primary_btn().hide();
    return render();
};
