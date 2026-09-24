/**
 * S34. Payment confirmed.
 *
 * Where a seller lands after their bank takes them away for a 3D Secure challenge.
 *
 * S33 confirms the card in place where the bank allows it, using redirect "if_required".
 * Where the bank insists on a redirect, the seller leaves the site and comes back here.
 * Until A14 this route did not exist, so that seller reached a 404 with their card already
 * verified and no way to know it had worked.
 *
 * Stripe appends setup_intent and redirect_status to the return URL. The status in the URL
 * is a hint for what to show first and nothing more. It arrives from the browser, so it is
 * never trusted as the record of what happened: the subscription state comes from the API.
 */

import Link from "next/link";
import { api } from "@/lib/api";

export const metadata = { title: "Payment confirmed" };

/**
 * @param {{ searchParams: Promise<Record<string, string | undefined>> }} props
 */
export default async function ConfirmedPage({ searchParams }) {
  const params = await searchParams;
  const hint = params.redirect_status;

  const { ok, data } = await api("/billing/subscription", { cache: "no-store" });
  const status = ok && data ? data.status : null;

  if (status === "trialing" || status === "active") {
    const firstPayment = data.trial_ends_at
      ? new Date(data.trial_ends_at).toLocaleDateString("en-GB", {
          day: "numeric",
          month: "long",
        })
      : null;
    return (
      <main className="confirmed">
        <h1>Your card is confirmed and your trial has started.</h1>
        {firstPayment ? (
          <p>
            We take nothing until {firstPayment}. We will email you three days before that.
          </p>
        ) : (
          <p>We will email you three days before the first payment.</p>
        )}
        <Link className="primary" href="/">
          Continue
        </Link>
      </main>
    );
  }

  if (hint === "failed" || status === "past_due") {
    return (
      <main className="confirmed">
        <h1>Your bank did not confirm the card.</h1>
        <p>
          Nothing has been charged. Banks refuse for ordinary reasons, and trying again
          usually works.
        </p>
        <Link className="primary" href="/billing">
          Try the card again
        </Link>
      </main>
    );
  }

  // Reloaded later, or arrived with no setup in progress. Showing the real state is more
  // useful than an error about a page that was only ever a staging post.
  return (
    <main className="confirmed">
      <h1>There is nothing waiting to be confirmed.</h1>
      <p>
        {status === "none" || status === null
          ? "You have not started a trial yet."
          : `Your subscription is ${status}.`}
      </p>
      <Link className="primary" href="/billing">
        Go to your plan
      </Link>
    </main>
  );
}
