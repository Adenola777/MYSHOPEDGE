"""QA of the read operations against independent SQL on the local copy of development."""
import json, urllib.request, urllib.error, psycopg
BASE="http://127.0.0.1:8801/v1"; SH="8a773a13-73b5-a382-7dd0-fda02e950369"
TOK=open("tok_a").read().strip()
db=psycopg.connect("postgresql://postgres@/myshopedge?host=/tmp&port=5439", autocommit=True)
def q(sql,*a): return db.execute(sql,a).fetchall()
def get(path, tok=TOK):
    r=urllib.request.Request(BASE+path, headers={"Authorization":f"Bearer {tok}"} if tok else {})
    try:
        with urllib.request.urlopen(r) as f: return f.status, json.load(f)
    except urllib.error.HTTPError as e: return e.code, json.loads(e.read() or b"{}")
res=[]
def check(name, got, want):
    ok = got==want; res.append((ok,name,got,want)); print(("PASS" if ok else "FAIL"), name, "" if ok else f"got {got!r} want {want!r}")
R="from=2026-07-01&to=2026-08-31"
# Money, sales basis
_,m=get(f"/shops/{SH}/money?{R}")
lines={}
for s in m["sections"]:
    for l in s["lines"]: lines[l["category"]]=lines.get(l["category"],0)+l["amount"]["amount_minor"]
led=dict(q("select category,sum(amount_minor)::int from ledger_entries where basis_month between '2026-07-01' and '2026-08-01' and category<>'cost_of_goods_sold' group by 1"))
for c,v in sorted(led.items()): check(f"money sales: {c} equals ledger", lines.get(c), v)
cogs=q("""select (select sum(ol.quantity*pc.cost_minor) from order_lines ol join product_costs pc using(sku_id))
 - (select sum(ri.quantity*pc.cost_minor) from return_items ri join product_costs pc using(sku_id))""")[0][0]
check("money sales: cost of goods is units less returns at cost", lines["cost_of_goods_sold"], -int(cogs))
t={k:v["amount_minor"] for k,v in m["totals"].items() if isinstance(v,dict)}
check("money: net sales = gross + discounts", t["net_sales"], led["gross_sales"]+led["seller_discount"])
np_=sum(v for c,v in led.items() if c not in("settlement","reserve_withheld","return_shipping","stock_written_off"))
check("money: net proceeds from ledger", t["net_proceeds"], np_)
check("money: gross profit = net proceeds + cogs", t["gross_profit"], np_-int(cogs))
check("money: after returns = gross profit - return postage - write off", t["gross_profit_after_returns"], np_-int(cogs)+led["return_shipping"]+led["stock_written_off"])
check("money: kept equals after returns", m["kept"]["amount_minor"], t["gross_profit_after_returns"])
check("money: payout 453.88", lines["settlement"], -45388)
# Money, cash basis
_,mc=get(f"/shops/{SH}/money?{R}&basis=cash")
cl={}
for s in mc["sections"]:
    for l in s["lines"]: cl[l["category"]]=cl.get(l["category"],0)+l["amount"]["amount_minor"]
cled=dict(q("select category,sum(amount_minor)::int from ledger_entries where settlement_month between '2026-07-01' and '2026-08-01' and category<>'cost_of_goods_sold' group by 1"))
for c,v in sorted(cled.items()): check(f"money cash: {c} equals settled ledger", cl.get(c), v)
check("money cash: confidence confirmed", mc["confidence"], "confirmed")
# Today Shop Money
_,td=get(f"/shops/{SH}/today"); sm=td["shop_money"]
check("today: net proceeds all time", sm["generated"]["amount_minor"], np_)
check("today: paid out 453.88", sm["paid_out"]["amount_minor"], 45388)
check("today: awaiting = proceeds - paid - postage", sm["awaiting"]["amount_minor"], np_-45388+led["return_shipping"])
check("today: awaiting breakdown sums to awaiting", sum(a["amount"]["amount_minor"] for a in sm["awaiting_breakdown"]), sm["awaiting"]["amount_minor"])
# Products
_,pr=get(f"/shops/{SH}/products?{R}")
for p in pr["products"]:
    pid=p["product_id"]
    u=q("select coalesce(sum(quantity),0)::int from order_lines ol join skus s on s.id=ol.sku_id where s.product_id=%s",pid)[0][0]
    g=q("select coalesce(sum(le.amount_minor),0)::int from ledger_entries le join order_lines ol on ol.id=le.order_line_id join skus s on s.id=ol.sku_id where s.product_id=%s and le.category='gross_sales'",pid)[0][0]
    r=q("select coalesce(sum(ri.quantity),0)::int from return_items ri join skus s on s.id=ri.sku_id where s.product_id=%s",pid)[0][0]
    check(f"products: {p['title']} units", p["units"], u)
    check(f"products: {p['title']} gross sales", p["gross_sales"]["amount_minor"], g)
    check(f"products: {p['title']} returned units", p["returns_units"], r)
    s,d=get(f"/shops/{SH}/products/{pid}?{R}")
    check(f"product detail: {p['title']} matches the list row", d["product"], p)
    check(f"product detail: {p['title']} per-unit gross times units", d["per_unit"]["sections"][0]["lines"][0]["amount"]["amount_minor"]*p["units"], p["gross_sales"]["amount_minor"])
check("products: total equals sum of rows", pr["total"]["amount_minor"], sum(p["kept"]["amount_minor"] for p in pr["products"] if p["kept"]))
check("products: shop total equals Money kept", pr["shop_total"]["amount_minor"], m["kept"]["amount_minor"])
loose=q("select coalesce(sum(amount_minor),0)::int from ledger_entries where sku_id is null and category='platform_adjustment' and basis_month between '2026-07-01' and '2026-08-01'")[0][0]
check("products: unattributed equals the ledger's entries with no variant", pr["unattributed"]["amount"]["amount_minor"], loose)
check("products: shop total = total + unattributed", pr["shop_total"]["amount_minor"], pr["total"]["amount_minor"]+pr["unattributed"]["amount"]["amount_minor"])
for meas, key in (("net_proceeds","net_proceeds"),("gross_sales","gross_sales")):
    _,x=get(f"/shops/{SH}/products?{R}&measure={meas}")
    check(f"products by {meas}: shop total equals Money {key}", x["shop_total"]["amount_minor"], m["totals"][key]["amount_minor"])
_,pc=get(f"/shops/{SH}/products?{R}&basis=cash")
check("products cash: shop total equals Money cash kept", pc["shop_total"]["amount_minor"], mc["kept"]["amount_minor"])
sk1=q("select k.id::text, p.title, k.seller_sku from skus k join products p on p.id=k.product_id where k.seller_sku='HAIR-BLUE'")[0]
_,mv=get(f"/shops/{SH}/stock/{sk1[0]}/movements")
check("movements: names the variant", (mv["sku"]["product_title"], mv["sku"]["seller_sku"]), (sk1[1], sk1[2]))
# Settlements
_,st=get(f"/shops/{SH}/settlements")
check("settlements: count", len(st["settlements"]), q("select count(*)::int from settlements")[0][0])
for s in st["settlements"]:
    _,d=get(f"/shops/{SH}/settlements/{s['id']}")
    dbv=q("select statement_amount_minor::int, payable_amount_minor::int from settlements where id=%s",s["id"])
    check(f"settlement {s['tiktok_statement_id']}: statement amount", s["statement_amount"]["amount_minor"], dbv[0][0] if dbv else None)
    check(f"settlement {s['tiktok_statement_id']}: detail opens", "id" in d or "settlement" in d, True)
# Records, walked to the end through the cursor
ids=[]; total=0; cur=""
while True:
    _,r=get(f"/shops/{SH}/records?limit=25"+(f"&cursor={cur}" if cur else ""))
    ids+= [e["id"] for e in r["entries"]]; total+=sum(e["amount"]["amount_minor"] for e in r["entries"])
    cur=r.get("next_cursor")
    if not cur: break
check("records: every entry once through the cursor", (len(ids),len(set(ids))), (119,119))
check("records: sum equals ledger", total, -31824)
# Returns
_,rt=get(f"/shops/{SH}/returns?limit=100")
check("returns: count", len(rt["returns"]), q("select count(*)::int from returns")[0][0])
_,rm=get(f"/shops/{SH}/returns/metrics?{R}")
check("return metrics: units", rm["returns_units"], q("select sum(quantity)::int from return_items")[0][0])
check("return metrics: write off", rm["write_off_total"]["amount_minor"], -led["stock_written_off"])
check("return metrics: rate = returned / sold", round(rm["return_rate"],6), round(q("select sum(quantity) from return_items")[0][0]/q("select sum(quantity) from order_lines")[0][0],6))
# Stock
_,sk=get(f"/shops/{SH}/stock?limit=100")
check("stock: one row per sku", len(sk["items"]), q("select count(*)::int from skus")[0][0])
for it in sk["items"]:
    v=q("select tiktok_stock from stock_positions where sku_id=%s order by as_of desc limit 1",it["sku_id"])
    if v: check(f"stock: {it['seller_sku'] or it['sku_id'][:8]} tiktok stock", it["tiktok_stock"], v[0][0])
# Discrepancies and Needs you
_,dc=get(f"/shops/{SH}/discrepancies")
check("discrepancies: open count", dc["open_count"], q("select count(*)::int from discrepancies where status='open'")[0][0])
_,ny=get(f"/shops/{SH}/needs-you")
check("needs you: carries open discrepancies", any(i["type"]=="open_discrepancies" and i["count"]==dc["open_count"] for i in ny["items"]), True)
_,cv=get(f"/shops/{SH}/costs/coverage?{R}")
check("cost coverage: every unit costed", cv["coverage"], 1.0)
print(f"\n{sum(r[0] for r in res)} passed, {sum(not r[0] for r in res)} failed")
json.dump([dict(ok=o,name=n,got=g,want=w) for o,n,g,w in res], open("reads.json","w"), indent=1, default=str)
