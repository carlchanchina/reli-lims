frappe.ui.form.on("Test Object", {
    refresh(frm) {
        reli_lims.relations.mount_object(frm);
    },
});
