"""Read-only bidirectional views for the unified testing dictionary."""
import frappe


CAPABILITY_FIELDS = [
    "name", "laboratory", "test_project", "test_object", "test_standard",
    "test_method", "product_scope", "project_parameter", "capability_scope",
    "limitation", "clause", "source", "source_row", "status",
]
ITEM_FIELDS = [
    "name", "item_code", "item_name", "is_sales_item", "is_stock_item",
    "disabled", "custom_reli_test_project", "custom_reli_service_capability",
]


def _named_rows(doctype, names, fields):
    names = sorted({name for name in names if name})
    if not names:
        return {}
    rows = frappe.get_all(
        doctype, filters={"name": ["in", names]}, fields=fields,
        limit_page_length=0,
    )
    return {row.name: row for row in rows}


def _project_rows(project_names):
    return _named_rows(
        "Test Project", project_names,
        ["name", "project_name", "category", "classification_status", "active"],
    )


def _object_rows(object_names):
    return _named_rows(
        "Test Object", object_names,
        ["name", "object_name", "category", "aliases", "active"],
    )


def _standard_rows(standard_names):
    return _named_rows(
        "Test Standard", standard_names,
        ["name", "standard_code", "title", "version", "full_name", "basis_type", "status"],
    )


def _laboratory_rows(laboratory_names):
    return _named_rows(
        "Laboratory Profile", laboratory_names,
        ["name", "laboratory_name", "review_status"],
    )


def _capabilities(filters):
    rows = frappe.get_list(
        "Laboratory Capability", filters=filters, fields=CAPABILITY_FIELDS,
        order_by="test_project asc, test_standard asc, laboratory asc, name asc",
        page_length=1000,
    )
    projects = _project_rows(row.test_project for row in rows)
    objects = _object_rows(row.test_object for row in rows)
    standards = _standard_rows(row.test_standard for row in rows)
    laboratories = _laboratory_rows(row.laboratory for row in rows)
    for row in rows:
        project = projects.get(row.test_project, {})
        test_object = objects.get(row.test_object, {})
        standard = standards.get(row.test_standard, {})
        laboratory = laboratories.get(row.laboratory, {})
        row["project_label"] = project.get("project_name")
        row["object_label"] = test_object.get("object_name") or row.product_scope
        row["standard_label"] = standard.get("full_name")
        row["laboratory_label"] = laboratory.get("laboratory_name")
    return rows


def _service_items(project_names):
    project_names = sorted({name for name in project_names if name})
    if not project_names:
        return []
    rows = frappe.get_list(
        "Item",
        filters={
            "is_stock_item": 0,
            "custom_reli_test_project": ["in", project_names],
        },
        fields=ITEM_FIELDS,
        order_by="item_name asc, item_code asc",
        page_length=1000,
    )
    projects = _project_rows(project_names)
    for row in rows:
        row["project_label"] = projects.get(row.custom_reli_test_project, {}).get("project_name")
    return rows


def _project_standard_rows(project_names):
    project_names = sorted({name for name in project_names if name})
    if not project_names:
        return []
    return frappe.get_all(
        "Test Project Standard",
        filters={"parent": ["in", project_names]},
        fields=["parent", "test_standard"],
        limit_page_length=0,
    )


def _project_object_rows(project_names):
    project_names = sorted({name for name in project_names if name})
    if not project_names:
        return []
    return frappe.get_all(
        "Test Project Object",
        filters={"parent": ["in", project_names]},
        fields=["parent", "test_object"],
        limit_page_length=0,
    )


def _serialize_projects(project_names, capabilities, items, project_standards):
    capabilities_by_project = {}
    standards_by_project = {}
    laboratories_by_project = {}
    for row in project_standards:
        standards_by_project.setdefault(row.parent, set()).add(row.test_standard)
    for capability in capabilities:
        project = capability.get("test_project")
        if not project:
            continue
        capabilities_by_project.setdefault(project, []).append(capability)
        if capability.get("test_standard"):
            standards_by_project.setdefault(project, set()).add(capability["test_standard"])
        if capability.get("laboratory"):
            laboratories_by_project.setdefault(project, set()).add(capability["laboratory"])

    capabilities_by_name = {row.name: row for row in capabilities}
    items_by_project = {}
    for item in items:
        items_by_project.setdefault(item.get("custom_reli_test_project"), []).append(item)

    result = []
    for project_name in sorted(project_names):
        capability_rows = capabilities_by_project.get(project_name, [])
        result.append({
            "name": project_name,
            "standard_ids": sorted(standards_by_project.get(project_name, set())),
            "laboratory_ids": sorted(laboratories_by_project.get(project_name, set())),
            "capability_count": len(capability_rows),
            "item_count": len(items_by_project.get(project_name, [])),
        })
    return result


@frappe.whitelist()
def test_object_relations(test_object):
    doc = frappe.get_doc("Test Object", test_object)
    doc.check_permission("read")

    project_names = set(frappe.get_all(
        "Test Project Object",
        filters={"test_object": test_object},
        pluck="parent",
        distinct=True,
        limit_page_length=0,
    ))
    capabilities = _capabilities({"test_object": test_object})
    project_names.update(row.test_project for row in capabilities if row.test_project)
    project_rows = _project_rows(project_names)

    project_standards = _project_standard_rows(project_names)
    standards_project_map = {}
    for row in project_standards:
        standards_project_map.setdefault(row.test_standard, set()).add(row.parent)
    for row in capabilities:
        if row.test_project and row.test_standard:
            standards_project_map.setdefault(row.test_standard, set()).add(row.test_project)

    standard_rows = _standard_rows(standards_project_map)
    standard_laboratories = {}
    standard_capability_count = {}
    for row in capabilities:
        if row.test_standard:
            standard_capability_count[row.test_standard] = standard_capability_count.get(row.test_standard, 0) + 1
            if row.laboratory:
                standard_laboratories.setdefault(row.test_standard, set()).add(row.laboratory)

    standards = []
    for name in sorted(standards_project_map):
        standard = dict(standard_rows.get(name) or {"name": name})
        standard.update({
            "project_ids": sorted(standards_project_map[name]),
            "laboratory_ids": sorted(standard_laboratories.get(name, set())),
            "project_count": len(standards_project_map[name]),
            "capability_count": standard_capability_count.get(name, 0),
        })
        standards.append(standard)

    items = _service_items(project_names)
    projects = _serialize_projects(project_names, capabilities, items, project_standards)
    project_meta = _project_rows(project_names)
    for project in projects:
        project.update({
            "project_name": project_meta.get(project["name"], {}).get("project_name", project["name"]),
            "category": project_meta.get(project["name"], {}).get("category"),
            "active": project_meta.get(project["name"], {}).get("active", 1),
        })

    project_links = _project_object_rows(project_names)
    for project in projects:
        project["object_ids"] = sorted({
            row.test_object for row in project_links
            if row.parent == project["name"]
        })

    laboratory_ids = sorted({row.laboratory for row in capabilities if row.laboratory})
    laboratories = [
        dict(row) for row in _laboratory_rows(laboratory_ids).values()
    ]
    laboratories.sort(key=lambda row: row.get("laboratory_name") or row["name"])

    return {
        "object": {"name": doc.name, "object_name": doc.object_name, "category": doc.category},
        "projects": projects,
        "standards": standards,
        "capabilities": capabilities,
        "items": items,
        "laboratories": laboratories,
        "counts": {
            "projects": len(projects),
            "standards": len(standards),
            "capabilities": len(capabilities),
            "laboratories": len(laboratories),
            "items": len(items),
        },
    }


@frappe.whitelist()
def test_project_relations(test_project):
    doc = frappe.get_doc("Test Project", test_project)
    doc.check_permission("read")

    capabilities = _capabilities({"test_project": test_project})
    object_names = {
        row.test_object for row in frappe.get_all(
            "Test Project Object", filters={"parent": test_project},
            fields=["test_object"], limit_page_length=0,
        ) if row.test_object
    }
    object_names.update(row.test_object for row in capabilities if row.test_object)
    objects = [dict(row) for row in _object_rows(object_names).values()]
    objects.sort(key=lambda row: (row.get("category") or "", row.get("object_name") or ""))

    standard_names = {
        row.test_standard for row in frappe.get_all(
            "Test Project Standard", filters={"parent": test_project},
            fields=["test_standard"], limit_page_length=0,
        ) if row.test_standard
    }
    standard_names.update(row.test_standard for row in capabilities if row.test_standard)
    standards = _standard_rows(standard_names)

    project_standard_count = {}
    standard_links = frappe.get_all(
        "Test Project Standard", filters={"test_standard": ["in", sorted(standard_names)]},
        fields=["test_standard"], limit_page_length=0,
    ) if standard_names else []
    for row in standard_links:
        project_standard_count[row.test_standard] = project_standard_count.get(row.test_standard, 0) + 1
    for name in sorted(standard_names):
        standard = standards.get(name)
        if standard is not None:
            standard["project_count"] = project_standard_count.get(name, 0)

    items = _service_items({test_project})
    return {
        "project": {
            "name": doc.name, "project_name": doc.project_name,
            "category": doc.category, "classification_status": doc.classification_status,
        },
        "objects": objects,
        "standards": [standards[name] for name in sorted(standards)],
        "capabilities": capabilities,
        "items": items,
        "counts": {
            "objects": len(objects), "standards": len(standards),
            "capabilities": len(capabilities), "items": len(items),
        },
    }


@frappe.whitelist()
def test_standard_relations(test_standard):
    doc = frappe.get_doc("Test Standard", test_standard)
    doc.check_permission("read")

    project_names = set(frappe.get_all(
        "Test Project Standard", filters={"test_standard": test_standard},
        pluck="parent", distinct=True, limit_page_length=0,
    ))
    capabilities = _capabilities({"test_standard": test_standard})
    project_names.update(row.test_project for row in capabilities if row.test_project)
    projects = []
    project_meta = _project_rows(project_names)
    for name in sorted(project_names):
        project = dict(project_meta.get(name) or {"name": name})
        project["project_name"] = project.get("project_name") or name
        projects.append(project)

    items = _service_items(project_names)
    laboratory_ids = sorted({row.laboratory for row in capabilities if row.laboratory})
    return {
        "standard": {
            "name": doc.name, "full_name": doc.full_name,
            "standard_code": doc.standard_code, "title": doc.title,
            "version": doc.version, "basis_type": doc.basis_type,
        },
        "projects": projects,
        "capabilities": capabilities,
        "items": items,
        "laboratories": [dict(row) for row in _laboratory_rows(laboratory_ids).values()],
        "counts": {
            "projects": len(projects), "capabilities": len(capabilities),
            "items": len(items), "laboratories": len(laboratory_ids),
        },
    }


@frappe.whitelist()
def item_relations(item):
    doc = frappe.get_doc("Item", item)
    doc.check_permission("read")
    project = doc.get("custom_reli_test_project")
    if not project or not frappe.db.exists("Test Project", project):
        return {"project": None, "counts": {}}

    project_doc = frappe.get_doc("Test Project", project)
    project_doc.check_permission("read")
    return {
        "project": {
            "name": project_doc.name,
            "project_name": project_doc.project_name,
            "category": project_doc.category,
            "classification_status": project_doc.classification_status,
        },
        "counts": {
            "objects": frappe.db.count("Test Project Object", {"parent": project}),
            "standards": frappe.db.count("Test Project Standard", {"parent": project}),
            "capabilities": frappe.db.count("Laboratory Capability", {"test_project": project}),
            "service_items": frappe.db.count(
                "Item", {"custom_reli_test_project": project, "is_stock_item": 0}
            ),
        },
    }
