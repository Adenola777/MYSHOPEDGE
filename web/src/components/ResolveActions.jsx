"use client";

/**
 * The three actions on S14. The service decides what each one does (discrepancies.py) and
 * whether a correction is allowed, which arrives as `correctable`. Nothing here moves
 * money: under the current rulings no resolution does (0013 ruling 3, TC-DSC-04).
 */

import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";
import { newKey } from "@/lib/money-input";

/** @param {{ shopId: string, id: string, correctable: boolean }} props */
export function ResolveActions({ shopId, id, correctable }) {
  const router = useRouter();
  const [mode, setMode] = useState(/** @type {"" | "corrected_seller" | "explained"} */ (""));
  const [text, setText] = useState("");
  const [error, setError] = useState(/** @type {string | null} */ (null));
  const [busy, setBusy] = useState(false);

  /** @param {"accepted_tiktok" | "corrected_seller" | "explained"} resolution */
  async function send(resolution) {
    if (resolution === "corrected_seller" && text.trim() === "") {
      setError("Enter the corrected value.");
      return;
    }
    setBusy(true);
    setError(null);
    const body =
      resolution === "corrected_seller" ? { resolution, applied_value: text.trim() }
      : resolution === "explained" ? { resolution, note: text.trim() || undefined }
      : { resolution };
    const r = await api(`/shops/${encodeURIComponent(shopId)}/discrepancies/${encodeURIComponent(id)}/resolve`, {
      method: "POST",
      body: JSON.stringify(body),
      idempotencyKey: newKey(),
    });
    setBusy(false);
    if (!r.ok) {
      setError(r.unreachable ? "MyShopEdge could not be reached, so nothing was changed." : (r.data?.detail ?? "That did not go through."));
      return;
    }
    router.refresh();
  }

  return (
    <div className="stack" style={{ marginTop: "var(--space-4)" }}>
      {mode === "" ? (
        <div className="actions">
          <button className="btn btn--primary" disabled={busy} onClick={() => send("accepted_tiktok")}>
            Accept TikTok&rsquo;s value
          </button>
          {correctable && (
            <button className="btn btn--quiet" disabled={busy} onClick={() => setMode("corrected_seller")}>
              Correct my record
            </button>
          )}
          <button className="btn btn--quiet" disabled={busy} onClick={() => setMode("explained")}>
            Mark as explained
          </button>
        </div>
      ) : (
        <div className="stack">
          <label htmlFor={`r-${id}`}>
            {mode === "corrected_seller" ? "Your corrected record" : "What explains it"}
          </label>
          <input id={`r-${id}`} maxLength={1000} value={text} onChange={(e) => setText(e.target.value)} />
          <div className="actions">
            <button className="btn btn--primary" disabled={busy} onClick={() => send(mode)}>
              {busy ? "Saving" : "Save"}
            </button>
            <button className="btn btn--quiet" disabled={busy} onClick={() => { setMode(""); setText(""); setError(null); }}>
              Cancel
            </button>
          </div>
        </div>
      )}
      {error && <p className="form-error" role="alert">{error}</p>}
      <p className="rows__sub">Every action is logged.</p>
    </div>
  );
}
