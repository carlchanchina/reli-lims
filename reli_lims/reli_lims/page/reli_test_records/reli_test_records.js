frappe.pages["reli-test-records"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({parent: wrapper, title: __("试验记录"), single_column: true});
    $("<p class='text-muted'>").text(__("查看方案内的试验条件、进度和结果，打开试验方案填写原始记录与复核结论。"))
        .appendTo(page.body);
    const host = $("<div>").appendTo(page.body);
    let start = 0;
    let generation = 0;
    let search;
    search = page.add_field({fieldname: "search", label: __("搜索"), fieldtype: "Data",
        change() { start = 0; load(); }});
    async function load() {
        const current = ++generation;
        const {message} = await frappe.call("reli_lims.execution_records.list_records", {
            text: search?.get_value(), start,
        });
        if (current !== generation) return;
        host.empty();
        const table = $("<table class='table table-bordered table-hover'>").appendTo(host);
        const header = $("<tr>").appendTo($("<thead>").appendTo(table));
        ["试验方案", "检测项目", "检测依据（标准/方法）", "试验条件", "状态", "结果", "结论"]
            .forEach(label => $("<th>").text(__(label)).appendTo(header));
        const body = $("<tbody>").appendTo(table);
        for (const row of message.rows) {
            const tr = $("<tr>").appendTo(body);
            $("<a>").attr("href", `/desk/reli-lims/test-program/${encodeURIComponent(row.parent)}`)
                .text(row.program_title).appendTo($("<td>").appendTo(tr));
            [row.project_label, row.standard_label, row.test_condition, __(row.status, null, "Test Program Item"), row.result, row.conclusion]
                .forEach(value => $("<td>").text(value || "—").appendTo(tr));
        }
        if (!message.rows.length) $("<td colspan='7'>").text(__("暂无匹配的试验记录"))
            .appendTo($("<tr>").appendTo(body));
        const pager = $("<div class='d-flex align-items-center gap-2'>").appendTo(host);
        $("<button class='btn btn-default btn-sm'>").text(__("上一页")).prop("disabled", start === 0)
            .on("click", () => { start = Math.max(0, start - 20); load(); }).appendTo(pager);
        $("<span>").text(__("第 {0} 页", [start / 20 + 1])).appendTo(pager);
        $("<button class='btn btn-default btn-sm'>").text(__("下一页")).prop("disabled", !message.has_more)
            .on("click", () => { start += 20; load(); }).appendTo(pager);
    };
    wrapper.reli_load_records = load;
};
frappe.pages["reli-test-records"].on_page_show = function (wrapper) {
    wrapper.reli_load_records();
};
