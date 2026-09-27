"use client";

/**
 * S2 First sync progress. Polls `getSyncStatus` while a sync is running, so onboarding shows
 * movement rather than a dead screen. A domain that has never run is not listed by the
 * service (it describes runs, not intentions), so before the first sync this shows a waiting
 * state honestly rather than a fake progress bar.
 */

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

const DOMAIN_LABEL = {
  orders: "Orders",
  returns: "Returns",
  statements: "Settlements",
  products: "Products",
  inventory: "Stock",
};

const STATUS_TONE = {
  completed: "chip chip--ok",
  running: "chip chip--warn",
  partial: "chip chip--warn",
  failed: "chip chip--danger",
  queued: "chip",
};

export function SyncProgress({ shopId, initial }) {
  const [data, setData] = useState(initial);
  const domains = data?.domains ?? [];
  const anyRunning = domains.some((d) => d.status === "running" || d.status === "queued");
  const done = domains.length > 0 && domains.every((d) => d.status === "completed");

  useEffect(() => {
    // Keep polling only while something is in flight or nothing has appeared yet.
    if (done) return undefined;
    const t = setInterval(async () => {
      const r = await api(`/shops/${encodeURIComponent(shopId)}/sync`, { cache: "no-store" });
      if (r.ok) setData(r.data);
    }, 4000);
    return () => clearInterval(t);
  }, [shopId, done]);

  if (domains.length === 0) {
    return (
      <div className="card" data-testid="sync-waiting">
        <h2>Waiting for your first sync</h2>
        <p className="card__why">
          Once your shop is connected, MyShopEdge starts bringing in your orders, returns and
          settlements. Nothing has arrived yet. This screen updates on its own.
        </p>
        <p className="muted">Checked {new Date(data.as_of).toLocaleTimeString("en-GB")}.</p>
      </div>
    );
  }

  return (
    <div className="card" data-testid="sync-progress">
      <h2>{done ? "Your shop is up to date" : "Bringing your shop in"}</h2>
      <p className="card__why">
        {done
          ? "Every part of your shop has been brought in at least once."
          : "This updates on its own while each part of your shop is brought in."}
      </p>
      <ul className="rows">
        {domains.map((d) => (
          <li key={d.domain} data-testid={`sync-domain-${d.domain}`}>
            <span>
              {DOMAIN_LABEL[d.domain] ?? d.domain}
              <div className="rows__sub">
                {d.records_written} record{d.records_written === 1 ? "" : "s"}
                {d.last_success_at ? ` · last done ${new Date(d.last_success_at).toLocaleString("en-GB")}` : ""}
                {d.stale ? " · out of date" : ""}
              </div>
            </span>
            <span className={STATUS_TONE[d.status] ?? "chip"}>{d.status}</span>
          </li>
        ))}
      </ul>
      {anyRunning && <p className="muted" data-testid="sync-live">Updating…</p>}
    </div>
  );
}
