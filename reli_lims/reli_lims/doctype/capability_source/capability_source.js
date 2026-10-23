frappe.ui.form.on('Capability Source', {
    refresh(frm) {
        if (frm.is_new() || frm.doc.documents_review_status !== 'Approved') return;
        if (!(frappe.user.has_role('Lab Manager') || frappe.user.has_role('System Manager'))) return;
        frm.add_custom_button(__('导入能力'), () => frappe.call({
            method: 'reli_lims.capability_api.import_capability_source',
            args: {source_name: frm.doc.name}, freeze: true,
            callback: (r) => { frappe.msgprint(JSON.stringify(r.message)); frm.reload_doc(); }
        }));
    }
});
