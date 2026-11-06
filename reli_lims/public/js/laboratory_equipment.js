frappe.ui.form.on("Asset", {
    refresh(frm) {
        if (!frm.doc.custom_reli_laboratory) return;
        frm.set_df_property("asset_name", "label", __("设备中文名称"));
        frm.set_query("capability", "custom_reli_scopes", (doc, cdt, cdn) => ({filters: {
            laboratory: doc.custom_reli_laboratory, test_project: locals[cdt][cdn].test_project,
        }}));
    },
});
