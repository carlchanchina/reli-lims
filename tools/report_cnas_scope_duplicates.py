#!/usr/bin/env python3
"""只读盘点 `cnas_scope_key` 的重复风险（不改数据、不迁移、不删除）。

为什么不能"直接在库里查重复"：
`Laboratory Capability` 只存了键和展示字段，**没存** `item_code` / `standard_no`
（历史导入把 item_code 编进 `source_row` = `"<item_code>#<idx>"`，Workbench 写回
则放在 `condition_schema` JSON 里，两者不通用），所以无法从库表反推出同一行的
两个不同哈希值。可靠的核对方式是**拿批次文件重算**：

    # 1) 只读统计（键是否唯一、空键、能反推口径的行）
    ../env/bin/python report_cnas_scope_duplicates.py --site carl \
        --scope-module /tmp/cnas_scope.py

    # 2) 导入前核对：批次里哪些行"旧键已在库里、新键不在" → 重导会插重
    ../env/bin/python report_cnas_scope_duplicates.py --site carl \
        --scope-module /tmp/cnas_scope.py --batch /tmp/batch.json

`--scope-module` 指向与仓库 `reli_lims/cnas_scope.py` 完全相同的副本，保证盘点
用的是修好之后的口径，而不是服务器上尚未升级的旧代码。

退出码：0 正常；2 参数/连接问题。
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from collections import defaultdict

FIELDS = (
    "name", "laboratory", "cnas_scope_key", "test_method", "test_standard",
    "product_scope", "clause", "limitation", "scope_effective_date",
    "capability_scope", "source", "source_row", "condition_schema", "status",
)

LIMITATIONS = [
    "库表不存 item_code / standard_no，无法从行记录反算历史键；"
    "跨路径重复必须用 --batch 拿原始批次重算才能判定。",
    "历史导入行没有 condition_schema，provenance 只能是 not_recomputable。",
    "cnas_scope_key 带唯一索引，同键重复理论上不存在；"
    "本工具统计的是'内容相同但键不同'的风险，只能通过批次核对发现。",
    "库里存的是归一后的字符串，'旧口径'与'新口径'对全字符串行给出同一个键，"
    "因此 provenance 只能区分 matches_canonical / mismatch，无法反推当年用的哪版代码。",
]


def _text(value):
    return str(value) if value else ""


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


def item_code_of(row):
    """优先 condition_schema.item_code，其次 source_row 的 `#` 前缀。"""
    schema = _condition(row.get("condition_schema"))
    value = schema.get("item_code")
    if value:
        return _text(value)
    source_row = _text(row.get("source_row"))
    return source_row.split("#", 1)[0] if "#" in source_row else source_row


def standard_no_of(row):
    """只有 condition_schema 里才是真正的标准号；test_standard 是文档名。"""
    return _text(_condition(row.get("condition_schema")).get("standard_no"))


def identity_of(row):
    return dict(
        item_code=item_code_of(row),
        standard_no=standard_no_of(row),
        test_object=_text(row.get("product_scope")),
        clause=_text(row.get("clause")),
        limit_note=_text(row.get("limitation")),
        effective_date=_text(row.get("scope_effective_date")),
    )


def _legacy_value(value):
    """旧口径按原样序列化：None 保持 None（→ json null）；
    date/Decimal 这类非 JSON 类型转字符串，只为让脚本不崩。"""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def legacy_scope_key(laboratory, identity):
    """2026-11-21 之前的口径：`json.dumps` 原值（None 会写成 null）。"""
    values = [_legacy_value(laboratory)] + [_legacy_value(identity[key]) for key in (
        "item_code", "standard_no", "test_object", "clause", "limit_note", "effective_date")]
    return hashlib.sha256(json.dumps(values).encode()).hexdigest()


def load_scope_module(path=None):
    if path is None:
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "reli_lims", "cnas_scope.py",
        )
    spec = importlib.util.spec_from_file_location("reli_lims_cnas_scope_copy", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def recompute_keys(row, module):
    identity = identity_of(row)
    if not identity["item_code"] or not identity["standard_no"]:
        return None
    return module.scope_key(_text(row.get("laboratory")), identity)


def build_report(rows, module):
    """库内只读统计。不做内容分组——见 LIMITATIONS。"""
    by_key = defaultdict(list)
    provenance = defaultdict(int)
    mismatched = []
    recomputable = 0
    for row in rows:
        key = _text(row.get("cnas_scope_key"))
        by_key[key].append(row)
        canonical = recompute_keys(row, module)
        if canonical is None:
            provenance["not_recomputable"] += 1
            continue
        recomputable += 1
        if key == canonical:
            provenance["matches_canonical"] += 1
        else:
            provenance["mismatch"] += 1
            mismatched.append(dict(name=row.get("name"), key=key, canonical=canonical))

    by_source = defaultdict(int)
    for row in rows:
        by_source[_text(row.get("source")) or "(no source)"] += 1

    return dict(
        read_only=True,
        total_rows=len(rows),
        rows_by_source=dict(sorted(by_source.items(), key=lambda item: -item[1])),
        empty_key_rows=len(by_key.get("", [])),
        distinct_nonempty_keys=len([key for key in by_key if key]),
        repeated_same_key=[
            dict(key=key, rows=len(group), names=[r.get("name") for r in group][:10])
            for key, group in by_key.items() if key and len(group) > 1
        ],
        recomputable_rows=recomputable,
        key_provenance=dict(provenance),
        mismatched_rows=mismatched[:50],
        limitations=LIMITATIONS,
    )


def audit_batch(batch, db_keys, module, laboratory=None):
    """批次 × 库内键：找出"旧键在库、新键不在"的行（重导会插重）。

    `laboratory` 必须是 ERP 里的 Laboratory Profile 文档名；缺省时退回批次的
    lab_name 并在结果里标记 laboratory_assumed，提醒结论可能因实验室名不一致而失真。
    """
    assumed = False
    if not laboratory:
        laboratory = (batch.get("laboratory") or {}).get("lab_name")
        assumed = True
    rows = []
    buckets = defaultdict(int)
    for item in batch.get("items") or []:
        identity = dict(
            item_code=item.get("item_code"),
            standard_no=item.get("standard_no") or item.get("standard"),
            test_object=item.get("test_object"),
            clause=item.get("clause"),
            limit_note=item.get("limit_note"),
            effective_date=item.get("effective_date"),
        )
        canonical = module.scope_key(laboratory, identity)
        legacy = legacy_scope_key(laboratory, identity)
        if canonical in db_keys:
            state = "already_canonical"
        elif legacy in db_keys:
            state = "legacy_key_only"      # 重导会新增一条内容重复的行
        else:
            state = "absent"
        buckets[state] += 1
        if state == "legacy_key_only":
            rows.append(dict(source_row=item.get("source_row"),
                             canonical=canonical, legacy=legacy,
                             item_code=identity["item_code"],
                             standard_no=identity["standard_no"]))
    return dict(
        laboratory=laboratory,
        laboratory_assumed=assumed,
        batch_rows=len(batch.get("items") or []),
        summary=dict(buckets),
        legacy_key_only_rows=rows[:100],
        verdict=("reimport_would_duplicate" if buckets.get("legacy_key_only")
                 else "reimport_is_safe"),
    )


def collect_site(site):
    import frappe

    frappe.init(site=site)
    frappe.connect()
    try:
        rows = frappe.get_all("Laboratory Capability", fields=list(FIELDS), limit_page_length=0)
    finally:
        frappe.destroy()
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", help="bench 站点名，例如 carl")
    parser.add_argument("--input", help="离线 JSON 数组，替代 --site 的库内数据")
    parser.add_argument("--batch", help="批次 JSON（含 items），做导入前重复核对")
    parser.add_argument("--laboratory", help="ERP 里的 Laboratory Profile 文档名，用于 --batch 核对")
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
    if args.batch:
        with open(args.batch, encoding="utf-8") as stream:
            batch = json.load(stream)
        db_keys = {_text(row.get("cnas_scope_key")) for row in rows if row.get("cnas_scope_key")}
        report["batch_audit"] = audit_batch(batch, db_keys, module, args.laboratory)

    payload = json.dumps(report, ensure_ascii=False, indent=2, default=str)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as stream:
            stream.write(payload + "\n")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
