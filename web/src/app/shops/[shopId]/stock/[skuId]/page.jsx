/**
 * S26 Stock movement history. Every movement for one variant, newest first.
 *
 * Movement types are named in plain English (A18.8), and a cancellation says the units went
 * back to stock. Each row carries the order or return it belongs to where one exists.
 *
 * **Not yet as A3 specifies.** A3 asks for the resulting count on every row and an opening
 * balance, so that the rows add up to the count on screen. `getStockMovements` serves
 * neither. A running balance summed here would be a figure the service never computed,
 * against A29.1, so the column waits for the contract to carry it. A3 also asks for every
 * row to link to its order or return. No order or return screen exists yet, and the
 * movement carries MyShopEdge's internal identifier rather than TikTok's order number,
 * which is the one a seller would recognise. The row therefore says only whether it
 * belongs to an order or a return.
 *
 * The heading names the product, the variant and the seller SKU from `sku` on the response.
 * The contract gained that field on 25 September 2026 at the owner's instruction, because
 * QA found this screen, which carries the adjustment form, named no item at all.
 */

import Link from "next/link";
import { fetchShop, formatDate } from "@/lib/api";
import { apiProblem } from "@/components/ApiProblem";
import { MOVEMENT } from "@/lib/terms";
import { AdjustForm } from "@/components/AdjustForm";

export const metadata = { title: "Stock movements" };

/**
 * @param {{
 *   params: Promise<{ shopId: string, skuId: string }>,
 *   searchParams: Promise<Record<string, string>>,
 * }} props
 */
export default async function MovementsPage({ params, searchParams }) {
  const { shopId, skuId } = await params;
  const query = await searchParams;

  const result = await fetchShop(shopId, `/stock/${encodeURIComponent(skuId)}/movements`, {
    cursor: query.cursor,
  });
  const problem = apiProblem(result, {
    what: "the movements for this variant",
    notFound: "That product variant was not found.",
  });
  if (problem) return problem;

  /**
   * @type {{
   *   sku: { product_title?: string | null, variant_label?: string | null, seller_sku?: string | null },
   *   movements: import("@/lib/api-types").components["schemas"]["StockMovement"][],
   *   next_cursor: string | null,
   * }}
   */
  const { sku, movements, next_cursor } = result.data;
  const variant = [sku.variant_label, sku.seller_sku ? `SKU ${sku.seller_sku}` : "No seller SKU"]
    .filter(Boolean).join(", ");
  const base = `/shops/${shopId}/stock/${skuId}`;

  return (
    <section>
      <header className="page-head">
        <p><Link href={`/shops/${shopId}/stock`}>Stock</Link></p>
        <h1>{sku.product_title || "Untitled product"}</h1>
        <p>{variant}. Every change to this variant&rsquo;s count, newest first.</p>
      </header>

      <AdjustForm shopId={shopId} skuId={skuId} />

      <h2 style={{ marginTop: "var(--space-5)" }}>History</h2>
      {movements.length === 0 ? (
        <section className="state">
          <h2>No movements recorded for this variant.</h2>
          <p>Sales, returns, cancellations and your own adjustments appear here as they happen.</p>
        </section>
      ) : (
        <div className="card">
          <ul className="rows">
            {movements.map((m) => (
              <li key={m.id}>
                <span>
                  <strong>{MOVEMENT[m.movement_type] ?? m.movement_type}</strong>
                  <div className="rows__sub">
                    {formatDate(m.occurred_at, { time: true })}
                    {m.order_id ? ". Belongs to an order" : m.return_id ? ". Belongs to a return" : ""}
                    {m.reason ? `. ${m.reason}` : ""}
                  </div>
                </span>
                <span className="money">
                  {m.quantity > 0 ? `+${m.quantity}` : m.quantity}{" "}
                  {Math.abs(m.quantity) === 1 ? "unit" : "units"}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {next_cursor && (
        <p className="pager">
          <Link className="btn btn--quiet" href={`${base}?cursor=${encodeURIComponent(next_cursor)}`}>
            Older movements
          </Link>
        </p>
      )}
    </section>
  );
}
