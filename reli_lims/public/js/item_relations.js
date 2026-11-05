frappe.ui.form.on("Item", {
    refresh(frm) {
        reli_lims.relations.mount_item(frm);
    },
});
