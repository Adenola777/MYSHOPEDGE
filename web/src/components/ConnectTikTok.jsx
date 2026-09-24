"use client";

/**
 * The action on S1 Connect TikTok Shop. `authorizeTiktok` returns a link with a single use
 * state bound to this seller, valid for ten minutes, and the browser goes there.
 *
 * `return_to` is `/shops`, which the service accepts because it is a path with one leading
 * slash (`_safe_return_to` in connections.py).
 */

import { useState } from "react";
import { api } from "@/lib/api";

/** Wording for the refusals `authorize_tiktok` can give. Anything else shows its detail. */
const REFUSAL = {
  tiktok_unconfigured:
    "Connecting a TikTok Shop is not switched on yet. The TikTok app details are not set on the service.",
  unauthenticated: "Your session has ended. Sign in again, then connect your shop.",
};

export function ConnectTikTok() {
  const [error, setError] = useState(/** @type {string | null} */ (null));
  const [busy, setBusy] = useState(false);

  async function connect() {
    setBusy(true);
    setError(null);
    const r = await api("/connections/tiktok/authorize", {
      method: "POST",
      body: JSON.stringify({ return_to: "/shops" }),
    });
    if (r.ok && r.data?.authorization_url) {
      window.location.assign(r.data.authorization_url);
      return;
    }
    setBusy(false);
    if (r.unreachable) {
      setError("MyShopEdge could not be reached. Try again in a moment.");
      return;
    }
    const code = /** @type {keyof typeof REFUSAL} */ (r.data?.code);
    setError(REFUSAL[code] ?? r.data?.detail ?? "The connection could not be started.");
  }

  return (
    <div className="stack">
      {error && <p className="form-error" role="alert">{error}</p>}
      <p>
        <button className="btn btn--primary" type="button" onClick={connect} disabled={busy}>
          {busy ? "Opening TikTok Shop" : "Connect with TikTok Shop"}
        </button>
      </p>
      <p className="rows__sub">You approve access on TikTok&rsquo;s own page, then come back here.</p>
    </div>
  );
}
