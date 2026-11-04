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
        frm.add_custom_button(__("CNAS 能力明细表"), async () => {
            await frappe.require("/assets/reli_lims/js/capability_grid.js");
            await frappe.require("/assets/reli_lims/js/capability_selector.js");
            return reli_lims.capabilities.open({mode: "catalog", source: frm.doc.name});
        });
    },
});
