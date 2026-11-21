#!/usr/bin/env python3
"""只读盘点 Laboratory Capability 中因哈希口径差异产生的重复行。

背景：2026-11-21 之前 reli-lims 的 cnas_dev_import 直接用字段原值做
json.dumps，`None` 会写成 `null`；cnas-workbench PR #7 归一为 `""`。
同一能力行经两条路径写入会得到两个不同的 cnas_scope_key，从而出现
内容重复但键不同的能力行。本脚本只统计，不改数据、不迁移、不删除。

用法（在 bench 上执行，只读连接）：
    cd /home/frappe/pilot/benches/dev-bench/sites
    ../env/bin/python /tmp/report_cnas_scope_duplicates.py \
        --site carl --scope-module /tmp/cnas_scope.py --out /tmp/report.json

`--scope-module` 指向与仓库内 reli_lims/cnas_scope.py 完全相同的副本，保证
盘点用的哈希口径就是修好之后的实现，而不是服务器上尚未升级的旧代码。

退出码恒为 0（除非连不上站点）；是否处理重复行由人决定。
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict

FIELDS = (
    "name", "laboratory", "cnas_scope_key", "test_method", "test_standard",
    "product_scope", "clause", "limitation", "scope_effective_date",
    "capability_scope", "source", "source_row", "condition_schema", "status",
    "published",
)


def _text(value):
    return str(value) if value else ""


def legacy_scope_key(laboratory, row):
    identity = [laboratory, row["item_code"], row["standard_no"], row["test_object"],
                row["clause"], row["limit_note"], row["effective_date"]]
    return hashlib.sha256(json.dumps(identity).encode()).hexdigest()


def canonical_scope_key(laboratory, row, module=None):
    """默认用本仓库 reli_lims/cnas_scope.py；--scope-module 可指向同内容的副本。"""
    if module is None:
        module = load_scope_module()
    return module.scope_key(laboratory, row)


def load_scope_module(path=None):
    import importlib.util
    import os

    if path is None:
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "reli_lims", "cnas_scope.py",
        )
    spec = importlib.util.spec_from_file_location("reli_lims_cnas_scope_copy", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _condition(raw):
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def content_identity(row):
    """不比键、只比业务内容的指纹（DB 里能拿到的字段）。"""
    schema = _condition(row.get("condition_schema"))
    return (
        _text(row.get("laboratory")),
        _text(schema.get("item_code") or row.get("source_row")),
        _text(schema.get("standard_no") or row.get("test_standard")),
        _text(row.get("product_scope") or schema.get("test_object")),
        _text(row.get("clause")),
        _text(row.get("limitation")),
        _text(row.get("scope_effective_date") or schema.get("scope_effective_date")),
    )


def recompute_keys(row, module=None):
    """能还原 7 个身份字段时，重算新旧两套键。"""
    schema = _condition(row.get("condition_schema"))
    item_code = schema.get("item_code")
    standard_no = schema.get("standard_no")
    if not item_code or not standard_no:
        return None
    identity = {
        "item_code": item_code,
        "standard_no": standard_no,
        "test_object": row.get("product_scope") or schema.get("test_object"),
        "clause": row.get("clause"),
        "limit_note": row.get("limitation"),
        "effective_date": schema.get("scope_effective_date") or row.get("scope_effective_date"),
    }
    laboratory = row.get("laboratory")
    return dict(canonical=canonical_scope_key(laboratory, identity, module),
                legacy=legacy_scope_key(laboratory, identity))


def build_report(rows, module=None):
    by_key = defaultdict(list)
    by_content = defaultdict(list)
    provenance = defaultdict(int)
    unknown_key_rows = []
    recomputable = 0
    for row in rows:
        key = _text(row.get("cnas_scope_key"))
        by_key[key].append(row)
        by_content[content_identity(row)].append(row)
        values = recompute_keys(row, module)
        if values is None:
            provenance["not_recomputable"] += 1
            continue
        recomputable += 1
        if key == values["canonical"]:
            provenance["canonical"] += 1
        elif key == values["legacy"]:
            provenance["legacy"] += 1
        else:
            provenance["unknown"] += 1
            unknown_key_rows.append(dict(
                name=row.get("name"), key=key,
                canonical=values["canonical"], legacy=values["legacy"],
            ))

    duplicates_by_content = []
    duplicates_missing_key = []
    for identity, group in by_content.items():
        keys = {_text(item.get("cnas_scope_key")) for item in group}
        filled = {key for key in keys if key}
        if len(group) > 1 and len(filled) > 1:
            duplicates_by_content.append(dict(
                identity=list(identity),
                rows=len(group),
                distinct_keys=len(filled),
                names=[item.get("name") for item in group][:20],
                keys=sorted(filled)[:6],
                sources=sorted({_text(item.get("source")) for item in group}),
            ))
        elif len(group) > 1 and not filled:
            duplicates_missing_key.append(dict(
                identity=list(identity),
                rows=len(group),
                names=[item.get("name") for item in group][:20],
                statuses=sorted({_text(item.get("status")) for item in group}),
            ))

    by_source = defaultdict(int)
    for row in rows:
        by_source[_text(row.get("source")) or "(no source)"] += 1

    repeated_key = [
        dict(key=key, rows=len(group), names=[item.get("name") for item in group][:10])
        for key, group in by_key.items() if key and len(group) > 1
    ]

    return dict(
        read_only=True,
        total_rows=len(rows),
        rows_by_source=dict(sorted(by_source.items(), key=lambda item: -item[1])),
        empty_key_rows=len(by_key.get("", [])),
        distinct_keys=len([key for key in by_key if key]),
        recomputable_rows=recomputable,
        key_provenance=dict(provenance),
        repeated_same_key=repeated_key,
        repeated_content_different_key=duplicates_by_content,
        repeated_content_without_key=duplicates_missing_key,
        unknown_provenance_rows=unknown_key_rows[:50],
    )


def collect_site(site):
    import frappe

    frappe.init(site=site)
    frappe.connect()
    try:
        return frappe.get_all("Laboratory Capability", fields=list(FIELDS), limit_page_length=0)
    finally:
        frappe.destroy()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site")
    parser.add_argument("--input", help="离线 JSON 数组，便于在没有 bench 时复算")
    parser.add_argument("--scope-module", help="cnas_scope.py 路径（默认取本仓库）")
    parser.add_argument("--out")
    args = parser.parse_args(argv)

    if args.input:
        with open(args.input, encoding="utf-8") as stream:
            rows = json.load(stream)
    elif args.site:
        rows = collect_site(args.site)
    else:
        parser.error("需要 --site 或 --input")

    module = load_scope_module(args.scope_module)
    report = build_report(rows, module)
    payload = json.dumps(report, ensure_ascii=False, indent=2, default=str)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as stream:
            stream.write(payload + "\n")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
