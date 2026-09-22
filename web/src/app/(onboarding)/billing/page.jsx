/**
 * S33. Choose a plan and verify your card.
 *
 * This screen sits after the TikTok Shop connection in the onboarding order, because a
 * seller who cannot connect a shop has nothing to pay for.
 *
 * The plans and their prices come from the API. Nothing on this page holds a price.
 */

import { fetchPlans, formatMoney } from "@/lib/api";

/** @typedef {import("@/lib/api-types").components["schemas"]["Plan"]} Plan */
import { PaymentForm } from "./PaymentForm";

export const metadata = { title: "Start your free trial" };

export default async function BillingPage() {
  const payload = await fetchPlans();

  if (!payload) {
    return (
      <main className="billing">
        <h1>We cannot show the plans right now.</h1>
        <p>
          Your shop is connected and your data is safe. Try again in a few minutes, and
          nothing has been charged.
        </p>
      </main>
    );
  }

  const { trial_days: trialDays, plans } = payload;
  const trialEnds = new Date(Date.now() + trialDays * 86_400_000).toLocaleDateString(
    "en-GB",
    { day: "numeric", month: "long" },
  );

  return (
    <main className="billing">
      <header className="billing__head">
        <h1>Your shop is connected. Choose a plan to start.</h1>
        <p className="billing__lede">
          Every plan begins with {trialDays} days free. We verify your card now and take
          nothing until {trialEnds}. You can cancel before then and you will not be charged.
        </p>
      </header>

      <ol className="plans" aria-label="Plans">
        {plans.map((/** @type {Plan} */ plan) => (
          <li
            key={plan.slug}
            className={plan.highlight ? "plan plan--highlight" : "plan"}
            aria-current={plan.highlight ? "true" : undefined}
          >
            {plan.highlight ? <p className="plan__flag">Most chosen</p> : null}
            <h2 className="plan__name">{plan.name}</h2>
            <p className="plan__strapline">{plan.strapline}</p>
            <p className="plan__price">
              <span className="plan__amount">{formatMoney(plan.price)}</span>
              <span className="plan__period"> a month</span>
            </p>
            <p className="plan__limit">
              Up to {plan.order_limit.toLocaleString("en-GB")} orders a month, and{" "}
              {plan.history_months} months of history.
            </p>
            <ul className="plan__features">
              {plan.features.map((/** @type {string} */ feature) => (
                <li key={feature}>{feature}</li>
              ))}
            </ul>
          </li>
        ))}
      </ol>

      <PaymentForm plans={plans} trialDays={trialDays} />

      <footer className="billing__foot">
        <p>
          Your bank may ask you to confirm the card. That confirmation is what lets us take
          the first payment when the trial ends, so the step cannot be skipped.
        </p>
        <p>
          We store no card details. Stripe holds them and we hold a reference. You can change
          the card or cancel at any time in Settings.
        </p>
      </footer>
    </main>
  );
}
