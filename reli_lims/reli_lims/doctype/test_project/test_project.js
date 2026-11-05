frappe.ui.form.on("Test Project", {
    refresh(frm) {
        if (frm.is_new()) return;
        if (frappe.model.can_read("Laboratory Capability")) {
            frm.add_custom_button(__("查看实验室能力"), () => frappe.set_route("List", "Laboratory Capability", {
                test_project: frm.doc.name,
            }));
        }
        if (frappe.model.can_read("Item")) {
            frm.add_custom_button(__("可报价服务"), () => frappe.set_route("List", "Item", {
                custom_reli_test_project: frm.doc.name,
                is_sales_item: 1,
                is_stock_item: 0,
                disabled: 0,
            }));
        }
        if (frappe.model.can_create("Item") && frappe.model.can_read("Item")) {
            frm.add_custom_button(__("新增服务商品"), () => frappe.new_doc("Item", {
                item_name: frm.doc.project_name,
                custom_reli_test_project: frm.doc.name,
                is_stock_item: 0,
                is_sales_item: 1,
            }));
        }
        if (frappe.model.can_read("Test Object")) {
            frm.add_custom_button(__("检测对象分类"), () => frappe.set_route("List", "Test Object", {
                name: ["in", (frm.doc.objects || []).map(row => row.test_object).filter(Boolean)],
            }));
        }
    },
});
