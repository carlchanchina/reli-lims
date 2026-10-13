frappe.ui.form.on("Test Program", {
    setup(frm) {
        frm.set_query("sample", "samples", () => ({ filters: { project: frm.doc.project } }));
        frm.set_query("sample", "sample_assignments", () => ({
            filters: { name: ["in", (frm.doc.samples || []).map(row => row.sample).filter(Boolean)] }
        }));
    },
    refresh(frm) {
        frm.events.update_item_choices(frm);
    },
    update_item_choices(frm) {
        const codes = (frm.doc.items || []).map(row => row.item_code).filter(Boolean)
            .map(value => ({ value, label: frappe.utils.escape_html(value) }));
        frm.fields_dict.sample_assignments.grid.update_docfield_property("item_code", "options", codes);
    }
});

frappe.ui.form.on("Test Program Item", {
    item_code(frm) {
        frm.events.update_item_choices(frm);
    },
    items_remove(frm) {
        frm.events.update_item_choices(frm);
    }
});
