"""Explicit, transaction-scoped import of the historical L11464 export into Carl DEV."""
import hashlib
import json

import frappe


def insert(doctype, **values):
    return frappe.get_doc(dict(doctype=doctype, **values)).insert(ignore_permissions=True).name


def apply(batch_path):
    if frappe.local.site != "carl" or not frappe.conf.developer_mode:
        frappe.throw("This historical import is restricted to the Carl development site.")
    with open(batch_path, encoding="utf-8") as stream:
        batch = json.load(stream)
    digest = batch.pop("digest")
    if digest != hashlib.sha256(json.dumps(batch, sort_keys=True).encode()).hexdigest():
        frappe.throw("CNAS batch digest mismatch.")
    lock = "reli_lims:cnas_import:L11464"
    with frappe.cache.lock(lock, timeout=300, blocking_timeout=5):
        try:
            counts = _apply(batch, digest)
            frappe.db.commit()
            return counts
        except Exception:
            frappe.db.rollback()
            raise
        finally:
            frappe.flags.in_cnas_dev_import = False


def _apply(batch, digest):
    existing = frappe.db.exists("Capability Source", {"documents_source_id": f"L11464:{digest}"})
    if existing:
        return {"source": existing, "created": 0,
                "scope": frappe.db.count("Laboratory Capability", {"source": existing})}
    frappe.flags.in_cnas_dev_import = True
    lab = batch["laboratory"]
    laboratory = frappe.db.exists("Laboratory Profile", {"mercur_seller_id": "sel_dev_cnas_L11464"})
    if not laboratory:
        laboratory = insert("Laboratory Profile", mercur_seller_id="sel_dev_cnas_L11464",
                            laboratory_name=lab["lab_name"], review_status="Draft")
    methods = {}
    for row in batch["methods"]:
        label = row["item_name"]
        name = frappe.db.get_value("Test Method", {"method_name": label}, "name")
        # Existing names alone do not establish identity. Keep a distinct stable catalog entry.
        if name:
            label = f"{label} [{row['item_code']}]"
        methods[row["item_code"]] = frappe.db.get_value("Test Method", {"method_name": label}, "name") or insert(
            "Test Method", method_name=label, category=row["custom_test_category"],
            notes=f"CNAS Workbench {row['item_code']}", active=0,
        )
    standards = {}
    for row in batch["standards"]:
        full = row["normalized_number"]
        code, separator, tail = full.rpartition("-")
        if not separator or tail != row["std_year"]:
            code = full
        version = row["std_year"] or "未核实"
        matches = frappe.get_all("Test Standard", filters={"standard_code": code, "version": version}, pluck="name")
        if len(matches) > 1:
            frappe.throw(f"Ambiguous standard: {full}")
        standards[full] = matches[0] if matches else insert(
            "Test Standard", standard_code=code, version=version, title=row["standard_name"] or full,
            status="Draft",
        )
    source = insert("Capability Source", laboratory=laboratory, source_type="CNAS",
                    certificate_no=lab["reg_no"], documents_source_id=f"L11464:{digest}",
                    documents_version="7b274ef", documents_review_status="Historical Preview",
                    structured_json=json.dumps(batch, ensure_ascii=False), import_status="部分导入")
    for row in batch["items"]:
        identity = [laboratory, row["item_code"], row["standard_no"], row["test_object"],
                    row["clause"], row["limit_note"], row["effective_date"]]
        key = hashlib.sha256(json.dumps(identity).encode()).hexdigest()
        if frappe.db.exists("Laboratory Capability", {"cnas_scope_key": key}):
            continue
        insert("Laboratory Capability", laboratory=laboratory, source=source, source_row=row["source_row"],
               cnas_scope_key=key, test_method=methods[row["item_code"]],
               test_standard=standards[row["standard_no"]], product_scope=row["test_object"],
               industry=row["object_category"], project_parameter=row["standard_name"],
               capability_scope=row["standard_name"] or row["test_object"], clause=row["clause"],
               scope_effective_date=row["effective_date"] or None, limitation=row["limit_note"],
               accreditation_type="CNAS", certificate_no=lab["reg_no"], status="待确认")
    return {"source": source, "scope": len(batch["items"]), "blocked": len(batch["blocked"]),
            "duplicates": len(batch["duplicates"])}
