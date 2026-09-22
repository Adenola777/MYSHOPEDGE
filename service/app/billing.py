"""Billing. The plans, the trial, and the Stripe webhook.

The trial is a Stripe Subscription created with a trial period and an incomplete payment
behaviour. Stripe returns a pending SetupIntent, the browser confirms it, and that
confirmation is where Strong Customer Authentication happens. Nothing is charged today.

Why a SetupIntent rather than a PaymentIntent or a small authorisation hold. Under the UK
SCA rules the card is authenticated at the moment it is saved, and the mandate recorded at
that moment is what allows the charge on day fifteen to be taken off session. A trial that
saves a card without authenticating it produces a first charge with no prior
authentication, and a meaningful share of UK issuers decline those.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Annotated, Literal

import stripe
from fastapi import APIRouter, Depends, Header, Request
from pydantic import BaseModel

from .auth import Account, require_account
from .money import Money, money
from .plans import PLAN_ORDER, PLANS, TRIAL_DAYS
from .problems import Problem

router = APIRouter(tags=["Billing"])


def _stripe() -> stripe.StripeClient:
    key = os.environ.get("STRIPE_SECRET_KEY")
    if not key:
        raise Problem(503, "billing_unconfigured", "Billing is not configured.")
    return stripe.StripeClient(key)


class PlanOut(BaseModel):
    slug: str
    name: str
    strapline: str
    price: Money
    order_limit: int
    history_months: int
    features: list[str]
    highlight: bool


class PlansOut(BaseModel):
    trial_days: int
    plans: list[PlanOut]


class TrialRequest(BaseModel):
    plan: Literal["starter", "growth", "pro"]


class TrialStart(BaseModel):
    status: Literal["requires_card", "trialing"]
    subscription_id: str
    trial_ends_at: str | None = None
    client_secret: str | None = None


@router.get("/billing/plans", response_model=PlansOut, summary="The plans on sale")
def list_plans() -> PlansOut:
    """The price is served rather than held in the client, so a price change does not
    require a client release. A plan lists only what the product does today."""
    return PlansOut(
        trial_days=TRIAL_DAYS,
        plans=[
            PlanOut(
                slug=p.slug,
                name=p.name,
                strapline=p.strapline,
                price=money(p.price_minor, p.currency),
                order_limit=p.order_limit,
                history_months=p.history_months,
                features=p.features,
                highlight=p.highlight,
            )
            for p in (PLANS[s] for s in PLAN_ORDER)
        ],
    )


@router.post("/billing/subscription", response_model=TrialStart, summary="Start the free trial")
def start_trial(
    body: TrialRequest,
    account: Annotated[Account, Depends(require_account)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> TrialStart:
    plan = PLANS[body.plan]

    # The price identifier comes from the environment. A price sent by a client is never
    # trusted, because a seller could otherwise start a Pro trial at the Starter price.
    price_id = os.environ.get(plan.price_env_var)
    if not price_id:
        raise Problem(503, "plan_unavailable", "This plan is not configured yet. Nobody has been charged.")

    client = _stripe()
    key = f"sub:{account.id}:{plan.slug}:{idempotency_key}" if idempotency_key else None

    try:
        customer = _find_or_create_customer(client, account, key)
        subscription = client.subscriptions.create(
            params={
                "customer": customer.id,
                "items": [{"price": price_id}],
                "trial_period_days": TRIAL_DAYS,
                "payment_behavior": "default_incomplete",
                "collection_method": "charge_automatically",
                "payment_settings": {
                    "save_default_payment_method": "on_subscription",
                    "payment_method_types": ["card"],
                },
                # A trial that reaches its end with no payment method is cancelled rather
                # than left owing. The seller keeps their data and is asked for a card.
                "trial_settings": {"end_behavior": {"missing_payment_method": "cancel"}},
                "expand": ["pending_setup_intent"],
                "metadata": {"account_id": account.id, "plan": plan.slug},
            },
            options={"idempotency_key": key} if key else None,
        )
    except stripe.CardError as exc:
        raise Problem(402, "card_declined", exc.user_message or "Your bank declined the card.") from exc
    except stripe.StripeError as exc:
        raise Problem(502, "stripe_error", "We could not start the trial. Nobody has been charged.") from exc

    intent = subscription.pending_setup_intent
    trial_ends = _iso(subscription.trial_end)

    # Stripe returns no setup intent when the customer already has a usable card on file.
    # That is a valid outcome and the trial has started.
    if intent is None or isinstance(intent, str) or not intent.client_secret:
        return TrialStart(status="trialing", subscription_id=subscription.id, trial_ends_at=trial_ends)

    return TrialStart(
        status="requires_card",
        subscription_id=subscription.id,
        trial_ends_at=trial_ends,
        client_secret=intent.client_secret,
    )


@router.post("/webhooks/stripe", summary="Stripe events", include_in_schema=True)
async def stripe_webhook(request: Request, stripe_signature: Annotated[str | None, Header(alias="Stripe-Signature")] = None):
    """Authenticated by the signature header rather than by a bearer token.

    Delivery is at least once and events can arrive out of order, so every handler is
    idempotent on the event id.
    """
    secret = os.environ.get("STRIPE_WEBHOOK_SECRET")
    if not secret or not stripe_signature:
        raise Problem(400, "signature_missing", "The signature did not verify.")

    payload = await request.body()
    try:
        event = stripe.Webhook.construct_event(payload, stripe_signature, secret)
    except Exception as exc:  # signature or payload failure
        raise Problem(400, "signature_invalid", "The signature did not verify.") from exc

    # invoice.payment_failed is the path towards a suspended account and it is the one
    # event a seller will feel. The handlers are written when the accounts table is wired.
    handled = {
        "invoice.payment_failed",
        "customer.subscription.updated",
        "customer.subscription.deleted",
    }
    if event["type"] in handled:
        pass  # Recorded here so the receiver is honest about what it does not yet do.

    return {"received": True}


def _find_or_create_customer(client: stripe.StripeClient, account: Account, key: str | None):
    found = client.customers.search(params={"query": f"metadata['account_id']:'{account.id}'", "limit": 1})
    if found.data:
        return found.data[0]
    return client.customers.create(
        params={"email": account.email, "name": account.name, "metadata": {"account_id": account.id}},
        options={"idempotency_key": f"cus:{key}"} if key else None,
    )


def _iso(seconds: int | None) -> str | None:
    if seconds is None:
        return None
    return datetime.fromtimestamp(seconds, tz=timezone.utc).isoformat()
