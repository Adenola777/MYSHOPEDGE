/**
 * S16 Product transactions. The records behind one product's figures (A18.5). It reads
 * `/records?product_id=…`, which the service resolves to every ledger entry on any of the
 * product's variants. Both totals are shown: the whole figure, and this page's sum, so a
 * seller on page one is never misled into thinking the figure is wrong.
 */

import Link from "next/link";
import { fetchShop, formatDate } from "@/lib/api";
import { apiProblem } from "@/components/ApiProblem";
import { Figure } from "@/components/Figure";

export const metadata = { title: "Product transactions" };

/**
 * @param {{
 *   params: Promise<{ shopId: string, productId: string }>,
 *   searchParams: Promise<Record<string, string>>,
 * }} props
 */
export default async function ProductTransactionsPage({ params, searchParams }) {
  const { shopId, productId } = await params;
  const query = await searchParams;

  const result = await fetchShop(shopId, "/records", {
    product_id: productId,
    basis: query.basis,
    from: query.from,
    to: query.to,
    cursor: query.cursor,
  });
  const problem = apiProblem(result, { what: "this product's records" });
  if (problem) return problem;

  const page = result.data;
  const entries = page.entries ?? [];

  return (
    <section data-testid="product-transactions-screen">
      <header className="page-head">
        <p className="crumb">
          <Link href={`/shops/${shopId}/products/${productId}`}>Back to product</Link>
        </p>
        <h1>Every record behind this product</h1>
        <p>These are the ledger entries that add up to the figures on the product screen.</p>
      </header>

      <div className="card">
        <ul className="rows">
          <li className="rows__total">
            <span>Total across all records</span><Figure amount={page.total} />
          </li>
          <li className="rows__sub">
            <span>Shown on this page</span><Figure amount={page.shown_total} />
          </li>
        </ul>
      </div>

      <div className="card" data-testid="records-list">
        {entries.length === 0 ? (
          <p className="muted">No records for this product in this period.</p>
        ) : (
          <ul className="rows">
            {entries.map((/** @type {any} */ e) => (
              <li key={e.id}>
                <span>
                  {e.label ?? e.entry_type}
                  <div className="rows__sub">
                    {formatDate(e.basis_day)}
                    {e.tiktok_order_id ? ` · order ${e.tiktok_order_id}` : ""}
                    {e.source ? ` · ${e.source}` : ""}
                  </div>
                </span>
                <Figure amount={e.amount} />
              </li>
            ))}
          </ul>
        )}
        {page.next_cursor && (
          <p className="card__foot">
            <Link
              data-testid="records-next"
              href={`/shops/${shopId}/products/${productId}/transactions?cursor=${encodeURIComponent(page.next_cursor)}${query.basis ? `&basis=${query.basis}` : ""}`}
            >
              Show more
            </Link>
          </p>
        )}
      </div>
    </section>
  );
}
