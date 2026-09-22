"""The three plans, and the single place they are defined.

A plan's price is never sent by a browser. The browser sends a slug, the service looks the
slug up here, and it uses the Stripe price identifier held in an environment variable. A
request carrying a price identifier is ignored.

Two lists exist on purpose. ``features`` holds what the product does today and is the only
list the sign-up screen renders. ``PENDING_SCOPE`` holds rows from the commercial price
sheet that the MVP does not yet have, recorded so they are not forgotten and not
advertised. Nothing moves from the second list to the first until the feature exists and is
tested.
"""

from __future__ import annotations

from dataclasses import dataclass, field

TRIAL_DAYS = 14


@dataclass(frozen=True)
class Plan:
    slug: str
    name: str
    strapline: str
    price_minor: int          # integer minor units, rule 3
    currency: str
    order_limit: int
    history_months: int
    highlight: bool
    price_env_var: str
    features: list[str] = field(default_factory=list)


PLANS: dict[str, Plan] = {
    "starter": Plan(
        slug="starter",
        name="Starter",
        strapline="Know your numbers.",
        price_minor=999,
        currency="GBP",
        order_limit=100,
        history_months=24,
        highlight=False,
        price_env_var="STRIPE_PRICE_STARTER",
        features=[
            "One TikTok Shop connection",
            "Sales, fees and payouts, reconciled to every statement",
            "Refunds and returns, with the stock effect of each",
            "Product costs, uploaded or typed",
            "Gross profit after returns, calculated line by line",
            "Stock levels and what runs out first",
            "VAT threshold tracking and set-aside guidance",
        ],
    ),
    "growth": Plan(
        slug="growth",
        name="Growth",
        strapline="Understand your business.",
        price_minor=2499,
        currency="GBP",
        order_limit=500,
        history_months=24,
        highlight=True,
        price_env_var="STRIPE_PRICE_GROWTH",
        features=[
            "Everything in Starter",
            "Up to 500 orders a month",
            "Profit by product and by variant",
            "Every transaction behind any figure",
            "Exports on a sales basis or a cash basis",
            "Priority support",
        ],
    ),
    "pro": Plan(
        slug="pro",
        name="Pro",
        strapline="Scale with confidence.",
        price_minor=4999,
        currency="GBP",
        order_limit=2000,
        history_months=24,
        highlight=False,
        price_env_var="STRIPE_PRICE_PRO",
        features=[
            "Everything in Growth",
            "Up to 2,000 orders a month",
            "Scheduled exports",
            "Priority support",
        ],
    ),
}

PLAN_ORDER = ["starter", "growth", "pro"]

# Rows from the commercial price sheet of 22 September 2026 that the MVP does not have.
# None of these is served to a client. Each needs a specification, a schema change and a
# test before it can be sold.
# Ruled out of the MVP on 22 September 2026. These are not pending decisions any more.
# They are recorded here so that nobody advertises them and nobody quietly builds them.
OUT_OF_MVP = [
    "Expense tracking. The product does not collect overheads, ruled in A8. There is no "
    "table, screen or endpoint.",
    "Multiple stores and channels. PRD 6.2 excludes multi-shop and A12.7 states the "
    "interface must not expose it.",
    "Profit and loss reporting. It appears nowhere in the specification pack.",
    "Advanced analytics. Nothing is named, so nothing can be built or tested.",
]

# Kept under the old name so nothing that imports it breaks.
PENDING_SCOPE = OUT_OF_MVP

# Ruled in on 22 September 2026, and not built yet. Unlike the list above, these are work.
#
# The order limit is the one with a design question still attached. Counting orders is
# straightforward. What happens when a seller passes the limit is not, and until that is
# settled the quota cannot be built, because a counter with no defined consequence is not
# enforcement. See A16.
IN_SCOPE_NOT_BUILT = [
    "Order limits as an enforced quota. Nothing counts orders per billing period yet, so "
    "100, 500 and 2,000 are commitments rather than controls.",
]
