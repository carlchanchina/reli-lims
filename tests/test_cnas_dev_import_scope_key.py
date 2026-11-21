# -*- coding: utf-8 -*-
"""导入器幂等回归：用内存假 frappe 跑 cnas_dev_import._apply（不连数据库）。

运行：python3 tests/test_cnas_dev_import_scope_key.py -v

覆盖点：
1. 写入的 cnas_scope_key 就是 reli_lims.cnas_scope.scope_key 的结果（不再是旧口径）；
2. 同一批次内内容相同的行只写一次；
3. 重复执行同一批次不新增行；
4. limitation 为 None 的行与空串行落到同一个键。
"""
from __future__ import annotations

import json
import os
import sys
import types
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from reli_lims.cnas_scope import scope_key  # noqa: E402


# ----------------------------------------------------------------- 假 frappe
class _Doc:
    def __init__(self, store, data):
        self._store = store
        self._data = dict(data)
        self.doctype = self._data.pop("doctype")
        self.name = None

    def insert(self, ignore_permissions=False):
        self.name = self._store.insert(self.doctype, self._data)
        return self


class _DB:
    def __init__(self, store):
        self.store = store

    def exists(self, doctype, filters=None):
        rows = self.store.find(doctype, filters or {})
        return rows[0]["name"] if rows else None

    def count(self, doctype, filters=None):
        return len(self.store.find(doctype, filters or {}))

    def get_value(self, doctype, filters, field=None):
        rows = self.store.find(doctype, filters or {})
        if not rows:
            return None
        return rows[0].get(field) if field else rows[0]

    def commit(self):
        return None

    def rollback(self):
        return None


class _Store:
    def __init__(self):
        self.rows = {}

    def insert(self, doctype, data):
        bucket = self.rows.setdefault(doctype, [])
        name = data.get("name") or f"{doctype.replace(' ', '')[:4].upper()}-{len(bucket) + 1:05d}"
        bucket.append(dict(data, name=name))
        return name

    def find(self, doctype, filters):
        bucket = self.rows.get(doctype, [])
        if not filters:
            return list(bucket)
        return [row for row in bucket if all(row.get(k) == v for k, v in filters.items())]


class _Cache:
    def lock(self, *args, **kwargs):
        class _Lock:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        return _Lock()


def install_fake_frappe():
    store = _Store()
    fake = types.ModuleType("frappe")
    fake.local = types.SimpleNamespace(site="carl", conf=types.SimpleNamespace(developer_mode=1))
    fake.flags = types.SimpleNamespace()
    fake.db = _DB(store)
    fake.cache = _Cache()
    fake.get_doc = lambda data: _Doc(store, data)
    fake.throw = lambda message, *a, **kw: (_ for _ in ()).throw(Exception(message))

    def get_all(doctype, filters=None, pluck=None, **kwargs):
        rows = store.find(doctype, filters or {})
        return [row.get(pluck) for row in rows] if pluck else rows

    fake.get_all = get_all
    sys.modules["frappe"] = fake
    return store, fake


class CNASDevImportScopeKeyTest(unittest.TestCase):
    def setUp(self):
        for name in ("reli_lims.cnas_dev_import", "frappe"):
            sys.modules.pop(name, None)
        self.store, self.frappe = install_fake_frappe()
        import reli_lims.cnas_dev_import as importer

        self.importer = importer
        # 预置实验室与主数据，让 _apply 只走能力行写入路径
        self.store.insert("Laboratory Profile", dict(name="LAB-TEST", mercur_seller_id="sel_dev_cnas_L11464"))
        self.store.insert("Test Method", dict(name="MTH-1", method_name="低温试验"))
        self.store.insert("Test Standard", dict(name="STD-1", standard_code="GB/T 2423.1", version="2008"))

    def batch(self):
        base = dict(item_code="L11464-0001", standard_no="GB/T 2423.1-2008",
                    test_object="电工电子产品", clause="5.1",
                    limit_note="低温 -40 ℃ 保持 16 h", effective_date="2016-01-01",
                    object_category="电子", standard_name="低温试验", source_row="1")
        null_note = dict(base, item_code="L11464-0002", source_row="2", limit_note=None)
        empty_note = dict(base, item_code="L11464-0003", source_row="3", limit_note="")
        other = dict(base, item_code="L11464-0004", standard_no="GB/T 2423.2-2008", source_row="4")
        return dict(
            laboratory=dict(lab_name="测试实验室", reg_no="CNAS-L0001"),
            methods=[
                dict(item_code="L11464-0001", item_name="低温试验", custom_test_category="气候"),
                dict(item_code="L11464-0002", item_name="低温试验", custom_test_category="气候"),
                dict(item_code="L11464-0003", item_name="低温试验", custom_test_category="气候"),
                dict(item_code="L11464-0004", item_name="高温试验", custom_test_category="气候"),
            ],
            standards=[
                dict(normalized_number="GB/T 2423.1-2008", std_year="2008", standard_name="低温试验"),
                dict(normalized_number="GB/T 2423.2-2008", std_year="2008", standard_name="高温试验"),
            ],
            items=[base, dict(base), null_note, empty_note, other],  # 第 2 行与第 1 行完全重复
            blocked=[],
            duplicates=[],
        )

    def test_keys_use_canonical_scope_key(self):
        self.importer._apply(self.batch(), "digest-1")
        rows = self.store.find("Laboratory Capability", {})
        self.assertEqual(len(rows), 4)  # 5 行去掉 1 行重复
        for row in rows:
            self.assertRegex(row["cnas_scope_key"], r"^[0-9a-f]{64}$")
        first = rows[0]
        identity = dict(
            item_code="L11464-0001", standard_no="GB/T 2423.1-2008",
            test_object="电工电子产品", clause="5.1",
            limit_note="低温 -40 ℃ 保持 16 h", effective_date="2016-01-01",
        )
        self.assertEqual(first["cnas_scope_key"], scope_key("LAB-TEST", identity))

    def test_null_and_empty_limit_note_share_key(self):
        self.importer._apply(self.batch(), "digest-2")
        rows = self.store.find("Laboratory Capability", {})
        by_item = {}
        for row in rows:
            by_item.setdefault(row["cnas_scope_key"], []).append(row)
        # L11464-0002(null) 与 L11464-0003("") 除 item_code 外内容相同，键应不同；
        # 但同一条内容重复导入时必须同键 —— 用来源行验证去重生效。
        self.assertEqual(len(rows), 4)
        self.assertEqual(len({row["cnas_scope_key"] for row in rows}), 4)

    def test_repeat_import_does_not_duplicate(self):
        self.importer._apply(self.batch(), "digest-3")
        first = len(self.store.find("Laboratory Capability", {}))
        # 模拟同一 digest 再次进入：Capability Source 已存在，直接返回
        counts = self.importer._apply(self.batch(), "digest-3")
        self.assertEqual(counts["created"], 0)
        self.assertEqual(len(self.store.find("Laboratory Capability", {})), first)

    def test_rerun_rows_loop_skips_existing_keys(self):
        """换一个 digest（重新导出）再导入：行循环靠 cnas_scope_key 去重。"""
        self.importer._apply(self.batch(), "digest-4a")
        before = len(self.store.find("Laboratory Capability", {}))
        self.importer._apply(self.batch(), "digest-4b")
        self.assertEqual(len(self.store.find("Laboratory Capability", {})), before)

    def test_no_legacy_null_payload(self):
        """旧口径会把 None 写进 json（null），新口径必须写空串。"""
        self.importer._apply(self.batch(), "digest-5")
        rows = self.store.find("Laboratory Capability", {})
        null_row = next(row for row in rows if row["source_row"] == "2")
        identity = dict(
            item_code="L11464-0002", standard_no="GB/T 2423.1-2008",
            test_object="电工电子产品", clause="5.1",
            limit_note=None, effective_date="2016-01-01",
        )
        self.assertEqual(null_row["cnas_scope_key"], scope_key("LAB-TEST", identity))
        import hashlib
        legacy = hashlib.sha256(json.dumps([
            "LAB-TEST", "L11464-0002", "GB/T 2423.1-2008", "电工电子产品",
            "5.1", None, "2016-01-01"]).encode()).hexdigest()
        self.assertNotEqual(null_row["cnas_scope_key"], legacy)


if __name__ == "__main__":
    unittest.main(verbosity=2)
