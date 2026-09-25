/**
 * S11 Money. Where every pound went, as a running calculation (A8.5).
 *
 * `getMoney` serves the sections, their lines and the running subtotal each section
 * reaches. This screen lays them out in order and does no arithmetic. Every line opens the
 * records behind it on S22, which is the rule A18.5 exists for.
 *
 * Drawn to wireframe sheet 07 (redrawn 24 September after the design audit): the period
 * switch, the basis switch, then the calculation.
 *
 * The period switch. "This month" is the service's default period. "Today" is that
 * period's last day, `period.to`, which is the service's own London date (A29.9), so the
 * browser never decides what day it is. "Tax year" needs the UK tax year's start, which is
 * a rule the contract does not state, so it is not offered until it does.
 *
 * Held and paid out is shown as A18.3 orders it, net proceeds, then the reserve held, then
 * the payout, with no subtotal: adding a payout to a reserve gives a figure with no meaning
 * a seller can use, and the screen showed one until 24 September.
 *
 * A fee TikTok names in a way MyShopEdge does not recognise is shown under that heading
 * with TikTok's own name beneath it (A18.4), never as a bare code.
 *
 * Expected payouts by week and the month summary and export are blocked (CLAUDE.md), so
 * they are not drawn.
 */

import Link from "next/link";
import { fetchShop, formatDate } from "@/lib/api";
import { apiProblem } from "@/components/ApiProblem";
import { LineLabel } from "@/components/LineLabel";
import { Figure } from "@/components/Figure";
import { BEFORE_OVERHEADS, CONFIDENCE, chipClass, keptReason } from "@/lib/terms";

export const metadata = { title: "Money" };

/**
 * @param {{
 *   params: Promise<{ shopId: string }>,
 *   searchParams: Promise<Record<string, string>>,
 * }} props
 */
export default async function MoneyPage({ params, searchParams }) {
  const { shopId } = await params;
  const query = await searchParams;
  const basis = query.basis === "cash" ? "cash" : "sales";
  const day = query.day;

  const result = await fetchShop(shopId, "/money", { basis, from: day, to: day });
  const problem = apiProblem(result, { what: "your money figures" });
  if (problem) return problem;

  /** @type {import("@/lib/api-types").components["schemas"]["MoneyView"]} */
  const m = result.data;
  const period = /** @type {{ from: string, to: string }} */ (m.period);
  const [confidence, tone] = CONFIDENCE[m.confidence] ?? [m.confidence, "quiet"];
  const base = `/shops/${shopId}/money`;

  /** @param {{ category?: string | null }} line */
  const recordsHref = (line) =>
    `/shops/${shopId}/records?${new URLSearchParams({
      basis,
      from: period.from,
      to: period.to,
      ...(line.category ? { category: line.category } : {}),
    })}`;

  /** The heading and TikTok's name for a line that carries one verbatim. */
  /** @param {any} l */
  /** @param {Record<string, string>} q */
  const href = (q) => `${base}${Object.keys(q).length ? `?${new URLSearchParams(q)}` : ""}`;
  /** @type {Record<string, string>} */
  const withBasis = basis === "cash" ? { basis } : {};

  return (
    <section>
      <header className="page-head">
        <h1>Money</h1>
        <p>
          Where every pound went, {day ? formatDate(day) : `${formatDate(period.from)} to ${formatDate(period.to)}`}.{" "}
          <span className={chipClass(tone)}>{confidence}</span>
        </p>
      </header>

      <nav className="switch" aria-label="Period">
        <Link href={href({ ...withBasis, day: period.to })} aria-current={day ? "true" : undefined}>Today</Link>
        <Link href={href(withBasis)} aria-current={!day ? "true" : undefined}>This month</Link>
      </nav>
      <nav className="switch" aria-label="Basis">
        <Link href={href(day ? { day } : {})} aria-current={basis === "sales" ? "true" : undefined}>Sales basis</Link>
        <Link href={href({ basis: "cash", ...(day ? { day } : {}) })} aria-current={basis === "cash" ? "true" : undefined}>Cash basis</Link>
      </nav>

      {(m.unmapped_fee_count ?? 0) > 0 && (
        <div className="note note--warn" role="status">
          <p>
            {m.unmapped_fee_count === 1
              ? "One fee in this period has a name we do not recognise."
              : `${m.unmapped_fee_count} fees in this period have names we do not recognise.`}{" "}
            The money is counted in full, under the name TikTok gave it.
          </p>
        </div>
      )}

      <div className="stack">
        {m.sections.map((s) => (
          <div className="card" key={s.key}>
            <h2>{s.label}</h2>
            <ul className="rows">
              {s.lines.map((l, i) => (
                <li key={`${l.category}-${l.tiktok_fee_type ?? i}`}>
                  <Link className="rowlink rowlink--quiet" href={recordsHref(l)}><LineLabel line={l} /></Link>
                  <Figure amount={l.amount} />
                </li>
              ))}
              {s.key !== "payout" && (
                <li className="rows__total">
                  <span>{s.subtotal_label ?? "Subtotal"}</span>
                  <Figure amount={s.subtotal} reason={s.key === "return_costs" ? keptReason(m.kept_reason) : null} />
                </li>
              )}
            </ul>
          </div>
        ))}
      </div>

      <p className="footnote">
        {basis === "sales" ? "Sales basis counts money on the day of the sale." : "Cash basis counts money in the month TikTok settled it."}{" "}
        {m.kept ? BEFORE_OVERHEADS : keptReason(m.kept_reason)}
      </p>
    </section>
  );
}
