"""Unified detection project, object and basis dictionary support."""
import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from reli_lims.reli_lims.doctype.test_project.test_project import project_key

BASIS_TYPES = ("国家标准", "行业标准", "国际标准", "企业标准", "实验室方法", "其他方法文件")


def classify_basis_type(code):
    value = (code or "").strip().upper()
    if not value:
        return "其他方法文件"
    if value.startswith(("Q/", "Q ")):
        return "企业标准"
    if value.startswith(("LAB", "SOP")):
        return "实验室方法"
    if value.startswith(("GB", "GJB")):
        return "国家标准"
    if value.startswith(("TB", "TJ", "CJ", "HB", "HAF", "JT", "YY", "JB", "DL", "SY", "HG")):
        return "行业标准"
    if value.startswith(("ISO", "IEC", "EN", "BS", "ASTM", "UIC", "DIN", "JIS", "ASME", "IEEE", "UL", "RTCA")):
        return "国际标准"
    return "其他方法文件"


def _ensure_field(doctype, fieldname, **values):
    meta = frappe.get_meta(doctype)
    field = meta.get_field(fieldname)
    if field:
        expected = {key: values[key] for key in ("fieldtype", "options") if key in values}
        if any(field.get(key) != value for key, value in expected.items()):
            frappe.throw(_("{0}.{1} 字段类型与统一字典不一致。").format(doctype, fieldname))
        custom_field = frappe.db.get_value(
            "Custom Field", {"dt": doctype, "fieldname": fieldname}, "name"
        )
        if custom_field:
            changes = {
                key: values[key] for key in ("label", "read_only", "description") if key in values
            }
            if changes:
                frappe.db.set_value("Custom Field", custom_field, changes, update_modified=False)
        return
    create_custom_fields({doctype: [dict(fieldname=fieldname, **values)]}, update=False)


def ensure_custom_fields():
    # These fields are created by older migrations on established sites. Keep a
    # single idempotent entry point so a fresh site can run the data patch too.
    _ensure_field("Item", "custom_reli_test_method", label="原检测项目（兼容）", fieldtype="Link",
                  options="Test Method", insert_after="item_group")
    _ensure_field("Item", "custom_reli_service_capability", label="能力目录生成来源", fieldtype="Link",
                  options="Laboratory Capability", insert_after="custom_reli_test_method", read_only=1)
    _ensure_field("Item", "custom_reli_test_project", label="检测项目", fieldtype="Link",
                  options="Test Project", insert_after="custom_reli_service_capability")
    _ensure_field("Quotation", "custom_reli_details", label="检测项目明细", fieldtype="HTML", insert_after="items")
    _ensure_field("Quotation Item", "custom_reli_capability", label="检测能力", fieldtype="Link",
                  options="Laboratory Capability", insert_after="description", read_only=1)
    _ensure_field("Quotation Item", "custom_reli_configuration", label="检测条件快照", fieldtype="JSON",
                  insert_after="custom_reli_capability", read_only=1)
    _ensure_field("Quotation Item", "custom_reli_test_project", label="检测项目", fieldtype="Link",
                  options="Test Project", insert_after="custom_reli_configuration", read_only=1)
    _ensure_field("Quotation Item", "custom_reli_test_object", label="检测对象", fieldtype="Link",
                  options="Test Object", insert_after="custom_reli_test_project", read_only=1)
    _ensure_field("Quotation Item", "custom_reli_test_standard", label="检测依据", fieldtype="Link",
                  options="Test Standard", insert_after="custom_reli_test_object", read_only=1)


def after_migrate():
    ensure_custom_fields()


def ensure_project_relations(project_name, standard=None, test_object=None):
    if not project_name or not frappe.db.exists("Test Project", project_name):
        return
    project = frappe.get_doc("Test Project", project_name)
    changed = False
    if standard and not any(row.test_standard == standard for row in project.standards):
        project.append("standards", {"test_standard": standard})
        changed = True
    if test_object and not any(row.test_object == test_object for row in project.objects):
        project.append("objects", {"test_object": test_object})
        changed = True
    if changed:
        project.flags.ignore_permissions = True
        project.save()


@frappe.whitelist()
def dashboard():
    """Small, permission-aware overview for the unified capability workspace."""
    project_total = frappe.db.count("Test Project")
    classified = frappe.db.count("Test Project", {"classification_status": "已归类"})
    pending = frappe.db.count("Test Project", {"classification_status": "待分类"})
    object_total = frappe.db.count("Test Object")
    standard_total = frappe.db.count("Test Standard")
    laboratory_total = frappe.db.count("Laboratory Profile")
    capability_total = frappe.db.count("Laboratory Capability")
    capability_unclassified = frappe.db.sql(
        """select count(*) from `tabLaboratory Capability`
           where ifnull(test_project,'')=''""",
    )[0][0]
    cnas_capabilities = frappe.db.sql(
        """select count(*) from `tabLaboratory Capability` c
           join `tabCapability Source` s on s.name=c.source
           where s.source_type='CNAS'""",
    )[0][0]
    item_total = frappe.db.count("Item", {"is_stock_item": 0, "custom_reli_test_project": ["is", "set"]})
    return {
        "projects": project_total,
        "classified": classified,
        "pending": pending,
        "objects": object_total,
        "standards": standard_total,
        "laboratories": laboratory_total,
        "capabilities": capability_total,
        "cnas_capabilities": cnas_capabilities,
        "unclassified_capabilities": capability_unclassified,
        "service_items": item_total,
    }


@frappe.whitelist()
def projects(text=None, category=None, offset=0):
    filters = {}
    if category:
        filters["category"] = str(category)[:140]
    or_filters = None
    if text:
        term = f"%{str(text)[:100]}%"
        or_filters = [[field, "like", term] for field in ("project_name", "category", "aliases", "description")]
    rows = frappe.get_list(
        "Test Project", filters=filters, or_filters=or_filters,
        fields=["name", "project_name", "category", "classification_status", "aliases", "description", "active"],
        order_by="project_name asc, name asc", start=max(0, int(offset)), page_length=31,
    )
    for row in rows[:30]:
        row.update(_project_counts(row.name))
    return {"rows": rows[:30], "has_more": len(rows) > 30}


def _project_counts(name):
    capability = frappe.db.sql(
        """select count(*) cap_count, count(distinct test_object) object_count,
                  count(distinct test_standard) standard_count,
                  count(distinct laboratory) laboratory_count
           from `tabLaboratory Capability` where test_project=%s""",
        name, as_dict=True,
    )[0]
    item_count = frappe.db.count("Item", {"custom_reli_test_project": name, "is_stock_item": 0})
    return dict(capability, item_count=item_count)


@frappe.whitelist()
def objects(text=None, offset=0):
    filters = {}
    or_filters = [[field, "like", f"%{str(text)[:100]}%"] for field in ("object_name", "category", "aliases")] if text else None
    rows = frappe.get_list(
        "Test Object", filters=filters, or_filters=or_filters,
        fields=["name", "object_name", "category", "aliases", "active"],
        order_by="category asc, object_name asc", start=max(0, int(offset)), page_length=200,
    )
    for row in rows:
        row["capability_count"] = frappe.db.count("Laboratory Capability", {"test_object": row.name})
        row["project_count"] = frappe.db.count("Test Project Object", {"test_object": row.name})
    groups = {}
    for row in rows:
        groups.setdefault(row.category or "未分类", []).append(row)
    return {"groups": [{"category": key, "objects": values} for key, values in groups.items()],
            "has_more": len(rows) >= 200}


@frappe.whitelist()
def standards(text=None, offset=0):
    filters = {}
    or_filters = [[field, "like", f"%{str(text)[:100]}%"] for field in ("standard_code", "title", "full_name")] if text else None
    rows = frappe.get_list(
        "Test Standard", filters=filters, or_filters=or_filters,
        fields=["name", "standard_code", "title", "version", "full_name", "basis_type", "status"],
        order_by="standard_code asc, version asc", start=max(0, int(offset)), page_length=31,
    )
    for row in rows[:30]:
        row["project_count"] = frappe.db.count("Test Project Standard", {"test_standard": row.name})
        row["capability_count"] = frappe.db.count("Laboratory Capability", {"test_standard": row.name})
    return {"rows": rows[:30], "has_more": len(rows) > 30}


@frappe.whitelist()
def laboratories(text=None):
    or_filters = [[field, "like", f"%{str(text)[:100]}%"] for field in ("laboratory_name",)] if text else None
    rows = frappe.get_list(
        "Laboratory Profile", or_filters=or_filters,
        fields=["name", "laboratory_name", "review_status"], order_by="laboratory_name asc", page_length=100,
    )
    for row in rows:
        row["capability_count"] = frappe.db.count("Laboratory Capability", {"laboratory": row.name})
        row["source_count"] = frappe.db.count("Capability Source", {"laboratory": row.name})
        row["item_count"] = frappe.db.sql(
            """select count(distinct i.name) from `tabItem` i
               join `tabLaboratory Capability` c on c.test_project=i.custom_reli_test_project
               where c.laboratory=%s and i.is_stock_item=0""",
            row.name,
        )[0][0]
    return {"rows": rows}


@frappe.whitelist()
def service_items(text=None, project=None, offset=0):
    filters = {"is_stock_item": 0}
    if project:
        filters["custom_reli_test_project"] = project
    or_filters = [[field, "like", f"%{str(text)[:100]}%"] for field in ("item_code", "item_name")] if text else None
    rows = frappe.get_list(
        "Item", filters=filters, or_filters=or_filters,
        fields=["name", "item_code", "item_name", "is_stock_item", "is_sales_item", "disabled",
                "custom_reli_test_project", "custom_reli_service_capability"],
        order_by="item_name asc", start=max(0, int(offset)), page_length=31,
    )
    for row in rows[:30]:
        row["project_label"] = frappe.db.get_value("Test Project", row.get("custom_reli_test_project"), "project_name")
    return {"rows": rows[:30], "has_more": len(rows) > 30}


@frappe.whitelist()
def laboratory_details(laboratory):
    doc = frappe.get_doc("Laboratory Profile", laboratory)
    doc.check_permission("read")
    capability_total = frappe.db.count("Laboratory Capability", {"laboratory": laboratory})
    project_names = frappe.get_all(
        "Laboratory Capability", filters={"laboratory": laboratory, "test_project": ["is", "set"]},
        pluck="test_project", distinct=True, limit_page_length=0,
    )
    capabilities = frappe.get_list(
        "Laboratory Capability", filters={"laboratory": laboratory},
        fields=["name", "test_project", "test_object", "test_standard", "product_scope",
                "capability_scope", "limitation", "status", "source", "source_row"],
        order_by="name asc", page_length=50,
    )
    for row in capabilities:
        row["project_label"] = frappe.db.get_value("Test Project", row.get("test_project"), "project_name")
        row["object_label"] = frappe.db.get_value("Test Object", row.get("test_object"), "object_name") or row.product_scope
        row["standard_label"] = frappe.db.get_value("Test Standard", row.get("test_standard"), "full_name")
    sources = frappe.get_list(
        "Capability Source", filters={"laboratory": laboratory},
        fields=["name", "source_type", "certificate_no", "documents_version", "documents_review_status", "import_status"],
        order_by="name asc", page_length=50,
    )
    project_names = sorted({name for name in project_names if name})
    items = frappe.get_list(
        "Item", filters={"custom_reli_test_project": ["in", project_names], "is_stock_item": 0} if project_names else {"name": ""},
        fields=["name", "item_code", "item_name", "custom_reli_test_project"], order_by="item_name asc", page_length=100,
    ) if project_names else []
    for row in items:
        row["project_label"] = frappe.db.get_value("Test Project", row.custom_reli_test_project, "project_name")
    return dict(capabilities=capabilities, sources=sources, items=items,
                counts={"capabilities": capability_total, "sources": frappe.db.count("Capability Source", {"laboratory": laboratory}),
                        "items": len(items),
                        "projects": len(project_names)})


@frappe.whitelist()
def source_details(source):
    doc = frappe.get_doc("Capability Source", source)
    doc.check_permission("read")
    counts = frappe.db.sql(
        """select count(*) capabilities, count(distinct test_project) projects,
                  count(distinct test_object) objects, count(distinct test_standard) standards,
                  count(distinct laboratory) laboratories
           from `tabLaboratory Capability` where source=%s""",
        source, as_dict=True,
    )[0]
    counts["unclassified"] = frappe.db.sql(
        """select count(*) from `tabLaboratory Capability`
           where source=%s and ifnull(test_project,'')=''""",
        source,
    )[0][0]
    return counts


@frappe.whitelist(methods=["POST"])
def reassign_capabilities(names, test_project):
    frappe.only_for(("System Manager", "Lab Manager"))
    project = frappe.get_doc("Test Project", test_project)
    project.check_permission("read")
    names = frappe.parse_json(names)
    if not isinstance(names, list) or not 1 <= len(names) <= 100:
        frappe.throw(_("请选择 1 至 100 条需要重新归类的实验室能力。"))
    updated = 0
    for name in dict.fromkeys(names):
        capability = frappe.get_doc("Laboratory Capability", name)
        capability.check_permission("write")
        capability.test_project = project.name
        capability.save()
        updated += 1
    return updated
