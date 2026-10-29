/* Shared by native Quotation, Test Request and Test Report forms. */
if (!frappe.reli_document_output_registered) {
    frappe.reli_document_output_registered = true;
    for (const doctype of ['Quotation', 'Test Request', 'Test Report']) {
        frappe.ui.form.on(doctype, {
            refresh(frm) {
                if (frm.is_new() || !(frm.perm || []).some(row => row.read && row.print)) return;
                frm.add_custom_button(__('生成文档'), async () => {
                    if (frm.is_dirty()) {
                        frappe.msgprint(__('请先保存单据，再生成文档。'));
                        return;
                    }
                    const sourceName = frm.doc.name;
                    const response = await frappe.call({
                        method: 'reli_lims.document_output.api.get_templates',
                        args: {doctype, name: sourceName}
                    });
                    const templates = response.message || [];
                    if (!templates.length || frm.doc.name !== sourceName) return;
                    const labels = {pdf: __('PDF'), docx: __('Word'), xlsx: __('Excel')};
                    const selected = () => templates.find(t => t.name === dialog.get_value('template'));
                    const dialog = new frappe.ui.Dialog({
                        title: __('生成文档'),
                        fields: [
                            {fieldname: 'template', label: __('模板'), fieldtype: 'Select', reqd: 1,
                                options: templates.map(t => ({label: t.label, value: t.name})),
                                default: templates[0].name,
                                onchange() {
                                    const template = selected();
                                    if (!template) return;
                                    dialog.set_df_property('output_format', 'options',
                                        template.formats.map(value => ({value, label: labels[value]})));
                                    dialog.set_value('output_format', template.default_format);
                                }},
                            {fieldname: 'output_format', label: __('格式'), fieldtype: 'Select', reqd: 1,
                                options: templates[0].formats.map(value => ({value, label: labels[value]})),
                                default: 'pdf'}
                        ],
                        primary_action_label: __('生成'),
                        async primary_action(values) {
                            if (frm.is_dirty() || frm.doc.name !== sourceName) {
                                frappe.msgprint(__('单据已发生变化，请保存后重新生成文档。'));
                                return;
                            }
                            dialog.disable_primary_action();
                            try {
                                const result = await frappe.call({
                                    method: 'reli_lims.document_output.api.generate_document',
                                    args: {doctype, name: sourceName, ...values}, freeze: true,
                                    freeze_message: __('正在生成文档…')
                                });
                                if (!result.message) return;
                                dialog.hide();
                                const file = result.message;
                                frappe.msgprint({title: __('文档已生成'), message:
                                    `<a href="${frappe.utils.escape_html(file.file_url)}" target="_blank" rel="noopener">` +
                                    `${frappe.utils.escape_html(file.file_name)}</a>`});
                                frm.reload_doc();
                            } finally {
                                dialog.enable_primary_action();
                            }
                        }
                    });
                    dialog.show();
                });
            }
        });
    }
}
