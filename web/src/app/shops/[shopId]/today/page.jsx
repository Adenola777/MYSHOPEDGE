/**
 * S6 Today. The first screen after sign in.
 *
 * Every figure here is served by `getToday` and rendered as it arrives. The hero's label
 * comes from the service, which names gross profit after returns only when every product
 * has a cost and net proceeds otherwise (A8). Settlement reconciles to what TikTok actually
 * paid, with return postage on its own line (A29.7). Needs you arrives sorted by the
 * service (A29.6) and is shown in that order, with the links the service gives it.
 *
 * Left out, and why. The wireframe's VAT line is out of scope for this view (A29.8). The
 * congratulation A15.5 keeps belongs to the first arrival after onboarding, and nothing
 * yet tells this screen that the seller has just finished onboarding.
 */

import Link from "next/link";
import { fetchShop, formatDate } from "@/lib/api";
import { apiProblem } from "@/components/ApiProblem";
import { Figure } from "@/components/Figure";
import {
  AWAITING, BEFORE_OVERHEADS, CONFIDENCE, FRESHNESS, HERO_LABEL, SEVERITY_TONE, chipClass, keptReason,
} from "@/lib/terms";

export const metadata = { title: "Today" };

/** @type {Record<string, string>} */
const SEVERITY_WORD = { critical: "Act now", warning: "Check", info: "Note" };

/** @param {{ params: Promise<{ shopId: string }> }} props */
export default async function TodayPage({ params }) {
  const { shopId } = await params;
  const result = await fetchShop(shopId, "/today");
  const problem = apiProblem(result, { what: "today's figures" });
  if (problem) return problem;

  /** @type {import("@/lib/api-types").components["schemas"]["TodayView"]} */
  const t = result.data;
  const [confidence, confidenceTone] =
    CONFIDENCE[t.hero.confidence] ?? [t.hero.confidence, "quiet"];
  const fresh = t.freshness ? FRESHNESS[t.freshness.status] : null;
  const isProfit = t.hero.label === "gross_profit_after_returns";
  const sm = t.shop_money;

  return (
    <section>
      <header className="page-head">
        <h1>Today</h1>
        <p>
          {t.freshness?.last_synced_at
            ? `Last synced ${formatDate(t.freshness.last_synced_at, { time: true })}. `
            : "No sync has finished yet. "}
          {fresh && <span className={chipClass(fresh[1])}>{fresh[0]}</span>}
        </p>
      </header>

      <div className="stack">
        <div className="card hero">
          <p className="hero__label">
            {HERO_LABEL[t.hero.label] ?? t.hero.label} today{" "}
            <span className={chipClass(confidenceTone)}>{confidence}</span>
          </p>
          <p className="hero__value"><Figure amount={t.hero.value} /></p>
          {isProfit ? (
            <p className="muted">{BEFORE_OVERHEADS}</p>
          ) : (
            <p className="muted">
              This is net proceeds because not every product has a cost price yet, so
              profit cannot be worked out.{" "}
              <Link href={`/shops/${shopId}/products`}>See which products</Link>.
            </p>
          )}
        </div>

        <div className="pair">
          <div className="card">
            <p className="stat__value"><Figure amount={t.month.gross} /></p>
            <p className="stat__label">Gross sales (GMV) this month</p>
          </div>
          <div className="card">
            <p className="stat__value">
              <Figure amount={t.month.kept} reason={keptReason(t.month.kept_reason)} />
            </p>
            <p className="stat__label">Gross profit after returns this month</p>
            {t.month.kept ? (
              <p className="rows__sub">{BEFORE_OVERHEADS}</p>
            ) : (
              t.month.kept_reason && <p className="rows__sub">{keptReason(t.month.kept_reason)}</p>
            )}
          </div>
        </div>

        <div className="card">
          <h2>Settlement</h2>
          <ul className="rows">
            <li><span>Net proceeds, all time</span><Figure amount={sm.generated} /></li>
            {sm.return_postage && (
              <li>
                <span>Return postage TikTok deducted</span>
                <Figure amount={sm.return_postage} />
              </li>
            )}
            <li className="rows__total">
              <span>Settled to your bank</span><Figure amount={sm.paid_out} />
            </li>
            <li><span>Awaiting settlement</span><Figure amount={sm.awaiting} /></li>
            {sm.awaiting_breakdown?.map((a) => (
              <li key={a.status} className="rows__sub">
                <span>
                  {AWAITING[a.status] ?? a.status}, {a.orders}{" "}
                  {a.orders === 1 ? "order" : "orders"}
                </span>
                <Figure amount={a.amount} />
              </li>
            ))}
          </ul>
          <p className="rows__sub" style={{ marginTop: "var(--space-3)" }}>
            Settled to your bank is what TikTok actually paid. Return postage TikTok took from
            a statement is shown on its own line so that the two can be reconciled.{" "}
            <Link href={`/shops/${shopId}/money`}>See where every pound went</Link>.
          </p>
        </div>

        <div className="card">
          <h2>Needs you</h2>
          {t.needs_you.length === 0 ? (
            <p className="muted">Nothing needs you right now.</p>
          ) : (
            <ul className="rows">
              {t.needs_you.map((n) => (
                <li key={n.type}>
                  <span>
                    {n.href ? <Link href={n.href}>{n.label ?? n.type}</Link> : (n.label ?? n.type)}
                    {n.amount_at_stake && (
                      <span className="rows__sub">
                        {" "}<Figure amount={n.amount_at_stake} /> affected
                      </span>
                    )}
                  </span>
                  <span className={chipClass(SEVERITY_TONE[n.severity] ?? "quiet")}>
                    {SEVERITY_WORD[n.severity] ?? n.severity}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </section>
  );
}
