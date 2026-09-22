#!/usr/bin/env python3
"""Patch openapi.yaml for the contract pass of 22 September 2026."""
import re, sys, yaml

P = "/home/claude/mse/v02/api/openapi.yaml"
src = open(P).read()
orig = src

# ---------------------------------------------------------------- 1. enum drift
old_cat = """      enum:
      - gross_sales
      - seller_discount
      - refund
      - platform_commission
      - affiliate_commission
      - transaction_fee
      - smart_promotions_fee
      - shipping_fee
      - return_handling_fee
      - fbt_operations_fee
      - fbt_shipping_fee
      - fbt_storage_fee
      - unmapped_fee
"""
new_cat = """      enum:
      - gross_sales
      - seller_discount
      - refund
      - platform_commission
      - affiliate_commission
      - transaction_fee
      - smart_promotions_fee
      - shipping_fee
      - return_handling_fee
      - fbt_operations_fee
      - fbt_shipping_fee
      - fbt_storage_fee
      - platform_adjustment
      - unmapped_fee
      - reserve_withheld
      - reserve_released
"""
assert src.count(old_cat) == 1, f"LedgerCategory enum anchor matched {src.count(old_cat)} times"
src = src.replace(old_cat, new_cat)

# The description still says eighteen and now understates the mapping rule.
src = src.replace(
    "      description: 'The eighteen categories in `ledger_entries.category`. `unmapped_fee` carries a fee",
    "      description: 'The twenty-one categories in `ledger_entries.category`. `platform_adjustment`\n\n        carries one of TikTok''s twenty-one documented statement adjustment types, with its\n\n        verbatim type in `tiktok_fee_type`, because a seller must be able to reconcile\n\n        against TikTok''s own screen. `unmapped_fee` carries a fee",
    1,
)

# --------------------------------------------------- 2. the accountant feed goes
before = len(re.findall(r"^\s+- accountant$", src, re.M))
assert before == 2, f"expected two accountant enum members, found {before}"
src = re.sub(r"^\s+- accountant\n", "", src, flags=re.M)
assert len(re.findall(r"^\s+- accountant$", src, re.M)) == 0

# ------------------------------------------------------- 3. /records cannot filter
old_rec = """          - write_off
          - adjustment
      - name: sku_id
        in: query
        schema:
          type: string
          format: uuid
      - name: order_id
        in: query
        schema:
          type: string
          format: uuid
"""
new_rec = """          - write_off
          - adjustment
          - reserve
      - name: sku_id
        in: query
        schema:
          type: string
          format: uuid
      - name: product_id
        in: query
        description: Every entry for a product, across all of its variants.
        schema:
          type: string
          format: uuid
      - name: order_id
        in: query
        schema:
          type: string
          format: uuid
      - name: return_id
        in: query
        description: The entries a return produced, its refund and its costs together.
        schema:
          type: string
          format: uuid
      - name: settlement_id
        in: query
        description: The entries behind one statement, which is what the payout screen links to.
        schema:
          type: string
          format: uuid
"""
assert src.count(old_rec) == 1, f"/records param anchor matched {src.count(old_rec)} times"
src = src.replace(old_rec, new_rec)

# ------------------------------------------------------------------ 4. new paths
NEW_PATHS = open("/tmp/claude-0/new_paths.yaml").read()
assert src.count("\ncomponents:\n") == 1
src = src.replace("\ncomponents:\n", "\n" + NEW_PATHS + "components:\n", 1)

# ------------------------------- 4b. the cost-uploads index joins the existing path
# /shops/{shopId}/cost-uploads already exists with a post. Adding a second block with
# the same key produces a duplicate mapping key, which PyYAML silently resolves by
# keeping the last one and which the OpenAPI parser rejects outright.
GET_OP = open("/tmp/claude-0/cost_uploads_get.yaml").read()
anchor = "  /shops/{shopId}/cost-uploads:\n    post:\n"
assert src.count(anchor) == 1, "cost-uploads anchor not unique"
src = src.replace(anchor, "  /shops/{shopId}/cost-uploads:\n" + GET_OP + "    post:\n", 1)

# ---------------------------------------------------------------- 5. new schemas
NEW_SCHEMAS = open("/tmp/claude-0/new_schemas.yaml").read()
assert src.count("\n  schemas:\n") == 1
src = src.replace("\n  schemas:\n", "\n  schemas:\n" + NEW_SCHEMAS, 1)

# ------------------------------------------------------------ 6. coverage note
src = src.replace(
    "    Coverage: 47 of the 50",
    "    Coverage: 58 of the 59",
)
src = src.replace(
    "endpoints in the catalogue. The three not present are the\\n    TikTok webhook receiver, which needs\\\n    \\ a subscription design, and the two cost upload\\n    endpoints that perform SKU matching, which need\\\n    \\ a ruling on an empty seller SKU.",
    "endpoints in the catalogue. The one not present is the\\n    TikTok webhook receiver, which needs\\\n    \\ a subscription design and is deferred.",
)

open(P, "w").write(src)

# ------------------------------------------------------------------- validate
doc = yaml.safe_load(open(P))
paths = doc["paths"]
ops = sum(1 for p in paths.values() for m in p if m in
          ("get", "post", "put", "patch", "delete"))
schemas = doc["components"]["schemas"]
refs = set(re.findall(r"#/components/schemas/([A-Za-z0-9_]+)", open(P).read()))
missing = sorted(r for r in refs if r not in schemas)
print(f"paths {len(paths)}  operations {ops}  schemas {len(schemas)}")
print("LedgerCategory:", len(schemas["LedgerCategory"]["enum"]), "values")
if missing:
    print("MISSING SCHEMA REFS:", missing)
    sys.exit(1)
print("every $ref resolves")
