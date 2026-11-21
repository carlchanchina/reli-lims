"""Canonical CNAS scope key shared by the LIMS importer and cnas-workbench.

`cnas_scope_key` is the idempotency key of `Laboratory Capability`. The same
capability row parsed by cnas-workbench and imported by reli-lims must produce
byte-identical keys, otherwise the batch import inserts duplicates instead of
skipping them.

Canonical form (must stay byte-identical with
`cnas-workbench server/testing_bridge.py::scope_key`):

    sha256(json.dumps([
        laboratory, item_code, standard_no, test_object,
        clause, limit_note, effective_date,
    ]).encode())

Rules that are part of the contract, not implementation details:

1. Field order is fixed — never reorder, never append.
2. Every value is normalised with ``str(value) if value else ''``; this makes
   ``None``, ``''``, ``0``, ``False`` hash identically.
3. ``standard_no`` falls back to ``standard`` when absent/empty.
4. ``json.dumps`` keeps its defaults (``ensure_ascii=True``, ``", "`` /
   ``": "`` separators) and ``str.encode()`` keeps UTF-8, so non-ASCII text is
   escaped as ``\\uXXXX`` on both sides.
5. No ``strip()`` / ``lower()`` / Unicode normalisation: values are hashed
   verbatim. Trimming here would silently break parity with cnas-workbench.

Well-formed rows (all seven fields non-empty strings) hash exactly as the
pre-2026-11-21 implementation did, so existing keys stay valid.
"""
import hashlib
import json

#: Identity fields, in hash order. Exported for tests and diagnostic tooling.
SCOPE_KEY_FIELDS = (
    "item_code",
    "standard_no",
    "test_object",
    "clause",
    "limit_note",
    "effective_date",
)


def canonical_text(value):
    """Mirror cnas-workbench ``str(value or '')`` exactly."""
    return str(value) if value else ""


def normalize_identity(laboratory, row):
    """Return the 7-element identity list that is hashed into the scope key."""
    return [
        canonical_text(laboratory),
        canonical_text(row.get("item_code")),
        canonical_text(row.get("standard_no") or row.get("standard")),
        canonical_text(row.get("test_object")),
        canonical_text(row.get("clause")),
        canonical_text(row.get("limit_note")),
        canonical_text(row.get("effective_date")),
    ]


def scope_key(laboratory, row):
    """Content hash of one capability row, scoped to a laboratory."""
    payload = json.dumps(normalize_identity(laboratory, row))
    return hashlib.sha256(payload.encode()).hexdigest()
