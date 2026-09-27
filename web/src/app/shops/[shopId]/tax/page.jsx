/**
 * S12 Tax. The VAT threshold monitor (TAX-2), the set-aside estimate (TAX-3) and the key
 * Self Assessment dates (TAX-4). Every figure is served, never worked out here. VAT is out
 * of scope as a filing feature (A29.8); this monitors a threshold and shows dates only.
 */

import Link from "next/link";
import { api, fetchShop, formatDate, formatMoney } from "@/lib/api";
import { apiProblem } from "@/components/ApiProblem";
import { Figure } from "@/components/Figure";

export const metadata = { title: "Tax" };

/** @param {{ params: Promise<{ shopId: string }> }} props */
export default async function TaxPage({ params }) {
  const { shopId } = await params;
  const [vatRes, setAsideRes, datesRes] = await Promise.all([
    fetchShop(shopId, "/tax/vat"),
    fetchShop(shopId, "/tax/set-aside"),
    api("/tax/dates", { cache: "no-store" }),
  ]);
  const problem = apiProblem(vatRes, { what: "your VAT position" });
  if (problem) return problem;

  const vat = vatRes.data;
  const setAside = setAsideRes.ok ? setAsideRes.data : null;
  const dates = datesRes.ok ? (datesRes.data.dates ?? []) : [];

  return (
    <section data-testid="tax-screen">
      <header className="page-head">
        <h1>Tax</h1>
        <p>Your VAT threshold position and the dates that matter. Not financial advice.</p>
      </header>

      <div className="stack">
        <div className="card" data-testid="vat-monitor">
          <h2>VAT registration threshold</h2>
          <p className="card__why">Your rolling twelve-month turnover against the current threshold.</p>
          <ul className="rows">
            <li><span>Rolling twelve-month turnover</span><Figure amount={vat.rolling_twelve_month_turnover} /></li>
            <li><span>Threshold</span><Figure amount={vat.threshold} /></li>
            <li className="rows__total">
              <span>{vat.above_threshold ? "Over the threshold by" : "Headroom before the threshold"}</span>
              <span className={vat.above_threshold ? "chip chip--warn" : "chip chip--ok"}>
                {formatMoney(vat.above_threshold
                  ? { amount_minor: -vat.headroom.amount_minor, currency: vat.headroom.currency }
                  : vat.headroom)}
              </span>
            </li>
          </ul>
          <p className="card__foot">
            {vat.includes_other_channels
              ? "This includes the other-channel sales you entered."
              : (<>Only TikTok turnover is counted. <Link href={`/shops/${shopId}/other-sales`}>Add other-channel sales</Link> to see your whole turnover.</>)}
          </p>
        </div>

        {setAside && (
          <div className="card" data-testid="set-aside">
            <h2>Tax to set aside</h2>
            <p className="card__why">An estimate of what to keep back for tax.</p>
            <p className="hero__value"><Figure amount={setAside.amount} reason={
              setAside.unavailable_reason === "no_tax_profile"
                ? "Fill in your tax profile so a set-aside can be estimated."
                : "Set-aside rates are not configured yet, so no amount is shown."
            } /></p>
          </div>
        )}

        <div className="card" data-testid="tax-dates">
          <h2>Key tax dates</h2>
          <p className="card__why">The Self Assessment dates for the current tax year.</p>
          {dates.length === 0 ? (
            <p className="muted">Tax dates are not configured on this deployment yet.</p>
          ) : (
            <ul className="rows">
              {dates.map((d) => (
                <li key={d.rule_key}>
                  <span>
                    {d.label}
                    {d.reviewed_at && <div className="rows__sub">Reviewed {formatDate(d.reviewed_at)}</div>}
                  </span>
                  <strong>{formatDate(d.date)}</strong>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </section>
  );
}
