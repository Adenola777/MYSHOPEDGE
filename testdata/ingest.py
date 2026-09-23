"""Ingest the synthetic TikTok payloads into MyShopEdge schema rows, and emit SQL.

This is deliberately independent of the generator. It reads TikTok's field names
and derives every MyShopEdge figure itself. Nothing is copied across from the
generator's own totals, so the reconciliation assertions test this mapping rather
than the generator's arithmetic.

Rules enforced here, each traceable to a finding:
  SYN-7   buyer_email and recipient_address are dropped before anything is written.
  A11.2   supplementary_component is never summed. It explains its parents.
  A11.2   a fee with no category becomes unmapped_fee, keeping TikTok's field name.
  A11.1   basis_day and basis_month are Europe/London, not UTC.
  0004    a deduction is split across order lines by largest remainder, no residual.
"""
import json, os, uuid, hashlib
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

HERE = os.path.dirname(__file__)
P = os.path.join(HERE, "payloads")
LONDON = ZoneInfo("Europe/London")

def load(n): return json.load(open(os.path.join(P, n)))

# A20.3. This function multiplied by 100 whatever the currency, which is wrong in
# principle and stayed invisible because the product is GBP only. The real settlement in
# testdata/real_payloads is IDR with whole-number amounts, which is what exposed it.
#
# GBP is the only entry, and it is the only one verified against a real payload. An
# unverified currency raises rather than guessing, because a wrong power of ten does not
# fail loudly, it produces plausible numbers that are off by a factor of a hundred.
MINOR_UNIT_EXPONENT = {"GBP": 2}

def pence(s, currency="GBP"):
    if currency not in MINOR_UNIT_EXPONENT:
        raise ValueError(
            f"No verified minor unit for {currency}. Add it to MINOR_UNIT_EXPONENT only "
            f"after reading a real payload in that currency."
        )
    if s in (None, ""):
        return 0
    return int(round(float(s) * 10 ** MINOR_UNIT_EXPONENT[currency]))

def uid(*parts):
    return str(uuid.UUID(hashlib.sha1(":".join(map(str, parts)).encode()).hexdigest()[:32]))

def london(epoch):
    return datetime.fromtimestamp(epoch, tz=timezone.utc).astimezone(LONDON)

# --------------------------------------------- TikTok field -> ledger category
FEE_MAP = {
    "platform_commission_amount":        "platform_commission",
    "affiliate_commission_amount":       "affiliate_commission",
    "affiliate_ads_commission_amount":   "affiliate_commission",
    "affiliate_partner_commission_amount": "affiliate_commission",
    "transaction_fee_amount":            "transaction_fee",
    "refund_administration_fee_amount":  "return_handling_fee",
    "cofunded_promotion_service_fee_amount": "smart_promotions_fee",
}
SHIP_MAP = {
    "actual_shipping_fee_amount":   "shipping_fee",
    "customer_paid_shipping_fee_amount": "shipping_fee",
    "shipping_fee_discount_amount": "shipping_fee",
    "fbt_free_shipping_fee_amount": "fbt_shipping_fee",
    "return_shipping_fee_amount":   "return_shipping",
}
TAX_MAP = {"local_vat_amount": None}   # UK VAT is not a MyShopEdge deduction category

ENTRY_TYPE = {
    "gross_sales": "sale", "seller_discount": "sale", "refund": "refund",
    "platform_commission": "platform_deduction", "affiliate_commission": "platform_deduction",
    "transaction_fee": "platform_deduction", "smart_promotions_fee": "platform_deduction",
    "shipping_fee": "platform_deduction", "return_handling_fee": "platform_deduction",
    "fbt_operations_fee": "platform_deduction", "fbt_shipping_fee": "platform_deduction",
    "fbt_storage_fee": "platform_deduction", "unmapped_fee": "platform_deduction",
    "return_shipping": "return_cost", "stock_written_off": "write_off",
    "cost_of_goods_sold": "adjustment",   # FINDING: entry_type has no value for a seller cost
    "seller_shipping": "adjustment",
    "platform_adjustment": "adjustment",
    "reserve_withheld": "reserve", "reserve_released": "reserve",
    "settlement": "payout",
}

def allocate(total, weights):
    """Largest remainder. Sums to total exactly, no residual pence."""
    if not weights or sum(weights) == 0:
        return [total] + [0] * (len(weights) - 1)
    tw = sum(weights)
    base = [total * w // tw for w in weights]
    rem = total - sum(base)
    order = sorted(range(len(weights)), key=lambda i: -((total * weights[i]) % tw))
    step = 1 if rem > 0 else -1
    for k in range(abs(rem)):
        base[order[k % len(order)]] += step
    return base

# ------------------------------------------------------------------ load
shop = load("authorization_shops.json")["data"]["shops"][0]
orders_raw = load("orders.json")["data"]["orders"]
tx = load("order_statement_transactions.json")
statements = load("statements.json")["data"]["statements"]
stmt_map = load("statement_order_map.json")
stmt_txns = load("statement_transactions.json")
returns_raw = load("returns.json")["data"]["return_orders"]
inventory = load("inventory.json")["data"]["inventory"]
CATALOGUE = load("catalogue.json")
COST = {s[0]: s[5] for s in CATALOGUE["skus"]}

ACCOUNT = uid("account", shop["id"])
SHOP = uid("shop", shop["id"])

rows = {k: [] for k in (
    "accounts","shops","tiktok_connections","products","skus","orders","order_lines",
    "settlements","order_settlements","returns","return_items","ledger_entries",
    "stock_positions","stock_movements","product_costs","cost_uploads","discrepancies",
    "notifications","alert_settings","tax_profiles","other_channel_sales","reference_rules",
    "raw_events","sync_runs","exports","export_schedules","feed_tokens","daily_metrics",
    "tiktok_invoices","change_log","audit_log","product_events")}

rows["accounts"].append(dict(id=ACCOUNT, email="owner@synthetic-uk-shop.test",
    auth_subject="stack|synthetic-uk-shop", display_name="Synthetic UK Shop Ltd",
    locale="en-GB", timezone="Europe/London", status="active"))
rows["shops"].append(dict(id=SHOP, account_id=ACCOUNT, platform="tiktok_shop",
    tiktok_shop_id=shop["id"], shop_name=shop["name"], region=shop["region"],
    currency="GBP", connection_status="connected"))
rows["tiktok_connections"].append(dict(shop_id=SHOP, key_version=1,
    scopes="{seller.finance.info,seller.order.info}"))

for pid, name in CATALOGUE["products"]:
    rows["products"].append(dict(id=uid("product", pid), shop_id=SHOP,
        tiktok_product_id=pid, title=name, status="ACTIVATE"))
for sid, pid, label, seller_sku, price, cost in CATALOGUE["skus"]:
    rows["skus"].append(dict(id=uid("sku", sid), shop_id=SHOP, product_id=uid("product", pid),
        tiktok_sku_id=sid, seller_sku=seller_sku or None, variant_label=label))
    rows["product_costs"].append(dict(id=uid("cost", sid), shop_id=SHOP, sku_id=uid("sku", sid),
        cost_minor=cost, currency="GBP", source="upload", effective_from="2026-07-01"))

# --------------------------------------------------------------- orders
ORDER_BY_TT, LINES_BY_ORDER = {}, {}
for o in orders_raw:
    oid = uid("order", o["id"])
    ORDER_BY_TT[o["id"]] = oid
    dt = london(o["create_time"])
    gross = pence(o["payment"]["original_total_product_price"])
    rows["orders"].append(dict(id=oid, shop_id=SHOP, tiktok_order_id=o["id"],
        status=o["status"], order_created_at=datetime.fromtimestamp(o["create_time"], timezone.utc).isoformat(),
        currency="GBP", gross_minor=gross, sales_channel="tiktok_shop"))
    # buyer_email and recipient_address are deliberately not carried. SYN-7.
    ls = []
    for l in o["line_items"]:
        lid = uid("line", l["id"])
        ls.append(dict(id=lid, shop_id=SHOP, order_id=oid, sku_id=uid("sku", l["sku_id"]),
            tiktok_line_id=l["id"], quantity=1, unit_price_minor=pence(l["sale_price"]),
            seller_discount_minor=0, _sku=l["sku_id"]))
    rows["order_lines"].extend([{k: v for k, v in d.items() if not k.startswith("_")} for d in ls])
    LINES_BY_ORDER[o["id"]] = ls

# --------------------------------------------------------- ledger entries
# A return's money must carry the return. Without this link,
# return_reconciliation.refund_posted_minor and return_cost_minor read zero on
# every row, because the entries are posted against the order and the statement
# only. Built here because the ledger loop runs before the returns loop.
RETURN_BY_ORDER = {r["order_id"]: uid("return", r["return_id"]) for r in returns_raw}
RETURN_CATEGORIES = {"refund", "return_shipping", "return_handling_fee"}

UNMAPPED = set()
def post(order_tt, category, amount, occurred, line=None, fee_type=None, source="tiktok", ref=None, return_id=None):
    if amount == 0 and category != "settlement":
        return
    dt = london(occurred)
    rows["ledger_entries"].append(dict(
        id=uid("led", order_tt or "", category, line["id"] if line else "", ref or "", str(amount)),
        shop_id=SHOP, order_id=ORDER_BY_TT.get(order_tt), return_id=return_id,
        entry_type=ENTRY_TYPE[category], category=category, amount_minor=amount, currency="GBP",
        occurred_at=datetime.fromtimestamp(occurred, timezone.utc).isoformat(),
        basis_month=dt.replace(day=1).date().isoformat(),
        # Null until the entry is attached to a settlement. This is the cash basis, and
        # leaving it null is what made every cash-basis screen return nothing.
        settlement_month=None,
        source=source, source_ref=ref, tiktok_fee_type=fee_type,
        order_line_id=line["id"] if line else None,
        sku_id=line["sku_id"] if line else None,
        attribution=("allocated" if line and line.get("_alloc") else "direct") if line else "none"))

for o in orders_raw:
    data = tx[o["id"]]["data"]
    when = o["create_time"]
    for t in data["sku_transactions"]:
        lines = [l for l in LINES_BY_ORDER[o["id"]] if l["_sku"] == t["sku_id"]]
        n = len(lines)
        for l in lines:
            l["_alloc"] = n > 1
        w = [1] * n

        def spread(cat, total, fee_type=None):
            rid = RETURN_BY_ORDER.get(o["id"]) if cat in RETURN_CATEGORIES else None
            for l, a in zip(lines, allocate(total, w)):
                post(o["id"], cat, a, when, line=l, fee_type=fee_type,
                     ref=f'{data["order_id"]}:{t["sku_id"]}:{cat}', return_id=rid)

        rb = t["revenue_breakdown"]
        spread("gross_sales", pence(rb["subtotal_before_discount_amount"]))
        spread("seller_discount", pence(rb["seller_discount_amount"]))
        spread("refund", pence(rb["refund_subtotal_before_discount_amount"]))
        for field, amt in t["fee_tax_breakdown"]["fee"].items():
            cat = FEE_MAP.get(field)
            if cat is None:
                UNMAPPED.add(field); cat = "unmapped_fee"
            spread(cat, pence(amt), fee_type=field)
        for field, amt in t["fee_tax_breakdown"]["tax"].items():
            # A19.5 and A20.3. This loop used to discard every field absent from TAX_MAP
            # without recording it, while the fee loop above records its unknowns. The real
            # payload carries seventeen tax fields and TAX_MAP holds one, so sixteen were
            # leaving no trace, `vat_amount` and `import_vat_amount` among them. Recording
            # them costs nothing and makes a future non-zero tax visible instead of silent.
            if field not in TAX_MAP:
                UNMAPPED.add(field)
                continue
            if TAX_MAP[field] and pence(amt):
                spread(TAX_MAP[field], pence(amt), fee_type=field)
        for field, amt in t["shipping_cost_breakdown"].items():
            if field == "supplementary_component":
                continue                       # explains its parents, never summed
            cat = SHIP_MAP.get(field)
            if cat is None:
                UNMAPPED.add(field); cat = "unmapped_fee"
            spread(cat, pence(amt), fee_type=field)
        # Cost of goods sold, from the seller's own cost file.
        spread("cost_of_goods_sold", -COST[t["sku_id"]] * n)

# ------------------------------------------------- settlements and payouts
for s in statements:
    sid = uid("settlement", s["id"])
    st = s["statement_time"]
    sth = stmt_txns[s["id"]]["data"]
    rows["settlements"].append(dict(id=sid, shop_id=SHOP, tiktok_statement_id=s["id"],
        statement_amount_minor=pence(s["settlement_amount"]), currency="GBP",
        payment_status=s["payment_status"], tiktok_payment_id=s["payment_id"],
        paid_at=datetime.fromtimestamp(s["payment_time"], timezone.utc).isoformat() if s["payment_time"] else None,
        statement_time=datetime.fromtimestamp(st, timezone.utc).isoformat(),
        net_sales_minor=pence(s["net_sales_amount"]), fee_minor=pence(s["fee_amount"]),
        shipping_cost_minor=pence(s["shipping_cost_amount"]),
        adjustment_minor=pence(s["adjustment_amount"]),
        revenue_minor=None,
        # Verified 22 September 2026: payable_amount and total_reserve_amount are
        # returned only by the per-statement transactions call, never by the
        # statements list. payable_amount is what reaches the seller's bank.
        payable_amount_minor=pence(sth["payable_amount"]),
        total_reserve_amount_minor=pence(sth["total_reserve_amount"])))
    # Attach every ledger entry of the orders in this statement, then post the payout
    # as the negative of what those entries came to. unexplained_minor is then a real
    # comparison between TikTok's stated total and our derived one.
    derived = 0
    # The month the money settled, in Europe/London, from the statement's own time. The
    # sales basis asks when the sale happened; the cash basis asks when it was paid, and
    # they are different months for anything settled near a month end.
    smonth = london(st).replace(day=1).date().isoformat()
    for tt in stmt_map[s["id"]]:
        for e in rows["ledger_entries"]:
            if e["order_id"] == ORDER_BY_TT[tt] and e["category"] != "cost_of_goods_sold":
                e["settlement_id"] = sid
                e["settlement_month"] = smonth
                derived += e["amount_minor"]
        rows["order_settlements"].append(dict(order_id=ORDER_BY_TT[tt], shop_id=SHOP,
            status="settled", settlement_id=sid))
    # Adjustments and reserves come from the per-statement transactions call.
    # An adjustment is a documented type, not an unrecognised field, so it takes
    # the platform_adjustment category and keeps TikTok's own type name. Where
    # TikTok names an order, that order ID is recorded: TikTok's identifier
    # overrides anything this product would infer.
    for t in sth["transactions"]:
        if t["type"] == "ORDER":
            continue
        if t["type"] == "RESERVE":
            amt = pence(t["reserve_amount"])
            post(None, "reserve_withheld" if amt < 0 else "reserve_released", amt, st,
                 fee_type="reserve_amount", ref=t["reserve_id"])
            e = rows["ledger_entries"][-1]
            e["settlement_id"] = sid
            e["settlement_month"] = smonth
            e["order_id"] = ORDER_BY_TT.get(t["associated_order_id"])
            continue
        amt = pence(t["adjustment_amount"])
        post(None, "platform_adjustment", amt, st, fee_type=t["type"], ref=t["adjustment_id"])
        e = rows["ledger_entries"][-1]
        e["settlement_id"] = sid
        e["settlement_month"] = smonth
        e["order_id"] = ORDER_BY_TT.get(t["adjustment_order_id"])
        derived += amt
        rows["discrepancies"].append(dict(id=uid("disc", t["adjustment_id"]), shop_id=SHOP,
            kind="amount", entity_type="settlement", entity_id=sid, field="adjustment_amount",
            tiktok_value=t["adjustment_amount"], seller_value=None,
            applied_value=t["adjustment_amount"], status="open",
            note=f'TikTok recorded this as {t["type"]} and gave no further reason'))
    post(None, "settlement", -derived, st, ref=s["id"])
    rows["ledger_entries"][-1]["settlement_id"] = sid
    rows["ledger_entries"][-1]["settlement_month"] = smonth

for o in orders_raw:
    if o["_flags"].get("unsettled"):
        rows["order_settlements"].append(dict(order_id=ORDER_BY_TT[o["id"]], shop_id=SHOP,
            status=o["_flags"]["unsettled"], settlement_id=None,
            est_settlement_date=london(o["create_time"] + 14 * 86400).date().isoformat()))

# ------------------------------------------------------ returns and stock
for r in returns_raw:
    rid = uid("return", r["return_id"])
    kind = r["return_type"].lower()
    rows["returns"].append(dict(id=rid, shop_id=SHOP, order_id=ORDER_BY_TT[r["order_id"]],
        tiktok_return_id=r["return_id"], kind=kind, status=r["return_status"],
        requested_at=datetime.fromtimestamp(r["create_time"], timezone.utc).isoformat(),
        refund_completed_at=datetime.fromtimestamp(r["update_time"], timezone.utc).isoformat(),
        refund_minor=-pence(r["refund_amount"]["refund_total"]), reason_code=r["return_reason_text"],
        tiktok_credit_note_number=r["credit_note_number"]))
    for sk in r["_skus"]:
        iid = uid("ritem", r["return_id"], sk)
        check = "not_applicable" if kind in ("cancellation", "refund_only") else (
                "unsellable" if r["_damaged"] else "resellable")
        rows["return_items"].append(dict(id=iid, shop_id=SHOP, return_id=rid,
            sku_id=uid("sku", sk), quantity=1, seller_check_status=check,
            checked_at=datetime.fromtimestamp(r["update_time"], timezone.utc).isoformat()
                       if check != "not_applicable" else None))
        # REC-2: a refund with no goods back moves no stock. A resellable return
        # moves once. A cancellation before dispatch returns the stock, because
        # the goods never left. Ruled 22 September 2026.
        if kind == "cancellation":
            rows["stock_movements"].append(dict(id=uid("sm", iid), shop_id=SHOP, sku_id=uid("sku", sk),
                movement_type="cancelled", quantity=1, return_id=rid, return_item_id=iid,
                occurred_at=datetime.fromtimestamp(r["update_time"], timezone.utc).isoformat()))
        elif check == "resellable":
            rows["stock_movements"].append(dict(id=uid("sm", iid), shop_id=SHOP, sku_id=uid("sku", sk),
                movement_type="return_resellable", quantity=1, return_id=rid, return_item_id=iid,
                occurred_at=datetime.fromtimestamp(r["update_time"], timezone.utc).isoformat()))
        elif check == "unsellable":
            rows["stock_movements"].append(dict(id=uid("sm", iid), shop_id=SHOP, sku_id=uid("sku", sk),
                movement_type="write_off", quantity=1, return_id=rid, return_item_id=iid,
                occurred_at=datetime.fromtimestamp(r["update_time"], timezone.utc).isoformat()))
            post(r["order_id"], "stock_written_off", -COST[sk], r["update_time"],
                 line=LINES_BY_ORDER[r["order_id"]][0], ref=r["return_id"] + ":writeoff",
                 return_id=rid)

for inv in inventory:
    rows["stock_positions"].append(dict(sku_id=uid("sku", inv["sku_id"]), shop_id=SHOP,
        tiktok_stock=inv["quantity"], adjusted_delta=0))
# A manual adjustment, and an absorption within tolerance.
rows["stock_movements"].append(dict(id=uid("sm","manual"), shop_id=SHOP,
    sku_id=uid("sku", CATALOGUE["skus"][0][0]), movement_type="manual_adjustment", quantity=-2,
    reason="Damaged in storage, counted out", occurred_at="2026-08-25T09:00:00+00:00"))
rows["stock_movements"].append(dict(id=uid("sm","absorb"), shop_id=SHOP,
    sku_id=uid("sku", CATALOGUE["skus"][1][0]), movement_type="adjustment_absorbed", quantity=1,
    reason="Unexplained rise in TikTok stock, within tolerance",
    occurred_at="2026-08-26T09:00:00+00:00"))
rows["stock_movements"].append(dict(id=uid("sm","sale_res"), shop_id=SHOP,
    sku_id=uid("sku", CATALOGUE["skus"][0][0]), movement_type="sale_reserved", quantity=-1,
    occurred_at="2026-08-01T12:00:00+00:00"))
rows["stock_movements"].append(dict(id=uid("sm","posted"), shop_id=SHOP,
    sku_id=uid("sku", CATALOGUE["skus"][0][0]), movement_type="posted", quantity=-1,
    occurred_at="2026-08-02T12:00:00+00:00"))
rows["stock_movements"].append(dict(id=uid("sm","cancel"), shop_id=SHOP,
    sku_id=uid("sku", CATALOGUE["skus"][0][0]), movement_type="cancelled", quantity=1,
    occurred_at="2026-08-13T12:00:00+00:00"))

print(json.dumps({k: len(v) for k, v in rows.items() if v}, indent=0))
print("unmapped TikTok fields seen:", sorted(UNMAPPED))
json.dump(rows, open(os.path.join(HERE, "rows.json"), "w"), indent=1)
