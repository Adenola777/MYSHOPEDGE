"use client";

/**
 * S23 Export. Builds a spreadsheet from the ledger and downloads it. The file is produced by
 * `createExport`, which returns a ready job; the download then fetches the bytes with the
 * seller's token (the store issues no public links) and saves them.
 */

import { useState } from "react";
import { api } from "@/lib/api";
import { authorizationHeader } from "@/lib/stack";
import { newKey } from "@/lib/money-input";

const KINDS = [
  ["month_summary", "Month summary", "Each section of the money view, with its subtotal."],
  ["ledger", "Full ledger", "Every accounting entry, one row each."],
  ["transactions", "Transactions", "Every entry with its TikTok order and invoice."],
];

function firstOfMonth() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-01`;
}
function today() {
  return new Date().toISOString().slice(0, 10);
}

export function ExportForm({ shopId }) {
  const [kind, setKind] = useState("month_summary");
  const [format, setFormat] = useState("xlsx");
  const [basis, setBasis] = useState("sales");
  const [from, setFrom] = useState(firstOfMonth());
  const [to, setTo] = useState(today());
  const [busy, setBusy] = useState(false);
  const [job, setJob] = useState(/** @type {any} */ (null));
  const [error, setError] = useState(/** @type {string | null} */ (null));

  async function build(e) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setJob(null);
    const r = await api(`/shops/${encodeURIComponent(shopId)}/exports`, {
      method: "POST",
      idempotencyKey: newKey(),
      body: JSON.stringify({
        kind, format, basis, period_start: from, period_end: to,
      }),
    });
    setBusy(false);
    if (!r.ok) {
      setError(r.unreachable ? "MyShopEdge could not be reached, so nothing was built." : (r.data?.detail ?? "That export could not be built."));
      return;
    }
    setJob(r.data);
  }

  async function download() {
    setError(null);
    const base = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";
    const auth = await authorizationHeader();
    const res = await fetch(`${base}${job.download_url}`, {
      headers: auth ? { Authorization: auth } : {},
    });
    if (!res.ok) {
      setError("The file could not be downloaded.");
      return;
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${job.kind}-${job.period_start}-to-${job.period_end}.${job.format}`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  return (
    <form onSubmit={build} className="card stack" data-testid="export-form">
      <div>
        <label htmlFor="ex-kind">What to export</label>
        <select id="ex-kind" data-testid="export-kind" value={kind} onChange={(e) => setKind(e.target.value)}>
          {KINDS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
        <p className="rows__sub">{KINDS.find((k) => k[0] === kind)?.[2]}</p>
      </div>
      <div className="pair">
        <div>
          <label htmlFor="ex-format">Format</label>
          <select id="ex-format" data-testid="export-format" value={format} onChange={(e) => setFormat(e.target.value)}>
            <option value="xlsx">Excel (.xlsx)</option>
            <option value="csv">CSV</option>
          </select>
        </div>
        <div>
          <label htmlFor="ex-basis">Basis</label>
          <select id="ex-basis" data-testid="export-basis" value={basis} onChange={(e) => setBasis(e.target.value)}>
            <option value="sales">Sales (when the sale happens)</option>
            <option value="cash">Cash (when TikTok pays out)</option>
          </select>
        </div>
      </div>
      <div className="pair">
        <div>
          <label htmlFor="ex-from">From</label>
          <input id="ex-from" data-testid="export-from" type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
        </div>
        <div>
          <label htmlFor="ex-to">To</label>
          <input id="ex-to" data-testid="export-to" type="date" value={to} onChange={(e) => setTo(e.target.value)} />
        </div>
      </div>
      {error && <p className="form-error" role="alert" data-testid="export-error">{error}</p>}
      <p><button className="btn btn--primary" data-testid="build-export" disabled={busy}>{busy ? "Building" : "Build the file"}</button></p>
      {job && (
        <div className="note note--ok" role="status" data-testid="export-ready">
          <p>Your {job.kind.replace("_", " ")} is ready{job.row_count != null ? ` (${job.row_count} rows)` : ""}.</p>
          <p><button type="button" className="btn btn--primary" data-testid="download-export" onClick={download}>Download the file</button></p>
        </div>
      )}
    </form>
  );
}
