// Copyright (c) 2026, ReliLab and contributors
// For license information, please see license.txt

frappe.ui.form.on("Test Method", {
	refresh(frm) {
		if (frm.is_new() || !frappe.model.can_read("Item")) return;
		frm.add_custom_button(__("可报价服务"), () => {
			frappe.set_route("List", "Item", {
				custom_reli_test_method: frm.doc.name,
				is_sales_item: 1,
				is_stock_item: 0,
				disabled: 0,
			});
		});
	},
});
