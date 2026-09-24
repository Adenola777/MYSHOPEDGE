/**
 * Where TikTok sends a seller back after they approve MyShopEdge.
 *
 * TikTok redirects the browser here with `code` and `state`. This page, on the server, hands
 * both to the service's `tiktokCallback`, which spends the state, exchanges the code, stores
 * the encrypted tokens and creates the shop, then tells the seller what happened in words.
 *
 * Why the redirect lands here and not on the service. The service answers `tiktokCallback`
 * with JSON, as the contract says, so a browser sent straight to it shows the seller a page
 * of raw data. Landing here keeps the contract as it is and gives the seller a screen. The
 * callback URL registered in TikTok Partner Center must therefore be
 * `https://my-shop-edge.vercel.app/connections/tiktok/callback`. That is the path the
 * runbook named on 23 September before any code existed.
 *
 * The page is not behind sign-in, because `tiktokCallback` carries `security: []`: the
 * state is what binds the result to the seller who started it.
 *
 * **Unverified against TikTok.** No real authorisation has passed through this page. What
 * TikTok puts in the address when a seller declines is not recorded in A23, so any arrival
 * without both `code` and `state` is treated as a connection that did not complete.
 */

import Link from "next/link";
import { api } from "@/lib/api";
import { Problem } from "@/components/ApiProblem";

export const metadata = { title: "Connecting your shop" };
export const dynamic = "force-dynamic";

/** What each refusal from `tiktok_callback` means to a seller. */
const REFUSAL = {
  state_invalid: [
    "That connection link has expired.",
    "A connection link lasts ten minutes and works once. Start the connection again.",
  ],
  not_a_seller_account: [
    "That TikTok account is not a Shop seller account.",
    "Sign in to TikTok with the account that owns your shop, then start again.",
  ],
  no_authorised_shop: [
    "No shop was shared with MyShopEdge.",
    "TikTok did not return a shop for that account. Start again and approve your shop.",
  ],
  shop_already_connected: [
    "That shop is already connected to another MyShopEdge account.",
    "Each shop can belong to one account. Sign in with the account that connected it.",
  ],
  tiktok_unconfigured: [
    "Connecting a TikTok Shop is not switched on yet.",
    "The TikTok app details are not set on the service, so nothing was connected.",
  ],
  token_encryption_unconfigured: [
    "Connecting a TikTok Shop is not switched on yet.",
    "The key that protects your TikTok access is not set on the service, so nothing was stored.",
  ],
};

/** Why a connected shop cannot produce figures, from `rejection_reason`. */
const NOT_SUPPORTED = {
  region_unsupported: "MyShopEdge reads UK shops only, and this shop is registered elsewhere.",
  seller_type_unsupported:
    "MyShopEdge reads shops that sell locally in the UK, and this shop sells cross border.",
};

/** @param {{ searchParams: Promise<Record<string, string>> }} props */
export default async function TikTokCallbackPage({ searchParams }) {
  const { code, state } = await searchParams;

  if (!code || !state) {
    return (
      <Problem
        title="The connection was not completed."
        note="TikTok sent you back without approving access, so nothing was connected. You can start again whenever you like."
        startAgain
      />
    );
  }

  const qs = new URLSearchParams({ code, state }).toString();
  const result = await api(`/connections/tiktok/callback?${qs}`, {
    cache: "no-store",
    timeoutMs: 45000,
  });

  if (result.unreachable) {
    return (
      <Problem
        title="MyShopEdge could not be reached."
        note="Your approval may not have been saved. Start the connection again in a moment."
        startAgain
      />
    );
  }

  if (!result.ok) {
    const code = /** @type {keyof typeof REFUSAL} */ (result.data?.code);
    const [title, note] = /** @type {[string, string]} */ (REFUSAL[code] ?? [
      "The shop could not be connected.",
      result.data?.detail ?? "MyShopEdge answered with an error, so nothing was connected.",
    ]);
    return <Problem title={title} note={note} startAgain />;
  }

  /** @type {{ shop: any, accepted: boolean, rejection_reason: string | null }} */
  const { shop, accepted, rejection_reason } = result.data;
  const name = shop?.shop_name ?? shop?.tiktok_shop_id ?? "Your shop";

  if (!accepted) {
    const reason = /** @type {keyof typeof NOT_SUPPORTED} */ (rejection_reason);
    return (
      <section className="state">
        <h1>{name} is connected, but MyShopEdge cannot read it.</h1>
        <p>{NOT_SUPPORTED[reason] ?? "This kind of shop is not supported yet."}</p>
      </section>
    );
  }

  return (
    <section className="state">
      <h1>{name} is connected.</h1>
      <p>
        MyShopEdge now holds read-only access to your shop. Reading your orders, returns and
        statements is not switched on yet, so no figures appear until it is.
      </p>
      <p>
        <Link className="btn btn--primary" href="/shops">Go to your shop</Link>
      </p>
    </section>
  );
}
