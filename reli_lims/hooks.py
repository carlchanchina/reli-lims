app_name = "reli_lims"
app_title = "Reli LIMS"
app_publisher = "ReliLab"
app_description = "Lean laboratory execution module for ERPNext/Frappe"
app_email = ""
app_license = "MIT"

required_apps = ["erpnext"]

fixtures = [
    {"dt": "Role", "filters": [["name", "in", ["Lab Manager", "Lab Engineer", "Lab Reviewer", "Mercur Integration", "Laboratory Directory Reader"]]]}
]
