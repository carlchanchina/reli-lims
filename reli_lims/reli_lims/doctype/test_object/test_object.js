frappe.ui.form.on("Test Object", {
    refresh(frm) {
        if (reli_lims.relations.mount_object) {
            reli_lims.relations.mount_object(frm);
        }
    },
});
