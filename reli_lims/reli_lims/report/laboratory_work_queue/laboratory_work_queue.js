frappe.query_reports['Laboratory Work Queue'] = {
    filters: [
        {fieldname: 'view', label: __('任务范围'), fieldtype: 'Select', reqd: 1,
            default: frappe.user.has_role('Lab Manager') ? '待分配任务'
                : frappe.user.has_role('Lab Reviewer') ? '待复核结果' : '我的待执行',
            options: [
                ...(frappe.user.has_role('Lab Engineer') || frappe.user.has_role('Lab Manager')
                    ? ['我的待执行', '我的进行中', '我的待补结果'] : []),
                ...(frappe.user.has_role('Lab Reviewer') || frappe.user.has_role('Lab Manager')
                    ? ['待复核结果'] : []),
                ...(frappe.user.has_role('Lab Manager') ? ['待分配任务'] : [])
            ].join('\n')},
        {fieldname: 'test_program', label: __('试验方案'), fieldtype: 'Link', options: 'Test Program'}
    ]
};
