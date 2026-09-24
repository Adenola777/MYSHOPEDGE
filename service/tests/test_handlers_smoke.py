"""Calls every route, because until 23 September 2026 nothing ever had.

Eight routes were served and none had been invoked. `test_contract_conformance.py` imports
the application and reads the schema FastAPI derives from the handlers, which exercises
their declarations and never their bodies. Every "verified against the seeded seller" line
in the service referred to SQL run by hand, not to the handler wrapping it.

That gap is how the authentication defect survived: the parts that were checked were
checked carefully, and the parts nobody called were assumed to work.

    python3 tests/test_handlers_smoke.py

It runs without a database, without credentials and without the network, by overriding the
account dependency and substituting a connection that returns canned rows.

**What this proves and what it does not.** It proves each handler executes end to end, that
its response validates against its own model, and that the arithmetic it performs on the
rows it is given is the arithmetic intended. It does not prove the SQL is right, because
the SQL never runs. A wrong query returning plausible rows would pass here and fail in
production, so this sits alongside the checks against the real database rather than
replacing them.
"""

import os, sys, hashlib, base64
from datetime import datetime, timezone, date
from uuid import UUID

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("NEON_AUTH_JWKS_URL", "http://127.0.0.1:1/jwks.json")
os.environ.setdefault("NEON_AUTH_AUDIENCE", "test")
os.environ.setdefault("NEON_AUTH_ISSUER", "https://test.invalid")

from fastapi.testclient import TestClient

from app.main import app
from app.auth import Account, require_account
from app import discrepancies, products, records, settlements, shops, stock

ACCOUNT = Account(
    id=UUID("56e487ea-e0fa-3691-7857-724855e716fc"),
    email="owner@synthetic-uk-shop.test", name="Synthetic UK Shop Ltd",
    subject="user_synthetic_uk_shop",
)
SHOP = UUID("8a773a13-73b5-a382-7dd0-fda02e950369")
PRODUCT = UUID("11111111-1111-4111-8111-111111111111")
SKU = UUID("22222222-2222-4222-8222-222222222222")
NOW = datetime(2026, 8, 15, 12, 0, tzinfo=timezone.utc)


class Col:
    def __init__(self, name): self.name = name


class Result:
    """One canned answer. Chosen by matching text in the SQL, which is crude and honest.

    Matching on SQL text means a rewritten query silently falls through to an empty
    result rather than failing loudly. The KeyError below is what stops that being silent.
    """
    def __init__(self, cols, rows):
        self.description = [Col(c) for c in cols]
        self._rows = rows
    def fetchall(self): return self._rows
    def fetchone(self): return self._rows[0] if self._rows else None


class Conn:
    def __init__(self, answers): self.answers = answers
    def execute(self, sql, args=None):
        for needle, result in self.answers:
            if needle in " ".join(sql.split()):
                return result
        raise KeyError(f"No canned answer for: {' '.join(sql.split())[:140]}")
    def __enter__(self): return self
    def __exit__(self, *a): return False


failures = []

def check(name, fn):
    try:
        fn()
        print(f"  PASS  {name}")
    except Exception as exc:
        failures.append((name, exc))
        print(f"  FAIL  {name}: {type(exc).__name__}: {exc}")


app.dependency_overrides[require_account] = lambda: ACCOUNT
app.dependency_overrides[shops.require_shop] = lambda: SHOP
client = TestClient(app)


def with_conn(module, answers):
    """Replace the module's tenant() for one call."""
    import contextlib
    @contextlib.contextmanager
    def fake(_account_id):
        yield Conn(answers)
    return fake


def _assert(cond, msg="assertion failed"):
    if not cond: raise AssertionError(msg)


print("handler smoke")

check("GET /health returns 200", lambda: _assert(client.get("/health").status_code == 200))


# --- billing plans needs no database at all
def plans():
    r = client.get("/v1/billing/plans")
    _assert(r.status_code == 200, f"status {r.status_code}: {r.text[:200]}")
    body = r.json()
    _assert(len(body["plans"]) == 3, f"expected 3 plans, got {len(body['plans'])}")
    _assert([p["slug"] for p in body["plans"]] == ["starter", "growth", "pro"])
check("GET /v1/billing/plans lists three plans in order", plans)


# --- settlements list
def settlements_list():
    cols = ["id","tiktok_statement_id","tiktok_payment_id","settlement_reference",
            "statement_time","activity_date","paid_at","payment_status","currency",
            "statement_amount_minor","payable_amount_minor","total_reserve_amount_minor",
            "tiktok_invoice_number"]
    row = (UUID("33333333-3333-4333-8333-333333333333"), "202608A-0002", None, None,
           NOW, date(2026,8,15), None, "PAID", "GBP", 14750, 13750, -1000, None)
    settlements.tenant = with_conn(settlements, [("from settlements where", Result(cols, [row]))])
    r = client.get(f"/v1/shops/{SHOP}/settlements")
    _assert(r.status_code == 200, f"status {r.status_code}: {r.text[:300]}")
    b = r.json()["settlements"][0]
    _assert(b["statement_amount"]["amount_minor"] == 14750)
    _assert(b["total_reserve"]["amount_minor"] == -1000, "reserve must keep its sign")
    _assert(b["payable_amount"]["amount_minor"] == 13750)
check("GET settlements returns statement, reserve and payout as three figures", settlements_list)


# --- records
def records_page():
    cols = ["id","entry_type","category","tiktok_fee_type","amount_minor","currency",
            "occurred_at","basis_day","basis_month","source","source_ref","attribution",
            "order_id","tiktok_order_id","sku_id","tiktok_invoice_number",
            "reverses_entry_id","reason"]
    row = (UUID("44444444-4444-4444-8444-444444444444"), "sale", "gross_sales", None,
           36000, "GBP", NOW, date(2026,8,15), date(2026,8,1), "tiktok", None, "direct",
           None, None, SKU, None, None, None)
    records.tenant = with_conn(records, [
        ("coalesce(sum(le.amount_minor), 0)", Result(["s","c"], [(50038, "GBP")])),
        ("from ledger_entries le", Result(cols, [row])),
    ])
    r = client.get(f"/v1/shops/{SHOP}/records")
    _assert(r.status_code == 200, f"status {r.status_code}: {r.text[:300]}")
    b = r.json()
    _assert(b["total"]["amount_minor"] == 50038, "total is every page")
    _assert(b["shown_total"]["amount_minor"] == 36000, "shown_total is this page")
    _assert(b["entries"][0]["label"] == "Gross sales (GMV)", "A18.5: every category has words")
check("GET records distinguishes the total from the page sum", records_page)


# --- products ranking, and the arithmetic that matters
def products_ranking():
    cols = ["product_id","tiktok_product_id","title","units_sold","returns_units",
            "gross_sales_minor","net_proceeds_minor","currency","return_loss_minor",
            "cost_retained_minor","skus_without_cost","kept_minor"]
    desk = (PRODUCT, "P-DESK", "Computer Desk 120cm", 3, 1, 36000, 21300, "GBP",
            5100, 10200, 0, 6000)
    nocost = (UUID("55555555-5555-4555-8555-555555555555"), "P-X", "No cost yet",
              2, 0, 4000, 3000, "GBP", 0, None, 1, None)
    products.tenant = with_conn(products, [("with scoped as", Result(cols, [desk, nocost]))])
    r = client.get(f"/v1/shops/{SHOP}/products")
    _assert(r.status_code == 200, f"status {r.status_code}: {r.text[:300]}")
    b = r.json()
    rows = {p["title"]: p for p in b["products"]}
    _assert(rows["Computer Desk 120cm"]["kept"]["amount_minor"] == 6000)
    _assert(rows["Computer Desk 120cm"]["cost_known"] is True)
    # The product with no cost must report null rather than a figure that reads as profit.
    _assert(rows["No cost yet"]["kept"] is None, "kept must be null when a cost is missing")
    _assert(rows["No cost yet"]["cost_known"] is False)
    _assert(rows["No cost yet"]["kept_reason"] is not None, "a null kept must say why")
    # A product with an unknown cost ranks last rather than first.
    _assert(b["products"][0]["title"] == "Computer Desk 120cm")
check("GET products returns null kept with a reason, and ranks unknowns last", products_ranking)


# --- money, the calculator for the whole shop
from app import money_view

MONEY_LINE_COLS = ["category","tiktok_fee_type","amount_minor","entries","unsettled","currency"]
MONEY_LINES = [
    ("gross_sales", None, 86200, 24, 2, "GBP"),
    ("seller_discount", None, -500, 2, 0, "GBP"),
    ("platform_commission", None, -5142, 24, 0, "GBP"),
    ("transaction_fee", None, -1283, 24, 0, "GBP"),
    ("unmapped_fee", "SOME_NEW_FEE", -199, 1, 0, "GBP"),
    ("platform_adjustment", "LOGISTICS_REIMBURSEMENT", -500, 1, 0, "GBP"),
    ("refund", None, -27400, 7, 0, "GBP"),
    ("return_shipping", None, -450, 1, 0, "GBP"),
    ("stock_written_off", None, -5100, 1, 0, "GBP"),
    ("reserve_withheld", "reserve_amount", -1000, 1, 0, "GBP"),
    ("settlement", None, -45388, 3, 0, "GBP"),
]
PRODUCT_COLS = ["product_id","tiktok_product_id","title","units_sold","returns_units",
                "gross_sales_minor","net_proceeds_minor","currency","return_loss_minor",
                "cost_retained_minor","skus_without_cost","kept_minor"]
DESK = (PRODUCT, "P-DESK", "Computer Desk 120cm", 3, 1, 36000, 21300, "GBP",
        5100, 10200, 0, 6000)
NOCOST = (UUID("55555555-5555-4555-8555-555555555555"), "P-X", "No cost yet",
          2, 0, 4000, 3000, "GBP", 0, None, 1, None)


def _money(products_rows):
    money_view.tenant = with_conn(money_view, [
        ("count(*) filter (where le.settlement_id is null", Result(MONEY_LINE_COLS, MONEY_LINES)),
        ("with scoped as", Result(PRODUCT_COLS, products_rows)),
    ])


def money_chain():
    _money([DESK])
    r = client.get(f"/v1/shops/{SHOP}/money")
    _assert(r.status_code == 200, f"status {r.status_code}: {r.text[:300]}")
    b = r.json()
    keys = [s["key"] for s in b["sections"]]
    _assert(keys == ["revenue","tiktok_fees","refunds","your_costs","return_costs","payout"],
            f"A8.5 order, then the payout section last: {keys}")
    sec = {s["key"]: s for s in b["sections"]}
    _assert(sec["revenue"]["subtotal"]["amount_minor"] == 85700)
    _assert(sec["revenue"]["subtotal_label"] == "Net sales")
    fees = sec["tiktok_fees"]
    labels = [l["label"] for l in fees["lines"]]
    # The adjustment sits inside TikTok fees under TikTok's own name, as ruled.
    _assert("LOGISTICS_REIMBURSEMENT" in labels, f"adjustment inside fees: {labels}")
    _assert("SOME_NEW_FEE" in labels, "an unrecognised fee keeps TikTok's name")
    _assert(fees["subtotal"]["amount_minor"] == 78576)
    _assert(sec["refunds"]["subtotal"]["amount_minor"] == 51176)
    _assert(sec["refunds"]["subtotal_label"] == "Net proceeds")
    # Cost of goods is computed from retained cost, never read from the ledger (A4.1).
    cogs = sec["your_costs"]["lines"][0]
    _assert(cogs["category"] == "cost_of_goods_sold" and cogs["amount"]["amount_minor"] == -10200)
    _assert(sec["your_costs"]["subtotal"]["amount_minor"] == 40976)
    _assert(sec["return_costs"]["subtotal"]["amount_minor"] == 35426)
    _assert(sec["return_costs"]["subtotal_label"] == "Gross profit after returns")
    t = b["totals"]
    _assert(t["gross_sales"]["amount_minor"] == 86200)
    _assert(t["net_sales"]["amount_minor"] == 85700)
    _assert(t["net_proceeds"]["amount_minor"] == 51176)
    _assert(t["cost_of_goods_sold"]["amount_minor"] == -10200)
    _assert(t["gross_profit"]["amount_minor"] == 40976)
    _assert(t["gross_profit_after_returns"]["amount_minor"] == 35426)
    _assert(b["kept"]["amount_minor"] == 35426 and b["kept_reason"] is None)
    # Reserve and payout keep the ledger's signs and are not part of the chain.
    payout = sec["payout"]
    _assert([l["label"] for l in payout["lines"]] == ["Reserve withheld", "Payout"])
    _assert(payout["subtotal"]["amount_minor"] == -46388)
    _assert(b["cost_coverage"] == 1.0)
    _assert(b["unmapped_fee_count"] == 1)
    _assert(b["period"]["basis"] == "sales" and b["granularity"] == "month")
    # Two sales have no settlement yet, so the sales basis is an estimate.
    _assert(b["confidence"] == "estimated", b["confidence"])
check("GET money follows A8.5 and puts the adjustment inside TikTok fees", money_chain)


def money_cash_is_confirmed():
    _money([DESK])
    r = client.get(f"/v1/shops/{SHOP}/money?basis=cash")
    _assert(r.status_code == 200, f"status {r.status_code}: {r.text[:300]}")
    _assert(r.json()["confidence"] == "confirmed", r.json()["confidence"])
check("GET money on the cash basis is confirmed", money_cash_is_confirmed)


def money_incomplete_costs():
    _money([DESK, NOCOST])
    r = client.get(f"/v1/shops/{SHOP}/money")
    _assert(r.status_code == 200, f"status {r.status_code}: {r.text[:300]}")
    b = r.json()
    _assert(b["cost_coverage"] == 0.5, b["cost_coverage"])
    _assert(b["confidence"] == "incomplete")
    _assert(b["kept"] is None and b["kept_reason"] == "incomplete_costs")
    t = b["totals"]
    _assert(t["gross_profit"] is None and t["gross_profit_after_returns"] is None,
            "gross profit is null, never a figure that leaves the goods out")
    _assert("cost_of_goods_sold" not in t, "an unknown cost is omitted, not sent as zero")
    _assert(t["net_proceeds"]["amount_minor"] == 51176, "net proceeds needs no cost")
    sec = {s["key"]: s for s in b["sections"]}
    _assert("your_costs" not in sec, "no cost line and no postage means no section")
    _assert(sec["return_costs"]["subtotal"]["amount_minor"] == -5550)
    _assert(sec["return_costs"]["subtotal_label"] == "Total return costs")
check("GET money with a missing cost returns null gross profit and says why", money_incomplete_costs)


def money_etag():
    _money([DESK])
    first = client.get(f"/v1/shops/{SHOP}/money")
    tag = first.headers.get("etag")
    _assert(tag, "an ETag is sent")
    _money([DESK])
    again = client.get(f"/v1/shops/{SHOP}/money", headers={"If-None-Match": tag})
    _assert(again.status_code == 304, f"status {again.status_code}")
check("GET money answers 304 when nothing has changed", money_etag)


# --- today, which reuses the calculator and counts what needs the seller
from datetime import timedelta
from app import today_view

SHOP_MONEY_COLS = ["status","amount_minor","postage_minor","orders","currency"]
# The development ledger's own figures. Settled includes the 4.50 of return postage TikTok
# deducted, so it is 453.88, which is the payout TikTok made.
SHOP_MONEY_ROWS = [("delivered_awaiting_settlement", 1850, None, 1, "GBP"),
                   ("settled", 45388, -450, 18, "GBP"),
                   ("waiting_delivery", 1850, None, 1, "GBP")]
NEEDS_COLS = ["returns_to_check","open_discrepancies","out_of_stock","missing_costs",
              "unmapped_fees","unmapped_fee_minor","last_synced_at","connection_status",
              "access_expires_at","refresh_expires_at","revoked_at","connections",
              "refresh_failure_code","refresh_attempted_at","refresh_succeeded_at",
              "missing_scopes","latest_sync_statuses"]


def _needs(**over):
    base = dict(returns_to_check=0, open_discrepancies=1, out_of_stock=1, missing_costs=0,
                unmapped_fees=1, unmapped_fee_minor=199, last_synced_at=None,
                connection_status="connected", access_expires_at=None,
                refresh_expires_at=None, revoked_at=None, connections=1,
                refresh_failure_code=None, refresh_attempted_at=None,
                refresh_succeeded_at=None, missing_scopes=[], latest_sync_statuses=None)
    base.update(over)
    return Result(NEEDS_COLS, [tuple(base[c] for c in NEEDS_COLS)])


def _today(products_rows, needs):
    today_view.tenant = with_conn(today_view, [
        ("count(*) filter (where le.settlement_id is null", Result(MONEY_LINE_COLS, MONEY_LINES)),
        ("with scoped as", Result(PRODUCT_COLS, products_rows)),
        ("left join order_settlements os", Result(SHOP_MONEY_COLS, SHOP_MONEY_ROWS)),
        ("seller_check_status = 'pending'", needs),
    ])
    r = client.get(f"/v1/shops/{SHOP}/today")
    _assert(r.status_code == 200, f"status {r.status_code}: {r.text[:300]}")
    return r.json()


def today_complete():
    b = _today([DESK], _needs())
    _assert(b["hero"]["label"] == "gross_profit_after_returns", b["hero"]["label"])
    _assert(b["hero"]["value"]["amount_minor"] == 35426)
    _assert(b["hero"]["confidence"] == "estimated")
    _assert(b["month"]["gross"]["amount_minor"] == 86200)
    _assert(b["month"]["kept"]["amount_minor"] == 35426)
    sm = b["shop_money"]
    # A29.7: generated is net proceeds, paid out is what TikTok paid, and the return postage
    # TikTok deducted is stated rather than dropped, so the three reconcile.
    _assert(sm["generated"]["amount_minor"] == 49538)
    _assert(sm["paid_out"]["amount_minor"] == 45388, "paid out equals the real payout")
    _assert(sm["awaiting"]["amount_minor"] == 3700)
    _assert(sm["return_postage"]["amount_minor"] == -450)
    _assert(sm["paid_out"]["amount_minor"] + sm["awaiting"]["amount_minor"]
            == sm["generated"]["amount_minor"] + sm["return_postage"]["amount_minor"])
    _assert(b["freshness"] == {"status": "stale", "last_synced_at": None})
    _assert([a["status"] for a in sm["awaiting_breakdown"]]
            == ["delivered_awaiting_settlement", "waiting_delivery"])
    # Never synced means stale, and the list runs warning before info, money first.
    _assert(b["stale"] is True)
    types = [(i["type"], i["severity"]) for i in b["needs_you"]]
    _assert(types == [("unmapped_fees", "warning"), ("open_discrepancies", "warning"),
                      ("first_sync_pending", "info"), ("out_of_stock", "info")], types)
    _assert(b["needs_you"][0]["amount_at_stake"]["amount_minor"] == 199)
check("GET today leads with gross profit after returns and reconciles Shop Money", today_complete)


def today_incomplete():
    b = _today([DESK, NOCOST], _needs(missing_costs=1))
    _assert(b["hero"]["label"] == "net_proceeds", "A8 withdrew Left after TikTok")
    _assert(b["hero"]["value"]["amount_minor"] == 51176)
    _assert(b["hero"]["confidence"] == "incomplete")
    _assert(b["month"]["kept"] is None and b["month"]["kept_reason"] == "incomplete_costs")
    _assert(any(i["type"] == "missing_costs" and i["severity"] == "info" for i in b["needs_you"]))
check("GET today falls back to net proceeds when a cost is missing", today_incomplete)


def today_connection():
    now = datetime.now(timezone.utc)
    b = _today([DESK], _needs(last_synced_at=now - timedelta(hours=2),
                               refresh_expires_at=now + timedelta(days=10),
                               access_expires_at=now + timedelta(days=3)))
    _assert(b["stale"] is False, "synced two hours ago is not stale")
    warn = [i["type"] for i in b["needs_you"] if i["severity"] == "warning"]
    # Within a severity, the item with money at stake leads, then the others by count.
    _assert(warn == ["unmapped_fees", "connection_expiring", "open_discrepancies"], warn)
    b = _today([DESK], _needs(last_synced_at=now - timedelta(hours=30), revoked_at=now))
    _assert(b["stale"] is True)
    _assert(b["needs_you"][0]["type"] == "connection_action_required")
    _assert(b["needs_you"][0]["severity"] == "critical")
    _assert(any(i["type"] == "stale_data" for i in b["needs_you"]))
check("GET today puts a broken connection first and flags a stale sync", today_connection)


def today_freshness():
    now = datetime.now(timezone.utc)
    for hours, expected in ((1, "fresh"), (5.9, "fresh"), (6, "getting_old"),
                            (23.9, "getting_old"), (24.1, "stale")):
        b = _today([DESK], _needs(last_synced_at=now - timedelta(hours=hours)))
        _assert(b["freshness"]["status"] == expected, f"{hours}h gave {b['freshness']['status']}")
        _assert(b["stale"] == (expected == "stale"), f"{hours}h stale={b['stale']}")
check("GET today reports fresh, getting old and stale at the ruled boundaries", today_freshness)


def today_health():
    now = datetime.now(timezone.utc)
    b = _today([DESK], _needs(
        last_synced_at=now - timedelta(hours=1),
        refresh_failure_code="36004004", refresh_attempted_at=now,
        refresh_succeeded_at=now - timedelta(days=2),
        missing_scopes=["seller.return.info"],
        latest_sync_statuses=["completed", "failed", "partial"]))
    by = {i["type"]: i["severity"] for i in b["needs_you"]}
    _assert(by.get("refresh_failed") == "critical", by)
    _assert(by.get("missing_scope") == "critical", by)
    _assert(by.get("sync_failed") == "warning" and by.get("sync_partial") == "warning", by)
    sev = [i["severity"] for i in b["needs_you"]]
    _assert(sev == sorted(sev, key=lambda x: {"critical": 0, "warning": 1, "info": 2}[x]),
            f"critical, then warning, then info: {sev}")
    # A refresh that has since succeeded is not a failure.
    b = _today([DESK], _needs(last_synced_at=now, refresh_failure_code="36004004",
                               refresh_attempted_at=now - timedelta(hours=2),
                               refresh_succeeded_at=now - timedelta(hours=1)))
    _assert(all(i["type"] != "refresh_failed" for i in b["needs_you"]))
check("GET today raises refresh, scope and sync failures at their ruled severities", today_health)


# --- the two connection handlers
#
# These matter more than the readers. The callback is the only unauthenticated endpoint in
# the service, and the state is the only thing standing between a seller's ledger and a
# shop they never approved. A handler that accepts any state connects the wrong shop.
import contextlib

from app import connections


def _fake_unscoped(answers):
    @contextlib.contextmanager
    def fake():
        yield Conn(answers)
    return fake


def connection_unconfigured():
    for var in ("TIKTOK_SERVICE_ID", "TIKTOK_APP_KEY", "TIKTOK_APP_SECRET"):
        os.environ.pop(var, None)
    r = client.post("/v1/connections/tiktok/authorize")
    _assert(r.status_code == 503, f"status {r.status_code}: {r.text[:200]}")
    _assert(r.json()["code"] == "tiktok_unconfigured", r.text[:200])
check("POST authorize refuses when TikTok is not configured", connection_unconfigured)


def authorize_rejects_open_redirect():
    os.environ["TIKTOK_SERVICE_ID"] = "7688277529379407633"
    connections.tenant = with_conn(connections, [("insert into tiktok_auth_state", Result([], []))])
    # A protocol-relative URL passes a naive "starts with /" check and sends the seller to
    # another host. That is the account takeover the contract warns about.
    for bad in ("//evil.example/x", "https://evil.example", "/ok\\evil"):
        r = client.post("/v1/connections/tiktok/authorize", json={"return_to": bad})
        _assert(r.status_code == 400, f"{bad!r} was accepted: {r.status_code}")
        _assert(r.json()["code"] == "return_to_not_allowed", r.text[:200])
check("POST authorize refuses an off-site return_to", authorize_rejects_open_redirect)


def authorize_issues_a_link():
    os.environ["TIKTOK_SERVICE_ID"] = "7688277529379407633"
    written = {}

    class Recorder(Conn):
        def execute(self, sql, args=None):
            if "insert into tiktok_auth_state" in " ".join(sql.split()):
                written["digest"], written["account"] = args[0], args[1]
                return Result([], [])
            return super().execute(sql, args)

    @contextlib.contextmanager
    def fake(_account_id):
        yield Recorder([])
    connections.tenant = fake

    r = client.post("/v1/connections/tiktok/authorize", json={"return_to": "/connect/done"})
    _assert(r.status_code == 201, f"status {r.status_code}: {r.text[:300]}")
    b = r.json()
    # A23.1. The seller link, not the partner link. Using the partner host is what produced
    # an Indonesian sandbox shop three times on 23 September.
    _assert(b["authorization_url"].startswith("https://services.tiktokshop.com/open/authorize"),
            f"wrong authorisation host: {b['authorization_url']}")
    _assert("partner.tiktokshop.com" not in b["authorization_url"])
    _assert(f"state={b['state']}" in b["authorization_url"], "the link must carry the state")
    _assert(len(b["state"]) >= 32, "the state must be long enough not to be guessed")
    # The stored value is the digest. A readable copy of the table must be worthless.
    _assert(written["digest"] != b["state"], "the raw state must never be stored")
    _assert(written["digest"] == hashlib.sha256(b["state"].encode()).hexdigest())
    _assert(written["account"] == str(ACCOUNT.id), "the state is bound to this account")
check("POST authorize issues a seller link and stores only the digest", authorize_issues_a_link)


def callback_refuses_unknown_state():
    # consume_tiktok_auth_state returns no row for unknown, spent and expired alike.
    connections.unscoped = _fake_unscoped([("consume_tiktok_auth_state", Result(["a", "r"], []))])
    r = client.get("/v1/connections/tiktok/callback", params={"code": "c", "state": "whatever"})
    _assert(r.status_code == 400, f"status {r.status_code}: {r.text[:200]}")
    _assert(r.json()["code"] == "state_invalid", r.text[:200])
    # The detail must not echo what it was given back into a page the seller may screenshot.
    _assert("whatever" not in r.text and "c" != r.json()["detail"], "the detail echoed the input")
check("GET callback refuses a state it did not issue", callback_refuses_unknown_state)


def callback_refuses_a_creator_account():
    connections.unscoped = _fake_unscoped(
        [("consume_tiktok_auth_state", Result(["a", "r"], [(ACCOUNT.id, "/connect/done")]))]
    )
    # A23.3. user_type 1 is a creator. Anything but 0 means the wrong authorisation link.
    connections._exchange_code = lambda code: {"access_token": "t", "user_type": 1}
    r = client.get("/v1/connections/tiktok/callback", params={"code": "c", "state": "s"})
    _assert(r.status_code == 400, f"status {r.status_code}: {r.text[:200]}")
    _assert(r.json()["code"] == "not_a_seller_account", r.text[:200])
check("GET callback refuses a TikTok account that is not a seller", callback_refuses_a_creator_account)


def signature_follows_the_documented_steps():
    """TikTok's algorithm, checked against the four properties its page states.

    There is no worked example with an expected digest on TikTok's page, so this cannot
    assert a known-good value. It asserts the properties that distinguish the documented
    algorithm from the obvious wrong implementations of it, which is what a refactor would
    break. The first live call remains the real test.
    """
    sign, secret = connections._sign, "SECRET"
    base = sign("/authorization/202309/shops", {"app_key": "k", "timestamp": "1"}, b"", secret)

    # sign and access_token are excluded, so adding either changes nothing.
    _assert(base == sign("/authorization/202309/shops",
                         {"app_key": "k", "timestamp": "1", "sign": "x"}, b"", secret),
            "sign must be excluded from its own input")
    _assert(base == sign("/authorization/202309/shops",
                         {"app_key": "k", "timestamp": "1", "access_token": "t"}, b"", secret),
            "access_token must be excluded: it travels in a header and is not signed")

    # The path is part of the input, so the same parameters on another path differ.
    _assert(base != sign("/authorization/202403/shops",
                         {"app_key": "k", "timestamp": "1"}, b"", secret),
            "the request path must be part of the signed input")

    # The body is appended.
    _assert(base != sign("/authorization/202309/shops",
                         {"app_key": "k", "timestamp": "1"}, b"{}", secret),
            "the body must be part of the signed input")

    # Keys sort alphabetically, so a value moved between keys changes the concatenation.
    _assert(sign("/p", {"a": "1", "b": "2"}, b"", secret)
            != sign("/p", {"a": "12", "b": ""}, b"", secret),
            "keys and values must concatenate as {key}{value} in sorted order")

    # Hex SHA-256.
    _assert(len(base) == 64 and all(c in "0123456789abcdef" for c in base), base)
check("the signature follows TikTok's documented steps", signature_follows_the_documented_steps)


def tokens_round_trip_and_refuse_a_missing_key():
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    os.environ.pop("TIKTOK_TOKEN_KEY", None)
    try:
        connections._encrypt("secret-token")
        raise AssertionError("a missing key must refuse rather than store in the clear")
    except Exception as exc:
        _assert(getattr(exc, "code", None) == "token_encryption_unconfigured", repr(exc))

    key = AESGCM.generate_key(bit_length=256)
    os.environ["TIKTOK_TOKEN_KEY"] = base64.b64encode(key).decode()
    blob = connections._encrypt("secret-token")
    _assert(b"secret-token" not in blob, "the token must not appear in the ciphertext")
    back = AESGCM(key).decrypt(blob[:12], blob[12:], None).decode()
    _assert(back == "secret-token", "the token must decrypt to what went in")
    # A fresh nonce every time, so the same token does not produce the same bytes.
    _assert(connections._encrypt("secret-token") != blob, "the nonce must not repeat")
check("tokens encrypt, round trip, and refuse to store without a key", tokens_round_trip_and_refuse_a_missing_key)


GB_SHOP = {"id": "7495", "code": "GBGBLCRKQTEX", "name": "My ShopEdge",
           "region": "GB", "seller_type": "LOCAL", "cipher": "GCP_test"}


def _callback_with(shop, written):
    connections.unscoped = _fake_unscoped(
        [("consume_tiktok_auth_state", Result(["a", "r"], [(ACCOUNT.id, "/connect/done")]))]
    )
    connections._exchange_code = lambda code: {
        "access_token": "act.tok", "refresh_token": "rft.tok", "user_type": 0,
        "access_token_expire_in": 604800, "refresh_token_expire_in": 2592000,
        "granted_scopes": ["seller.finance"],
    }
    connections._authorized_shops = lambda token: [shop]

    class Writer(Conn):
        def execute(self, sql, args=None):
            flat = " ".join(sql.split())
            if "insert into shops" in flat:
                written["shop"] = args
                return Result(["id"], [(SHOP,)])
            if "insert into tiktok_connections" in flat:
                written["conn"] = args
                return Result([], [])
            return Result([], [])

    @contextlib.contextmanager
    def fake(_account_id):
        yield Writer([])
    connections.tenant = fake
    return client.get("/v1/connections/tiktok/callback", params={"code": "c", "state": "s"})


def callback_connects_a_gb_shop():
    written = {}
    r = _callback_with(GB_SHOP, written)
    _assert(r.status_code == 200, f"status {r.status_code}: {r.text[:400]}")
    b = r.json()
    _assert(b["accepted"] is True, b)
    _assert(b["rejection_reason"] is None, b)
    _assert(b["shop"]["tiktok_shop_code"] == "GBGBLCRKQTEX", b["shop"])
    _assert(b["shop"]["seller_type"] == "LOCAL", b["shop"])
    # The contract says the connection is recorded as pending, not connected.
    _assert(b["shop"]["connection_status"] == "pending", b["shop"])
    _assert(b["return_to"] == "/connect/done", b)
    # Nothing readable reaches the database.
    enc_access, enc_refresh, enc_cipher = written["conn"][1], written["conn"][2], written["conn"][3]
    _assert(b"act.tok" not in enc_access, "the access token was stored in the clear")
    _assert(b"rft.tok" not in enc_refresh, "the refresh token was stored in the clear")
    _assert(b"GCP_test" not in enc_cipher, "the shop cipher was stored in the clear")
check("GET callback connects a GB shop and stores nothing readable", callback_connects_a_gb_shop)


def callback_lists_but_refuses_an_unsupported_shop():
    # A28: the shop is stored and listed, and it produces no figures. Refusing outright
    # would lose the authorisation the seller just granted.
    for field, value, reason in [("region", "ID", "region_unsupported"),
                                 ("seller_type", "CROSS_BORDER", "seller_type_unsupported")]:
        r = _callback_with({**GB_SHOP, field: value}, {})
        _assert(r.status_code == 200, f"status {r.status_code}: {r.text[:300]}")
        b = r.json()
        _assert(b["accepted"] is False, b)
        _assert(b["rejection_reason"] == reason, b)
        _assert(b["shop"] is not None, "the shop must still be listed")
check("GET callback stores an unsupported shop but marks it not accepted", callback_lists_but_refuses_an_unsupported_shop)


# --- stock, movements and discrepancies
STOCK_COLS = ["sku_id","tiktok_sku_id","seller_sku","product_title","tiktok_stock",
              "adjusted_delta","on_shelf","sold_not_posted","coming_back","written_off",
              "as_of","days_left","state"]

def _stock_row(sku, on_shelf, days_left, state):
    from decimal import Decimal
    return (sku, "1729", "SKU", "Title", on_shelf, 0, on_shelf, 0, 0, 0, NOW,
            Decimal(days_left) if days_left is not None else None, state)

def stock_page():
    rows = [_stock_row(UUID(int=i), 5, "3.5", "low") for i in range(1, 4)]
    stock.tenant = with_conn(stock, [
        ("with settings as", Result(STOCK_COLS, rows)),
        ("select max(as_of) from stock_positions", Result(["m"], [(NOW,)])),
    ])
    r = client.get(f"/v1/shops/{SHOP}/stock?limit=2&state=low")
    _assert(r.status_code == 200, f"status {r.status_code}: {r.text[:300]}")
    b = r.json()
    _assert(len(b["items"]) == 2, "the extra row only signals another page")
    _assert(b["items"][0]["days_left"] == 3.5, b["items"][0])
    _assert(b["items"][0]["state"] == "low")
    _assert(b["next_cursor"] is not None)
    r2 = client.get(f"/v1/shops/{SHOP}/stock?cursor={b['next_cursor']}")
    _assert(r2.status_code == 200, f"status {r2.status_code}: {r2.text[:300]}")
check("GET stock pages by SKU and serves days left as a number", stock_page)

def stock_out_is_null():
    stock.tenant = with_conn(stock, [
        ("with settings as", Result(STOCK_COLS, [_stock_row(SKU, 0, None, "out")])),
        ("select max(as_of) from stock_positions", Result(["m"], [(NOW,)])),
    ])
    b = client.get(f"/v1/shops/{SHOP}/stock").json()
    _assert(b["items"][0]["days_left"] is None, "A12 row 29: sold out is null, not a division")
    _assert(b["next_cursor"] is None)
check("GET stock returns null days left for a sold out SKU", stock_out_is_null)

def stock_refuses_bad_input():
    _assert(client.get(f"/v1/shops/{SHOP}/stock?cursor=nonsense").status_code == 400)
    _assert(client.get(f"/v1/shops/{SHOP}/stock?state=gone").status_code == 422)
check("GET stock refuses a malformed cursor and an unknown state", stock_refuses_bad_input)

MOVE_COLS = ["id","movement_type","quantity","occurred_at","order_id","return_id",
             "reason","created_by"]

def movements_page():
    rows = [(UUID(int=i), "manual_adjustment", -2, NOW, None, None, "Damaged", None)
            for i in range(1, 3)]
    stock.tenant = with_conn(stock, [
        ("select 1 from skus", Result(["x"], [(1,)])),
        ("from stock_movements where", Result(MOVE_COLS, rows)),
    ])
    r = client.get(f"/v1/shops/{SHOP}/stock/{SKU}/movements?limit=1")
    _assert(r.status_code == 200, f"status {r.status_code}: {r.text[:300]}")
    b = r.json()
    _assert(b["movements"][0]["quantity"] == -2)
    _assert(b["movements"][0]["reason"] == "Damaged")
    _assert(b["next_cursor"] is not None)
check("GET movements lists a SKU's ledger newest first", movements_page)

def movements_unknown_sku():
    stock.tenant = with_conn(stock, [("select 1 from skus", Result(["x"], []))])
    r = client.get(f"/v1/shops/{SHOP}/stock/{SKU}/movements")
    _assert(r.status_code == 404, f"status {r.status_code}")
    _assert(r.json()["code"] == "sku_not_found")
check("GET movements answers 404 for a SKU outside the shop", movements_unknown_sku)

DISC_COLS = ["id","kind","entity_type","entity_id","field","tiktok_value","seller_value",
             "applied_value","status","resolution","note","effect","opened_at","resolved_at"]

def discrepancies_page():
    row = (UUID(int=7), "unmapped_fee", "settlement", None, "adjustment_amount", "-5.00",
           None, "-5.00", "open", None, "PLATFORM_PENALTY", None, NOW, None)
    discrepancies.tenant = with_conn(discrepancies, [
        ("from discrepancies where shop_id = %s and status = 'open'", Result(["c"], [(2,)])),
        ("from discrepancies where", Result(DISC_COLS, [row])),
    ])
    r = client.get(f"/v1/shops/{SHOP}/discrepancies?kind=unmapped_fee")
    _assert(r.status_code == 200, f"status {r.status_code}: {r.text[:300]}")
    b = r.json()
    _assert(b["open_count"] == 2, "TC-DSC-05: the open count ignores the page filters")
    _assert(b["discrepancies"][0]["kind"] == "unmapped_fee")
    _assert(b["discrepancies"][0]["applied_value"] == "-5.00")
check("GET discrepancies serves the seventh kind and an unfiltered open count", discrepancies_page)


def product_detail_stock_state():
    # getProduct had never been invoked. When it was, on 24 September, its stock state was
    # its own "in_stock" or "out_of_stock", outside the contract's enum. It now reads the
    # position from stock.positions, the one place the stock rule lives.
    rank_cols = ["product_id","tiktok_product_id","title","units_sold","returns_units",
                 "gross_sales_minor","net_proceeds_minor","currency","return_loss_minor",
                 "cost_retained_minor","skus_without_cost","kept_minor"]
    desk = (PRODUCT, "P-DESK", "Computer Desk 120cm", 3, 1, 36000, 21300, "GBP",
            5100, 10200, 0, 6000)
    products.tenant = with_conn(products, [
        ("from products where id=%s", Result(["id","tiktok_product_id","title"],
                                              [(PRODUCT, "P-DESK", "Computer Desk 120cm")])),
        ("group by le.category, le.tiktok_fee_type",
         Result(["category","tiktok_fee_type","amount_minor","currency"],
                [("gross_sales", None, 36000, "GBP")])),
        ("from skus s where s.product_id", Result(["id","tiktok_sku_id","seller_sku",
                                                   "variant_label","cost_minor"],
                                                  [(SKU, "1729", "DESK-BLK", None, 3400)])),
        ("with settings as", Result(STOCK_COLS, [_stock_row(SKU, 0, None, "out")])),
        ("with scoped as", Result(rank_cols, [desk])),
    ])
    r = client.get(f"/v1/shops/{SHOP}/products/{PRODUCT}")
    _assert(r.status_code == 200, f"status {r.status_code}: {r.text[:300]}")
    st = r.json()["stock"]
    _assert(st is not None and st["state"] == "out", st)
    _assert(st["days_left"] is None)
check("GET product detail takes its stock state from the one stock rule", product_detail_stock_state)


def needs_you_links_only_to_built_screens():
    from app.today_view import needs_href
    d = date(2026, 9, 24)
    _assert(needs_href("open_discrepancies", SHOP, d) == f"/shops/{SHOP}/discrepancies?status=open")
    _assert(needs_href("unmapped_fees", SHOP, d).endswith(
        "records?category=unmapped_fee&from=2026-09-01&to=2026-09-24"))
    _assert(needs_href("out_of_stock", SHOP, d) == f"/shops/{SHOP}/stock?state=out")
    # No screen yet, so no link rather than a link to nothing.
    _assert(needs_href("returns_to_check", SHOP, d) is None)
    _assert(needs_href("connection_action_required", SHOP, d) is None)
check("Needs you links only to screens that exist", needs_you_links_only_to_built_screens)


def product_and_money_use_the_same_words():
    # A8 and TC-CLR-06. The product calculator and the Money calculator name the same money,
    # so they must use the same words, and none of the withdrawn labels may appear.
    from app import money_view
    for key, label in products.LABELS.items():
        _assert(money_view.LABELS.get(key) == label,
                f"{key}: product says {label!r}, money says {money_view.LABELS.get(key)!r}")
    withdrawn = ("Their cut", "You keep", "Left after TikTok", "Contribution", "Return Loss")
    words = [w for s in products.SECTIONS for w in s[1:3]] + list(products.LABELS.values())
    for w in words:
        _assert(not any(x.lower() in w.lower() for x in withdrawn), f"withdrawn label: {w}")
check("Product and Money calculators use A8's words and no withdrawn label", product_and_money_use_the_same_words)


print()
if failures:
    print(f"{len(failures)} failure(s)")
    sys.exit(1)
print("every handler executed and returned what it promised")
