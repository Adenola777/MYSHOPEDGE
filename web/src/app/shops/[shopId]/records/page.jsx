/**
 * S22 Records behind a figure.
 *
 * A18.5: every figure a seller sees can be opened, and what opens is the ledger rows that
 * produced it, not a recalculation. `getRecords` serves the rows, the total across every
 * page and the sum of this page, and both totals are shown so that a seller on page one of
 * four does not read the page sum as the figure being wrong.
 *
 * Every category carries the label the service gives it, the same words the Money screen
 * uses. Where TikTok named a fee in a way MyShopEdge does not recognise, TikTok's own name
 * is shown beside it.
 *
 * Not yet here: the discrepancy marker A3 asks for on affected rows, because a ledger entry
 * does not say which discrepancy touches it.
 */

import Link from "next/link";
import { fetchShop, formatDate } from "@/lib/api";
import { apiProblem } from "@/components/ApiProblem";
import { Figure } from "@/components/Figure";

export const metadata = { title: "Records" };

const PASSED = [
  "basis", "from", "to", "category", "entry_type", "sku_id", "product_id", "order_id",
  "return_id", "settlement_id",
];

/**
 * @param {{
 *   params: Promise<{ shopId: string }>,
 *   searchParams: Promise<Record<string, string>>,
 * }} props
 */
export default async function RecordsPage({ params, searchParams }) {
  const { shopId } = await params;
  const query = await searchParams;
  /** @type {Record<string, string>} */
  const filters = Object.fromEntries(
    PASSED.filter((k) => query[k]).map((k) => [k, String(query[k])]),
  );

  const result = await fetchShop(shopId, "/records", { ...filters, cursor: query.cursor });
  const problem = apiProblem(result, { what: "these records" });
  if (problem) return problem;

  /** @type {{ entries: import("@/lib/api-types").components["schemas"]["LedgerEntry"][], total: any, shown_total: any, next_cursor: string | null }} */
  const page = result.data;
  const first = page.entries[0];
  const heading = filters.category && first?.label ? first.label : "Records";
  const base = `/shops/${shopId}/records`;

  return (
    <section>
      <header className="page-head">
        <p><Link href={`/shops/${shopId}/money`}>Money</Link></p>
        <h1>{heading}</h1>
        <p>
          {filters.from && filters.to
            ? `${formatDate(filters.from)} to ${formatDate(filters.to)}, on the `
            : "On the "}
          {filters.basis === "cash" ? "cash basis" : "sales basis"}. These are the records
          behind the figure, as the ledger holds them.
        </p>
      </header>

      {page.entries.length === 0 ? (
        <section className="state">
          <h2>No records make up this figure.</h2>
          <p>Nothing was recorded against it in this period, which is why it reads as zero.</p>
        </section>
      ) : (
        <div className="card">
          <ul className="rows">
            {page.entries.map((e) => (
              <li key={e.id}>
                <span>
                  <strong>{e.label ?? e.category ?? e.entry_type}</strong>
                  <div className="rows__sub">
                    {formatDate(e.basis_day)}
                    {e.tiktok_order_id
                      ? `. TikTok order ${e.tiktok_order_id}`
                      : e.tiktok_invoice_number
                        ? `. TikTok invoice ${e.tiktok_invoice_number}`
                        : ""}
                    {e.tiktok_fee_type ? `. TikTok calls it ${e.tiktok_fee_type}` : ""}
                    {e.reason ? `. ${e.reason}` : ""}
                  </div>
                </span>
                <Figure amount={e.amount} />
              </li>
            ))}
            {page.next_cursor && (
              <li className="rows__total"><span>This page</span><Figure amount={page.shown_total} /></li>
            )}
            <li className="rows__total"><span>Total, every page</span><Figure amount={page.total} /></li>
          </ul>
        </div>
      )}

      {page.next_cursor && (
        <p className="pager">
          <Link
            className="btn btn--quiet"
            href={`${base}?${new URLSearchParams({ ...filters, cursor: page.next_cursor })}`}
          >
            Next page
          </Link>
        </p>
      )}
    </section>
  );
}
