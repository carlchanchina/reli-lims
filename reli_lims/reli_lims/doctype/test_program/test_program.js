frappe.ui.form.on("Test Program", {
    setup(frm) {
        frm.set_query("sample", "samples", () => ({ filters: { project: frm.doc.project } }));
        frm.set_query("sample", "sample_assignments", () => ({
            filters: { name: ["in", (frm.doc.samples || []).map(row => row.sample).filter(Boolean)] }
        }));
    },
    refresh(frm) {
        frm.set_intro(__("请逐步保存状态：待安排 → 待执行 → 执行中 → 已完成 → 已复核。完成时须填写结果和结论；复核须由检测复核员或实验室负责人执行。"), "blue");
        frm.events.update_item_choices(frm);
        if (!frm.is_new() && (frm.doc.items || []).length && frm.doc.items.every(row => row.status === 'Reviewed') &&
            frappe.model.can_create('Test Report')) {
            frm.add_custom_button(__('编制检测报告'), () => frappe.new_doc('Test Report', {
                project: frm.doc.project, test_program: frm.doc.name,
                test_request: frm.doc.test_request, engineer: frm.doc.responsible_engineer
            }));
        }
    },
    update_item_choices(frm) {
        for (const row of frm.doc.items || []) {
            row.applicable_sample_names = (frm.doc.sample_assignments || [])
                .filter(pair => pair.item_code === row.item_code).map(pair => pair.sample).join('、');
        }
        const codes = (frm.doc.items || []).map(row => row.item_code).filter(Boolean)
            .map(value => ({ value, label: frappe.utils.escape_html(value) }));
        frm.fields_dict.sample_assignments.grid.update_docfield_property("item_code", "options", codes);
    }
});

frappe.ui.form.on("Test Program Item", {
    before_items_remove(frm, cdt, cdn) {
        const item = frappe.get_doc(cdt, cdn);
        if (["Running", "Completed", "Reviewed"].includes(item.status)) {
            frappe.throw(__("检测项目 {0} 已开始执行，不能删除。", [frappe.utils.escape_html(item.item_code)]));
        }
        program_remove_assignments(frm, row => row.item_code === item.item_code);
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
        if (sample) {
            const locked = new Set((frm.doc.items || []).filter(row =>
                ['Running', 'Completed', 'Reviewed'].includes(row.status)).map(row => row.item_code));
            if ((frm.doc.sample_assignments || []).some(row => row.sample === sample && locked.has(row.item_code))) {
                frappe.throw(__("试验已开始，不能移除此样品。"));
            }
            program_remove_assignments(frm, row => row.sample === sample);
        }
    }
});

frappe.ui.form.on('Test Program Item', {
    select_samples(frm, cdt, cdn) {
        const item = frappe.get_doc(cdt, cdn);
        if (['Running', 'Completed', 'Reviewed'].includes(item.status)) {
            frappe.throw(__("开始执行后，检测依据与适用样品将锁定。"));
        }
        if (!item.item_code) frappe.throw(__("请先填写试验项目编号。"));
        const samples = (frm.doc.samples || []).filter(row => row.sample);
        if (!samples.length) frappe.throw(__("请先选择方案样品。"));
        const selected = (frm.doc.sample_assignments || []).filter(row => row.item_code === item.item_code).map(row => row.sample);
        const dialog = new frappe.ui.Dialog({title: __("选择适用样品"), fields: [
            {fieldname: 'samples', fieldtype: 'MultiCheck', columns: 2,
                options: samples.map(row => ({value: row.sample,
                    label: frappe.utils.escape_html(`${row.sample_label || ''} ${row.sample}`),
                    checked: selected.includes(row.sample)}))}
        ], primary_action_label: __("应用"), primary_action(values) {
            const allowed = new Set(samples.map(row => row.sample));
            const chosen = [...new Set(values.samples || [])].filter(name => allowed.has(name));
            const retained = (frm.doc.sample_assignments || []).filter(row => row.item_code && row.item_code !== item.item_code)
                .map(row => ({item_code: row.item_code, sample: row.sample}));
            frm.clear_table('sample_assignments');
            for (const pair of retained.concat(chosen.map(sample => ({item_code: item.item_code, sample})))) {
                frm.add_child('sample_assignments', pair);
            }
            frm.events.update_item_choices(frm);
            frm.refresh_field('items');
            frm.dirty();
            dialog.hide();
        }});
        dialog.show();
    }
});

function program_remove_assignments(frm, remove) {
    const retained = (frm.doc.sample_assignments || []).filter(row => !remove(row))
        .map(row => ({item_code: row.item_code, sample: row.sample}));
    frm.clear_table('sample_assignments');
    for (const row of retained) frm.add_child('sample_assignments', row);
    frm.events.update_item_choices(frm);
    frm.refresh_field('items');
}

frappe.ui.form.on('Test Program Item', {
    items_add(frm, cdt, cdn) {
        const row = frappe.get_doc(cdt, cdn);
        const used = new Set((frm.doc.items || []).map(item => item.item_code));
        let number = 1;
        while (used.has('T' + number)) number++;
        row.item_code = 'T' + number;
        row.status = 'Pending';
        frm.refresh_field('items');
        frm.events.update_item_choices(frm);
    }
});
