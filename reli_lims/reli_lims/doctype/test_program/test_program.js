frappe.ui.form.on("Test Program", {
    setup(frm) {
        frm.set_query("sample", "samples", () => ({ filters: { project: frm.doc.project } }));
        frm.set_query("sample", "sample_assignments", () => ({
            filters: { name: ["in", (frm.doc.samples || []).map(row => row.sample).filter(Boolean)] }
        }));
    },
    refresh(frm) {
        frm.set_intro(__("Save each status transition separately: Pending → Ready → Running → Completed → Reviewed. Completion needs a result and conclusion; review requires Lab Reviewer or Lab Manager."), "blue");
        frm.events.update_item_choices(frm);
    },
    update_item_choices(frm) {
        const codes = (frm.doc.items || []).map(row => row.item_code).filter(Boolean)
            .map(value => ({ value, label: frappe.utils.escape_html(value) }));
        frm.fields_dict.sample_assignments.grid.update_docfield_property("item_code", "options", codes);
    }
});

frappe.ui.form.on("Test Program Item", {
    before_items_remove(frm, cdt, cdn) {
        const item = frappe.get_doc(cdt, cdn);
        if (["Running", "Completed", "Reviewed"].includes(item.status)) {
            frappe.throw(__("Item {0} has started and cannot be removed.", [frappe.utils.escape_html(item.item_code)]));
        }
        if (item.item_code && (frm.doc.sample_assignments || []).some(row => row.item_code === item.item_code)) {
            frappe.throw(__("Item {0}: remove its Sample Assignments rows before deleting this item.", [frappe.utils.escape_html(item.item_code)]));
        }
    },
    item_code(frm) {
        frm.events.update_item_choices(frm);
    },
    items_remove(frm) {
        frm.events.update_item_choices(frm);
    }
});

frappe.ui.form.on("Test Program Sample", {
    before_samples_remove(frm, cdt, cdn) {
        const sample = frappe.get_doc(cdt, cdn).sample;
        if (sample && (frm.doc.sample_assignments || []).some(row => row.sample === sample)) {
            frappe.throw(__("Sample {0}: remove its Sample Assignments rows before deleting this sample.", [frappe.utils.escape_html(sample)]));
        }
    }
});
