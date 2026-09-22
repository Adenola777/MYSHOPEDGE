"""Creates the three products and the three prices, from app/plans.py.

Run it once against a sandbox, then once against live when the prices are settled.

    STRIPE_SECRET_KEY=sk_test_... python3 scripts/setup_stripe.py

It is idempotent. Each product carries metadata['plan'] and each price carries a lookup key
derived from the slug, so running it twice finds what it created the first time rather than
making a duplicate. A Stripe price cannot be edited once created, so changing an amount
archives the old price and the new one claims the lookup key. Sellers already on the old
price stay on it until they are explicitly migrated.

The secret key is read from the environment. It is never printed and never written to a
file. The output is the three environment variables to set where the service runs.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import stripe  # noqa: E402

from app.plans import PLAN_ORDER, PLANS, TRIAL_DAYS  # noqa: E402


def main() -> int:
    key = os.environ.get("STRIPE_SECRET_KEY")
    if not key:
        print("STRIPE_SECRET_KEY is not set.", file=sys.stderr)
        return 1

    if key.startswith("sk_live_"):
        print("This key is a live key. Products and prices created here are real.")
        if os.environ.get("I_MEAN_LIVE") != "yes":
            print("Refusing to write to a live account. Set I_MEAN_LIVE=yes to proceed.", file=sys.stderr)
            return 1

    client = stripe.StripeClient(key)
    results: list[tuple[str, str]] = []

    for slug in PLAN_ORDER:
        plan = PLANS[slug]
        lookup_key = f"myshopedge_{plan.slug}_gbp_monthly"

        product = _find_or_create_product(client, plan.slug, plan.name, plan.strapline)
        price, created = _find_or_create_price(
            client, product.id, lookup_key, plan.price_minor, plan.currency
        )
        results.append((plan.price_env_var, price.id))
        print(f"{plan.name:<8} {product.id}  {price.id}  {'created' if created else 'existing'}")

    print(f"\nThe trial is {TRIAL_DAYS} days and it is set on the subscription, not on the")
    print("price, so it does not appear here.\n")
    print("Set these where the service runs:\n")
    for env_var, price_id in results:
        print(f"{env_var}={price_id}")
    print("\nThe VAT treatment of these prices is not settled. Set tax_behavior on each")
    print("price before anyone subscribes, because it cannot be changed afterwards.")
    return 0


def _find_or_create_product(client: stripe.StripeClient, slug: str, name: str, description: str):
    found = client.products.search(params={"query": f"metadata['plan']:'{slug}'", "limit": 1})
    if found.data:
        return found.data[0]
    return client.products.create(
        params={"name": f"MyShopEdge {name}", "description": description, "metadata": {"plan": slug}}
    )


def _find_or_create_price(
    client: stripe.StripeClient, product_id: str, lookup_key: str, unit_amount: int, currency: str
):
    found = client.prices.list(params={"lookup_keys": [lookup_key], "active": True, "limit": 1})
    existing = found.data[0] if found.data else None

    if existing is not None:
        if existing.unit_amount == unit_amount and existing.currency == currency.lower():
            return existing, False
        client.prices.update(existing.id, params={"active": False})

    price = client.prices.create(
        params={
            "product": product_id,
            "currency": currency.lower(),
            "unit_amount": unit_amount,
            "recurring": {"interval": "month"},
            "lookup_key": lookup_key,
            "transfer_lookup_key": True,
        }
    )
    return price, True


if __name__ == "__main__":
    raise SystemExit(main())
