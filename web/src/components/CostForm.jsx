"use client";

/**
 * S21, add or change one variant's cost price. The service keeps the old cost and stamps it
 * superseded (CST-4), so saving here never overwrites a cost.
 */

import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";
import { newKey, parsePounds } from "@/lib/money-input";

/** @param {{ shopId: string, skuId: string, currency?: string }} props */
export function CostForm({ shopId, skuId, currency = "GBP" }) {
  const router = useRouter();
  const [value, setValue] = useState("");
  const [error, setError] = useState(/** @type {string | null} */ (null));
  const [busy, setBusy] = useState(false);

  /** @param {React.FormEvent} e */
  async function save(e) {
    e.preventDefault();
    const pence = parsePounds(value);
    if (pence === null) {
      setError("Enter the cost in pounds and pence, for example 3.40.");
      return;
    }
    setBusy(true);
    setError(null);
    const r = await api(`/shops/${encodeURIComponent(shopId)}/skus/${encodeURIComponent(skuId)}/cost`, {
      method: "PUT",
      body: JSON.stringify({ cost: { amount_minor: pence, currency } }),
      idempotencyKey: newKey(),
    });
    setBusy(false);
    if (!r.ok) {
      setError(r.unreachable ? "MyShopEdge could not be reached, so nothing was saved." : (r.data?.detail ?? "The cost was not saved."));
      return;
    }
    setValue("");
    router.refresh();
  }

  return (
    <form onSubmit={save} className="inline-form">
      <label className="visually-hidden" htmlFor={`cost-${skuId}`}>Cost price per unit</label>
      <input
        id={`cost-${skuId}`}
        inputMode="decimal"
        placeholder="Cost, e.g. 3.40"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        aria-describedby={error ? `cost-${skuId}-error` : undefined}
      />
      <button className="btn btn--quiet" disabled={busy || value.trim() === ""}>
        {busy ? "Saving" : "Save cost"}
      </button>
      {error && <p id={`cost-${skuId}-error`} className="form-error" role="alert">{error}</p>}
    </form>
  );
}
