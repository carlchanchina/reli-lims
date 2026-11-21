# -*- coding: utf-8 -*-
"""跨仓库 cnas_scope_key 平价测试（reli-lims ↔ cnas-workbench PR #7）。

运行：python3 tests/test_cnas_scope_key_parity.py -v

向量文件 tests/fixtures/cnas_scope_key_vectors.json 的 expected_scope_key
由 cnas-workbench PR #7 的 server/testing_bridge.scope_key() 实际计算生成
（commit 5826d98，文件 sha256 记录在向量文件 source 段），不是手写常量。
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from reli_lims.cnas_scope import (  # noqa: E402
    ROW_IDENTITY_FIELDS,
    normalize_identity,
    scope_key,
)

VECTORS_PATH = os.path.join(ROOT, "tests", "fixtures", "cnas_scope_key_vectors.json")


def load_vectors():
    with open(VECTORS_PATH, encoding="utf-8") as stream:
        return json.load(stream)


def legacy_scope_key(laboratory, row):
    """2026-11-21 之前的实现：字段原值直接序列化。

    仅作辅助，**不作为断言基准**——基准是 fixture 里冻结的 legacy_scope_key。
    """
    identity = [laboratory, row["item_code"], row["standard_no"], row["test_object"],
                row["clause"], row["limit_note"], row["effective_date"]]
    return hashlib.sha256(json.dumps(identity).encode()).hexdigest()


class ScopeKeyContractTest(unittest.TestCase):
    def setUp(self):
        self.fixture = load_vectors()
        self.by_name = {item["name"]: item for item in self.fixture["vectors"]}

    # ---------------------------------------------------------------- 契约
    def test_field_order_is_frozen(self):
        self.assertEqual(
            ROW_IDENTITY_FIELDS,
            ("item_code", "standard_no", "test_object", "clause",
             "limit_note", "effective_date"),
        )
        # 完整身份 = laboratory + 6 个行级字段
        self.assertEqual(len(normalize_identity("LAB", {"item_code": "x"})), 7)

    def test_identity_matches_cnas_workbench_shape(self):
        identity = normalize_identity("LAB-L11464", dict(
            item_code="A", standard_no="B", test_object="C",
            clause="D", limit_note="E", effective_date="F"))
        self.assertEqual(identity, ["LAB-L11464", "A", "B", "C", "D", "E", "F"])

    # ------------------------------------------------- 与另一仓库逐条一致
    def test_all_vectors_match_cnas_workbench(self):
        for item in self.fixture["vectors"]:
            with self.subTest(vector=item["name"]):
                self.assertEqual(
                    scope_key(item["laboratory"], item["row"]),
                    item["expected_scope_key"],
                    f"{item['name']}: {item['note']}",
                )

    # ------------------------------------------------------ null / 空串
    def test_null_and_empty_string_are_equivalent(self):
        null_case = self.by_name["null_clause"]
        empty_case = self.by_name["empty_clause"]
        self.assertEqual(
            scope_key(null_case["laboratory"], null_case["row"]),
            scope_key(empty_case["laboratory"], empty_case["row"]),
        )
        null_note = self.by_name["null_limit_note"]
        empty_note = self.by_name["empty_limit_note"]
        self.assertEqual(
            scope_key(null_note["laboratory"], null_note["row"]),
            scope_key(empty_note["laboratory"], empty_note["row"]),
        )

    def test_missing_fields_normalize_to_empty_string(self):
        row = {"item_code": "L11464-9001", "standard_no": "GB/T 2423.10-2019"}
        self.assertEqual(
            normalize_identity("LAB-L11464", row)[2:],
            ["GB/T 2423.10-2019", "", "", "", ""],
        )
        self.assertEqual(scope_key("LAB-L11464", row),
                         self.by_name["missing_optional_fields"]["expected_scope_key"])

    # ------------------------------------------------------------- 中文
    def test_chinese_limit_note_is_ascii_escaped(self):
        item = self.by_name["chinese_limit_note"]
        self.assertEqual(scope_key(item["laboratory"], item["row"]), item["expected_scope_key"])
        payload = json.dumps(normalize_identity(item["laboratory"], item["row"]))
        self.assertIn("\\u4ec5\\u9650", payload)


    # ----------------------------------------------------------- Unicode
    def test_unicode_values_are_hashed_verbatim(self):
        item = self.by_name["unicode_mixed"]
        self.assertEqual(scope_key(item["laboratory"], item["row"]), item["expected_scope_key"])
        # 不做 NFKC / 大小写归一
        fullwidth = self.by_name["unicode_fullwidth"]
        halfwidth = self.by_name["standard_a"]
        self.assertNotEqual(
            scope_key(fullwidth["laboratory"], fullwidth["row"]),
            scope_key(halfwidth["laboratory"], halfwidth["row"]),
        )

    # ------------------------------------------------------- 标准编号
    def test_different_standard_numbers_differ(self):
        a = self.by_name["standard_a"]
        b = self.by_name["standard_b"]
        self.assertNotEqual(scope_key(a["laboratory"], a["row"]),
                            scope_key(b["laboratory"], b["row"]))

    def test_standard_field_fallback(self):
        item = self.by_name["standard_fallback"]
        self.assertEqual(scope_key(item["laboratory"], item["row"]), item["expected_scope_key"])

    # ------------------------------------------------------- 重复导入
    def test_repeated_import_is_idempotent(self):
        row = dict(self.by_name["baseline_full_row"]["row"])
        keys = {scope_key("LAB-L11464", dict(row)) for _ in range(5)}
        self.assertEqual(len(keys), 1)

    def test_row_order_does_not_affect_key(self):
        """跨仓库字段插入顺序不改变键（dict 顺序无关）。"""
        row = self.by_name["baseline_full_row"]["row"]
        reordered = {key: row[key] for key in reversed(list(row))}
        self.assertEqual(scope_key("LAB-L11464", row), scope_key("LAB-L11464", reordered))

    def test_duplicate_batch_rows_collapse_to_one_key(self):
        """同一能力行在批量中出现两次，只应写入一次。"""
        rows = [dict(self.by_name["baseline_full_row"]["row"]) for _ in range(2)]
        rows.append(dict(self.by_name["standard_b"]["row"]))
        seen, unique = set(), []
        for row in rows:
            key = scope_key("LAB-L11464", row)
            if key in seen:
                continue
            seen.add(key)
            unique.append(key)
        self.assertEqual(len(unique), 2)

    # --------------------------------------------------- 既有合法键不变
    def test_existing_wellformed_keys_unchanged(self):
        """基准是 fixture 里冻结的 legacy_scope_key（旧实现实算值），不是本地重写。"""
        self.assertTrue(self.fixture["legacy_unchanged"])
        for name in self.fixture["legacy_unchanged"]:
            item = self.by_name[name]
            with self.subTest(vector=name):
                self.assertIsNotNone(item["legacy_scope_key"])
                self.assertEqual(
                    scope_key(item["laboratory"], item["row"]),
                    item["legacy_scope_key"],
                )

    def test_malformed_rows_change_key(self):
        """null / 非字符串字段的行：新键必须与冻结的旧键不同。"""
        expected = ["laboratory_null", "null_clause", "null_limit_note",
                    "numeric_effective_date", "standard_fallback"]
        self.assertEqual(sorted(self.fixture["legacy_changed"]), expected)
        for name in expected:
            item = self.by_name[name]
            with self.subTest(vector=name):
                self.assertNotEqual(
                    scope_key(item["laboratory"], item["row"]),
                    item["legacy_scope_key"],
                )

    def test_legacy_helper_agrees_with_frozen_values(self):
        """辅助 helper 与冻结值一致，防止 helper 写错后断言失去意义。"""
        for item in self.fixture["vectors"]:
            if not item["legacy_scope_key"]:
                continue
            with self.subTest(vector=item["name"]):
                self.assertEqual(
                    legacy_scope_key(item["laboratory"], item["row"]),
                    item["legacy_scope_key"],
                )

    # ----------------------------------------------------- 向量文件自检
    def test_vector_fixture_provenance(self):
        source = self.fixture["source"]
        self.assertEqual(source["repo"], "carlchanchina/cnas-workbench")
        self.assertEqual(source["function"], "scope_key")
        self.assertRegex(source["file_sha256"], r"^[0-9a-f]{64}$")
        self.assertGreaterEqual(len(self.fixture["vectors"]), 12)

    def test_scope_key_is_64_hex(self):
        self.assertRegex(scope_key("LAB-L11464", {}), r"^[0-9a-f]{64}$")


if __name__ == "__main__":
    unittest.main(verbosity=2)
