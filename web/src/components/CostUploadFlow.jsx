"use client";

/**
 * S3/S4 Cost upload. The whole flow on one screen: choose a file, confirm how its columns
 * map, see what matched, and apply the costs the seller confirms. Nothing is applied without
 * the seller confirming, and no product is ever created from a file (CST-2).
 *
 * The file goes through the service, because the store issues no presigned upload URLs: a
 * create returns an upload_url that points back at the API, and the bytes are PUT there with
 * the seller's token.
 */

import { useState } from "react";
import { api, formatMoney } from "@/lib/api";
import { authorizationHeader } from "@/lib/stack";
import { newKey } from "@/lib/money-input";

const XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";

export function CostUploadFlow({ shopId }) {
  const [upload, setUpload] = useState(/** @type {any} */ (null));
  const [mapping, setMapping] = useState(/** @type {any} */ (null));
  const [result, setResult] = useState(/** @type {any} */ (null));
  const [applied, setApplied] = useState(false);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState(/** @type {string | null} */ (null));

  async function onFile(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setError(null);
    setResult(null);
    setApplied(false);
    setUpload(null);
    setBusy("Uploading");
    const content_type = file.name.toLowerCase().endsWith(".xlsx") ? XLSX : "text/csv";
    const created = await api(`/shops/${encodeURIComponent(shopId)}/cost-uploads`, {
      method: "POST",
      body: JSON.stringify({ filename: file.name, content_type, size_bytes: file.size }),
    });
    if (!created.ok) {
      setBusy("");
      setError(created.data?.detail ?? "The upload could not be started.");
      return;
    }
    const base = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";
    const auth = await authorizationHeader();
    const put = await fetch(`${base}${created.data.upload_url}`, {
      method: "PUT",
      headers: { "Content-Type": content_type, ...(auth ? { Authorization: auth } : {}) },
      body: file,
    });
    setBusy("");
    if (!put.ok) {
      setError("The file could not be read. It must be a CSV or Excel (.xlsx) file.");
      return;
    }
    const data = await put.json();
    setUpload(data);
    setMapping(
      data.suggested_mapping ?? { match_on: "seller_sku", cost_column: data.detected_columns?.[0] ?? "" },
    );
    if (data.status === "failed") setError(data.error ?? "The file could not be read.");
  }

  async function match(e) {
    e.preventDefault();
    setBusy("Matching");
    setError(null);
    const saved = await api(`/shops/${encodeURIComponent(shopId)}/cost-uploads/${upload.id}/mapping`, {
      method: "PUT",
      body: JSON.stringify({ ...mapping, currency: mapping.currency ?? "GBP" }),
    });
    if (!saved.ok) {
      setBusy("");
      setError(saved.data?.detail ?? "That mapping could not be saved.");
      return;
    }
    const m = await api(`/shops/${encodeURIComponent(shopId)}/cost-uploads/${upload.id}/match`, {
      method: "POST",
    });
    setBusy("");
    if (!m.ok) {
      setError(m.data?.detail ?? "The file could not be matched.");
      return;
    }
    setResult(m.data);
  }

  async function apply() {
    setBusy("Applying");
    setError(null);
    const ids = result.rows.filter((/** @type {any} */ r) => r.outcome === "matched").map((/** @type {any} */ r) => r.row_id);
    const r = await api(`/shops/${encodeURIComponent(shopId)}/cost-uploads/${upload.id}/apply`, {
      method: "POST",
      idempotencyKey: newKey(),
      body: JSON.stringify({ apply_row_ids: ids }),
    });
    setBusy("");
    if (!r.ok) {
      setError(r.data?.detail ?? "The costs could not be applied.");
      return;
    }
    setApplied(true);
  }

  const cols = upload?.detected_columns ?? [];

  return (
    <div className="stack" data-testid="cost-upload-flow">
      <div className="card">
        <h2>Choose your file</h2>
        <p className="card__why">A CSV or Excel (.xlsx) file with a column for the SKU and a column for the cost.</p>
        <input
          type="file" accept=".csv,.xlsx" data-testid="cost-file-input"
          onChange={onFile} disabled={busy !== ""}
        />
        {busy && <p className="muted" data-testid="cost-upload-busy">{busy}…</p>}
      </div>

      {error && <p className="form-error" role="alert" data-testid="cost-upload-error">{error}</p>}

      {upload && upload.status !== "failed" && !result && (
        <form onSubmit={match} className="card stack" data-testid="cost-mapping-form">
          <h2>Confirm the columns</h2>
          <p className="card__why">We read your headings. Check they point at the right columns.</p>
          <div>
            <label htmlFor="match-on">Which column identifies the SKU?</label>
            <select id="match-on" data-testid="mapping-match-on" value={mapping.match_on}
                    onChange={(e) => setMapping({ ...mapping, match_on: e.target.value })}>
              <option value="seller_sku">Your seller SKU</option>
              <option value="tiktok_sku_id">TikTok SKU id</option>
            </select>
          </div>
          <div>
            <label htmlFor="key-col">SKU column</label>
            <select id="key-col" data-testid="mapping-key-column" value={mapping.key_column ?? ""}
                    onChange={(e) => setMapping({ ...mapping, key_column: e.target.value })}>
              <option value="">Choose a column</option>
              {cols.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <div>
            <label htmlFor="cost-col">Cost column</label>
            <select id="cost-col" data-testid="mapping-cost-column" value={mapping.cost_column ?? ""}
                    onChange={(e) => setMapping({ ...mapping, cost_column: e.target.value })}>
              <option value="">Choose a column</option>
              {cols.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <div className="pair">
            <div>
              <label htmlFor="pack-col">Packing column (optional)</label>
              <select id="pack-col" data-testid="mapping-packing-column" value={mapping.packing_column ?? ""}
                      onChange={(e) => setMapping({ ...mapping, packing_column: e.target.value || null })}>
                <option value="">None</option>
                {cols.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            <div>
              <label htmlFor="post-col">Postage column (optional)</label>
              <select id="post-col" data-testid="mapping-postage-column" value={mapping.postage_column ?? ""}
                      onChange={(e) => setMapping({ ...mapping, postage_column: e.target.value || null })}>
                <option value="">None</option>
                {cols.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
          </div>
          <p><button className="btn btn--primary" data-testid="match-costs" disabled={busy !== ""}>Match my file</button></p>
        </form>
      )}

      {result && (
        <div className="card" data-testid="cost-match-result">
          <h2>What matched</h2>
          <p className="card__why">
            {result.rows_matched} matched, {result.rows_unmatched} not matched
            {result.rows_duplicate ? `, ${result.rows_duplicate} duplicate` : ""}. Nothing is
            changed until you apply.
          </p>
          <ul className="rows">
            {result.rows.map((/** @type {any} */ r) => (
              <li key={r.row_id} data-testid={`match-row-${r.outcome}`}>
                <span>
                  {r.seller_sku ?? "—"}
                  {r.reason && <div className="rows__sub">{r.reason}</div>}
                </span>
                <span className={r.outcome === "matched" ? "chip chip--ok" : r.outcome === "duplicate" ? "chip chip--warn" : "chip chip--danger"}>
                  {r.unit_cost ? formatMoney(r.unit_cost) : r.outcome}
                </span>
              </li>
            ))}
          </ul>
          {applied ? (
            <p className="note note--ok" role="status" data-testid="cost-applied">
              Done. {result.rows_matched} cost{result.rows_matched === 1 ? "" : "s"} applied.
            </p>
          ) : (
            <p>
              <button className="btn btn--primary" data-testid="apply-costs" onClick={apply}
                      disabled={busy !== "" || result.rows_matched === 0}>
                Apply {result.rows_matched} cost{result.rows_matched === 1 ? "" : "s"}
              </button>
            </p>
          )}
        </div>
      )}
    </div>
  );
}
