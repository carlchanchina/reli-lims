frappe.ui.form.on('Test Request', {
    refresh(frm) {
        frm.events.update_choices(frm);
        if (frm.doc.docstatus !== 1) return;
        if (frm.doc.project) {
            frm.add_custom_button(__('Project'), () => frappe.set_route('Form', 'Project', frm.doc.project));
            frm.add_custom_button(__('Tasks'), () => frappe.set_route('List', 'Task', {project: frm.doc.project}));
        }
        if (!frappe.user_roles.some(role => ['Lab Manager', 'Lab Engineer'].includes(role))) return;
        frm.add_custom_button(__('Receive Samples'), () => frm.events.receive_samples(frm));
        frm.add_custom_button(__('Create Test Program'), () => {
            frappe.call({method: 'reli_lims.services.test_request.make_test_program',
                args: {request_name: frm.doc.name}, freeze: true,
                callback: response => {
                    if (response.message) frappe.set_route('Form', 'Test Program', response.message);
                }});
        });
    },
    update_choices(frm) {
        const choices = field => (frm.doc[field] || []).map(row => {
            const value = row[field === 'samples' ? 'sample_code' : 'item_code'];
            return value ? {value, label: frappe.utils.escape_html(value)} : null;
        }).filter(Boolean);
        frm._request_codes = frm._request_codes || {};
        for (const [table, key] of [['samples','sample_code'],['items','item_code']]) {
            for (const row of frm.doc[table] || []) {
                if (row.name && row[key]) frm._request_codes[row.name] = row[key];
            }
        }
        frm.fields_dict.photos.grid.update_docfield_property('sample_code', 'options', choices('samples'));
        frm.fields_dict.sample_assignments.grid.update_docfield_property('sample_code', 'options', choices('samples'));
        frm.fields_dict.sample_assignments.grid.update_docfield_property('item_code', 'options', choices('items'));
        for (const row of frm.doc.items || []) {
            row.applicable_sample_codes = (frm.doc.sample_assignments || [])
                .filter(pair => pair.item_code === row.item_code).map(pair => pair.sample_code).join(', ');
        }
    },
    receive_samples(frm) {
        frappe.call({method:'reli_lims.services.test_request.get_receivable_samples',
            args:{request_name:frm.doc.name},callback:response => {
                if (!response.message) return;
                if (!response.message.length) {
                    frappe.msgprint(__('All requested samples have been received.'));
                    return;
                }
                frm.events.open_receipts(frm, response.message);
            }});
    },
    open_receipts(frm, pending) {
        const dialog = new frappe.ui.Dialog({title: __('Receive Samples'), size: 'extra-large', fields: [
            {fieldtype: 'HTML', options: __('Select the rows being received. Explain any quantity difference.')},
            {fieldname: 'receipts', fieldtype: 'Table', label: __('Sample Receipts'),
                cannot_add_rows: true, cannot_delete_rows: true,
                data: pending.map(row => ({sample_code: row.sample_code,
                    product_name: row.product_name, quantity: row.quantity,
                    received_date: frappe.datetime.get_today(), received_by: frappe.session.user})),
                fields: [
                    {fieldname:'sample_code',fieldtype:'Data',label:__('Request Sample Code'),read_only:1,in_list_view:1},
                    {fieldname:'product_name',fieldtype:'Data',label:__('Product Name'),read_only:1},
                    {fieldname:'quantity',fieldtype:'Float',label:__('Received Quantity'),reqd:1,in_list_view:1},
                    {fieldname:'received_date',fieldtype:'Date',label:__('Received Date'),reqd:1,in_list_view:1},
                    {fieldname:'received_by',fieldtype:'Link',options:'User',label:__('Received By'),reqd:1},
                    {fieldname:'condition',fieldtype:'Small Text',label:__('Condition')},
                    {fieldname:'difference_reason',fieldtype:'Small Text',label:__('Quantity Difference Reason')}
                ]}
        ], primary_action_label: __('Receive Samples'), primary_action() {
            const receipts = dialog.fields_dict.receipts.grid.get_selected_children().map(row => ({
                sample_code:row.sample_code,quantity:row.quantity,received_date:row.received_date,
                received_by:row.received_by,condition:row.condition,difference_reason:row.difference_reason
            }));
            if (!receipts.length) frappe.throw(__('Select at least one sample to receive.'));
            frappe.call({method:'reli_lims.services.test_request.receive_samples',
                args:{request_name:frm.doc.name,receipts},freeze:true,
                callback:response => {
                    if (response.message) {
                        dialog.hide();
                        frappe.msgprint(__('Samples received: {0}', [response.message.join(', ')]));
                        frm.reload_doc();
                    }
                }});
        }});
        dialog.show();
    }
});

function request_rekey(doc, key, old_code, new_code) {
    if (!old_code || !new_code || old_code === new_code) return;
    for (const row of doc.sample_assignments || []) {
        if (row[key] === old_code) row[key] = new_code;
    }
    if (key === 'sample_code') {
        for (const photo of doc.photos || []) {
            if (photo.sample_code === old_code) photo.sample_code = new_code;
        }
    }
}

function request_code_changed(frm, cdt, cdn, key) {
    const row = frappe.get_doc(cdt, cdn);
    request_rekey(frm.doc, key, (frm._request_codes || {})[cdn], row[key]);
    frm.events.update_choices(frm);
    frm.refresh_field('photos');
    frm.refresh_field('items');
}

frappe.ui.form.on('Test Request Sample', {
    sample_code(frm, cdt, cdn) {request_code_changed(frm, cdt, cdn, 'sample_code');},
    before_samples_remove(frm, cdt, cdn) {
        const code=frappe.get_doc(cdt,cdn).sample_code;
        if (code && ([...(frm.doc.photos || []),...(frm.doc.sample_assignments || [])]).some(row=>row.sample_code===code)) {
            frappe.throw(__('Remove photo and test assignments before deleting this sample.'));
        }
    }
});
function request_assignments_for_item(assignments, item_code, selected) {
    return assignments.filter(row => (row.item_code || row.sample_code) && row.item_code !== item_code)
        .map(row => ({item_code: row.item_code, sample_code: row.sample_code}))
        .concat([...new Set(selected)].map(sample_code => ({item_code, sample_code})));
}

frappe.ui.form.on('Test Request Item', {
    select_samples(frm, cdt, cdn) {
        if (frm.doc.docstatus !== 0) return;
        const item = frappe.get_doc(cdt, cdn);
        if (!item.item_code) frappe.throw(__('Enter the test item code first.'));
        const rows = (frm.doc.samples || []).filter(row => row.sample_code);
        if (!rows.length) frappe.throw(__('Add the requested samples first.'));
        const selected = (frm.doc.sample_assignments || []).filter(row => row.item_code === item.item_code)
            .map(row => row.sample_code);
        const dialog = new frappe.ui.Dialog({title: __('Select Applicable Samples'), fields: [
            {fieldname: 'samples', fieldtype: 'MultiCheck', columns: 2,
                options: rows.map(row => ({value: row.sample_code,
                    label: frappe.utils.escape_html(`${row.sample_code} - ${row.product_name || ''}`),
                    checked: selected.includes(row.sample_code)}))}
        ], primary_action_label: __('Apply'), primary_action(values) {
            const allowed = new Set(rows.map(row => row.sample_code));
            const chosen = (values.samples || []).filter(code => allowed.has(code));
            const pairs = request_assignments_for_item(frm.doc.sample_assignments || [], item.item_code, chosen);
            frm.clear_table('sample_assignments');
            for (const pair of pairs) frm.add_child('sample_assignments', pair);
            frm.events.update_choices(frm);
            frm.refresh_field('items');
            frm.dirty();
            dialog.hide();
        }});
        dialog.show();
    },
    item_code(frm, cdt, cdn) {request_code_changed(frm, cdt, cdn, 'item_code');},
    before_items_remove(frm, cdt, cdn) {
        const code=frappe.get_doc(cdt,cdn).item_code;
        if (code && (frm.doc.sample_assignments || []).some(row=>row.item_code===code)) {
            frappe.throw(__('Remove sample assignments before deleting this test item.'));
        }
    }
});
