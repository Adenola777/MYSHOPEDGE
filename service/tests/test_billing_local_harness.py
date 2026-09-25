"""Backend QA suite for MyShopEdge Stripe billing.

Covers:
- GET /v1/billing/plans
- POST /v1/billing/subscription (auth required, trial start)
- GET  /v1/billing/subscription
- POST /v1/webhooks/stripe (signed lifecycle events + idempotency + unknown customer + bad sig)
"""
from __future__ import annotations
import hashlib, hmac, json, os, time, uuid
import psycopg
import pytest
import requests

BASE = "http://127.0.0.1:8801"
MIG = "postgresql://mse_migrator:migpw_local@127.0.0.1:5432/myshopedge"

# Load .env manually so pytest can pick up Stripe secrets
def _load_env():
    p = "/app/service/.env"
    if os.path.exists(p):
        for line in open(p):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            v = v.strip().strip('"').strip("'")
            os.environ.setdefault(k.strip(), v)
_load_env()

TOK = open("/app/scripts/qa/tok_a").read().strip()
SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
STARTER = os.environ.get("STRIPE_PRICE_STARTER", "")


def db_row():
    with psycopg.connect(MIG) as c:
        r = c.execute(
            "select plan_slug,status,stripe_customer_id,stripe_subscription_id,trial_end,current_period_end from subscriptions"
        ).fetchone()
        return r


def _sign(payload: bytes):
    ts = int(time.time())
    sig = hmac.new(SECRET.encode(), f"{ts}.".encode() + payload, hashlib.sha256).hexdigest()
    return f"t={ts},v1={sig}"


def _sub_obj(status, cust, sid):
    now = int(time.time())
    return {
        "id": sid, "customer": cust, "status": status,
        "metadata": {"plan": "starter"},
        "trial_end": now + 10 * 86400,
        "current_period_start": now, "current_period_end": now + 10 * 86400,
        "cancel_at_period_end": False,
        "items": {"data": [{"price": {"id": STARTER},
                            "current_period_start": now,
                            "current_period_end": now + 10 * 86400}]},
    }


def _send_event(event):
    payload = json.dumps(event).encode()
    r = requests.post(f"{BASE}/v1/webhooks/stripe",
                      data=payload,
                      headers={"Content-Type": "application/json",
                               "Stripe-Signature": _sign(payload)},
                      timeout=30)
    return r


# ---------- Plans ----------
class TestPlans:
    def test_plans_no_auth(self):
        r = requests.get(f"{BASE}/v1/billing/plans", timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert d["trial_days"] == 14
        slugs = [p["slug"] for p in d["plans"]]
        assert slugs == ["starter", "growth", "pro"]
        prices = {p["slug"]: p["price"] for p in d["plans"]}
        assert prices["starter"] == {"amount_minor": 999, "currency": "GBP"}
        assert prices["growth"] == {"amount_minor": 2499, "currency": "GBP"}
        assert prices["pro"] == {"amount_minor": 4999, "currency": "GBP"}


# ---------- Auth ----------
class TestSubscriptionAuth:
    def test_start_trial_requires_bearer(self):
        r = requests.post(f"{BASE}/v1/billing/subscription",
                          json={"plan": "starter"},
                          headers={"Idempotency-Key": str(uuid.uuid4())},
                          timeout=15)
        assert r.status_code == 401


# ---------- Trial start + status ----------
class TestSubscriptionTrial:
    def test_start_trial_starter(self):
        r = requests.post(f"{BASE}/v1/billing/subscription",
                          json={"plan": "starter"},
                          headers={"Authorization": f"Bearer {TOK}",
                                   "Idempotency-Key": str(uuid.uuid4())},
                          timeout=60)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("status") in ("requires_card", "trialing"), d
        assert d.get("subscription_id"), d
        assert d.get("trial_ends_at"), d
        assert d.get("client_secret"), d

        row = db_row()
        assert row is not None
        plan_slug, status, cust, sid, trial_end, cpe = row
        assert status == "trialing", row
        assert cust and cust.startswith("cus_"), row
        assert sid and sid.startswith("sub_"), row
        assert trial_end is not None
        assert cpe is not None

    def test_get_subscription_returns_trialing(self):
        r = requests.get(f"{BASE}/v1/billing/subscription",
                         headers={"Authorization": f"Bearer {TOK}"},
                         timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("status") == "trialing", d
        assert d.get("plan") == "starter", d
        assert d.get("trial_ends_at"), d
        assert d.get("current_period_end"), d


# ---------- Webhook lifecycle ----------
class TestWebhookLifecycle:
    def _cust_sid(self):
        with psycopg.connect(MIG) as c:
            return c.execute(
                "select stripe_customer_id, stripe_subscription_id from subscriptions"
            ).fetchone()

    def test_past_due_and_idempotent(self):
        cust, sid = self._cust_sid()
        eid = f"evt_pastdue_{uuid.uuid4().hex[:8]}"
        r = _send_event({"id": eid, "type": "customer.subscription.updated",
                         "data": {"object": _sub_obj("past_due", cust, sid)}})
        assert r.status_code == 200, r.text
        assert db_row()[1] == "past_due"

        # replay
        r2 = _send_event({"id": eid, "type": "customer.subscription.updated",
                          "data": {"object": _sub_obj("past_due", cust, sid)}})
        assert r2.status_code == 200
        assert db_row()[1] == "past_due"

    def test_active_recovery(self):
        cust, sid = self._cust_sid()
        r = _send_event({"id": f"evt_active_{uuid.uuid4().hex[:8]}",
                         "type": "customer.subscription.updated",
                         "data": {"object": _sub_obj("active", cust, sid)}})
        assert r.status_code == 200
        assert db_row()[1] == "active"

    def test_canceled(self):
        cust, sid = self._cust_sid()
        r = _send_event({"id": f"evt_del_{uuid.uuid4().hex[:8]}",
                         "type": "customer.subscription.deleted",
                         "data": {"object": _sub_obj("canceled", cust, sid)}})
        assert r.status_code == 200
        assert db_row()[1] == "canceled"

    def test_unknown_customer_is_200_and_noop(self):
        before = db_row()[1]
        r = _send_event({"id": f"evt_unknown_{uuid.uuid4().hex[:8]}",
                         "type": "customer.subscription.updated",
                         "data": {"object": _sub_obj("active", "cus_does_not_exist", "sub_x")}})
        assert r.status_code == 200, r.text
        assert db_row()[1] == before

    def test_bad_signature_400(self):
        payload = b'{"id":"evt_bad","type":"customer.subscription.updated","data":{"object":{}}}'
        r = requests.post(f"{BASE}/v1/webhooks/stripe", data=payload,
                          headers={"Content-Type": "application/json",
                                   "Stripe-Signature": "t=1,v1=deadbeef"},
                          timeout=15)
        assert r.status_code == 400
