"""P1.6: map real CNAS projects into the unified Test Project dictionary."""
import json

import frappe

from reli_lims.capability_catalog import BASIS_TYPES, classify_basis_type, ensure_custom_fields
from reli_lims.reli_lims.doctype.test_project.test_project import project_key

CNAS_PREFIX = "CNAS Workbench "


def _batch_methods():
    for source in frappe.get_all(
        "Capability Source", fields=["name", "structured_json"],
        filters={"source_type": "CNAS"}, order_by="creation desc",
    ):
        if not source.structured_json:
            continue
        payload = source.structured_json
        if isinstance(payload, str):
            payload = json.loads(payload)
        methods = payload.get("methods") if isinstance(payload, dict) else None
        if isinstance(methods, list) and methods:
            return methods
    return []


def _safe_insert(doctype, **values):
    return frappe.get_doc(dict(doctype=doctype, **values)).insert(ignore_permissions=True).name


def _method_project_name(method):
    notes = method.notes or ""
    label = method.method_name
    if notes.startswith(CNAS_PREFIX):
        label = label.removesuffix(f" [{notes[len(CNAS_PREFIX):]}]")
    return label.strip()


def _split_aliases(value):
    return [part.strip() for part in (value or "").split("/") if part.strip()]


def _detection_projects_by_name():
    if not frappe.db.exists("DocType", "Detection Project"):
        return {}
    return {
        project_key(row.project_name): row.project_name
        for row in frappe.get_all("Detection Project", fields=["name", "project_name"])
        if row.project_name
    }


def _ensure_projects(batch_methods, methods):
    by_key = {}
    for project in frappe.get_all("Test Project", fields=["name", "project_name", "normalized_name"]):
        key = project.normalized_name or project_key(project.project_name)
        by_key[key] = project.name

    source_by_code = {row.get("item_code"): row for row in batch_methods}
    for method in methods:
        if not (method.notes or "").startswith(CNAS_PREFIX):
            continue
        code = method.notes[len(CNAS_PREFIX):].strip()
        source = source_by_code.get(code, {})
        label = source.get("item_name") or _method_project_name(method)
        key = project_key(label)
        if not key:
            continue
        project = by_key.get(key)
        aliases = [
            value for value in _split_aliases(source.get("custom_raw_names"))
            if project_key(value) != key and project_key(value) not in by_key
        ]
        if not project:
            project = _safe_insert(
                "Test Project", project_name=label,
                category=source.get("custom_test_category") or method.category,
                aliases="\n".join(aliases), classification_status="已归类", active=1,
                description=(source.get("description") or "").strip()
                if (source.get("description") or "").strip() != label else "",
                condition_template="[]",
            )
            by_key[key] = project
        else:
            doc = frappe.get_doc("Test Project", project)
            current_aliases = set(_split_aliases(doc.aliases))
            for alias in aliases:
                if alias not in current_aliases:
                    current_aliases.add(alias)
            if current_aliases != set(_split_aliases(doc.aliases)):
                frappe.db.set_value("Test Project", project, "aliases", "\n".join(sorted(current_aliases)),
                                    update_modified=False)
            if not doc.category and (source.get("custom_test_category") or method.category):
                frappe.db.set_value("Test Project", project, "category",
                                    source.get("custom_test_category") or method.category,
                                    update_modified=False)
            if doc.classification_status != "已归类":
                frappe.db.set_value("Test Project", project, "classification_status", "已归类",
                                    update_modified=False)
        if method.name and frappe.db.get_value("Test Method", method.name, "test_project") != project:
            frappe.db.set_value("Test Method", method.name, "test_project", project, update_modified=False)

    # Only exact names are mapped for legacy methods. This preserves the two
    # existing capabilities (低温试验/随机振动试验) without fuzzy matching.
    for method in methods:
        if method.notes and method.notes.startswith(CNAS_PREFIX):
            continue
        if (method.category or "").upper() == "DEMO" or (method.method_name or "").startswith("TEST "):
            continue
        project = by_key.get(project_key(_method_project_name(method)))
        if project and not frappe.db.get_value("Test Method", method.name, "test_project"):
            frappe.db.set_value("Test Method", method.name, "test_project", project, update_modified=False)


def _ensure_basis_types():
    for standard in frappe.get_all("Test Standard", fields=["name", "standard_code", "basis_type"]):
        # The new Select field gives existing rows its default before this patch
        # runs. Re-derive only that default; preserve an explicit manual choice.
        if standard.basis_type in BASIS_TYPES and standard.basis_type != "其他方法文件":
            continue
        frappe.db.set_value(
            "Test Standard", standard.name, "basis_type",
            classify_basis_type(standard.standard_code), update_modified=False,
        )


def _ensure_objects():
    rows = frappe.db.sql(
        """select product_scope, min(industry) industry, count(*) rows_seen
           from `tabLaboratory Capability`
           where ifnull(product_scope,'')!='' group by product_scope order by product_scope""",
        as_dict=True,
    )
    by_name = {project_key(row.object_name): row.name for row in frappe.get_all(
        "Test Object", fields=["name", "object_name"]
    )}
    for row in rows:
        key = project_key(row.product_scope)
        name = by_name.get(key)
        if not name:
            name = _safe_insert(
                "Test Object", object_name=row.product_scope,
                category=row.industry or "", active=1,
            )
            by_name[key] = name
        elif row.industry and not frappe.db.get_value("Test Object", name, "category"):
            frappe.db.set_value("Test Object", name, "category", row.industry, update_modified=False)
        frappe.db.sql(
            "update `tabLaboratory Capability` set test_object=%s where product_scope=%s",
            (name, row.product_scope),
        )
    return len(rows)


def _assign_projects_to_capabilities():
    frappe.db.sql(
        """update `tabLaboratory Capability` c
           join `tabTest Method` m on m.name=c.test_method
           set c.test_project=m.test_project
           where ifnull(c.test_project,'')='' and ifnull(m.test_project,'')!=''"""
    )
    # The intermediate Detection Project table existed only on the dev site.
    columns = {row[0] for row in frappe.db.sql("show columns from `tabLaboratory Capability`")}
    if "detection_project" in columns and frappe.db.exists("DocType", "Detection Project"):
        project_by_name = {
            project_key(row.project_name): row.name
            for row in frappe.get_all("Test Project", fields=["name", "project_name"])
        }
        detection_projects = {
            row.name: row.project_name
            for row in frappe.get_all("Detection Project", fields=["name", "project_name"])
        }
        for capability in frappe.get_all(
            "Laboratory Capability", fields=["name", "detection_project"],
            filters={"test_project": ["is", "not set"], "detection_project": ["is", "set"]},
        ):
            project = project_by_name.get(
                project_key(detection_projects.get(capability.detection_project))
            )
            if project:
                frappe.db.set_value("Laboratory Capability", capability.name, "test_project",
                                    project, update_modified=False)


def _ensure_project_relations():
    for project in frappe.get_all("Test Project", fields=["name", "condition_template"]):
        standards = frappe.db.sql(
            """select test_standard, count(*) c from `tabLaboratory Capability`
               where test_project=%s and ifnull(test_standard,'')!=''
               group by test_standard order by c desc""",
            project.name, as_dict=True,
        )
        objects = frappe.db.sql(
            """select test_object, count(*) c from `tabLaboratory Capability`
               where test_project=%s and ifnull(test_object,'')!=''
               group by test_object order by c desc""",
            project.name, as_dict=True,
        )
        existing_standards = set(frappe.get_all(
            "Test Project Standard", filters={"parent": project.name}, pluck="test_standard"
        ))
        existing_objects = set(frappe.get_all(
            "Test Project Object", filters={"parent": project.name}, pluck="test_object"
        ))
        method_standards = frappe.get_all(
            "Test Method", filters={"test_project": project.name, "default_standard": ["is", "set"]},
            pluck="default_standard", distinct=True, limit_page_length=0,
        )
        doc = frappe.get_doc("Test Project", project.name)
        changed = False
        standard_names = {row.test_standard for row in standards} | set(method_standards)
        for standard in sorted(standard_names):
            if standard not in existing_standards:
                doc.append("standards", {"test_standard": standard})
                changed = True
        for row in objects:
            if row.test_object not in existing_objects:
                doc.append("objects", {"test_object": row.test_object})
                changed = True
        schemas = {
            row.condition_schema for row in frappe.get_all(
                "Laboratory Capability", filters={"test_project": project.name},
                fields=["condition_schema"],
            ) if row.condition_schema and row.condition_schema not in ("", "[]", "null")
        }
        if len(schemas) == 1 and project.condition_template in (None, "", "[]"):
            doc.condition_template = next(iter(schemas))
            changed = True
        if changed:
            doc.flags.ignore_permissions = True
            doc.save()


def _map_items_and_lines():
    ensure_custom_fields()
    detection_projects = _detection_projects_by_name()
    item_fields = ["name", "custom_reli_test_method"]
    if frappe.db.has_column("Item", "custom_reli_detection_project"):
        item_fields.append("custom_reli_detection_project")
    for row in frappe.get_all(
        "Item", fields=item_fields,
    ):
        project = None
        if row.custom_reli_test_method:
            project = frappe.db.get_value("Test Method", row.custom_reli_test_method, "test_project")
        if not project and row.get("custom_reli_detection_project"):
            source = frappe.db.get_value(
                "Detection Project", row.custom_reli_detection_project, "project_name"
            ) if frappe.db.exists("DocType", "Detection Project") else None
            project_name = detection_projects.get(project_key(source)) if source else None
            if project_name:
                project = frappe.db.get_value(
                    "Test Project", {"normalized_name": project_key(project_name)}, "name"
                )
        if project and not frappe.db.get_value("Item", row.name, "custom_reli_test_project"):
            frappe.db.set_value("Item", row.name, "custom_reli_test_project", project,
                                update_modified=False)

    for row in frappe.get_all(
        "Quotation Item", fields=["name", "parent", "custom_reli_capability"],
        filters={"custom_reli_capability": ["is", "set"]},
    ):
        capability = frappe.db.get_value(
            "Laboratory Capability", row.custom_reli_capability,
            ["test_project", "test_object", "test_standard"], as_dict=True,
        )
        if capability:
            project_label = frappe.db.get_value("Test Project", capability.test_project, "project_name")
            frappe.db.set_value("Quotation Item", row.name, {
                "custom_reli_test_project": capability.test_project,
                "custom_reli_test_object": capability.test_object,
                "custom_reli_test_standard": capability.test_standard,
                "item_name": project_label or None,
            }, update_modified=False)

    frappe.db.sql(
        """update `tabTest Request Item` i
           join `tabLaboratory Capability` c on c.name=i.capability
           set i.test_project=c.test_project, i.test_object=c.test_object
           where ifnull(i.capability,'')!=''"""
    )
    frappe.db.sql(
        """update `tabTest Request Item` i
           join `tabTest Method` m on m.name=i.test_method
           set i.test_project=m.test_project
           where ifnull(i.test_project,'')='' and ifnull(m.test_project,'')!=''"""
    )
    frappe.db.sql(
        """update `tabTest Program Item` i
           join `tabTest Method` m on m.name=i.test_method
           set i.test_project=m.test_project
           where ifnull(i.test_project,'')='' and ifnull(m.test_project,'')!=''"""
    )
    frappe.db.sql(
        """update `tabTest Program Item` i
           join `tabTest Program` p on p.name=i.parent
           join `tabTest Request Item` r on r.parent=p.test_request and r.item_code=i.item_code
           set i.test_object=r.test_object
           where ifnull(i.test_object,'')='' and ifnull(r.test_object,'')!=''"""
    )


def _retire_intermediate_detection_project():
    # Detection Project was an unpushed local experiment. Keep any historical
    # table data for audit, but hide the duplicate concept from business forms.
    custom_field = frappe.db.get_value("Custom Field", {
        "dt": "Item", "fieldname": "custom_reli_detection_project"
    })
    if custom_field:
        frappe.db.set_value("Custom Field", custom_field, {
            "label": "旧预研检测项目（兼容）", "hidden": 1, "read_only": 1,
        }, update_modified=False)
    if frappe.db.exists("DocType", "Detection Project"):
        frappe.db.set_value("DocType", "Detection Project", "hidden", 1, update_modified=False)
    field = frappe.db.get_value("DocField", {
        "parent": "Laboratory Capability", "fieldname": "detection_project"
    })
    if field:
        frappe.db.set_value("DocField", field, "hidden", 1, update_modified=False)
    custom_field = frappe.db.get_value("Custom Field", {
        "dt": "Laboratory Capability", "fieldname": "detection_project"
    })
    if custom_field:
        frappe.db.set_value("Custom Field", custom_field, {
            "label": "旧预研检测项目（兼容）", "hidden": 1, "read_only": 1,
        }, update_modified=False)


def execute():
    ensure_custom_fields()
    methods = frappe.get_all(
        "Test Method", fields=["name", "method_name", "category", "notes", "default_standard"],
    )
    _ensure_projects(_batch_methods(), methods)
    _ensure_basis_types()
    _ensure_objects()
    _assign_projects_to_capabilities()
    _ensure_project_relations()
    _map_items_and_lines()
    _retire_intermediate_detection_project()
    frappe.db.commit()
