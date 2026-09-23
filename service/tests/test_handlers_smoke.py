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

import os, sys, json, hashlib
from datetime import datetime, timezone, date
from uuid import UUID

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("NEON_AUTH_JWKS_URL", "http://127.0.0.1:1/jwks.json")
os.environ.setdefault("NEON_AUTH_AUDIENCE", "test")
os.environ.setdefault("NEON_AUTH_ISSUER", "https://test.invalid")

from fastapi.testclient import TestClient

from app.main import app
from app.auth import Account, require_account
from app import products, records, settlements, shops

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


def callback_stops_at_the_signing_gap():
    connections.unscoped = _fake_unscoped(
        [("consume_tiktok_auth_state", Result(["a", "r"], [(ACCOUNT.id, "/connect/done")]))]
    )
    connections._exchange_code = lambda code: {"access_token": "t", "user_type": 0}
    r = client.get("/v1/connections/tiktok/callback", params={"code": "c", "state": "s"})
    # Not a pass in the ordinary sense. It asserts that the unfinished part fails loudly and
    # in one named place, rather than writing a half connection that can never reconcile.
    _assert(r.status_code == 503, f"status {r.status_code}: {r.text[:300]}")
    _assert(r.json()["code"] == "tiktok_signing_unimplemented", r.text[:200])
check("GET callback stops at the signing gap rather than guessing", callback_stops_at_the_signing_gap)


print()
if failures:
    print(f"{len(failures)} failure(s)")
    sys.exit(1)
print("every handler executed and returned what it promised")
