app_name = "reli_lims"
app_title = "检测工作台"
app_publisher = "ReliLab"
app_description = "Lean laboratory execution module for ERPNext/Frappe"
app_email = ""
app_license = "MIT"

required_apps = ["erpnext"]

fixtures = [
    {"dt": "Role", "filters": [["name", "in", ["Lab Manager", "Lab Engineer", "Lab Reviewer", "Mercur Integration", "Laboratory Directory Reader"]]]}
]

app_logo_url = "/assets/reli_lims/images/reli-lims.svg"
app_home = "/desk/reli-lims/testing-center"

app_include_js = ["business_relations.bundle.js"]
app_include_css = ["workbench.bundle.css"]

add_to_apps_screen = [
    {
        "name": app_name,
        "title": app_title,
        "logo": app_logo_url,
        "route": app_home,
        "has_permission": "reli_lims.permissions.has_app_permission",
    }
]

# Server-derived business stages keep the native Kanban in sync.
doc_events = {
    dt: {event: "reli_lims.progress.update_progress" for event in
         ("on_update", "on_submit", "on_cancel", "after_delete")}
    for dt in ("Test Request", "Sample", "Test Program", "Test Report")
}
after_migrate = ["reli_lims.setup_v1.after_migrate"]

scheduler_events = {"daily": ["reli_lims.progress.refresh_all"]}

# One shared output dialog, including ERPNext's native Quotation form.
doctype_js = {dt: 'public/js/document_output.js'
              for dt in ('Quotation', 'Test Request', 'Test Report')}

# Sprint4: native private attachment changes invalidate technical confirmation.
doc_events['File'] = {event: 'reli_lims.request_confirmation.file_changed' for event in ('after_insert','on_update','after_delete')}
after_migrate.append('reli_lims.request_confirmation_setup.after_migrate')
doc_events['File']['validate'] = 'reli_lims.request_confirmation.validate_file_visibility'

after_migrate.append("reli_lims.capability_quotation.after_migrate")
after_migrate.append("reli_lims.capability_catalog.after_migrate")
after_migrate.append("reli_lims.patches.p161_legacy_dictionary_cleanup.after_migrate")
after_migrate.append("reli_lims.workbench_navigation.after_migrate")
doctype_js["Quotation"] = ["public/js/document_output.js", "public/js/capability_quotation.js"]
doc_events["Quotation"] = {"validate": "reli_lims.capability_quotation.validate"}
doctype_js["Test Request"] = ["public/js/document_output.js", "public/js/capability_request.js"]
doc_events["Test Request"]["validate"] = "reli_lims.capability_request.validate"
doctype_js["Item"] = "public/js/item_relations.js"
jinja = {"methods": ["reli_lims.execution_records.print_context"]}

# 客户共同填写：复用原生 Web Form + Web Form Request，不引入新的表单系统。
after_migrate.append("reli_lims.customer_share_setup.after_migrate")
override_whitelisted_methods = {
    "frappe.website.doctype.web_form.web_form.accept": "reli_lims.customer_share.accept",
}
doc_events["Test Request"]["on_trash"] = "reli_lims.customer_share.prevent_linked_trash"
