"""Verify the Stripe webhook handlers against the running local service. QA harness only.

Signs events with STRIPE_WEBHOOK_SECRET exactly as Stripe does, POSTs them to the real
service, and asserts the subscriptions row after each. Not a mock: the handler runs, the
signature is verified, and the SECURITY DEFINER write path updates the real database.
"""
from __future__ import annotations
import hashlib, hmac, json, os, time, urllib.request, urllib.error
import psycopg

SVC = "http://127.0.0.1:8801/v1/webhooks/stripe"
MIG = "postgresql://mse_migrator:migpw_local@127.0.0.1:5432/myshopedge"
SECRET = os.environ["STRIPE_WEBHOOK_SECRET"]
STARTER = os.environ["STRIPE_PRICE_STARTER"]

def customer_id() -> str:
    with psycopg.connect(MIG) as c:
        return c.execute("select stripe_customer_id from subscriptions").fetchone()[0]

def sub_id() -> str:
    with psycopg.connect(MIG) as c:
        return c.execute("select stripe_subscription_id from subscriptions").fetchone()[0]

def row_status() -> str:
    with psycopg.connect(MIG) as c:
        return c.execute("select status from subscriptions").fetchone()[0]

def send(event: dict) -> tuple[int, str]:
    payload = json.dumps(event).encode()
    ts = int(time.time())
    signed = f"{ts}.".encode() + payload
    sig = hmac.new(SECRET.encode(), signed, hashlib.sha256).hexdigest()
    header = f"t={ts},v1={sig}"
    req = urllib.request.Request(SVC, data=payload, method="POST",
        headers={"Content-Type": "application/json", "Stripe-Signature": header})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()

def subscription_object(status: str, cust: str, sid: str) -> dict:
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

def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        raise SystemExit(1)

def main():
    cust, sid = customer_id(), sub_id()
    print("customer:", cust, "subscription:", sid, "start status:", row_status())

    # 1. subscription.updated -> past_due
    code, _ = send({"id": "evt_1", "type": "customer.subscription.updated",
                    "data": {"object": subscription_object("past_due", cust, sid)}})
    check("subscription.updated(past_due) returns 200", code == 200)
    check("row is past_due after the event", row_status() == "past_due")

    # 2. replay the same event -> still past_due (idempotent)
    send({"id": "evt_1", "type": "customer.subscription.updated",
          "data": {"object": subscription_object("past_due", cust, sid)}})
    check("replay leaves row at past_due (idempotent)", row_status() == "past_due")

    # 3. invoice.payment_failed with a customer and no subscription -> past_due
    code, _ = send({"id": "evt_2", "type": "invoice.payment_failed",
                    "data": {"object": {"id": "in_1", "customer": cust}}})
    check("invoice.payment_failed returns 200", code == 200)
    check("row remains past_due", row_status() == "past_due")

    # 4. subscription.updated -> active (recovery)
    code, _ = send({"id": "evt_3", "type": "customer.subscription.updated",
                    "data": {"object": subscription_object("active", cust, sid)}})
    check("row recovers to active", row_status() == "active")

    # 5. subscription.deleted -> canceled
    code, _ = send({"id": "evt_4", "type": "customer.subscription.deleted",
                    "data": {"object": subscription_object("canceled", cust, sid)}})
    check("subscription.deleted moves row to canceled", row_status() == "canceled")

    # 6. an event for an unknown customer is accepted with 200 and changes nothing
    before = row_status()
    code, body = send({"id": "evt_5", "type": "customer.subscription.updated",
                       "data": {"object": subscription_object("active", "cus_does_not_exist", "sub_x")}})
    check("unknown customer returns 200 (not a 500)", code == 200)
    check("unknown customer leaves our row unchanged", row_status() == before)

    # 7. a bad signature is refused with 400
    payload = b'{"id":"evt_6","type":"customer.subscription.updated","data":{"object":{}}}'
    req = urllib.request.Request(SVC, data=payload, method="POST",
        headers={"Content-Type": "application/json", "Stripe-Signature": "t=1,v1=deadbeef"})
    try:
        urllib.request.urlopen(req, timeout=30); code = 200
    except urllib.error.HTTPError as e:
        code = e.code
    check("a forged signature is refused with 400", code == 400)

    print("\nALL WEBHOOK CHECKS PASSED")

if __name__ == "__main__":
    main()
