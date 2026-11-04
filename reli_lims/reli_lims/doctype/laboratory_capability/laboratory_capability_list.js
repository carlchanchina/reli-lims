frappe.listview_settings["Laboratory Capability"] = {
    onload(list) {
        list.page.add_inner_button(__("CNAS 能力明细表"), async () => {
            await frappe.require("/assets/reli_lims/js/capability_grid.js");
            await frappe.require("/assets/reli_lims/js/capability_selector.js");
            return reli_lims.capabilities.open({mode: "catalog"});
        });
    },
};
