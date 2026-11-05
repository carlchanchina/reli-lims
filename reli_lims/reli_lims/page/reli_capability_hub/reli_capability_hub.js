frappe.pages["reli-capability-hub"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper, title: __("能力查询"), single_column: true,
    });
    const body = $(page.body);

    const open_capabilities = async () => {
        await frappe.require("capability_grid.bundle.js");
        await frappe.require("capability_selector.bundle.js");
        return reli_lims.capabilities.open({mode: "catalog"});
    };

    page.set_primary_action(__("新增检测项目"), () => frappe.new_doc("Test Project"));
    page.add_inner_button(__("添加实验室能力"), () => frappe.new_doc("Laboratory Capability"));
    page.add_inner_button(__("筛选全部能力"), open_capabilities);

    $("<p class='text-muted'>")
        .text(__("检测项目是全平台统一主数据；实验室能力按实验室、对象、依据和限制范围保留独立明细。"))
        .appendTo(body);

    frappe.call("reli_lims.capability_catalog.dashboard").then(({message}) => {
        const counts = $("<div class='reli-capability-counts d-flex flex-wrap gap-2 mb-4'>").appendTo(body);
        for (const [label, value] of [
            [__("检测项目"), message.projects], [__("已归类"), message.classified],
            [__("待分类"), message.pending], [__("检测对象"), message.objects],
            [__("检测依据"), message.standards], [__("实验室"), message.laboratories],
            [__("实验室能力"), message.capabilities], [__("CNAS 能力"), message.cnas_capabilities],
            [__("未归类能力"), message.unclassified_capabilities], [__("服务商品"), message.service_items],
        ]) {
            $("<div class='border rounded px-3 py-2'>").append(
                $("<div class='text-muted small'>").text(label),
                $("<div class='h4 mb-0'>").text(value || 0),
            ).appendTo(counts);
        }
    });

    const nav = $("<div class='row mb-4'>").appendTo(body);
    const entries = [
        [__("检测项目库"), __("统一检测项目、分类、别名和条件模板"), () => frappe.set_route("List", "Test Project")],
        [__("全部能力明细"), __("按项目、对象、依据和实验室筛选"), open_capabilities],
        [__("检测对象分类"), __("受控检测对象及分类、别名"), () => frappe.set_route("List", "Test Object")],
        [__("检测依据（标准/方法）"), __("标准编号、名称、版本与依据类型"), () => frappe.set_route("List", "Test Standard")],
        [__("实验室管理"), __("实验室资料、能力来源与服务商品"), () => frappe.set_route("List", "Laboratory Profile")],
        [__("能力来源"), __("来源文件与原始结构化能力明细"), () => frappe.set_route("List", "Capability Source")],
        [__("服务商品关联"), __("以中文服务名称关联检测项目与 Item"), () => {
            frappe.route_options = {is_stock_item: 0, is_sales_item: 1};
            frappe.set_route("List", "Item");
        }],
    ];
    for (const [title, description, action] of entries) {
        const column = $("<div class='col-sm-6 col-lg-4 mb-3'>").appendTo(nav);
        const card = $("<button type='button' class='btn btn-default text-left w-100 h-100 p-3'>")
            .on("click", action).appendTo(column);
        $("<div class='h5'>").text(title).appendTo(card);
        $("<div class='text-muted'>").text(description).appendTo(card);
    }

    render_review(body);

    $("<div class='border-top pt-3'>").append(
        $("<h5>").text(__("操作边界")),
        $("<p class='text-muted mb-0'>").text(__("新增检测项目用于建立公共项目字典；添加实验室能力用于登记某个实验室针对对象、项目、依据和限制范围的具体能力。两者不会互相替代。")),
    ).appendTo(body);

    function render_review(container) {
        const state = {status: "待确认", laboratory: "", test_project: "", test_standard: "",
                       batch_limit: 50, rows: []};
        const section = $("<div class='border rounded p-3 mb-4'>").appendTo(container);
        $("<h5>").text(__("能力审核台（按 CNAS 范围逐条留痕）")).appendTo(section);
        $("<p class='text-muted small mb-2'>").text(__(
            "批量只省点击、不省审核：审核与发布分属两个角色，每条能力都会追加一条审核记录；单次最多 50 条；演示能力必须单独确认后才会发布。"
        )).appendTo(section);

        const filters = $("<div class='row g-2 mb-2'>").appendTo(section);
        const make_select = (label, onchange) => {
            const col = $("<div class='col-sm-6 col-lg-3 mb-2'>").appendTo(filters);
            $("<label class='small text-muted d-block'>").text(label).appendTo(col);
            return $("<select class='form-control form-control-sm'>").on("change", function () {
                onchange(this.value);
            }).appendTo(col);
        };
        const status_select = make_select(__("状态"), value => { state.status = value; load(); });
        const lab_select = make_select(__("实验室"), value => { state.laboratory = value; load(); });
        const project_select = make_select(__("检测项目"), value => { state.test_project = value; load(); });
        const standard_select = make_select(__("检测依据"), value => { state.test_standard = value; load(); });

        const fill = (select, items, all_label) => {
            select.empty();
            $("<option>").attr("value", "").text(all_label).appendTo(select);
            for (const item of items || []) {
                $("<option>").attr("value", item.value).text(item.label).appendTo(select);
            }
        };
        fill(status_select, ["待确认", "已确认", "已发布", "已停用"].map(v => ({value: v, label: v})),
             __("全部状态"));
        status_select.val("待确认");

        const counts = $("<div class='d-flex flex-wrap gap-3 small text-muted mb-2'>").appendTo(section);
        const table_wrap = $("<div class='table-responsive'>").appendTo(section);
        const table = $("<table class='table table-sm align-middle mb-2'>").appendTo(table_wrap);
        $("<thead>").append($("<tr>").append(
            ["", __("能力"), __("检测项目"), __("检测依据"), __("认可类型"), __("证书编号"), __("状态"), __("发布预检")]
                .map(text => $("<th class='small text-muted'>").text(text))
        )).appendTo(table);
        const tbody = $("<tbody>").appendTo(table);

        const actions = $("<div class='d-flex flex-wrap gap-2 align-items-center'>").appendTo(section);
        const hint = $("<span class='small text-muted ms-2'>").appendTo(actions);
        const selected = () => tbody.find("input[type=checkbox]:checked").map((i, el) => el.value).get();

        const update_hint = () => {
            const names = selected();
            hint.text(__("已选 {0} 条（单次上限 {1} 条）", [names.length, state.batch_limit]));
        };

        const run = (method, title, extra_fields, extra_args) => {
            const names = selected();
            if (!names.length) { frappe.msgprint(__("请先勾选要处理的能力。")); return; }
            if (names.length > state.batch_limit) {
                frappe.msgprint(__("单次最多 {0} 条，当前选了 {1} 条，请分组处理。",
                    [state.batch_limit, names.length]));
                return;
            }
            frappe.prompt(
                [{fieldname: "note", fieldtype: "Small Text", label: __("处理说明（写入审核记录）"), reqd: 1}]
                    .concat(extra_fields || []),
                values => {
                    frappe.call({
                        method: `reli_lims.capability_review.${method}`,
                        args: Object.assign({names: names, note: values.note}, extra_args ? extra_args(values) : {}),
                        freeze: true,
                        callback: response => {
                            const message = response.message || {};
                            const done = (message.done || message.published || []).length;
                            const skipped = message.skipped || [];
                            frappe.msgprint({
                                title: __(title),
                                indicator: done ? "green" : "orange",
                                message: __("已处理 {0} 条", [done]) +
                                    (skipped.length ? "<br>" + skipped.map(row =>
                                        `${frappe.utils.escape_html(row.name)}：${frappe.utils.escape_html(row.reason)}`).join("<br>") : ""),
                            });
                            load();
                        },
                    });
                },
                __(title), __("执行")
            );
        };

        $("<button class='btn btn-sm btn-primary'>").text(__("审核通过")).on("click",
            () => run("review", __("审核通过"), [], () => ({decision: "approve"}))).appendTo(actions);
        $("<button class='btn btn-sm btn-default'>").text(__("退回补充")).on("click",
            () => run("review", __("退回补充"), [], () => ({decision: "return"}))).appendTo(actions);
        $("<button class='btn btn-sm btn-success'>").text(__("发布")).on("click",
            () => run("publish", __("批量发布"),
                [{fieldname: "include_demo", fieldtype: "Check", label: __("本次包含演示能力（非认可）")}],
                values => ({include_demo: values.include_demo ? 1 : 0}))).appendTo(actions);
        $("<button class='btn btn-sm btn-default'>").text(__("停用")).on("click",
            () => run("retire", __("停用"))).appendTo(actions);
        $("<button class='btn btn-sm btn-default'>").text(__("刷新")).on("click", load).appendTo(actions);
        hint.text(__("已选 0 条（单次上限 {0} 条）", [state.batch_limit]));

        function load() {
            frappe.call({
                method: "reli_lims.capability_review.search",
                args: {laboratory: state.laboratory, test_project: state.test_project,
                       test_standard: state.test_standard, status: state.status, limit: 50},
                callback: response => {
                    const payload = response.message || {};
                    state.rows = payload.rows || [];
                    state.batch_limit = payload.batch_limit || 50;
                    const summary = payload.status_counts || {};
                    counts.empty();
                    for (const key of ["待确认", "已确认", "已发布", "已停用", "演示"]) {
                        $("<span class='badge bg-light text-dark border me-2'>")
                            .text(`${key} ${summary[key] || 0}`).appendTo(counts);
                    }
                    tbody.empty();
                    if (!state.rows.length) {
                        $("<tr>").append($("<td colspan='8' class='text-muted small'>")
                            .text(__("当前筛选条件下没有能力。"))).appendTo(tbody);
                        update_hint();
                        return;
                    }
                    for (const row of state.rows) {
                        const tr = $("<tr>").appendTo(tbody);
                        $("<td>").append($("<input type='checkbox' class='reli-review-check'>")
                            .attr("value", row.name).on("change", update_hint)).appendTo(tr);
                        $("<td>").append(
                            $("<a href='#'>").text(row.name).on("click", event => {
                                event.preventDefault();
                                frappe.set_route("Form", "Laboratory Capability", row.name);
                            }),
                            row.demo_only ? $("<span class='badge bg-warning text-dark ms-1'>").text(__("演示")) : null
                        ).appendTo(tr);
                        $("<td class='small'>").text(row.test_project || "—").appendTo(tr);
                        $("<td class='small'>").text(row.test_standard || "—").appendTo(tr);
                        $("<td class='small'>").text(row.accreditation_type || "—").appendTo(tr);
                        $("<td class='small'>").text(row.certificate_no || "—").appendTo(tr);
                        $("<td class='small'>").text(__(row.status)).appendTo(tr);
                        $("<td class='small'>").append(
                            row.publishable
                                ? $("<span class='text-success'>").text(__("可发布"))
                                : $("<span class='text-muted'>").text(row.blockers.join("；"))
                        ).appendTo(tr);
                    }
                    update_hint();
                },
            });
        }

        frappe.call("reli_lims.capability_review.filter_options").then(({message}) => {
            const options = message || {};
            fill(lab_select, options.laboratories, __("全部实验室"));
            fill(project_select, options.projects, __("全部检测项目"));
            fill(standard_select, options.standards, __("全部检测依据"));
            load();
        });
    }
};
