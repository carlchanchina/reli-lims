frappe.ui.form.on("Test Project", {
    refresh(frm) {
        if (reli_lims.relations.mount_project) {
            reli_lims.relations.mount_project(frm);
        }
        if (frm.is_new()) return;
        if (frappe.model.can_read("Asset")) {
            frm.add_custom_button(__("可用实验设备"), () => {
                let start = 0;
                const dialog = new frappe.ui.Dialog({title: __("可用实验设备"), fields: [
                    {fieldname: "search", fieldtype: "Data", label: __("中文名称／型号／序列号"), change() { start = 0; load(); }},
                    {fieldname: "equipment", fieldtype: "HTML"},
                ]});
                async function load() {
                    const {message} = await frappe.call("reli_lims.equipment.available", {
                        test_project: frm.doc.name, text: dialog.get_value("search"), start,
                    });
                    const host = dialog.fields_dict.equipment.$wrapper.empty();
                    for (const row of message.rows) {
                        $("<button type='button' class='btn btn-link d-block'>").text(
                            `${row.asset_name} · ${row.custom_reli_model || ""} · ${row.custom_reli_calibration_until}`
                        ).on("click", () => { dialog.hide(); frappe.set_route("Form", "Asset", row.name); }).appendTo(host);
                    }
                    if (!message.rows.length) $("<p>").text(__("暂无可用设备" )).appendTo(host);
                    $("<button class='btn btn-default btn-sm'>").text(__("上一页")).prop("disabled", !start)
                        .on("click", () => { start = Math.max(0, start - 20); load(); }).appendTo(host);
                    $("<button class='btn btn-default btn-sm'>").text(__("下一页")).prop("disabled", !message.has_more)
                        .on("click", () => { start += 20; load(); }).appendTo(host);
                }
                dialog.show(); load();
            });
        }
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
