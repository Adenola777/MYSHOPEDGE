"""Generate synthetic TikTok Shop API payloads for a GB LOCAL seller.

This produces what TikTok would return, in TikTok's own field names and nesting.
It does NOT produce MyShopEdge schema rows. The ingester derives those, so the
assertions test the mapping rather than this generator's arithmetic.

Two rules this file obeys, both taken from observed TikTok behaviour:
  1. One line item per unit. Three units is three line items, not a quantity of 3.
  2. A GB LOCAL seller gets net_sales_amount and shipping_cost_amount.
     revenue_amount is null for UK and US sellers.
"""
import json, os, hashlib
from datetime import datetime, timezone, timedelta

OUT = os.path.join(os.path.dirname(__file__), "payloads")
os.makedirs(OUT, exist_ok=True)

SHOP_ID = "7495000000000000001"
SHOP_CIPHER = "GBP_SyntheticCipherAAAAAAAAAAAAAA"
SHOP_CODE = "GBSYNTH0001"

def p(pence):
    """TikTok returns amounts as strings with two decimals."""
    return f"{pence/100:.2f}"

def ts(iso):
    return int(datetime.fromisoformat(iso).replace(tzinfo=timezone.utc).timestamp())

# ---------------------------------------------------------------- catalogue
PRODUCTS = [
    ("1729000000000000001", "Double Use Curly Hair Brush"),
    ("1729000000000000002", "Computer Desk 120cm"),
    ("1729000000000000003", "Vacuum Food Flask 500ml"),
    ("1729000000000000004", "Travel Duffel Bag"),
    ("1729000000000000005", "LED Desk Lamp"),
    ("1729000000000000006", "Seasonal Gift Box"),
]
# sku_id, product_id, sku_name, seller_sku, price_pence, cost_pence
SKUS = [
    ("1729100000000000001", PRODUCTS[0][0], "Blue",    "HAIR-BLUE",  2000,  324),
    ("1729100000000000002", PRODUCTS[0][0], "Red",     "HAIR-RED",   2000,  324),
    ("1729100000000000003", PRODUCTS[0][0], "Green",   "",           2000,  324),  # blank seller_sku
    ("1729100000000000004", PRODUCTS[1][0], "Black",   "DESK-BLK",  12000, 5100),
    ("1729100000000000005", PRODUCTS[1][0], "Oak",     "",          12000, 5100),  # blank seller_sku
    ("1729100000000000006", PRODUCTS[2][0], "Default", "FLASK-DEF",  1800,  500),
    ("1729100000000000007", PRODUCTS[3][0], "Black",   "BAG-BLK",    3500, 1450),
    ("1729100000000000008", PRODUCTS[3][0], "Brown",   "BAG-BRN",    3500, 1450),
    ("1729100000000000009", PRODUCTS[4][0], "White",   "LAMP-WHT",   2400,  780),
    ("1729100000000000010", PRODUCTS[5][0], "Default", "GIFT-DEF",   4000, 1700),
]
SKU = {s[0]: s for s in SKUS}
PRODUCT_NAME = {p_[0]: p_[1] for p_ in PRODUCTS}

# ------------------------------------------------------- order definitions
# (ref, created_utc, [(sku_id, units)], flags)
# flags drive which fee fields TikTok returns.
ORDERS = [
    ("A01", "2026-08-01T12:00:00", [(SKUS[0][0], 1)], {}),
    ("A02", "2026-08-02T12:00:00", [(SKUS[0][0], 3)], {}),                      # three units, three line items
    ("A03", "2026-08-03T12:00:00", [(SKUS[0][0], 1), (SKUS[3][0], 1)], {}),     # two SKUs, allocation
    ("A04", "2026-08-04T12:00:00", [(SKUS[5][0], 2)], {"seller_discount": 500}),
    ("A05", "2026-08-05T12:00:00", [(SKUS[6][0], 1)], {"affiliate": True}),
    ("A06", "2026-08-06T12:00:00", [(SKUS[8][0], 1)], {"affiliate_ads": True}),
    ("A07", "2026-08-07T12:00:00", [(SKUS[1][0], 1)], {"unsettled": "waiting_delivery"}),
    ("A08", "2026-08-08T12:00:00", [(SKUS[2][0], 1)], {"unsettled": "delivered_awaiting_settlement"}),
    ("A09", "2026-08-09T12:00:00", [(SKUS[7][0], 1)], {"promo": True}),
    # BST boundary: 23:30 UTC on 31 July is 00:30 on 1 August in London.
    ("A10", "2026-07-31T23:30:00", [(SKUS[0][0], 1)], {}),
    # Just inside 31 July London.
    ("A11", "2026-07-31T21:30:00", [(SKUS[3][0], 1)], {}),
    ("A12", "2026-08-12T12:00:00", [(SKUS[9][0], 1)], {"fbt": True}),
    ("A13", "2026-08-13T12:00:00", [(SKUS[0][0], 1)], {"cancelled": True}),
    ("A14", "2026-08-14T12:00:00", [(SKUS[1][0], 1)], {"refund_only": True}),
    ("A15", "2026-08-15T12:00:00", [(SKUS[2][0], 1)], {"return_resellable": True}),
    ("A16", "2026-08-16T12:00:00", [(SKUS[3][0], 1)], {"return_damaged": True}),
    ("A17", "2026-08-17T12:00:00", [(SKUS[6][0], 1)], {"return_resellable": True, "return_postage": 450}),
    ("A18", "2026-08-18T12:00:00", [(SKUS[7][0], 1)], {"return_resellable": True, "return_handling": 325}),
    ("A19", "2026-08-19T12:00:00", [(SKUS[8][0], 1)], {"return_resellable": True, "credit_note": True}),
    # Carries a fee MyShopEdge has no category for.
    ("A20", "2026-08-20T12:00:00", [(SKUS[5][0], 1)], {"mystery_fee": 199}),
]

def order_id(ref):
    return "5767" + hashlib.sha1(ref.encode()).hexdigest()[:14].upper()

def line_id(ref, i):
    return "5768" + hashlib.sha1(f"{ref}:{i}".encode()).hexdigest()[:14].upper()

COMMISSION_BP, TXN_BP = 600, 150   # 6.00% and 1.50%, applied to the discounted subtotal

def build_order(ref, created, items, flags):
    oid, lines, seq = order_id(ref), [], 0
    for sku_id, units in items:
        s = SKU[sku_id]
        for _ in range(units):                       # one line item per unit
            seq += 1
            lines.append({
                "id": line_id(ref, seq), "sku_id": sku_id, "product_id": s[1],
                "product_name": PRODUCT_NAME[s[1]], "sku_name": s[2],
                "seller_sku": s[3], "sku_type": "NORMAL", "currency": "GBP",
                "original_price": p(s[4]), "sale_price": p(s[4]),
                "platform_discount": "0.00", "seller_discount": "0.00",
                "display_status": "CANCELLED" if flags.get("cancelled") else "DELIVERED",
                "is_gift": False,
            })
    subtotal = sum(SKU[l["sku_id"]][4] for l in lines)
    disc = flags.get("seller_discount", 0)
    return {
        "id": oid, "create_time": ts(created), "update_time": ts(created) + 86400,
        "status": "CANCELLED" if flags.get("cancelled") else "COMPLETED",
        "commerce_platform": "TIKTOK_SHOP", "fulfillment_type": "FULFILLMENT_BY_TIKTOK" if flags.get("fbt") else "FULFILLMENT_BY_SELLER",
        "is_cod": False, "order_type": "NORMAL", "line_items": lines,
        "payment": {"currency": "GBP", "original_total_product_price": p(subtotal),
                    "sub_total": p(subtotal - disc), "seller_discount": p(disc),
                    "platform_discount": "0.00", "shipping_fee": "0.00", "tax": "0.00",
                    "total_amount": p(subtotal - disc)},
        # Buyer personal data TikTok sends whether we want it or not. SYN-7 drops it.
        "buyer_email": f"{hashlib.sha1(ref.encode()).hexdigest()[:29].upper()}@scs2.tiktok.com",
        "recipient_address": {"name": "", "phone_number": "", "full_address": "", "postal_code": "", "region_code": "GB"},
        "_ref": ref, "_flags": flags, "_subtotal": subtotal, "_discount": disc,
    }

orders = [build_order(*o) for o in ORDERS]

# --------------------------------------- finance: per-order SKU transactions
def statement_transactions(o):
    """GET /finance/202501/orders/{order_id}/statement_transactions"""
    f, by_sku = o["_flags"], {}
    for l in o["line_items"]:
        by_sku.setdefault(l["sku_id"], []).append(l)
    disc_left, sku_tx = o["_discount"], []
    for sku_id, ls in by_sku.items():
        gross = sum(SKU[sku_id][4] for _ in ls)
        disc = min(disc_left, gross); disc_left -= disc
        net = gross - disc
        fee = {}
        fee["platform_commission_amount"] = p(-(net * COMMISSION_BP // 10000))
        fee["transaction_fee_amount"] = p(-(net * TXN_BP // 10000))
        if f.get("affiliate"):     fee["affiliate_commission_amount"] = p(-(net * 1000 // 10000))
        if f.get("affiliate_ads"): fee["affiliate_ads_commission_amount"] = p(-(net * 1200 // 10000))
        if f.get("promo"):         fee["cofunded_promotion_service_fee_amount"] = p(-125)
        if f.get("return_handling"): fee["refund_administration_fee_amount"] = p(-f["return_handling"])
        if f.get("mystery_fee"):   fee["live_specials_fee_amount"] = p(-f["mystery_fee"])
        tax = {"local_vat_amount": "0.00"}
        ship = {}
        if f.get("fbt"):
            ship["fbt_free_shipping_fee_amount"] = p(-250)
            ship["actual_shipping_fee_amount"] = p(-300)
            ship["supplementary_component"] = {"fbt_fulfillment_fee_amount": p(-300)}  # explains the above, never summed
        if f.get("return_postage"):
            ship["return_shipping_fee_amount"] = p(-f["return_postage"])
        refund = gross if (f.get("refund_only") or f.get("return_resellable") or f.get("return_damaged") or f.get("cancelled")) else 0
        rev = {"subtotal_before_discount_amount": p(gross), "seller_discount_amount": p(-disc),
               "refund_subtotal_before_discount_amount": p(-refund), "seller_discount_refund_amount": "0.00"}
        fee_total = sum(int(round(float(v) * 100)) for v in fee.values())
        ship_total = sum(int(round(float(v) * 100)) for k, v in ship.items() if k != "supplementary_component")
        rev_total = gross - disc - refund
        sku_tx.append({"sku_id": sku_id, "sku_name": SKU[sku_id][2],
                       "product_name": PRODUCT_NAME[SKU[sku_id][1]], "quantity": str(len(ls)),
                       "statement_id": None,
                       "revenue_breakdown": rev, "revenue_amount": p(rev_total),
                       "fee_tax_breakdown": {"fee": fee, "tax": tax}, "fee_tax_amount": p(fee_total),
                       "shipping_cost_breakdown": ship, "shipping_cost_amount": p(ship_total),
                       "settlement_amount": p(rev_total + fee_total + ship_total)})
    return {"code": 0, "message": "Success", "request_id": "SYNTH-" + o["_ref"],
            "data": {"order_id": o["id"], "order_create_time": o["create_time"],
                     "currency": "GBP", "total_count": len(sku_tx),
                     "fee_and_tax_amount": p(sum(int(round(float(t["fee_tax_amount"]) * 100)) for t in sku_tx)),
                     "shipping_cost_amount": p(sum(int(round(float(t["shipping_cost_amount"]) * 100)) for t in sku_tx)),
                     "revenue_amount": None,          # null for a UK seller
                     "settlement_amount": p(sum(int(round(float(t["settlement_amount"]) * 100)) for t in sku_tx)),
                     "sku_transactions": sku_tx}}

tx = {o["id"]: statement_transactions(o) for o in orders}

# ------------------------------------------------------------- statements
# Statements are stamped the day AFTER the activity they cover.
SETTLED = [o for o in orders if not o["_flags"].get("unsettled")]
GROUPS = [("202608A-0001", "2026-08-21T00:00:00", SETTLED[0:7],  "PAID"),
          ("202608A-0002", "2026-08-22T00:00:00", SETTLED[7:14], "PROCESSING"),
          ("202608A-0003", "2026-08-23T00:00:00", SETTLED[14:],  "PAID")]

statements, stmt_tx, STMT_TXNS = [], {}, {}
for sid, stime, grp, status in GROUPS:
    net = fee = ship = 0
    for o in grp:
        for t in tx[o["id"]]["data"]["sku_transactions"]:
            t["statement_id"] = sid
            net  += int(round(float(t["revenue_amount"]) * 100))
            fee  += int(round(float(t["fee_tax_amount"]) * 100))
            ship += int(round(float(t["shipping_cost_amount"]) * 100))
    adj = -500 if sid.endswith("0003") else 0     # an adjustment TikTok gives no reason for
    res = -1000 if sid.endswith("0002") else 0    # funds withheld under the reserve policy
    settle = net + fee + ship + adj
    statements.append({"id": sid, "statement_time": ts(stime), "currency": "GBP",
                       "payment_status": status, "payment_id": "PAY-" + sid,
                       "payment_time": ts(stime) + 3600 if status == "PAID" else None,
                       "net_sales_amount": p(net), "fee_amount": p(fee),
                       "shipping_cost_amount": p(ship), "adjustment_amount": p(adj),
                       "revenue_amount": None,      # null for a UK seller
                       "settlement_amount": p(settle)})
    stmt_tx[sid] = [o["id"] for o in grp]

    # The per-statement transactions call. Verified 22 September 2026 against the
    # bundled OAS: this is the only source of adjustments, reserves and the
    # payable amount, and it carries no sku_transactions, so it cannot replace
    # the per-order call.
    txns = [{"id": f"TXN-{sid}-{i+1}", "type": "ORDER", "order_id": o["id"],
             "adjustment_id": None, "adjustment_order_id": None,
             "associated_order_id": None, "reserve_id": None,
             "reserve_amount": "0.00", "reserve_status": None,
             "estimated_release_time": None,
             "order_create_time": o["create_time"],
             "settlement_amount": tx[o["id"]]["data"]["settlement_amount"]}
            for i, o in enumerate(grp)]
    if adj:
        txns.append({"id": f"TXN-{sid}-ADJ", "type": "PLATFORM_PENALTY",
                     "order_id": None, "adjustment_id": f"ADJ-{sid}-1",
                     "adjustment_order_id": grp[0]["id"],   # an adjustment may name an order
                     "associated_order_id": None, "reserve_id": None,
                     "reserve_amount": "0.00", "reserve_status": None,
                     "estimated_release_time": None, "order_create_time": None,
                     "adjustment_amount": p(adj), "settlement_amount": p(adj)})
    if res:
        txns.append({"id": f"TXN-{sid}-RES", "type": "RESERVE",
                     "order_id": None, "adjustment_id": None,
                     "adjustment_order_id": None,
                     "associated_order_id": grp[0]["id"],
                     "reserve_id": f"RES-{sid}-1", "reserve_amount": p(res),
                     "reserve_status": "COLLECTED",
                     "estimated_release_time": ts(stime) + 90 * 86400,
                     "order_create_time": None, "settlement_amount": "0.00"})
    STMT_TXNS[sid] = {"code": 0, "message": "Success", "data": {
        "id": sid, "currency": "GBP", "status": status,
        "create_time": ts(stime), "next_page_token": "",
        "total_count": len(txns),
        "total_settlement_amount": p(settle),
        "total_reserve_amount": p(res),
        "payable_amount": p(settle + res),
        "total_settlement_breakdown": {
            "total_revenue_amount": p(net), "total_fee_tax_amount": p(fee),
            "total_shipping_cost_amount": p(ship),
            "total_adjustment_amount": p(adj)},
        "transactions": txns}}

# ---------------------------------------------------------------- returns
RETURNS = []
for o in orders:
    f = o["_flags"]
    kind = ("cancellation" if f.get("cancelled") else
            "refund_only" if f.get("refund_only") else
            "return_refund" if (f.get("return_resellable") or f.get("return_damaged")) else None)
    if not kind: continue
    RETURNS.append({
        "return_id": "RET" + o["_ref"], "order_id": o["id"], "return_type": kind.upper(),
        "return_status": "RETURN_OR_REFUND_REQUEST_COMPLETE",
        "return_reason_text": "无库存" if f.get("cancelled") else "Item not as described",
        "refund_amount": {"currency": "GBP", "refund_total": p(o["_subtotal"])},
        "create_time": o["create_time"] + 172800,
        "update_time": o["create_time"] + 259200,
        "credit_note_number": "CN-UK-2026-0019" if f.get("credit_note") else None,
        "_damaged": bool(f.get("return_damaged")),
        "_skus": sorted({l["sku_id"] for l in o["line_items"]}),
    })

# -------------------------------------------------------------- inventory
inventory = [{"sku_id": s[0], "product_id": s[1], "seller_sku": s[3],
              "quantity": 0 if s[0] == SKUS[9][0] else 25 - i * 2,
              "warehouse_id": "7352000000000000001"} for i, s in enumerate(SKUS)]

# ------------------------------------------------------------------ write
def dump(name, obj):
    with open(os.path.join(OUT, name), "w") as fh:
        json.dump(obj, fh, indent=1)

dump("authorization_shops.json", {"code": 0, "message": "Success", "data": {"shops": [
    {"id": SHOP_ID, "cipher": SHOP_CIPHER, "code": SHOP_CODE,
     "name": "Synthetic UK Shop", "region": "GB", "seller_type": "LOCAL"}]}})
dump("orders.json", {"code": 0, "message": "Success",
                     "data": {"orders": orders, "total_count": len(orders), "next_page_token": ""}})
dump("order_statement_transactions.json", tx)
dump("statement_transactions.json", STMT_TXNS)
dump("statements.json", {"code": 0, "message": "Success",
                         "data": {"statements": statements, "next_page_token": ""}})
dump("statement_order_map.json", stmt_tx)
dump("returns.json", {"code": 0, "message": "Success",
                      "data": {"return_orders": RETURNS, "total_count": len(RETURNS)}})
dump("inventory.json", {"code": 0, "message": "Success", "data": {"inventory": inventory}})
dump("catalogue.json", {"products": PRODUCTS, "skus": SKUS})

print(f"orders {len(orders)}  line_items {sum(len(o['line_items']) for o in orders)}  "
      f"statements {len(statements)}  returns {len(RETURNS)}  skus {len(SKUS)}")
print("statement totals:", [(s["id"], s["settlement_amount"], s["payment_status"]) for s in statements])
