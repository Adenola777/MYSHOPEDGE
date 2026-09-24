/**
 * Stack Auth's own pages: sign in, sign up, the OAuth return, sign out.
 *
 * A14 section 14.3 rules that the provider hosts sign-in (S19) and that we brand it rather
 * than rebuild it. `StackHandler` in 2.8.108 takes its app from `StackProvider` in the root
 * layout; the `app` and `routeProps` props are marked deprecated in its own types.
 *
 * The OAuth return lands on /handler/oauth-callback on this domain, which is why
 * `https://my-shop-edge.vercel.app` was added to Neon Auth's trusted domains on
 * 24 September 2026.
 */

import { StackHandler } from "@stackframe/stack";
import { STACK_CONFIGURED } from "@/lib/stack";
import { Problem } from "@/components/ApiProblem";

export const metadata = { title: "Account" };

export default function Handler() {
  if (!STACK_CONFIGURED) {
    return (
      <Problem
        title="Sign-in is not set up on this copy of MyShopEdge."
        note="The Stack project id is not configured here, so nobody can sign in yet."
      />
    );
  }
  return <StackHandler fullPage />;
}
