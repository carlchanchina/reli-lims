frappe.ui.form.on("Test Standard", {
    refresh(frm) {
        if (reli_lims.relations.mount_standard) {
            reli_lims.relations.mount_standard(frm);
        }
    },
});
