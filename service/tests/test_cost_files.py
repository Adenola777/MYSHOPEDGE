"""Every rule in app/cost_files.py, run on real CSV and real Excel bytes.

    python3 tests/test_cost_files.py

No database, credentials or network. The variants are the development branch's own codes,
queried on 24 September 2026, including one with no seller SKU.
"""

import io
import os
import sys
from uuid import UUID

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.cost_files import (  # noqa: E402
    CSV_TYPE, XLSX_TYPE, FileUnreadable, Variant, match, parse, read_amount, suggest_mapping,
)

DESK = Variant(UUID("1b126d84-efdf-c9ea-0182-cdcc0a6af22f"), "DESK-BLK", "1729100000000000004")
HAIR = Variant(UUID("3173cfe6-d825-9cb6-1979-f065a4741f33"), "HAIR-RED", "1729100000000000002")
NOSKU = Variant(UUID("f1be3e79-aab6-06fa-b53c-05d1367720bf"), None, "1729100000000000003")
VARIANTS = [DESK, HAIR, NOSKU]

failures = []


def check(name, fn):
    try:
        fn()
        print(f"  PASS  {name}")
    except Exception as exc:
        failures.append(name)
        print(f"  FAIL  {name}: {type(exc).__name__}: {exc}")


def eq(a, b):
    if a != b:
        raise AssertionError(f"{a!r} != {b!r}")


def raises(fn, kind=Exception):
    try:
        fn()
    except kind:
        return
    raise AssertionError("expected an exception")


CSV = (
    "﻿Seller SKU,Unit cost,Packing\r\n"
    "DESK-BLK,£51.00,1.20\r\n"
    "HAIR-RED,3.4,\r\n"
    "1729100000000000003,2.50,\r\n"
    "NOT-OURS,9.99,\r\n"
    "DESK-BLK,50.00,\r\n"
    "HAIR-RED,3.405,\r\n"
    ",1.00,\r\n"
).encode("utf-8")


def xlsx_bytes():
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.append(["TikTok SKU ID", "Cost price"])
    ws.append(["1729100000000000004", 3.4])       # a numeric cell, stored as a double
    ws.append([1729100000000000002, 3.4])         # a 19 digit id typed as a number
    ws.append(["1729100000000000003", 3.405])     # three decimals in a number cell
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


print("cost files")

check("amounts are read through Decimal into pence", lambda: (
    eq(read_amount("£51.00"), 5100), eq(read_amount("3.4"), 340),
    eq(read_amount("1,234.56"), 123456), eq(read_amount("0"), 0)))
check("an amount with three decimals, a negative or text is refused", lambda: (
    raises(lambda: read_amount("3.405"), ValueError), raises(lambda: read_amount("-1"), ValueError),
    raises(lambda: read_amount("about 3"), ValueError), raises(lambda: read_amount(""), ValueError)))


def csv_rules():
    p = parse(CSV, CSV_TYPE)
    eq(p.columns, ["Seller SKU", "Unit cost", "Packing"])
    m = suggest_mapping(p.columns)
    eq((m["match_on"], m["key_column"], m["cost_column"], m["packing_column"]),
       ("seller_sku", "Seller SKU", "Unit cost", "Packing"))
    out = match(p, m, VARIANTS)
    eq([o.outcome for o in out],
       ["matched", "matched", "matched", "unmatched", "duplicate", "unmatched", "unmatched"])
    eq((out[0].unit_cost_minor, out[0].packing_minor, out[0].matched_on), (5100, 120, "seller_sku"))
    eq(out[1].unit_cost_minor, 340)
    # No seller SKU on this variant, so the key falls back to TikTok's own id.
    eq((out[2].sku_id, out[2].matched_on), (NOSKU.sku_id, "tiktok_sku_id"))
    eq(out[3].sku_id, None)
    eq("row 2" in out[4].reason, True)
    eq("two decimal places" in out[5].reason, True)
    eq(out[6].reason, "The row has no SKU, so it cannot be matched.")
    eq(out[0].row_number, 2)
check("a CSV matches, refuses a stranger, flags a duplicate and falls back to TikTok's id", csv_rules)


def xlsx_rules():
    p = parse(xlsx_bytes(), XLSX_TYPE)
    m = suggest_mapping(p.columns)
    eq((m["match_on"], m["key_column"], m["cost_column"]), ("tiktok_sku_id", "TikTok SKU ID", "Cost price"))
    out = match(p, m, VARIANTS)
    eq((out[0].outcome, out[0].unit_cost_minor), ("matched", 340))
    # Excel cannot hold 19 digits, so the key is refused rather than matched to a neighbour.
    eq((out[1].outcome, out[1].sku_id), ("unmatched", None))
    eq("15 digits" in out[1].reason, True)
    # 3.405 is refused, not rounded to 341p.
    eq((out[2].outcome, out[2].unit_cost_minor), ("unmatched", None))
    eq("two decimal places" in out[2].reason, True)
check("an Excel file's numeric cells never pass through a float into a cost", xlsx_rules)


def seller_sku_only_when_asked():
    p = parse(b"SKU,Cost\n1729100000000000004,5.00\n", CSV_TYPE)
    out = match(p, {"match_on": "tiktok_sku_id", "key_column": "SKU", "cost_column": "Cost"}, VARIANTS)
    eq((out[0].outcome, out[0].matched_on), ("matched", "tiktok_sku_id"))
    out = match(p, {"match_on": "tiktok_sku_id", "key_column": "SKU", "cost_column": "Cost"},
                [Variant(DESK.sku_id, "1729100000000000004x", "other")])
    eq(out[0].outcome, "unmatched")
check("with match_on tiktok_sku_id, a seller SKU is never compared", seller_sku_only_when_asked)

check("a file with no heading, a repeated heading, or another type is refused", lambda: (
    raises(lambda: parse(b"SKU,\nA,1\n", CSV_TYPE), FileUnreadable),
    raises(lambda: parse(b"SKU,SKU\nA,1\n", CSV_TYPE), FileUnreadable),
    raises(lambda: parse(b"", CSV_TYPE), FileUnreadable),
    raises(lambda: parse(b"%PDF", "application/pdf"), FileUnreadable)))
check("no mapping is suggested when no heading names a cost", lambda: eq(
    suggest_mapping(["Code", "Price"]), None))
check("a mapping naming a missing column is refused", lambda: raises(
    lambda: match(parse(CSV, CSV_TYPE), {"match_on": "seller_sku", "key_column": "Code",
                                         "cost_column": "Unit cost"}, VARIANTS), FileUnreadable))

print()
if failures:
    print(f"{len(failures)} failure(s)")
    sys.exit(1)
print("every cost file rule held")
