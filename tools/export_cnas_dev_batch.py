"""Package the Workbench's existing structured output for the Carl DEV importer."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

from preview_cnas_seed import read_csv

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("workbench", type=Path)
args = parser.parse_args()
sys.dont_write_bytecode = True
sys.path.insert(0, str(args.workbench / "app"))
from validate_scope import norm_std_no, validate

directory = args.workbench / "app/labs/L11464/out_v2"
rows = read_csv(directory / "scope_standards.csv")
methods = read_csv(directory / "items.csv")
standards = read_csv(directory / "standards.csv")
validated = validate([dict(row, item_code=row["parent"]) for row in rows])
items = []
duplicates = []
seen = set()
for row in validated["ok"]:
    key = tuple(row[field] for field in ("item_code", "test_object", "standard_no", "clause", "limit_note"))
    if key in seen:
        duplicates.append(row)
        continue
    seen.add(key)
    items.append(dict(row, test_method_name=row["item_code"], standard_code=row["standard_no"],
                      source_row=f"{row['item_code']}#{row['idx']}"))
for standard in standards:
    standard["normalized_number"] = norm_std_no(standard["standard_no"], [])
batch = dict(methods=methods, standards=standards, items=items, raw_rows=rows, duplicates=duplicates,
             blocked=validated["blocked"], warnings=validated["warns"], fixes=validated["fixes"],
             laboratory=next(row for row in read_csv(args.workbench / "app/labs.csv") if row["lab_code"] == "L11464"))
assert tuple(map(len, (methods, standards, rows, items, duplicates, batch["blocked"]))) == (118, 207, 660, 650, 3, 7)
batch["digest"] = hashlib.sha256(json.dumps(batch, sort_keys=True).encode()).hexdigest()
print(json.dumps(batch, ensure_ascii=False))
