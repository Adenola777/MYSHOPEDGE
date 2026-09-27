"use client";

/**
 * The interactive parts of the settings area, S27 to S31 and S24. Each is a small client
 * component so its server page stays a plain read. Every write goes through `lib/api`, so it
 * carries the seller's token and the same row-level security as any other request.
 */

import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";
import { newKey } from "@/lib/money-input";

/** S27 Alert settings. A full replacement of the three thresholds. */
export function AlertSettingsForm({ shopId, initial }) {
  const router = useRouter();
  const [low, setLow] = useState(String(initial.low_stock_days));
  const [coming, setComing] = useState(String(initial.coming_back_days));
  const [absorb, setAbsorb] = useState(String(initial.absorption_tolerance_units));
  const [error, setError] = useState(/** @type {string | null} */ (null));
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);

  async function save(e) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setSaved(false);
    const r = await api(`/shops/${encodeURIComponent(shopId)}/alert-settings`, {
      method: "PUT",
      body: JSON.stringify({
        low_stock_days: Number(low),
        coming_back_days: Number(coming),
        absorption_tolerance_units: Number(absorb),
      }),
    });
    setBusy(false);
    if (!r.ok) {
      setError(r.unreachable ? "MyShopEdge could not be reached, so nothing was saved." : (r.data?.detail ?? "Those settings were not saved."));
      return;
    }
    setSaved(true);
    router.refresh();
  }

  return (
    <form onSubmit={save} className="card stack" data-testid="alert-settings-form">
      <div>
        <label htmlFor="low">Low stock warning (days of cover)</label>
        <input id="low" data-testid="low-stock-days" inputMode="numeric" value={low}
               onChange={(e) => setLow(e.target.value)} />
        <p className="rows__sub">A variant is marked low when it has fewer than this many days of stock left.</p>
      </div>
      <div>
        <label htmlFor="coming">Coming back window (days)</label>
        <input id="coming" data-testid="coming-back-days" inputMode="numeric" value={coming}
               onChange={(e) => setComing(e.target.value)} />
      </div>
      <div>
        <label htmlFor="absorb">Absorption tolerance (units)</label>
        <input id="absorb" data-testid="absorption-tolerance" inputMode="numeric" value={absorb}
               onChange={(e) => setAbsorb(e.target.value)} />
        <p className="rows__sub">Above this, an unexplained rise in TikTok stock is raised as a discrepancy rather than absorbed quietly.</p>
      </div>
      {error && <p className="form-error" role="alert" data-testid="alert-settings-error">{error}</p>}
      {saved && <p className="note note--ok" role="status" data-testid="alert-settings-saved">Saved.</p>}
      <p><button className="btn btn--primary" data-testid="save-alert-settings" disabled={busy}>{busy ? "Saving" : "Save thresholds"}</button></p>
    </form>
  );
}

/** S29 Disconnect. Confirms first, because a seller reads "disconnect" as "delete". */
export function DisconnectAction({ shopId }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState(/** @type {string | null} */ (null));

  async function disconnect() {
    setBusy(true);
    setError(null);
    const r = await api(`/shops/${encodeURIComponent(shopId)}/connection`, {
      method: "DELETE",
      idempotencyKey: newKey(),
    });
    setBusy(false);
    if (!r.ok) {
      setError(r.unreachable ? "MyShopEdge could not be reached, so nothing was changed." : (r.data?.detail ?? "The shop was not disconnected."));
      return;
    }
    setDone(true);
    router.refresh();
  }

  if (done) {
    return (
      <div className="note note--ok" role="status" data-testid="disconnect-done">
        <p>Your shop is disconnected. Your records are still here, and reconnecting the same shop resumes against them.</p>
      </div>
    );
  }

  return (
    <div className="stack">
      {error && <p className="form-error" role="alert" data-testid="disconnect-error">{error}</p>}
      <p><button className="btn btn--danger" data-testid="confirm-disconnect" onClick={disconnect} disabled={busy}>{busy ? "Disconnecting" : "Disconnect this shop"}</button></p>
    </div>
  );
}

/** S30 Delete my account. The typed email must match exactly, guarding a mis-click. */
export function DeleteAccountForm({ email }) {
  const [confirm, setConfirm] = useState("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [ack, setAck] = useState(/** @type {any} */ (null));
  const [error, setError] = useState(/** @type {string | null} */ (null));

  async function del(e) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const r = await api("/me", {
      method: "DELETE",
      body: JSON.stringify({ confirm_email: confirm.trim(), reason: reason.trim() || undefined }),
      idempotencyKey: newKey(),
    });
    setBusy(false);
    if (!r.ok) {
      setError(r.unreachable ? "MyShopEdge could not be reached, so nothing was changed." : (r.data?.detail ?? "The account was not deleted."));
      return;
    }
    setAck(r.data);
  }

  if (ack) {
    return (
      <div className="note note--warn" role="status" data-testid="delete-done">
        <p>Your account is closed. This is what will be removed:</p>
        <ul className="rows">
          {(ack.includes ?? []).map((/** @type {string} */ line) => (
            <li key={line}><span>{line}</span></li>
          ))}
        </ul>
        <p><a className="btn btn--primary" href="/start">Back to start</a></p>
      </div>
    );
  }

  return (
    <form onSubmit={del} className="card stack" data-testid="delete-account-form">
      <p className="card__why">This closes your account and disconnects your shop. Your ledger is kept as a record and is not erased.</p>
      <div>
        <label htmlFor="confirm">Type your email to confirm</label>
        <input id="confirm" data-testid="confirm-email" type="email" placeholder={email}
               value={confirm} onChange={(e) => setConfirm(e.target.value)} />
      </div>
      <div>
        <label htmlFor="reason">Reason (optional)</label>
        <input id="reason" maxLength={500} value={reason} onChange={(e) => setReason(e.target.value)} />
      </div>
      {error && <p className="form-error" role="alert" data-testid="delete-error">{error}</p>}
      <p><button className="btn btn--danger" data-testid="confirm-delete" disabled={busy || confirm.trim() === ""}>{busy ? "Closing" : "Delete my account"}</button></p>
    </form>
  );
}

/** S31 Download my data. Triggers the export and reports the queued job. */
export function ExportAction() {
  const [busy, setBusy] = useState(false);
  const [job, setJob] = useState(/** @type {any} */ (null));
  const [error, setError] = useState(/** @type {string | null} */ (null));

  async function request() {
    setBusy(true);
    setError(null);
    const r = await api("/me/export", { method: "POST", idempotencyKey: newKey() });
    setBusy(false);
    if (!r.ok) {
      setError(r.unreachable ? "MyShopEdge could not be reached, so nothing was requested." : (r.data?.detail ?? "The export was not requested."));
      return;
    }
    setJob(r.data);
  }

  if (job) {
    return (
      <div className="note note--ok" role="status" data-testid="export-queued">
        <p>Your download is being prepared. We will let you know when it is ready, and the link will appear here.</p>
        <p className="rows__sub">Request reference {job.id}. Status: {job.status}.</p>
      </div>
    );
  }

  return (
    <div className="stack">
      {error && <p className="form-error" role="alert" data-testid="export-error">{error}</p>}
      <p><button className="btn btn--primary" data-testid="request-export" onClick={request} disabled={busy}>{busy ? "Requesting" : "Prepare my download"}</button></p>
    </div>
  );
}

/** S24 Other-channel sales. Enter a month's total from a channel outside TikTok. */
export function OtherSalesForm({ shopId }) {
  const router = useRouter();
  const [month, setMonth] = useState("");
  const [channel, setChannel] = useState("");
  const [amount, setAmount] = useState("");
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState(/** @type {string | null} */ (null));

  async function save(e) {
    e.preventDefault();
    if (!/^\d{4}-(0[1-9]|1[0-2])$/.test(month.trim())) {
      setError("Enter the month as YYYY-MM, for example 2026-06.");
      return;
    }
    if (channel.trim() === "") {
      setError("Name the channel, for example Etsy or eBay.");
      return;
    }
    if (!/^\d+(\.\d{1,2})?$/.test(amount.trim())) {
      setError("Enter the total in pounds, for example 1234.56.");
      return;
    }
    setBusy(true);
    setError(null);
    setSaved(false);
    const minor = Math.round(Number(amount) * 100);
    const r = await api(`/shops/${encodeURIComponent(shopId)}/other-sales/${month.trim()}`, {
      method: "PUT",
      body: JSON.stringify({ channel: channel.trim(), gross: { amount_minor: minor, currency: "GBP" } }),
    });
    setBusy(false);
    if (!r.ok) {
      setError(r.unreachable ? "MyShopEdge could not be reached, so nothing was saved." : (r.data?.detail ?? "That figure was not saved."));
      return;
    }
    setSaved(true);
    setAmount("");
    router.refresh();
  }

  return (
    <form onSubmit={save} className="card stack" data-testid="other-sales-form">
      <div>
        <label htmlFor="os-month">Month</label>
        <input id="os-month" data-testid="other-sales-month" placeholder="2026-06" value={month}
               onChange={(e) => setMonth(e.target.value)} />
      </div>
      <div>
        <label htmlFor="os-channel">Channel</label>
        <input id="os-channel" data-testid="other-sales-channel" maxLength={100} placeholder="Etsy"
               value={channel} onChange={(e) => setChannel(e.target.value)} />
      </div>
      <div>
        <label htmlFor="os-amount">Total for the month (£)</label>
        <input id="os-amount" data-testid="other-sales-amount" inputMode="decimal" placeholder="1234.56"
               value={amount} onChange={(e) => setAmount(e.target.value)} />
      </div>
      {error && <p className="form-error" role="alert" data-testid="other-sales-error">{error}</p>}
      {saved && <p className="note note--ok" role="status" data-testid="other-sales-saved">Saved.</p>}
      <p><button className="btn btn--primary" data-testid="save-other-sales" disabled={busy}>{busy ? "Saving" : "Save month"}</button></p>
    </form>
  );
}
