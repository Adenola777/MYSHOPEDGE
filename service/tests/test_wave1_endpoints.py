"""WAVE 1 endpoint contract & behaviour tests via public preview URL."""
import os
import time
import uuid
import pytest
import requests

BASE = "https://3574af37-00da-4199-8fc8-75173ccd4d0b.preview.emergentagent.com/api/v1"
SHOP_ID = "8a773a13-73b5-a382-7dd0-fda02e950369"
FOREIGN_SHOP = "00000000-0000-0000-0000-000000000001"
ACCOUNT_EMAIL = "owner@synthetic-uk-shop.test"

with open("/app/scripts/qa/tok_a") as f:
    TOKEN = f.read().strip()

# Attempt to fetch one settlement id for invoice test
try:
    import subprocess
    SETTLEMENT_ID = subprocess.check_output(
        ["psql", "postgresql://mse_migrator@127.0.0.1:5432/myshopedge", "-tAc",
         "select id from settlements limit 1"], text=True).strip() or None
except Exception:
    SETTLEMENT_ID = None


@pytest.fixture(scope="session")
def s():
    sess = requests.Session()
    sess.headers.update({
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
    })
    return sess


# ---------------- Rules ----------------
class TestRules:
    def test_rules_200_with_etag(self, s):
        r = s.get(f"{BASE}/rules")
        assert r.status_code == 200
        assert r.headers.get("ETag"), "ETag header missing"
        body = r.json()
        assert isinstance(body, (list, dict))

    def test_rules_filter_vat(self, s):
        r = s.get(f"{BASE}/rules?rule_set=vat")
        assert r.status_code == 200
        data = r.json()
        items = data if isinstance(data, list) else data.get("rules", data.get("items", []))
        # Each returned should reference vat
        for item in items:
            rs = item.get("rule_set") or item.get("set") or ""
            if rs:
                assert "vat" in rs.lower()

    def test_rules_requires_auth(self):
        r = requests.get(f"{BASE}/rules")
        assert r.status_code == 401


# ---------------- Tax dates ----------------
class TestTaxDates:
    def test_tax_dates_200(self, s):
        r = s.get(f"{BASE}/tax/dates?tax_year=2025")
        assert r.status_code == 200
        body = r.json()
        assert body.get("tax_year") in (2025, "2025", "2025-26", "2025/26")
        assert isinstance(body.get("dates"), list) and len(body["dates"]) >= 1
        d0 = body["dates"][0]
        for k in ("label", "date", "rule_key", "reviewed_at"):
            assert k in d0, f"missing {k} in tax date entry"


# ---------------- Quarterly check ----------------
class TestQuarterlyCheck:
    def test_above_threshold(self, s):
        # tax_year 2026 to pick up the MTD ITSA threshold (£50,000) effective from 2026-04-06
        r = s.post(f"{BASE}/tax/quarterly-check", json={
            "prior_year_gross": {"amount_minor": 15000000, "currency": "GBP"},
            "tax_year": 2026,
        })
        assert r.status_code == 200, r.text
        body = r.json()
        thresholds = body.get("thresholds", [])
        assert len(thresholds) >= 1, "expected at least one threshold row"
        assert any(t.get("above_threshold") is True for t in thresholds)

    def test_below_threshold(self, s):
        r = s.post(f"{BASE}/tax/quarterly-check", json={
            "prior_year_gross": {"amount_minor": 100000, "currency": "GBP"},
            "tax_year": 2026,
        })
        assert r.status_code == 200
        thresholds = r.json().get("thresholds", [])
        assert len(thresholds) >= 1
        assert all(t.get("above_threshold") is False for t in thresholds)

    def test_negative_gross_422(self, s):
        r = s.post(f"{BASE}/tax/quarterly-check", json={
            "prior_year_gross": {"amount_minor": -100, "currency": "GBP"},
            "tax_year": 2025,
        })
        assert r.status_code == 422


# ---------------- Alert settings ----------------
class TestAlertSettings:
    def test_get_defaults(self, s):
        r = s.get(f"{BASE}/shops/{SHOP_ID}/alert-settings")
        assert r.status_code == 200
        body = r.json()
        # defaults 14/7/20 when unset - accept any int values but keys must exist
        assert "low_stock_days" in body

    def test_put_and_echo(self, s):
        payload = {"low_stock_days": 10, "payout_delay_days": 5, "return_rate_percent": 15}
        r = s.put(f"{BASE}/shops/{SHOP_ID}/alert-settings", json=payload)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("low_stock_days") == 10
        # verify persistence
        r2 = s.get(f"{BASE}/shops/{SHOP_ID}/alert-settings")
        assert r2.json().get("low_stock_days") == 10

    def test_put_out_of_range_low_422(self, s):
        r = s.put(f"{BASE}/shops/{SHOP_ID}/alert-settings",
                  json={"low_stock_days": 0, "payout_delay_days": 7, "return_rate_percent": 20})
        assert r.status_code == 422

    def test_put_out_of_range_high_422(self, s):
        r = s.put(f"{BASE}/shops/{SHOP_ID}/alert-settings",
                  json={"low_stock_days": 999, "payout_delay_days": 7, "return_rate_percent": 20})
        assert r.status_code == 422


# ---------------- Velocity ----------------
class TestVelocity:
    def test_velocity_shape(self, s):
        r = s.get(f"{BASE}/shops/{SHOP_ID}/velocity?window_days=30")
        assert r.status_code == 200
        body = r.json()
        for k in ("window_days", "period", "average_daily_gross",
                  "average_daily_net_proceeds", "average_daily_units"):
            assert k in body, f"missing {k}"
        assert body["window_days"] == 30


# ---------------- Money where-it-went ----------------
class TestWhereItWent:
    def test_shape(self, s):
        r = s.get(f"{BASE}/shops/{SHOP_ID}/money/where-it-went")
        assert r.status_code == 200
        body = r.json()
        for k in ("period", "gross_sales", "lines"):
            assert k in body
        for line in body["lines"]:
            assert "pence_per_pound" in line
            assert isinstance(line["pence_per_pound"], int)


# ---------------- Month summary ----------------
class TestMonthSummary:
    def test_valid_month(self, s):
        r = s.get(f"{BASE}/shops/{SHOP_ID}/summary/2026-08")
        assert r.status_code == 200

    def test_invalid_month_422(self, s):
        r = s.get(f"{BASE}/shops/{SHOP_ID}/summary/2026-13")
        assert r.status_code == 422


# ---------------- Other sales ----------------
class TestOtherSales:
    def test_put_and_list(self, s):
        payload = {"channel": "eBay", "gross": {"amount_minor": 50000, "currency": "GBP"}}
        r = s.put(f"{BASE}/shops/{SHOP_ID}/other-sales/2026-06", json=payload)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("channel") == "eBay" or "eBay" in str(body)

        # List
        r2 = s.get(f"{BASE}/shops/{SHOP_ID}/other-sales")
        assert r2.status_code == 200
        listing = r2.json()
        assert isinstance(listing, (list, dict))

    def test_negative_gross_422(self, s):
        r = s.put(f"{BASE}/shops/{SHOP_ID}/other-sales/2026-06",
                  json={"channel": "eBay", "gross": {"amount_minor": -1, "currency": "GBP"}})
        assert r.status_code == 422


# ---------------- Settlement invoice ----------------
class TestSettlementInvoice:
    @pytest.mark.skipif(not SETTLEMENT_ID, reason="no settlement id available")
    def test_put_invoice(self, s):
        inv = f"INV-TEST-{uuid.uuid4().hex[:6]}"
        r = s.put(f"{BASE}/shops/{SHOP_ID}/settlements/{SETTLEMENT_ID}/invoice",
                  json={"invoice_number": inv})
        assert r.status_code == 200, r.text
        body = r.json()
        assert inv in str(body)

    def test_unknown_settlement_404(self, s):
        r = s.put(f"{BASE}/shops/{SHOP_ID}/settlements/{uuid.uuid4()}/invoice",
                  json={"invoice_number": "X"})
        assert r.status_code == 404

    @pytest.mark.skipif(not SETTLEMENT_ID, reason="no settlement id available")
    def test_empty_invoice_422(self, s):
        r = s.put(f"{BASE}/shops/{SHOP_ID}/settlements/{SETTLEMENT_ID}/invoice",
                  json={"invoice_number": ""})
        assert r.status_code == 422


# ---------------- Export (idempotency) ----------------
class TestExport:
    def test_short_key_422(self, s):
        r = s.post(f"{BASE}/me/export", headers={"Idempotency-Key": "abc"})
        assert r.status_code == 422

    def test_same_key_same_job(self, s):
        key = f"export-{uuid.uuid4().hex[:16]}"
        r1 = s.post(f"{BASE}/me/export", headers={"Idempotency-Key": key})
        assert r1.status_code == 202, r1.text
        j1 = r1.json()
        r2 = s.post(f"{BASE}/me/export", headers={"Idempotency-Key": key})
        assert r2.status_code == 202
        j2 = r2.json()
        id1 = j1.get("id") or j1.get("job_id")
        id2 = j2.get("id") or j2.get("job_id")
        assert id1 and id1 == id2


# ---------------- Tenancy / auth ----------------
class TestTenancy:
    def test_no_auth_401(self):
        r = requests.get(f"{BASE}/shops/{SHOP_ID}/alert-settings")
        assert r.status_code == 401

    def test_foreign_shop_403(self, s):
        r = s.get(f"{BASE}/shops/{FOREIGN_SHOP}/alert-settings")
        assert r.status_code == 403


# ---------------- DELETE /me guard (non-destructive path) ----------------
class TestDeleteMeGuard:
    def test_wrong_email_422(self, s):
        r = s.request("DELETE", f"{BASE}/me", json={"confirm_email": "wrong@example.com"})
        assert r.status_code == 422
        body = r.json()
        assert "confirm_email_mismatch" in str(body).lower() or "mismatch" in str(body).lower()


# ---------------- DESTRUCTIVE — connection disconnect + delete /me last ----------------
# These run last (alphabetical Zz prefix) then restore.

class TestZzDestructive:
    def test_disconnect_shop_idempotent(self, s):
        key = f"disc-{uuid.uuid4().hex[:16]}"
        r1 = s.delete(f"{BASE}/shops/{SHOP_ID}/connection",
                      headers={"Idempotency-Key": key})
        assert r1.status_code == 200, r1.text
        body = r1.json()
        assert body.get("connection_status") == "disconnected"
        assert body.get("data_retained") is True

        r2 = s.delete(f"{BASE}/shops/{SHOP_ID}/connection",
                      headers={"Idempotency-Key": key})
        assert r2.status_code == 200
        assert r2.json().get("connection_status") == "disconnected"

    def test_delete_me_success_last(self, s):
        r = s.request("DELETE", f"{BASE}/me", json={"confirm_email": ACCOUNT_EMAIL})
        assert r.status_code == 202, r.text
        body = r.json()
        assert "includes" in body and isinstance(body["includes"], list)

    @classmethod
    def teardown_class(cls):
        import subprocess
        subprocess.run([
            "psql", "postgresql://mse_migrator@127.0.0.1:5432/myshopedge", "-c",
            "update accounts set status='active', deleted_at=null; "
            "update shops set connection_status='connected'; "
            "update tiktok_connections set revoked_at=null; "
            "delete from idempotency_keys;"
        ], check=False)
