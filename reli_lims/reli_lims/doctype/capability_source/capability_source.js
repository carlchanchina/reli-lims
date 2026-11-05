frappe.ui.form.on('Capability Source', {
    refresh(frm) {
        if (frm.is_new() || frm.doc.documents_review_status !== 'Approved') return;
        if (!(frappe.user.has_role('Lab Manager') || frappe.user.has_role('System Manager'))) return;
        frm.add_custom_button(__('导入能力'), () => {
            if (frm.is_dirty()) { frappe.msgprint(__("请先保存修改，再执行操作。")); return; }
            return frappe.call({
            method: 'reli_lims.capability_api.import_capability_source',
            args: {source_name: frm.doc.name}, freeze: true,
            callback: (r) => { frappe.msgprint(JSON.stringify(r.message)); frm.reload_doc(); }
        }); });
    }
});

frappe.ui.form.on("Capability Source", {
    refresh(frm) {
        if (frm.is_new()) return;
        render_source_overview(frm);
        frm.add_custom_button(__("CNAS 能力明细表"), async () => {
            await frappe.require("capability_grid.bundle.js");
            await frappe.require("/assets/reli_lims/js/capability_selector.js");
            return reli_lims.capabilities.open({mode: "catalog", source: frm.doc.name});
        });
    },
});

function render_source_overview(frm) {
    const wrapper = frm.fields_dict.capability_overview?.$wrapper;
    if (!wrapper) return;
    wrapper.empty();
    frappe.call({
        method: "reli_lims.capability_catalog.source_details",
        args: {source: frm.doc.name},
    }).then(({message}) => {
        const summary = $("<div class='d-flex flex-wrap gap-2 mb-3'>").appendTo(wrapper);
        for (const [label, value] of [
            [__("能力"), message.capabilities], [__("检测项目"), message.projects],
            [__("检测对象"), message.objects], [__("检测依据"), message.standards],
            [__("待归类"), message.unclassified],
        ]) {
            $("<div class='border rounded px-3 py-2'>").append(
                $("<div class='text-muted small'>").text(label),
                $("<div class='h5 mb-0'>").text(value || 0),
            ).appendTo(summary);
        }
        $("<button type='button' class='btn btn-primary btn-sm mr-2'>")
            .text(__("按项目、对象、依据、实验室筛选"))
            .on("click", async () => {
                await frappe.require("capability_grid.bundle.js");
                await frappe.require("/assets/reli_lims/js/capability_selector.js");
                reli_lims.capabilities.open({mode: "catalog", source: frm.doc.name});
            }).appendTo(wrapper);
        $("<button type='button' class='btn btn-default btn-sm'>")
            .text(__("添加实验室能力"))
            .on("click", () => frappe.new_doc("Laboratory Capability", {
                laboratory: frm.doc.laboratory, source: frm.doc.name,
            })).appendTo(wrapper);
    });
}
