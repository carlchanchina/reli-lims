frappe.ui.form.on("Test Standard", {
    refresh(frm) {
        reli_lims.relations.mount_standard(frm);
    },
});
