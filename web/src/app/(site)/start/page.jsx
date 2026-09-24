/**
 * S17 Start. The first thing a seller sees, in our name and our words, before the provider.
 *
 * A14 section 14.3: the logo, the tagline, one sentence saying what happens next, and two
 * actions, "Create an account" and "Sign in", which both hand off to the identity provider.
 * No password field appears here, because we never receive one. The logo and the tagline
 * are the masthead the root layout already draws.
 *
 * A15 section 15.3 folds the old S18 wait into this screen. A seller who is already signed in
 * is sent straight to their shops, so the wait never needs a page of its own.
 *
 * **Not yet as A14 specifies.** A14 requires links to the privacy notice and the terms below
 * the actions, and section 11 of the Data Protection Document requires the privacy notice.
 * Neither page exists anywhere in this repository or at a known address, so no link is drawn
 * rather than a link to nothing. This must be closed before a real seller is invited.
 *
 * The three providers switched on in Neon Auth on 24 September 2026 are Google, GitHub and
 * Microsoft. Email and password sign-in is off. The provider's page shows whichever are on.
 */

import { redirect } from "next/navigation";
import { STACK_CONFIGURED, currentUser } from "@/lib/stack";
import { Problem } from "@/components/ApiProblem";

export const metadata = { title: "Start" };
export const dynamic = "force-dynamic";

export default async function StartPage() {
  if (!STACK_CONFIGURED) {
    return (
      <Problem
        title="Sign-in is not set up on this copy of MyShopEdge."
        note="The Stack project id is not configured here, so nobody can sign in yet."
      />
    );
  }

  if (await currentUser()) redirect("/shops");

  return (
    <section className="start">
      {/* A7.7: the sign-in and sign-up screens carry the horizontal lockup with the tagline.
          A7.6 allows it from 180 px wide; it is drawn at 240. */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img className="start__logo" src="/brand/mse-logo-horizontal.svg" alt="MyShopEdge, Know Your Numbers" width={240} height={89} />
      <h1>See what your TikTok Shop actually earned.</h1>
      <p className="muted">
        You create an account or sign in with Google, GitHub or Microsoft. After that you
        connect your TikTok Shop, and MyShopEdge reads your orders, returns and statements.
      </p>
      <div className="stack" style={{ maxWidth: 360, margin: "0 auto" }}>
        <a className="btn btn--primary btn--block" href="/handler/sign-up">Create an account</a>
        <a className="btn btn--quiet btn--block" href="/handler/sign-in">Sign in</a>
      </div>
    </section>
  );
}
