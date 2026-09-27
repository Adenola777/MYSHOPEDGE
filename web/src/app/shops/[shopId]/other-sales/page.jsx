/**
 * S24 Other-channel sales, bound to listOtherChannelSales and putOtherChannelSales (MON-3).
 * These figures never enter the ledger and never appear in a money view. They exist only so
 * the VAT threshold monitor measures total turnover rather than TikTok turnover alone.
 */

import Link from "next/link";
import { fetchShop, formatDate } from "@/lib/api";
import { apiProblem } from "@/components/ApiProblem";
import { Figure } from "@/components/Figure";
import { OtherSalesForm } from "@/components/SettingsForms";

export const metadata = { title: "Other-channel sales" };

const MONTH = new Intl.DateTimeFormat("en-GB", { timeZone: "Europe/London", month: "long", year: "numeric" });

/** @param {{ params: Promise<{ shopId: string }> }} props */
export default async function OtherSalesPage({ params }) {
  const { shopId } = await params;
  const result = await fetchShop(shopId, "/other-sales");
  const problem = apiProblem(result, { what: "your other-channel sales" });
  if (problem) return problem;

  const months = result.data.months ?? [];

  return (
    <section data-testid="other-sales-screen">
      <header className="page-head">
        <h1>Other-channel sales</h1>
        <p>Sales you make outside TikTok, so the VAT monitor sees your whole turnover.</p>
      </header>

      <div className="stack">
        <OtherSalesForm shopId={shopId} />

        <div className="card" data-testid="other-sales-list">
          <h2>Months entered</h2>
          {months.length === 0 ? (
            <p className="muted">Nothing entered yet. Add a month above.</p>
          ) : (
            <ul className="rows">
              {months.map((m) => (
                <li key={m.month}>
                  <span>{MONTH.format(new Date(`${m.month}T12:00:00Z`))}
                    {m.updated_at && <div className="rows__sub">Updated {formatDate(m.updated_at)}</div>}
                  </span>
                  <Figure amount={m.amount} />
                </li>
              ))}
            </ul>
          )}
          <p className="card__foot">
            <Link href={`/shops/${shopId}/tax`}>See your VAT position</Link>
          </p>
        </div>
      </div>
    </section>
  );
}
