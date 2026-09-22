/**
 * POST /api/billing/subscription
 *
 * Starts a 14 day trial and verifies the card without charging it.
 *
 * The shape is a Stripe Subscription created with a trial and an incomplete payment
 * behaviour. Stripe then returns a pending SetupIntent, the browser confirms that intent,
 * and the confirmation is where Strong Customer Authentication happens. Nothing is charged
 * until the trial ends.
 *
 * Why a SetupIntent rather than a PaymentIntent or a small authorisation hold. Under the
 * UK SCA rules the card is authenticated at the moment it is saved, and the mandate
 * recorded at that moment is what allows the charge on day fifteen to be taken off session.
 * A trial that saves a card without authenticating it produces a first charge with no prior
 * authentication, and a meaningful share of UK issuers decline those.
 *
 * If the seller abandons the screen the subscription stays incomplete and the trial does
 * not run, because trial_settings.end_behavior cancels a trial that never acquired a
 * payment method.
 */

import { NextRequest, NextResponse } from "next/server";
import Stripe from "stripe";
import { PLANS, TRIAL_DAYS, isPlanSlug } from "@/lib/plans";
import { stripe } from "@/lib/stripe";
import { requireAccount } from "@/lib/auth";

interface Body {
  plan?: unknown;
  /** Supplied by the browser so a retry does not create a second subscription. */
  idempotencyKey?: unknown;
}

export async function POST(request: NextRequest) {
  const account = await requireAccount(request);
  if (!account) {
    return problem(401, "unauthenticated", "Sign in before starting a trial.");
  }

  let body: Body;
  try {
    body = await request.json();
  } catch {
    return problem(400, "malformed_body", "The request body was not valid JSON.");
  }

  if (!isPlanSlug(body.plan)) {
    return problem(400, "unknown_plan", "Choose Starter, Growth or Pro.");
  }
  const plan = PLANS[body.plan];

  // The price identifier comes from the server environment. A price sent by a browser is
  // never trusted, because a seller could otherwise start a Pro trial at the Starter price.
  const priceId = process.env[plan.priceEnvVar];
  if (!priceId) {
    return problem(
      503,
      "plan_unavailable",
      "This plan is not configured yet. Nobody has been charged.",
    );
  }

  const idempotencyKey =
    typeof body.idempotencyKey === "string" && body.idempotencyKey.length > 0
      ? `sub:${account.id}:${plan.slug}:${body.idempotencyKey}`
      : undefined;

  try {
    const customer = await findOrCreateCustomer(account, idempotencyKey);

    const subscription = await stripe.subscriptions.create(
      {
        customer: customer.id,
        items: [{ price: priceId }],
        trial_period_days: TRIAL_DAYS,
        payment_behavior: "default_incomplete",
        collection_method: "charge_automatically",
        payment_settings: {
          save_default_payment_method: "on_subscription",
          payment_method_types: ["card"],
        },
        // A trial that reaches its end with no payment method is cancelled rather than
        // left owing. The seller keeps their data and is asked to add a card to continue.
        trial_settings: { end_behavior: { missing_payment_method: "cancel" } },
        // The VAT treatment of these prices is not settled. Until it is, tax is left to
        // the price configuration in Stripe rather than calculated here, so that a wrong
        // assumption cannot reach an invoice.
        expand: ["pending_setup_intent"],
        metadata: {
          account_id: account.id,
          plan: plan.slug,
        },
      },
      idempotencyKey ? { idempotencyKey } : undefined,
    );

    const setupIntent = subscription.pending_setup_intent;
    if (!setupIntent || typeof setupIntent === "string" || !setupIntent.client_secret) {
      // Stripe returns no setup intent when the customer already has a usable card on
      // file. That is a valid outcome and the trial has started.
      return NextResponse.json({
        status: "trialing",
        subscription_id: subscription.id,
        trial_ends_at: isoOrNull(subscription.trial_end),
        client_secret: null,
      });
    }

    return NextResponse.json({
      status: "requires_card",
      subscription_id: subscription.id,
      trial_ends_at: isoOrNull(subscription.trial_end),
      client_secret: setupIntent.client_secret,
    });
  } catch (error) {
    if (error instanceof Stripe.errors.StripeError) {
      // Stripe's own message is shown only when it is written for a cardholder.
      const detail =
        error.type === "StripeCardError"
          ? (error.message ?? "Your bank declined the card.")
          : "We could not start the trial. Nobody has been charged.";
      return problem(error.type === "StripeCardError" ? 402 : 502, "stripe_error", detail);
    }
    throw error;
  }
}

async function findOrCreateCustomer(
  account: { id: string; email: string; name: string | null },
  idempotencyKey: string | undefined,
) {
  const existing = await stripe.customers.search({
    query: `metadata['account_id']:'${account.id}'`,
    limit: 1,
  });
  const found = existing.data[0];
  if (found) {
    return found;
  }
  return stripe.customers.create(
    {
      email: account.email,
      name: account.name ?? undefined,
      metadata: { account_id: account.id },
    },
    idempotencyKey ? { idempotencyKey: `cus:${idempotencyKey}` } : undefined,
  );
}

function isoOrNull(seconds: number | null): string | null {
  return seconds === null ? null : new Date(seconds * 1000).toISOString();
}

/** RFC 9457 problem details, as the API contract requires. */
function problem(status: number, code: string, detail: string) {
  return NextResponse.json(
    { type: `https://api.myshopedge.com/problems/${code}`, title: code, status, detail, code },
    { status, headers: { "content-type": "application/problem+json" } },
  );
}
