frappe.listview_settings["Laboratory Capability"] = {
    onload(list) {
        if (frappe.user.has_role("Lab Manager") || frappe.user.has_role("System Manager")) {
            list.page.add_action_item(__("重新归类到检测项目"), () => {
                const names = list.get_checked_items().map(row => row.name);
                if (!names.length) {
                    frappe.msgprint(__("请先选择实验室能力。"));
                    return;
                }
                if (names.length > 100) {
                    frappe.msgprint(__("请一次最多选择 100 条能力。"));
                    return;
                }
                frappe.prompt(
                    [{fieldname: "test_project", fieldtype: "Link", options: "Test Project",
                        label: __("目标检测项目"), reqd: 1}],
                    values => frappe.call({
                        method: "reli_lims.capability_catalog.reassign_capabilities",
                        args: {names, test_project: values.test_project}, freeze: true,
                        callback: () => list.refresh(),
                    }),
                    __("重新归类检测能力"),
                    __("应用"),
                );
            });
        }
        list.page.add_inner_button(__("CNAS 能力明细表"), async () => {
            await frappe.require("capability_grid.bundle.js");
            await frappe.require("/assets/reli_lims/js/capability_selector.js");
            return reli_lims.capabilities.open({mode: "catalog"});
        });
    },
};
