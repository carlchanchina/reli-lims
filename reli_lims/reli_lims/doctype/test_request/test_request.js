frappe.ui.form.on('Test Request', {
    setup(frm) {
        frm.set_query('quotation', () => ({filters: {
            quotation_to: 'Customer', party_name: frm.doc.customer,
            company: frm.doc.company, docstatus: 1
        }}));
        frm.set_query('sales_order', () => ({filters: {
            customer: frm.doc.customer, company: frm.doc.company, docstatus: 1
        }}));
    },
    refresh(frm) {
        frm.events.update_choices(frm);
        if (frm.doc.docstatus === 0 && !frm.is_new() &&
            frappe.user_roles.some(role => ['Lab Manager', 'Lab Engineer'].includes(role))) {
            frm.add_custom_button(__('请求客户确认'), () => {
                if (frm.is_dirty()) { frappe.msgprint(__('请先保存委托内容，再请求客户确认。')); return; }
                frm.call('request_customer_confirmation').then(() => frm.reload_doc());
            });
            frm.add_custom_button(__('分享私有附件给客户'), () => {
                if (frm.is_dirty()) { frappe.msgprint(__('请先保存委托内容，再分享附件。')); return; }
                frappe.prompt([{fieldname:'file_id',fieldtype:'Link',options:'File',label:__('当前委托私有附件'),reqd:1,
                    get_query: () => ({filters:{attached_to_doctype:'Test Request',attached_to_name:frm.doc.name,is_private:1}})}],
                    values => frm.call('share_customer_attachment', values).then(() => frm.reload_doc()), __('分享委托附件'));
            });
        }
        frm.events.customer_collaboration(frm);
        if (frm.doc.docstatus !== 1) return;
        if (frm.doc.project) {
            frm.add_custom_button(__("项目"), () => frappe.set_route('Form', 'Project', frm.doc.project));
            frm.add_custom_button(__("任务"), () => frappe.set_route('List', 'Task', {project: frm.doc.project}));
        }
        if (!frappe.user_roles.some(role => ['Lab Manager', 'Lab Engineer'].includes(role))) return;
        frm.add_custom_button(__("登记收样"), () => frm.events.receive_samples(frm));
        frm.add_custom_button(__("生成实验计划"), () => {
            frappe.call({method: 'reli_lims.services.test_request.make_test_program',
                args: {request_name: frm.doc.name}, freeze: true,
                callback: response => {
                    if (response.message) frappe.set_route('Form', 'Test Program', response.message);
                }});
        });
    },
    customer_collaboration(frm) {
        if (frm.doc.docstatus !== 0 || frm.is_new()) return;
        if (!frappe.user_roles.some(role => ['Lab Manager', 'Lab Engineer'].includes(role))) return;
        const group = __('客户共同填写');
        const state = frm.doc.customer_confirmation_state;

        frm.add_custom_button(__('发送客户填写链接'), () => {
            if (frm.is_dirty()) { frappe.msgprint(__('请先保存委托内容，再发送客户链接。')); return; }
            const dialog = new frappe.ui.Dialog({
                title: __('发送客户填写链接'),
                fields: [
                    {fieldname: 'expires_days', fieldtype: 'Int', label: __('链接有效期（天）'), default: 7, reqd: 1},
                    {fieldname: 'customer_email', fieldtype: 'Data', label: __('客户邮箱（可选）'), default: frm.doc.contact_email || ''},
                ],
                primary_action_label: __('生成链接'),
                primary_action(values) {
                    frm.call({method: 'send_customer_fill_link', args: values}).then(response => {
                        dialog.hide();
                        const data = response.message || {};
                        frappe.msgprint({
                            title: __('客户填写链接已生成'),
                            indicator: 'green',
                            message: `<p>${__('请把下面的链接发给客户，客户免登录即可填写。')}</p>
                                <p><a href="${data.url}" target="_blank">${data.url}</a></p>
                                <p class="text-muted">${__('有效期至')} ${data.expires_on}</p>`,
                        });
                        frm.reload_doc();
                    });
                },
            });
            dialog.show();
        }, group);

        frm.add_custom_button(__('查看客户链接'), () => {
            frm.call('list_links').then(response => {
                const rows = response.message || [];
                if (!rows.length) { frappe.msgprint(__('尚未生成客户填写链接。')); return; }
                const body = rows.map(row => `<tr>
                    <td><a href="${row.url}" target="_blank">${__('打开')}</a></td>
                    <td>${row.status}</td><td>${row.expires_on}</td>
                    <td>${row.used ? row.used_on : __('未填写')}</td><td>${row.use_count}</td></tr>`).join('');
                frappe.msgprint({
                    title: __('客户填写链接'),
                    wide: true,
                    message: `<table class="table table-bordered table-sm"><thead><tr>
                        <th></th><th>${__('状态')}</th><th>${__('有效期至')}</th>
                        <th>${__('首次填写')}</th><th>${__('填写次数')}</th></tr></thead><tbody>${body}</tbody></table>`,
                });
            });
        }, group);

        if (['Draft', 'Awaiting Customer Confirmation', 'Needs Reconfirmation'].includes(state)) {
            frm.add_custom_button(__('撤销客户链接'), () => {
                frappe.confirm(__('撤销后客户将无法再通过现有链接填写，是否继续？'), () => {
                    frm.call('revoke_customer_fill_link').then(() => {
                        frappe.show_alert({message: __('链接已撤销'), indicator: 'orange'});
                        frm.reload_doc();
                    });
                });
            }, group);
        }

        if (state === 'Awaiting Lab Review') {
            frm.add_custom_button(__('实验室审核'), () => {
                const dialog = new frappe.ui.Dialog({
                    title: __('实验室审核客户填写内容'),
                    fields: [{fieldname: 'note', fieldtype: 'Small Text', label: __('审核意见')}],
                    primary_action_label: __('通过并允许正式受理'),
                    primary_action(values) {
                        frm.call({method: 'review_customer_fill', args: {approve: 1, note: values.note}})
                            .then(() => { dialog.hide(); frm.reload_doc(); });
                    },
                    secondary_action_label: __('退回客户补充'),
                    secondary_action() {
                        frm.call({method: 'review_customer_fill', args: {approve: 0, note: dialog.get_value('note')}})
                            .then(() => { dialog.hide(); frm.reload_doc(); });
                    },
                });
                dialog.show();
            }, group).addClass('btn-primary');
        }
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
                    frappe.msgprint(__("所有委托样品均已完成收样。"));
                    return;
                }
                frm.events.open_receipts(frm, response.message);
            }});
    },
    open_receipts(frm, pending) {
        const dialog = new frappe.ui.Dialog({title: __("登记收样"), size: 'extra-large', fields: [
            {fieldtype: 'HTML', options: __("请选择本次接收的样品行；数量不一致时请填写原因。")},
            {fieldname: 'receipts', fieldtype: 'Table', label: __("样品接收"),
                cannot_add_rows: true, cannot_delete_rows: true,
                data: pending.map(row => ({sample_code: row.sample_code,
                    product_name: row.product_name, quantity: row.quantity,
                    received_date: frappe.datetime.get_today(), received_by: frappe.session.user})),
                fields: [
                    {fieldname:'sample_code',fieldtype:'Data',label:__("委托样品编号"),read_only:1,in_list_view:1},
                    {fieldname:'product_name',fieldtype:'Data',label:__("产品名称"),read_only:1},
                    {fieldname:'quantity',fieldtype:'Float',label:__("实际接收数量"),reqd:1,in_list_view:1},
                    {fieldname:'received_date',fieldtype:'Date',label:__("收样日期"),reqd:1,in_list_view:1},
                    {fieldname:'received_by',fieldtype:'Link',options:'User',label:__("收样人"),reqd:1},
                    {fieldname:'condition',fieldtype:'Small Text',label:__("条件")},
                    {fieldname:'difference_reason',fieldtype:'Small Text',label:__("数量差异说明")}
                ]}
        ], primary_action_label: __("登记收样"), primary_action() {
            const receipts = dialog.fields_dict.receipts.grid.get_selected_children().map(row => ({
                sample_code:row.sample_code,quantity:row.quantity,received_date:row.received_date,
                received_by:row.received_by,condition:row.condition,difference_reason:row.difference_reason
            }));
            if (!receipts.length) frappe.throw(__("请至少选择一个待接收样品。"));
            frappe.call({method:'reli_lims.services.test_request.receive_samples',
                args:{request_name:frm.doc.name,receipts},freeze:true,
                callback:response => {
                    if (response.message) {
                        dialog.hide();
                        frappe.msgprint(__("已接收样品：{0}", [response.message.join(', ')]));
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
        frm.doc.sample_assignments = (frm.doc.sample_assignments || []).filter(row => row.sample_code !== code);
        frm.doc.photos = (frm.doc.photos || []).filter(row => row.sample_code !== code);
        frm.refresh_field('photos');
        frm.events.update_choices(frm);
        frm.refresh_field('items');
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
        if (!item.item_code) frappe.throw(__("请先填写试验项目编号。"));
        const rows = (frm.doc.samples || []).filter(row => row.sample_code);
        if (!rows.length) frappe.throw(__("请先填写委托样品。"));
        const selected = (frm.doc.sample_assignments || []).filter(row => row.item_code === item.item_code)
            .map(row => row.sample_code);
        const dialog = new frappe.ui.Dialog({title: __("选择适用样品"), fields: [
            {fieldname: 'samples', fieldtype: 'MultiCheck', columns: 2,
                options: rows.map(row => ({value: row.sample_code,
                    label: frappe.utils.escape_html(`${row.sample_code} - ${row.product_name || ''}`),
                    checked: selected.includes(row.sample_code)}))}
        ], primary_action_label: __("应用"), primary_action(values) {
            const allowed = new Set(rows.map(row => row.sample_code));
            const chosen = (values.samples || []).filter(code => allowed.has(code));
            const pairs = request_assignments_for_item(frm.doc.sample_assignments || [], item.item_code, chosen);
            frm.clear_table('sample_assignments');
            for (const pair of pairs) frm.add_child('sample_assignments', pair);
            frm.events.update_choices(frm);
            frm.refresh_field('items');
            frm.dirty();
            window.reli_lims?.capabilities?.mount?.(frm, "request");
            dialog.hide();
        }});
        dialog.show();
    },
    item_code(frm, cdt, cdn) {request_code_changed(frm, cdt, cdn, 'item_code');},
    before_items_remove(frm, cdt, cdn) {
        const code=frappe.get_doc(cdt,cdn).item_code;
        frm.doc.sample_assignments = (frm.doc.sample_assignments || []).filter(row => row.item_code !== code);
    }
});

function request_next_code(rows, field, prefix) {
    const used = new Set(rows.map(row => row[field]));
    let number = 1;
    while (used.has(prefix + number)) number++;
    return prefix + number;
}
frappe.ui.form.on('Test Request Sample', {
    samples_add(frm, cdt, cdn) {
        const row = frappe.get_doc(cdt, cdn);
        row.sample_code = request_next_code(frm.doc.samples || [], 'sample_code', 'S');
        frm.refresh_field('samples');
        frm.events.update_choices(frm);
    }
});
frappe.ui.form.on('Test Request Item', {
    items_add(frm, cdt, cdn) {
        const row = frappe.get_doc(cdt, cdn);
        row.item_code = request_next_code(frm.doc.items || [], 'item_code', 'T');
        frm.refresh_field('items');
        frm.events.update_choices(frm);
    }
});
