# -*- coding: utf-8 -*-
"""只读盘点脚本的自测：证明它真的能识别"旧键在库、新键不在"的行。

运行：python3 tests/test_cnas_scope_duplicate_report.py -v
"""
from __future__ import annotations

import datetime
import hashlib
import importlib.util
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from reli_lims.cnas_scope import scope_key  # noqa: E402

TOOL_PATH = os.path.join(ROOT, "tools", "report_cnas_scope_duplicates.py")


def load_tool():
    spec = importlib.util.spec_from_file_location("report_cnas_scope_duplicates", TOOL_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def db_row(name, laboratory, key, item_code, standard_no, source_row="1", **extra):
    schema = json.dumps(dict(item_code=item_code, standard_no=standard_no))
    row = dict(name=name, laboratory=laboratory, cnas_scope_key=key,
               product_scope="电工电子产品", clause="5.1",
               limitation="低温 -40 ℃", scope_effective_date="2016-01-01",
               source="CAPSRC-1", source_row=source_row, status="待确认",
               condition_schema=schema, test_standard="STD-1", test_method="MTH-1")
    row.update(extra)
    return row


IDENTITY = dict(item_code="L11464-0001", standard_no="GB/T 2423.1-2008",
                test_object="电工电子产品", clause="5.1",
                limit_note="低温 -40 ℃", effective_date="2016-01-01")


class DuplicateReportToolTest(unittest.TestCase):
    def setUp(self):
        self.tool = load_tool()
        self.canonical = scope_key("LAB-1", IDENTITY)
        self.legacy = self.tool.legacy_scope_key("LAB-1", IDENTITY)

    def test_item_code_prefers_condition_schema_then_source_row(self):
        self.assertEqual(self.tool.item_code_of(db_row("C1", "LAB-1", "k", "ITEM-9", "STD-9")), "ITEM-9")
        legacy_row = dict(source_row="L11464-0001#7", condition_schema=None)
        self.assertEqual(self.tool.item_code_of(legacy_row), "L11464-0001")

    def test_legacy_key_tolerates_date_objects(self):
        identity = dict(IDENTITY, effective_date=datetime.date(2016, 1, 1))
        value = self.tool.legacy_scope_key("LAB-1", identity)
        self.assertRegex(value, r"^[0-9a-f]{64}$")

    def test_provenance_matches_canonical_or_mismatch(self):
        rows = [
            db_row("C-CANON", "LAB-1", self.canonical, "L11464-0001", "GB/T 2423.1-2008"),
            db_row("C-BAD", "LAB-1", "deadbeef", "L11464-0001", "GB/T 2423.1-2008"),
            dict(name="C-EMPTY", laboratory="LAB-2", cnas_scope_key=None, condition_schema=None),
        ]
        report = self.tool.build_report(rows, self.tool.load_scope_module())
        self.assertEqual(report["total_rows"], 3)
        self.assertEqual(report["empty_key_rows"], 1)
        self.assertEqual(report["recomputable_rows"], 2)
        self.assertEqual(report["key_provenance"]["matches_canonical"], 1)
        self.assertEqual(report["key_provenance"]["mismatch"], 1)
        self.assertEqual(report["key_provenance"]["not_recomputable"], 1)
        self.assertEqual(report["mismatched_rows"][0]["name"], "C-BAD")
        self.assertEqual(report["repeated_same_key"], [])
        self.assertTrue(report["limitations"])

    def test_batch_audit_flags_reimport_that_would_duplicate(self):
        legacy_batch_item = dict(IDENTITY, limit_note=None, source_row="L11464-0001#1")
        batch = dict(
            laboratory=dict(lab_name="LAB-1"),
            items=[legacy_batch_item,
                   dict(IDENTITY, item_code="L11464-0002", source_row="L11464-0002#2")],
        )
        legacy_key = self.tool.legacy_scope_key("LAB-1", legacy_batch_item)
        rows = [db_row("C-LEGACY", "LAB-1", legacy_key, "L11464-0001", "GB/T 2423.1-2008")]
        keys = {row["cnas_scope_key"] for row in rows}
        audit = self.tool.audit_batch(batch, keys, self.tool.load_scope_module(), "LAB-1")
        self.assertEqual(audit["verdict"], "reimport_would_duplicate")
        self.assertEqual(audit["summary"]["legacy_key_only"], 1)
        self.assertEqual(audit["summary"]["absent"], 1)
        self.assertEqual(audit["legacy_key_only_rows"][0]["source_row"], "L11464-0001#1")

    def test_batch_audit_is_safe_when_db_already_canonical(self):
        batch = dict(laboratory=dict(lab_name="LAB-1"),
                     items=[dict(IDENTITY, source_row="L11464-0001#1")])
        rows = [db_row("C-CANON", "LAB-1", self.canonical, "L11464-0001", "GB/T 2423.1-2008")]
        audit = self.tool.audit_batch(batch, {rows[0]["cnas_scope_key"]},
                                      self.tool.load_scope_module(), "LAB-1")
        self.assertEqual(audit["verdict"], "reimport_is_safe")
        self.assertEqual(audit["summary"]["already_canonical"], 1)

    def test_legacy_key_differs_from_canonical_for_null_note(self):
        identity = dict(IDENTITY, limit_note=None)
        legacy = self.tool.legacy_scope_key("LAB-1", identity)
        canonical = scope_key("LAB-1", identity)
        self.assertNotEqual(legacy, canonical)
        self.assertEqual(legacy, hashlib.sha256(json.dumps(
            ["LAB-1", "L11464-0001", "GB/T 2423.1-2008", "电工电子产品",
             "5.1", None, "2016-01-01"]).encode()).hexdigest())


if __name__ == "__main__":
    unittest.main(verbosity=2)
