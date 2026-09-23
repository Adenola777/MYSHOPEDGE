"""Measure our field maps against a real TikTok settlement, not a generated one.

A20 found that the generated fixtures are far thinner than reality. They carry seven fee
fields where TikTok sends fifty-seven, and one tax field where TikTok sends seventeen. So
the ingest can pass every assertion against its own fixtures while covering a fraction of
what a real shop returns, which is the failure this project has already been bitten by
twice.

This script reads the real payload in testdata/real_payloads and reports coverage. It
imports the maps from ingest.py rather than restating them, so it cannot drift.

    python3 testdata/check_maps_against_real.py

It prints counts and exits 0. It is a measurement, not a gate, because an unmapped fee is
the designed behaviour under A8: the value is carried in full and TikTok's own field name
is kept in tiktok_fee_type. A tax field with no entry in TAX_MAP used to be discarded
silently, and this script is how that stays visible.
"""

import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

REAL = os.path.join(HERE, "real_payloads", "statement_transactions_202501.json")

# Imported rather than copied, so this cannot fall out of step with the ingest.
import contextlib, io, importlib.util
spec = importlib.util.spec_from_file_location("ingest_maps", os.path.join(HERE, "ingest.py"))
mod = importlib.util.module_from_spec(spec)
try:
    # The ingest prints its row counts on import. Swallowed here so this script's own
    # output is the only thing on stdout.
    with contextlib.redirect_stdout(io.StringIO()):
        spec.loader.exec_module(mod)
except Exception:
    # The ingest runs at import and needs its fixtures. The maps are defined before that
    # work begins, so a partially executed module still carries them.
    pass

FEE_MAP, SHIP_MAP, TAX_MAP = mod.FEE_MAP, mod.SHIP_MAP, mod.TAX_MAP

d = json.load(open(REAL))["data"]
t = d["transactions"][0]

groups = [
    ("fee", set(t["fee_tax_breakdown"]["fee"]), FEE_MAP, "carried as unmapped_fee"),
    ("tax", set(t["fee_tax_breakdown"]["tax"]), TAX_MAP, "recorded in UNMAPPED since A20"),
    ("shipping", set(t["shipping_cost_breakdown"]), SHIP_MAP, "carried as unmapped_fee"),
]

print(f"real payload: statement {d['id']}, {d['currency']}, {d['total_count']} transactions\n")
print(f"{'group':10} {'TikTok sends':>12} {'we map':>8} {'unmapped':>9}   disposition")
for name, fields, mapping, disposition in groups:
    known = fields & set(mapping)
    print(f"{name:10} {len(fields):>12} {len(known):>8} {len(fields - known):>9}   {disposition}")

unknown_tax = sorted(set(t["fee_tax_breakdown"]["tax"]) - set(TAX_MAP))
print(f"\ntax fields with no entry in TAX_MAP ({len(unknown_tax)}):")
for f in unknown_tax:
    print(f"   {f}")

print("\nThese are all zero in this Indonesian payload. A16 and A20.7 both record that the")
print("mapping decision waits for a payload from the GB shop, because fee and tax fields")
print("vary by region and most of the taxes above are not UK taxes.")
