frappe.provide("reli_lims.capabilities");

const RELI_CAPABILITY_PAGE_SIZE = 30;

// 长列表会把 Frappe 对话框顶到视口外，导致底部“使用所选能力”按钮看不见。
// 固定 footer、限制内容高度，让确认按钮在第一页就始终可见。
const RELI_CAPABILITY_DIALOG_STYLE = `
.reli-cap-dialog .modal-content { display: flex; flex-direction: column; max-height: calc(100vh - 40px); }
.reli-cap-dialog .modal-body { overflow-y: auto; min-height: 0; }
.reli-cap-dialog .modal-footer { flex: 0 0 auto; }
.reli-cap-toolbar { position: sticky; top: 0; z-index: 3; display: flex; align-items: center;
    justify-content: space-between; gap: 8px; padding: 6px 0; margin-bottom: 6px;
    background: var(--fg-color, #fff); border-bottom: 1px solid var(--border-color, #d1d8dd); }
.reli-cap-actions { display: flex; align-items: center; gap: 8px; }
.reli-cap-scroll { max-height: 45vh; overflow: auto; }
`;

reli_lims.capabilities.open = function ({ mode = "catalog", onSelect, source }) {
    if (!document.getElementById("reli-cap-dialog-style")) {
        $("<style id='reli-cap-dialog-style'>").text(RELI_CAPABILITY_DIALOG_STYLE).appendTo(document.head);
    }
    const selected = new Map();
    let offset = 0;
    let generation = 0;
    let rowCount = 0;
    let hasMore = false;
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
        primary_action: () => confirmSelection(),
    });
    dialog.$wrapper.find(".modal-dialog").addClass("reli-cap-dialog");

    async function confirmSelection() {
        if (!selected.size) {
            frappe.msgprint(__("请至少选择一条实验室能力。"));
            return;
        }
        await onSelect?.([...selected.values()]);
        dialog.hide();
    }

    // 常驻工具条放在结果区上方，翻页与已选数量不必滚到列表底部才看得到。
    const area = dialog.fields_dict.results.$wrapper.empty();
    const toolbar = $("<div class='reli-cap-toolbar'>").appendTo(area);
    const summary = $("<div class='text-muted small'>").appendTo(toolbar);
    const controls = $("<div class='reli-cap-actions'>").appendTo(toolbar);
    const previous = $("<button type='button' class='btn btn-default btn-sm'>").text(__("上一页"))
        .on("click", () => {
            offset = Math.max(0, offset - RELI_CAPABILITY_PAGE_SIZE);
            render();
        }).appendTo(controls);
    const next = $("<button type='button' class='btn btn-default btn-sm'>").text(__("下一页"))
        .on("click", () => {
            offset += RELI_CAPABILITY_PAGE_SIZE;
            render();
        }).appendTo(controls);
    const scroller = $("<div class='reli-cap-scroll'>").appendTo(area);
    scroller.on("change", "input[type='checkbox']", () => updateToolbar());

    function updateToolbar() {
        summary.text(__("第 {0} 页 · 当前 {1} 条 · 已选 {2} 条",
            [offset / RELI_CAPABILITY_PAGE_SIZE + 1, rowCount, selected.size]));
        previous.prop("disabled", offset === 0);
        next.prop("disabled", !hasMore);
        dialog.get_primary_btn().prop("disabled", selected.size === 0);
    }

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
        rowCount = message.rows.length;
        hasMore = Boolean(message.has_more);
        scroller.empty();
        reli_lims.capabilities.renderGrid(scroller, message.rows, {
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
        updateToolbar();
    }

    dialog.show();
    if (!onSelect) dialog.get_primary_btn().hide();
    return render();
};
