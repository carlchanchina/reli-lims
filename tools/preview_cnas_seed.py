"""Reconcile the historical CNAS Workbench fixture without writing to any database."""
import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def preview(workbench, lab, snapshot=None):
    # Use the original Workbench validator; the LIMS runtime never imports a parser.
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(workbench / "app"))
    from validate_scope import norm_std_no, validate

    export = workbench / "app" / "labs" / lab / "out_v2"
    paths = [export / f"{name}.csv" for name in ("items", "standards", "scope_standards", "pending")]
    methods, standards, rows, pending = map(read_csv, paths)
    method_codes = {row["item_code"] for row in methods}
    standard_codes = {row["standard_no"] for row in standards}
    validated = validate([dict(row, item_code=row["parent"]) for row in rows])

    key_fields = ("item_code", "test_object", "standard_no", "clause", "limit_note")
    comparison_fields = (*key_fields, "object_category", "effective_date")
    retained = {}
    duplicates = []
    for row in validated["ok"]:
        key = tuple(row[field] for field in key_fields)
        if key in retained:
            duplicates.append({"method": row["item_code"], "export_index": row["idx"]})
        else:
            retained[key] = row

    seed = workbench / "seed" / "cnas.db"
    with sqlite3.connect(seed.resolve().as_uri() + "?mode=ro&immutable=1", uri=True) as conn:
        seeded = set(conn.execute(
            "SELECT item_code,test_object,standard_no,clause,limit_note,object_category,effective_date "
            "FROM scope WHERE lab_code = ?", (lab,),
        ))
    kept = {tuple(row[field] for field in comparison_fields) for row in retained.values()}
    normalized_standards = {norm_std_no(code, []) for code in standard_codes}
    missing_refs = [
        {"method": row["item_code"], "export_index": row["idx"]}
        for row in retained.values()
        if row["item_code"] not in method_codes or row["standard_no"] not in normalized_standards
    ]
    result = {
        "source_revision": subprocess.check_output(["git", "-C", str(workbench), "rev-parse", "HEAD"], text=True).strip(),
        "source_hashes": {str(path.relative_to(workbench)): hashlib.sha256(path.read_bytes()).hexdigest()
                          for path in (*paths, seed, workbench / "app" / "validate_scope.py")},
        "laboratory_code": lab,
        "method_candidates": len(methods),
        "duplicate_method_codes": len(methods) - len(method_codes),
        "standard_candidates": len(standards),
        "duplicate_standard_codes": len(standards) - len(standard_codes),
        "raw_scope_rows": len(rows),
        "retained_scope_rows": len(retained),
        "matching_seed_rows": len(kept & seeded),
        "retained_only": len(kept - seeded),
        "seed_only": len(seeded - kept),
        "normalization_fixes": len(validated["fixes"]),
        "warning_rows": len(validated["warns"]),
        "historical_pending_csv_rows": len(pending),
        "duplicates": duplicates,
        "blocked": [{"export_key": record["key"], "reasons": [issue[2] for issue in record["reasons"]]}
                    for record in validated["blocked"]],
        "normalized_standard_collisions": len(standard_codes) - len(normalized_standards),
        "standard_aliases": {code: norm_std_no(code, []) for code in sorted(standard_codes)
                             if code != norm_std_no(code, [])},
        "missing_master_references": missing_refs,
        "source_page_column_available": bool(rows and "source_page" in rows[0]),
        "database_writes": 0,
    }

    if snapshot is not None:
        site_codes = Counter(
            (norm_std_no(f"{row['standard_code']}-{row['version']}", []), str(row["version"]))
            for row in snapshot["standards"]
        )
        site_names = Counter(row["method_name"].strip() for row in snapshot["methods"])
        lab_names = [
            row["lab_name"] for row in read_csv(workbench / "app" / "labs.csv")
            if row["lab_code"] == lab
        ]
        result["site_preview"] = {
            "standard_exact_version_matches": sum(
                site_codes[norm_std_no(row["standard_no"], []), row["std_year"]] == 1
                for row in standards
            ),
            "standard_ambiguous_matches": sum(
                site_codes[norm_std_no(row["standard_no"], []), row["std_year"]] > 1
                for row in standards
            ),
            "method_exact_name_review_candidates": sum(
                site_names[row["item_name"].strip()] > 0 for row in methods
            ),
            "laboratory_exact_name_candidates": sum(
                row["laboratory_name"] in lab_names for row in snapshot["laboratories"]
            ),
            "active_non_stock_sales_items": snapshot["service_item_count"],
            "authorized_creates_or_updates": 0,
        }
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workbench", type=Path)
    parser.add_argument("--lab", default="L11464")
    parser.add_argument("--site-snapshot", type=Path, help="Private read-only Frappe master snapshot")
    args = parser.parse_args()
    snapshot = json.loads(args.site_snapshot.read_text()) if args.site_snapshot else None
    print(json.dumps(preview(args.workbench.resolve(), args.lab, snapshot), ensure_ascii=False, indent=2))
