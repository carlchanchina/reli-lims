frappe.ui.form.on('Test Report', {
    setup(frm) {
        frm.set_query('test_program', () => ({filters: frm.doc.project ? {project: frm.doc.project} : {}}));
    },
    async test_program(frm) {
        if (!frm.doc.test_program || !frm.is_new()) return;
        const program = frm.doc.test_program;
        const response = await frappe.db.get_value('Test Program', program,
            ['project', 'test_request', 'customer']);
        if (frm.doc.test_program === program && response.message) await frm.set_value(response.message);
    },
    refresh(frm) {
        if (frm.is_new()) return;
        const roles = frappe.user_roles || [];
        const actions = {Draft: ['提交审核', 'Review'], Review: ['批准报告', 'Approved'], Approved: ['签发报告', 'Issued']};
        const action = actions[frm.doc.status];
        const allowed = frm.doc.status === 'Draft' ||
            (frm.doc.status === 'Review' && roles.some(role => ['Lab Reviewer', 'Lab Manager'].includes(role))) ||
            (frm.doc.status === 'Approved' && roles.includes('Lab Manager'));
        if (action && allowed && frm.perm.some(p => p.write)) {
            frm.add_custom_button(__(action[0]), async () => {
                await frm.set_value('status', action[1]);
                await frm.save();
            });
        }
        if (frm.doc.status === 'Issued' && frappe.model.can_create('Test Report')) {
            frm.add_custom_button(__('新建修订报告'), () => frappe.new_doc('Test Report', {
                test_program: frm.doc.test_program, project: frm.doc.project,
                test_request: frm.doc.test_request, notes: `修订自 ${frm.doc.name}（${frm.doc.version || ''}），请填写新版本号并重新审核。`
            }));
        }
    }
});
