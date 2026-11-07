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
after_migrate.append("reli_lims.ui_terms.after_migrate")
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

# P4 extends ERPNext commercial documents and Asset without replacing their models.
after_migrate.append("reli_lims.p4_setup.after_migrate")
doc_events["Item"] = {"validate": "reli_lims.sales_order_testing.validate_item"}
doc_events["Quotation"]["validate"] = ["reli_lims.sales_order_testing.validate_lines", "reli_lims.capability_quotation.validate"]
doc_events["Sales Order"] = {
    "before_validate": "reli_lims.sales_order_testing.inherit_quotation_terms",
    "validate": "reli_lims.sales_order_testing.validate_lines",
    "on_submit": "reli_lims.sales_order_testing.on_submit",
    "on_update_after_submit": "reli_lims.sales_order_testing.changed",
    "before_cancel": "reli_lims.sales_order_testing.before_cancel",
    "on_cancel": "reli_lims.sales_order_testing.changed",
}
doc_events["Test Request"]["validate"] = ["reli_lims.capability_request.validate", "reli_lims.sales_order_testing.validate_request_source"]
doc_events["Asset"] = {"validate": "reli_lims.equipment.validate_asset"}
doc_events["Test Program"]["validate"] = "reli_lims.equipment.validate_execution"
doctype_js["Sales Order"] = "public/js/sales_order_testing.js"
doctype_js["Asset"] = "public/js/laboratory_equipment.js"

doctype_js["Quotation"].append("public/js/quotation_acceptance.js")

jinja["methods"].append("reli_lims.document_output.mapping.quotation.customer_quotation_context")

for dt in ("Sales Invoice", "Delivery Note"):
    doc_events[dt] = {event: "reli_lims.sales_order_testing.commercial_return_changed" for event in ("on_submit", "on_cancel")}
scheduler_events["daily"].append("reli_lims.sales_order_testing.reconcile_orders")

# Four-repo closure: append-only qualification evidence and laboratory isolation.
permission_query_conditions = {"Laboratory Capability": "reli_lims.integration_access.capability_query"}
has_permission = {
    "Laboratory Capability": "reli_lims.integration_access.capability_permission",
    "Incoming Document": "reli_lims.integration_access.document_permission",
}
for dt in ("Laboratory Capability", "Test Standard", "Laboratory Profile", "Capability Source", "Test Project"):
    doc_events.setdefault(dt, {})["on_update"] = "reli_lims.capability_eligibility.changed"
scheduler_events.setdefault("hourly", []).append("reli_lims.capability_eligibility.refresh_all")

permission_query_conditions["Capability Source"] = "reli_lims.integration_access.source_query"
has_permission.update({
    "Capability Source": "reli_lims.integration_access.source_permission",
    "Capability Upload": "reli_lims.integration_access.upload_permission",
    "Document Processing Run": "reli_lims.integration_access.document_run_permission",
    "Document Extraction": "reli_lims.integration_access.document_run_permission",
    "Document Template": "reli_lims.integration_access.document_config_permission",
    "Document Schema": "reli_lims.integration_access.document_config_permission",
    "Document AI Provider": "reli_lims.integration_access.document_config_permission",
})

# Dedicated role DocPerms are narrowed by the document hooks above.
after_migrate.append("reli_lims.integration_setup.after_migrate")
has_permission["Laboratory Profile"] = "reli_lims.integration_access.profile_permission"
permission_query_conditions.update({
    "Laboratory Profile": "reli_lims.integration_access.profile_query",
    "Incoming Document": "reli_lims.integration_access.document_query",
    "Document Processing Run": "reli_lims.integration_access.run_query",
    "Document Extraction": "reli_lims.integration_access.run_query",
    "Document Template": "reli_lims.integration_access.config_query",
    "Document Schema": "reli_lims.integration_access.config_query",
    "Document AI Provider": "reli_lims.integration_access.config_query",
})

has_permission["Item"] = "reli_lims.integration_access.item_permission"
permission_query_conditions["Item"] = "reli_lims.integration_access.config_query"

has_permission["Document Approved Version"] = "reli_lims.integration_access.approved_version_permission"
permission_query_conditions["Document Approved Version"] = "reli_lims.integration_access.approved_version_query"
