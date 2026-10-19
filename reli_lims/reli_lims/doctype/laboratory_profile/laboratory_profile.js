frappe.ui.form.on("Laboratory Profile", {
  refresh(frm) {
    if (frm.doc.review_status !== "Pending" || !frappe.user.has_role("Lab Reviewer")) return;
    for (const [label, approve] of [["通过审核", true], ["退回修改", false]]) {
      frm.add_custom_button(__(label), () => {
        frappe.prompt(
          [{ fieldname: "note", fieldtype: "Small Text", label: __("审核备注") }],
          async ({ note }) => {
            await frappe.call({
              method: "reli_lims.laboratory_api.review_profile",
              args: {
                seller_id: frm.doc.mercur_seller_id,
                revision: frm.doc.draft_revision,
                approve,
                note: note || "",
              },
            });
            await frm.reload_doc();
          },
          __(label),
          __("确认"),
        );
      });
    }
  },
});
