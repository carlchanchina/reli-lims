frappe.provide("reli_lims.relations");

frappe.ui.form.on("Item", {
    refresh(frm) {
        if (reli_lims.relations.mount_item) {
            reli_lims.relations.mount_item(frm);
        }
    },
});
