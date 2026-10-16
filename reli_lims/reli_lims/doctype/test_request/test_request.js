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
        frm.fields_dict.photos.grid.update_docfield_property('sample_code', 'options', choices('samples'));
        frm.fields_dict.sample_assignments.grid.update_docfield_property('sample_code', 'options', choices('samples'));
        frm.fields_dict.sample_assignments.grid.update_docfield_property('item_code', 'options', choices('items'));
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

frappe.ui.form.on('Test Request Sample', {
    sample_code(frm) {frm.events.update_choices(frm);},
    before_samples_remove(frm, cdt, cdn) {
        const code=frappe.get_doc(cdt,cdn).sample_code;
        if (code && ([...(frm.doc.photos || []),...(frm.doc.sample_assignments || [])]).some(row=>row.sample_code===code)) {
            frappe.throw(__('Remove photo and test assignments before deleting this sample.'));
        }
    }
});
frappe.ui.form.on('Test Request Item', {
    item_code(frm) {frm.events.update_choices(frm);},
    before_items_remove(frm, cdt, cdn) {
        const code=frappe.get_doc(cdt,cdn).item_code;
        if (code && (frm.doc.sample_assignments || []).some(row=>row.item_code===code)) {
            frappe.throw(__('Remove sample assignments before deleting this test item.'));
        }
    }
});
