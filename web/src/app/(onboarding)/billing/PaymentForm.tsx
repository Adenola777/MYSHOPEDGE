"use client";

/**
 * The card half of S33.
 *
 * The flow is two steps and the second one is the important one.
 *
 *   1. Ask the server for a subscription. The server creates it with a 14 day trial and an
 *      incomplete payment behaviour, and returns the client secret of a SetupIntent.
 *   2. Confirm that SetupIntent in the browser. This is where the bank may present a
 *      challenge, and where the mandate for later off session charges is recorded.
 *
 * The component never sees a price and never sends one. It sends a plan slug.
 */

import { useCallback, useMemo, useState } from "react";
import { loadStripe } from "@stripe/stripe-js";
import {
  Elements,
  PaymentElement,
  useElements,
  useStripe,
} from "@stripe/react-stripe-js";
import { PLANS, PLAN_ORDER, TRIAL_DAYS, formatPrice, type PlanSlug } from "@/lib/plans";

const stripePromise = loadStripe(process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY!);

type Phase = "choosing" | "collecting" | "done";

export function PaymentForm() {
  const [plan, setPlan] = useState<PlanSlug>("growth");
  const [phase, setPhase] = useState<Phase>("choosing");
  const [clientSecret, setClientSecret] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Held for the life of the component so a retry after a network failure does not create
  // a second subscription.
  const idempotencyKey = useMemo(() => crypto.randomUUID(), []);

  const start = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const response = await fetch("/api/billing/subscription", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ plan, idempotencyKey }),
      });
      const payload = await response.json();
      if (!response.ok) {
        setError(payload.detail ?? "We could not start the trial.");
        return;
      }
      if (payload.status === "trialing") {
        setPhase("done");
        return;
      }
      setClientSecret(payload.client_secret);
      setPhase("collecting");
    } catch {
      setError("We could not reach the server. Nobody has been charged.");
    } finally {
      setBusy(false);
    }
  }, [plan, idempotencyKey]);

  if (phase === "done") {
    return (
      <section className="card-step" aria-live="polite">
        <h2>Your trial has started.</h2>
        <p>
          You have {TRIAL_DAYS} days on {PLANS[plan].name}. We will email you three days
          before the first payment.
        </p>
      </section>
    );
  }

  return (
    <section className="card-step">
      <h2>Start your free trial</h2>

      <fieldset className="plan-choice" disabled={phase === "collecting"}>
        <legend>Plan</legend>
        {PLAN_ORDER.map((slug) => (
          <label key={slug} className="plan-choice__option">
            <input
              type="radio"
              name="plan"
              value={slug}
              checked={plan === slug}
              onChange={() => setPlan(slug)}
            />
            <span>
              {PLANS[slug].name}, {formatPrice(PLANS[slug])} a month after the trial
            </span>
          </label>
        ))}
      </fieldset>

      {error ? (
        <p className="error" role="alert">
          {error}
        </p>
      ) : null}

      {phase === "choosing" ? (
        <button type="button" className="primary" onClick={start} disabled={busy}>
          {busy ? "One moment" : "Continue to card details"}
        </button>
      ) : null}

      {phase === "collecting" && clientSecret ? (
        <Elements
          stripe={stripePromise}
          options={{
            clientSecret,
            appearance: { theme: "flat", variables: { colorPrimary: "#C4400C" } },
          }}
        >
          <ConfirmCard planName={PLANS[plan].name} onDone={() => setPhase("done")} />
        </Elements>
      ) : null}
    </section>
  );
}

function ConfirmCard({ planName, onDone }: { planName: string; onDone: () => void }) {
  const stripe = useStripe();
  const elements = useElements();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!stripe || !elements) return;
    setBusy(true);
    setError(null);

    // redirect: "if_required" keeps the seller on this screen unless their bank insists on
    // a redirect for the authentication challenge.
    const result = await stripe.confirmSetup({
      elements,
      confirmParams: {
        return_url: `${window.location.origin}/billing/confirmed`,
      },
      redirect: "if_required",
    });

    if (result.error) {
      setError(result.error.message ?? "Your bank did not confirm the card.");
      setBusy(false);
      return;
    }
    onDone();
  }

  return (
    <form onSubmit={submit} className="card-form">
      <p className="card-form__note">
        We verify the card now and charge nothing today. Your bank may ask you to confirm.
      </p>
      <PaymentElement options={{ layout: "tabs" }} />
      {error ? (
        <p className="error" role="alert">
          {error}
        </p>
      ) : null}
      <button type="submit" className="primary" disabled={!stripe || busy}>
        {busy ? "Confirming with your bank" : `Start ${planName} free for ${TRIAL_DAYS} days`}
      </button>
    </form>
  );
}
