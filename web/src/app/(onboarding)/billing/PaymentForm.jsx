"use client";

/**
 * The card half of S33.
 *
 * Two steps, and the second one is the important one.
 *
 *   1. Ask the API for a subscription. It creates one with a trial and an incomplete
 *      payment behaviour, and returns the client secret of a SetupIntent.
 *   2. Confirm that SetupIntent in the browser. This is where the bank may present a
 *      challenge, and where the mandate for later off session charges is recorded.
 *
 * The component never sees a price and never sends one. It sends a plan slug.
 *
 * @typedef {import("@/lib/api-types").components["schemas"]} Schemas
 * @typedef {Schemas["Plan"]} Plan
 */

import { useCallback, useMemo, useState } from "react";
import { loadStripe } from "@stripe/stripe-js";
import { Elements, PaymentElement, useElements, useStripe } from "@stripe/react-stripe-js";
import { api, formatMoney } from "@/lib/api";

const stripePromise = loadStripe(
  /** @type {string} */ (process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY),
);

/**
 * @param {{ plans: Plan[], trialDays: number }} props
 */
export function PaymentForm({ plans, trialDays }) {
  const preferred = plans.find((p) => p.highlight) ?? plans[0];
  const [slug, setSlug] = useState(preferred ? preferred.slug : "");
  const [phase, setPhase] = useState(
    /** @type {"choosing" | "collecting" | "done"} */ ("choosing"),
  );
  const [clientSecret, setClientSecret] = useState(/** @type {string | null} */ (null));
  const [error, setError] = useState(/** @type {string | null} */ (null));
  const [busy, setBusy] = useState(false);

  // Held for the life of the component so a retry after a dropped connection does not
  // create a second subscription.
  const idempotencyKey = useMemo(() => crypto.randomUUID(), []);

  const chosen = plans.find((p) => p.slug === slug);

  const start = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const { ok, data } = await api("/billing/subscription", {
        method: "POST",
        body: JSON.stringify({ plan: slug }),
        idempotencyKey,
      });
      if (!ok) {
        setError(data?.detail ?? "We could not start the trial.");
        return;
      }
      if (data.status === "trialing") {
        setPhase("done");
        return;
      }
      setClientSecret(data.client_secret);
      setPhase("collecting");
    } catch {
      setError("We could not reach the server. Nobody has been charged.");
    } finally {
      setBusy(false);
    }
  }, [slug, idempotencyKey]);

  if (phase === "done") {
    return (
      <section className="card-step" aria-live="polite">
        <h2>Your trial has started.</h2>
        <p>
          You have {trialDays} days on {chosen ? chosen.name : "your plan"}. We will email
          you three days before the first payment.
        </p>
      </section>
    );
  }

  return (
    <section className="card-step">
      <h2>Start your free trial</h2>

      <fieldset className="plan-choice" disabled={phase === "collecting"}>
        <legend>Plan</legend>
        {plans.map((plan) => (
          <label key={plan.slug} className="plan-choice__option">
            <input
              type="radio"
              name="plan"
              value={plan.slug}
              checked={slug === plan.slug}
              onChange={() => setSlug(plan.slug)}
            />
            <span>
              {plan.name}, {formatMoney(plan.price)} a month after the trial
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
          <ConfirmCard
            planName={chosen ? chosen.name : "your plan"}
            trialDays={trialDays}
            onDone={() => setPhase("done")}
          />
        </Elements>
      ) : null}
    </section>
  );
}

/**
 * @param {{ planName: string, trialDays: number, onDone: () => void }} props
 */
function ConfirmCard({ planName, trialDays, onDone }) {
  const stripe = useStripe();
  const elements = useElements();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(/** @type {string | null} */ (null));

  /** @param {{ preventDefault: () => void }} event */
  async function submit(event) {
    event.preventDefault();
    if (!stripe || !elements) return;
    setBusy(true);
    setError(null);

    // redirect "if_required" keeps the seller on this screen unless their bank insists on
    // a redirect for the authentication challenge.
    const result = await stripe.confirmSetup({
      elements,
      confirmParams: { return_url: `${window.location.origin}/billing/confirmed` },
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
        {busy ? "Confirming with your bank" : `Start ${planName} free for ${trialDays} days`}
      </button>
    </form>
  );
}
