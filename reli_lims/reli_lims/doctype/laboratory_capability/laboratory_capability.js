frappe.ui.form.on('Laboratory Capability', {
    refresh(frm) {
        if (frm.is_new()) return;
        const manager = frappe.user.has_role('Lab Manager') || frappe.user.has_role('System Manager');
        const reviewer = manager || frappe.user.has_role('Lab Reviewer');
        const action = (label, method) => frm.add_custom_button(__(label), () => {
            if (frm.is_dirty()) { frappe.msgprint(__("请先保存修改，再执行操作。")); return; }
            return frappe.call({method: `reli_lims.capability_api.${method}`, args: {name: frm.doc.name},
                freeze: true, callback: () => frm.reload_doc()}); });
        if (reviewer && frm.doc.status === '待确认') action('确认能力', 'confirm_capability');
        if (manager && frm.doc.status === '已确认') action('发布能力', 'publish_capability');
        if (manager && frm.doc.status === '已发布') action('取消发布', 'unpublish_capability');
    }
});
