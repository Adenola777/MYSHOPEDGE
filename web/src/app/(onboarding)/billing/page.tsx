/**
 * S33. Choose a plan and verify your card.
 *
 * This screen sits after the TikTok Shop connection in the onboarding order, because a
 * seller who cannot connect a shop has nothing to pay for. It is a server component. It
 * renders the plans and hands the card collection to a client component, which is the only
 * part of the screen that touches Stripe in the browser.
 */

import type { Metadata } from "next";
import { PLANS, PLAN_ORDER, TRIAL_DAYS, formatPrice } from "@/lib/plans";
import { PaymentForm } from "./PaymentForm";

export const metadata: Metadata = {
  title: "Start your free trial",
};

export default function BillingPage() {
  const trialEnds = new Date(Date.now() + TRIAL_DAYS * 86_400_000).toLocaleDateString(
    "en-GB",
    { day: "numeric", month: "long" },
  );

  return (
    <main className="billing">
      <header className="billing__head">
        <h1>Your shop is connected. Choose a plan to start.</h1>
        <p className="billing__lede">
          Every plan begins with {TRIAL_DAYS} days free. We verify your card now and take
          nothing until {trialEnds}. You can cancel before then and you will not be charged.
        </p>
      </header>

      <ol className="plans" aria-label="Plans">
        {PLAN_ORDER.map((slug) => {
          const plan = PLANS[slug];
          return (
            <li
              key={plan.slug}
              className={plan.highlight ? "plan plan--highlight" : "plan"}
              aria-current={plan.highlight ? "true" : undefined}
            >
              {plan.highlight ? <p className="plan__flag">Most chosen</p> : null}
              <h2 className="plan__name">{plan.name}</h2>
              <p className="plan__strapline">{plan.strapline}</p>
              <p className="plan__price">
                <span className="plan__amount">{formatPrice(plan)}</span>
                <span className="plan__period"> a month</span>
              </p>
              <p className="plan__limit">
                Up to {plan.orderLimit.toLocaleString("en-GB")} orders a month, and{" "}
                {plan.historyMonths} months of history.
              </p>
              <ul className="plan__features">
                {plan.features.map((feature) => (
                  <li key={feature}>{feature}</li>
                ))}
              </ul>
            </li>
          );
        })}
      </ol>

      <PaymentForm />

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
