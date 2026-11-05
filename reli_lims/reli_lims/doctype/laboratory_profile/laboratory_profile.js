frappe.ui.form.on("Laboratory Profile", {
  refresh(frm) {
    render_capability_overview(frm);
    if (frm.doc.review_status !== "Pending" || !frappe.user.has_role("Lab Reviewer")) return;
    for (const [label, approve] of [["通过审核", true], ["退回修改", false]]) {
      frm.add_custom_button(__(label), () => {
        frappe.prompt(
          [{ fieldname: "note", fieldtype: "Small Text", label: __("审核备注") }],
          async ({ note }) => {
            await frappe.call({
              method: "reli_lims.laboratory_api.review_profile",
              args: {
                seller_id: frm.doc.mercur_seller_id,
                revision: frm.doc.draft_revision,
                approve,
                note: note || "",
              },
            });
            await frm.reload_doc();
          },
          __(label),
          __("确认"),
        );
      });
    }
  },
});

function render_capability_overview(frm) {
  const wrapper = frm.fields_dict.capability_overview?.$wrapper;
  if (!wrapper) return;
  wrapper.empty();
  if (frm.is_new()) {
    wrapper.text(__("保存实验室资料后可查看能力、来源与服务商品。"));
    return;
  }
  frappe.call({
    method: "reli_lims.capability_catalog.laboratory_details",
    args: {laboratory: frm.doc.name},
  }).then(({message}) => {
    const counts = message.counts || {};
    const summary = $("<div class='d-flex flex-wrap gap-2 mb-3'>").appendTo(wrapper);
    for (const [label, value] of [
      [__("检测能力"), counts.capabilities], [__("能力来源"), counts.sources],
      [__("检测项目"), counts.projects], [__("服务商品"), counts.items],
    ]) {
      $("<div class='border rounded px-3 py-2'>").append(
        $("<div class='text-muted small'>").text(label),
        $("<div class='h5 mb-0'>").text(value || 0),
      ).appendTo(summary);
    }
    $("<button type='button' class='btn btn-primary btn-sm mr-2 mb-3'>")
      .text(__("添加实验室能力"))
      .on("click", () => frappe.new_doc("Laboratory Capability", {laboratory: frm.doc.name}))
      .appendTo(wrapper);
    $("<button type='button' class='btn btn-default btn-sm mr-2 mb-3'>")
      .text(__("查看全部能力"))
      .on("click", () => frappe.set_route("List", "Laboratory Capability", {laboratory: frm.doc.name}))
      .appendTo(wrapper);
    $("<button type='button' class='btn btn-default btn-sm mb-3'>")
      .text(__("查看能力来源"))
      .on("click", () => frappe.set_route("List", "Capability Source", {laboratory: frm.doc.name}))
      .appendTo(wrapper);

    render_lab_capability_table(wrapper, __("检测能力"), ["检测对象", "检测项目", "检测依据", "审核状态", "来源行"], message.capabilities,
      row => [row.object_label || row.product_scope, row.project_label, row.standard_label, row.status, row.source_row],
      row => ["Laboratory Capability", row.name]);
    render_lab_capability_table(wrapper, __("能力来源"), ["来源", "类型", "证书编号", "文档审核", "导入状态"], message.sources,
      row => [row.name, row.source_type, row.certificate_no, row.documents_review_status, row.import_status],
      row => ["Capability Source", row.name]);
    render_lab_capability_table(wrapper, __("服务商品"), ["服务名称", "Item 编码", "检测项目"], message.items,
      row => [row.item_name, row.item_code, row.project_label], row => ["Item", row.name]);
  });
}

function render_lab_capability_table(wrapper, title, headers, rows, values, route) {
  $("<h6 class='mt-3'>").text(`${title} · ${rows.length}`).appendTo(wrapper);
  if (!rows.length) {
    $("<p class='text-muted'>").text(__("暂无记录")).appendTo(wrapper);
    return;
  }
  const grid = $("<table class='table table-sm table-bordered'>").appendTo(wrapper);
  const heading = $("<tr>").appendTo($("<thead>").appendTo(grid));
  [...headers, __("操作")].forEach(label => $("<th scope='col'>").text(__(label)).appendTo(heading));
  const body = $("<tbody>").appendTo(grid);
  for (const row of rows) {
    const tr = $("<tr>").appendTo(body);
    values(row).forEach(value => $("<td>").text(value || "—").appendTo(tr));
    const [doctype, name] = route(row);
    $("<td>").append($("<button type='button' class='btn btn-xs btn-default'>").text(__("打开"))
      .on("click", () => frappe.set_route("Form", doctype, name))).appendTo(tr);
  }
}
