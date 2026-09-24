/**
 * Products, ranked by what the seller actually kept.
 *
 * This is the screen the product exists for. TikTok tells a seller what it paid out.
 * This tells them which products earned it.
 *
 * Two things on this page are load bearing and neither is cosmetic.
 *
 * **A product with no cost shows no profit.** The API returns `kept` as null with a
 * `kept_reason` when a SKU has no cost price, and `Figure` renders that as a rule rather
 * than as zero. A seller who sees £0.00 concludes the product breaks even. A seller who
 * sees a dash and "no cost price yet" goes and uploads their costs. The first is a wrong
 * number presented as a fact, and this product is worth nothing if it does that.
 *
 * **Unreachable is not empty.** A network failure, an expired session and a shop that is
 * not yours all produce no rows, and a screen that renders "no products yet" for all
 * three tells a seller their shop is empty when it is not. Section 49 requires each state
 * separately and they are separate here.
 */

import Link from "next/link";
import { fetchProducts } from "@/lib/api";
import { Figure } from "@/components/Figure";
import { apiProblem } from "@/components/ApiProblem";
import { BEFORE_OVERHEADS } from "@/lib/terms";

export const metadata = { title: "Products" };

/** @type {Record<string, string>} */
const MEASURE = {
  kept: "gross profit after returns",
  net_proceeds: "net proceeds",
  gross_sales: "gross sales",
  units: "units sold",
  returns: "units returned",
};

/** @param {{ params: Promise<{ shopId: string }>, searchParams: Promise<Record<string,string>> }} props */
export default async function ProductsPage({ params, searchParams }) {
  const { shopId } = await params;
  const query = await searchParams;

  const result = await fetchProducts(shopId, {
    measure: query.measure,
    from: query.from,
    to: query.to,
  });

  const problem = apiProblem(result, { what: "your products" });
  if (problem) return problem;

  /** @typedef {import("@/lib/api-types").components["schemas"]["ProductRow"]} ProductRow */
  /** @type {{ products: ProductRow[], total?: any, measure?: string, others?: { count: number, amount: any } }} */
  const { products = [], total, measure, others } = result.data;

  if (products.length === 0) {
    return (
      <section className="state">
        <h1>No products in this period yet.</h1>
        <p>
          Once orders come through, every product you sell appears here ranked by what you
          made in gross profit after TikTok&rsquo;s deductions, your costs and any returns.
        </p>
      </section>
    );
  }

  const missingCosts = products.filter((p) => !p.cost_known).length;

  return (
    <section>
      <header className="billing__head">
        <h1>Products</h1>
        <p className="billing__lede">
          Ranked by gross profit after returns, not by what sold. That is what each
          product made after TikTok&rsquo;s deductions, your own costs and any returns.{" "}
          {BEFORE_OVERHEADS}
        </p>
      </header>

      {missingCosts > 0 && (
        <div className="note note--warn" role="status">
          <p>
            {missingCosts === 1
              ? "One product has no cost price yet, so its profit is unknown rather than zero."
              : `${missingCosts} products have no cost price yet, so their profit is unknown rather than zero.`}{" "}
            Once a cost price is added, the figure fills in on its own.
          </p>
        </div>
      )}

      <div className="card">
        <p className="rows__sub" style={{ marginTop: 0 }}>
          Every product sold in this period, measured by {MEASURE[measure ?? "kept"] ?? measure}.
        </p>
        <ul className="rows">
          {products.map((p) => (
            <li key={p.product_id}>
              <span>
                <Link href={`/shops/${shopId}/products/${p.product_id}`}>
                  {p.title || p.tiktok_product_id || "Untitled product"}
                </Link>
                <div className="rows__sub">
                  {p.units} sold, {p.returns_units || 0} returned. Gross sales{" "}
                  <Figure amount={p.gross_sales} />, net proceeds <Figure amount={p.net_proceeds} />.
                </div>
              </span>
              <Figure amount={p.kept} reason={p.kept_reason} />
            </li>
          ))}
          {total && (
            <li className="rows__total"><span>Total</span><Figure amount={total} /></li>
          )}
        </ul>
      </div>

      {others && others.count > 0 && (
        <p style={{ marginTop: "var(--space-4)", color: "var(--ink-500)" }}>
          {others.count} further {others.count === 1 ? "product" : "products"} outside this
          ranking, together worth <Figure amount={others.amount} />.
        </p>
      )}
    </section>
  );
}
