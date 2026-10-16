app_name = "reli_lims"
app_title = "Reli LIMS"
app_publisher = "ReliLab"
app_description = "Lean laboratory execution module for ERPNext/Frappe"
app_email = ""
app_license = "MIT"

required_apps = ["erpnext"]

fixtures = [
    {"dt": "Role", "filters": [["name", "in", ["Lab Manager", "Lab Engineer", "Lab Reviewer"]]]}
]

app_logo_url = "/assets/reli_lims/images/reli-lims.svg"
app_home = "/desk/reli-lims/testing-center"

add_to_apps_screen = [
    {
        "name": app_name,
        "title": app_title,
        "logo": app_logo_url,
        "route": app_home,
        "has_permission": "reli_lims.permissions.has_app_permission",
    }
]
