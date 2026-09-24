/**
 * The top bar on every screen (WFW 1.1): the logo on the left, and inside a shop the
 * Updated stamp and the notification bell on the right.
 *
 * The logo is `mse-logo-horizontal-notagline.svg` from `brand/`, drawn at 48 px high, which
 * makes it 129 px wide. A7.6 allows the lockup without the tagline from 110 px wide, and
 * forbids setting the wordmark in a font or setting the tagline on its own, which is what
 * this bar did until 24 September.
 *
 * The Updated stamp is `freshness.last_synced_at` from TodayView, the one freshness the
 * service computes (A29.3). The bell count is `unread_count` from listNotifications. Both
 * are read, never worked out here (A29.1). If either request fails, its part of the bar is
 * left out rather than shown as a guess.
 */

import { api } from "@/lib/api";

const TIME = new Intl.DateTimeFormat("en-GB", {
  timeZone: "Europe/London",
  hour: "2-digit",
  minute: "2-digit",
});
const DAY = new Intl.DateTimeFormat("en-GB", {
  timeZone: "Europe/London",
  day: "numeric",
  month: "short",
});
const LONDON_DAY = new Intl.DateTimeFormat("en-CA", { timeZone: "Europe/London" });

/** "09:12" today, "23 Sep" before today, both in London time. */
function stamp(/** @type {string} */ iso) {
  const at = new Date(iso);
  return LONDON_DAY.format(at) === LONDON_DAY.format(new Date()) ? TIME.format(at) : DAY.format(at);
}

/** @param {{ shopId?: string }} props */
export async function AppBar({ shopId }) {
  let freshness = null;
  let unread = null;
  if (shopId) {
    const id = encodeURIComponent(shopId);
    const [today, notes] = await Promise.all([
      api(`/shops/${id}/today`, { cache: "no-store" }),
      api("/notifications?status=unread&limit=1", { cache: "no-store" }),
    ]);
    if (today.ok) freshness = today.data?.freshness ?? null;
    if (notes.ok) unread = Number(notes.data?.unread_count ?? 0);
  }

  return (
    <header className="appbar">
      <div className="appbar__inner">
        <a className="appbar__logo" href="/">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/brand/mse-logo-horizontal-notagline.svg" alt="MyShopEdge" width={129} height={48} />
        </a>
        {shopId && (
          <div className="appbar__status">
            {freshness && (
              <span
                className={`appbar__updated${freshness.status === "stale" ? " appbar__updated--stale" : ""}`}
              >
                {freshness.last_synced_at ? `Updated ${stamp(freshness.last_synced_at)}` : "Not updated yet"}
              </span>
            )}
            <a
              className="bell"
              href={`/shops/${encodeURIComponent(shopId)}/notifications`}
              aria-label={unread ? `Notifications, ${unread} unread` : "Notifications"}
            >
              <svg viewBox="0 0 32 32" fill="none" aria-hidden="true">
                <circle cx="16" cy="16" r="13" stroke="currentColor" strokeWidth="2" />
                <path d="M16 9v9" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" />
                <circle cx="16" cy="22.5" r="1.7" fill="currentColor" />
              </svg>
              {unread ? <span className="bell__dot">{unread > 9 ? "9+" : unread}</span> : null}
            </a>
          </div>
        )}
      </div>
    </header>
  );
}
