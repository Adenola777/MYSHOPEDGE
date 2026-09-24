/**
 * S7 Stock. What is on hand for each variant, its state and its days of cover.
 *
 * The state and days of cover are computed by `getStock` (service/app/stock.py) and shown as
 * they arrive. The labels are A8's: stock on hand, sold not yet dispatched, returns in
 * transit, stock written off and days of cover.
 *
 * Two parts of the wireframe are not here yet, and both wait on the contract rather than
 * on this screen. The "Units in hand" block is a set of totals across every variant, and
 * `getStock` serves no totals. Adding them up here would put a figure in the browser that
 * the service never computed, against A29.1. "What runs out first" is an ordering by days
 * of cover, and the endpoint pages by variant, so an ordering applied here would sort only
 * the page in hand.
 */

import Link from "next/link";
import { fetchShop, formatDate } from "@/lib/api";
import { apiProblem } from "@/components/ApiProblem";
import { STOCK_STATE, chipClass } from "@/lib/terms";

export const metadata = { title: "Stock" };

const FILTERS = [
  ["", "All"],
  ["out", "Out of stock"],
  ["low", "Low"],
  ["coming_back", "Returns in transit"],
  ["healthy", "Healthy"],
];

/**
 * @param {{
 *   params: Promise<{ shopId: string }>,
 *   searchParams: Promise<Record<string, string>>,
 * }} props
 */
export default async function StockPage({ params, searchParams }) {
  const { shopId } = await params;
  const query = await searchParams;
  const state = query.state ?? "";

  const result = await fetchShop(shopId, "/stock", { state, cursor: query.cursor });
  const problem = apiProblem(result, { what: "your stock" });
  if (problem) return problem;

  /** @type {{ as_of: string, items: import("@/lib/api-types").components["schemas"]["StockPosition"][], next_cursor: string | null }} */
  const { as_of, items, next_cursor } = result.data;
  const base = `/shops/${shopId}/stock`;

  return (
    <section>
      <header className="page-head">
        <h1>Stock</h1>
        <p>What you have, as TikTok last reported it with your adjustments. Counted {formatDate(as_of, { time: true })}.</p>
      </header>

      <nav className="switch" aria-label="Show">
        {FILTERS.map(([value, label]) => (
          <Link
            key={value || "all"}
            href={value ? `${base}?state=${value}` : base}
            aria-current={state === value ? "true" : undefined}
          >
            {label}
          </Link>
        ))}
      </nav>

      {items.length === 0 ? (
        <section className="state">
          <h2>{state ? "No variants in this state." : "No stock recorded yet."}</h2>
          <p>
            {state
              ? "Nothing matches this filter right now."
              : "Stock appears here once the first sync brings in your products."}
          </p>
        </section>
      ) : (
        <div className="card">
          <p className="rows__sub" style={{ marginTop: 0 }}>
            Days of cover is stock on hand divided by the daily rate of the last fourteen days.
            It is not shown when nothing sold in that time.
          </p>
          <ul className="rows">
            {items.map((s) => {
              const [label, tone] = STOCK_STATE[s.state] ?? [s.state, "quiet"];
              return (
                <li key={s.sku_id}>
                  <span>
                    <Link href={`${base}/${s.sku_id}`}>{s.product_title || "Untitled product"}</Link>
                    <span className="rows__sub"> {s.seller_sku ?? "No seller SKU"}</span>
                    <div className="rows__sub">
                      {s.on_shelf} on hand
                      {s.days_left != null ? `, ${s.days_left} days of cover` : ""}
                      {s.sold_not_posted ? `. ${s.sold_not_posted} sold, not yet dispatched` : ""}
                      {s.coming_back ? `. ${s.coming_back} returns in transit` : ""}
                      {s.written_off ? `. ${s.written_off} written off` : ""}
                      .
                    </div>
                  </span>
                  <span className={chipClass(tone)}>{label}</span>
                </li>
              );
            })}
          </ul>
        </div>
      )}

      {next_cursor && (
        <p className="pager">
          <Link
            className="btn btn--quiet"
            href={`${base}?${new URLSearchParams({ ...(state ? { state } : {}), cursor: next_cursor })}`}
          >
            Next page
          </Link>
        </p>
      )}
    </section>
  );
}
