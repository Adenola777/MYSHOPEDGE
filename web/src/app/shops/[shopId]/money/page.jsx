/**
 * S11 Money. Where every pound went, as a running calculation (A8.5).
 *
 * `getMoney` serves the sections, their lines and the running subtotal each section
 * reaches. This screen lays them out in order and does no arithmetic. Every line opens the
 * records behind it on S22, which is the rule A18.5 exists for.
 *
 * The basis switch is served by the API. The wireframe's period switch (today, this month,
 * tax year) is not here. The service owns the business date (A29.9), and a period chosen
 * here would mean the browser deciding which day it is in London, so the screen shows the
 * service's default period, the current month, until the contract can name a period. The
 * expected payouts by week and the export are not served by any built endpoint.
 */

import Link from "next/link";
import { fetchShop, formatDate } from "@/lib/api";
import { apiProblem } from "@/components/ApiProblem";
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

  const result = await fetchShop(shopId, "/money", { basis, from: query.from, to: query.to });
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

  return (
    <section>
      <header className="page-head">
        <h1>Money</h1>
        <p>
          Where every pound went, {formatDate(period.from)} to {formatDate(period.to)}.{" "}
          <span className={chipClass(tone)}>{confidence}</span>
        </p>
      </header>

      <nav className="switch" aria-label="Basis">
        <Link href={base} aria-current={basis === "sales" ? "true" : undefined}>Sales basis</Link>
        <Link href={`${base}?basis=cash`} aria-current={basis === "cash" ? "true" : undefined}>
          Cash basis
        </Link>
      </nav>
      <p className="muted">
        {basis === "sales"
          ? "Sales basis counts money on the day of the sale."
          : "Cash basis counts money in the month TikTok settled it."}
      </p>

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
                  <Link href={recordsHref(l)}>{l.label}</Link>
                  <Figure amount={l.amount} />
                </li>
              ))}
              <li className="rows__total">
                <span>{s.subtotal_label ?? "Subtotal"}</span>
                <Figure amount={s.subtotal} />
              </li>
            </ul>
          </div>
        ))}

        <div className="card hero">
          <p className="hero__label">Gross profit after returns</p>
          <p className="hero__value"><Figure amount={m.kept} reason={keptReason(m.kept_reason)} /></p>
          <p className="muted">{m.kept ? BEFORE_OVERHEADS : keptReason(m.kept_reason)}</p>
        </div>
      </div>
    </section>
  );
}
