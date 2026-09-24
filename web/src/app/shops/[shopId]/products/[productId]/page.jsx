/**
 * S10 Product detail. Whether one product makes money.
 *
 * `getProduct` serves the calculator for the product over the period, the same calculator
 * per unit, the stock position, and each variant with its cost. The screen lays them out
 * and computes nothing. A18.2 requires the screen to say that the figures are allocated,
 * because TikTok reports deductions per order, not per product.
 *
 * Drawn to wireframe sheet 06 (redrawn 24 September after the design audit): the title
 * with the SKU and the count on the shelf, one unit pound by pound, the figures for the
 * period, then the variants with their costs.
 *
 * Not yet as the sheet shows. The segmented bar across one unit waits for the per product
 * split that phase 3 of the audit adds to the contract. "Worth a look" is not served by
 * anything. The Returns card needs a product's return rate, which the contract does not
 * carry. None of these is drawn empty.
 *
 * A cost is set per variant through `putSkuCost` (S21). The stock count appears only for a
 * product with a single variant, which is what the service serves (products.py says why).
 */

import Link from "next/link";
import { fetchShop } from "@/lib/api";
import { apiProblem } from "@/components/ApiProblem";
import { CostForm } from "@/components/CostForm";
import { Figure } from "@/components/Figure";
import { BEFORE_OVERHEADS, STOCK_STATE, chipClass } from "@/lib/terms";

export const metadata = { title: "Product" };

/**
 * @param {{
 *   params: Promise<{ shopId: string, productId: string }>,
 *   searchParams: Promise<Record<string, string>>,
 * }} props
 */
export default async function ProductDetailPage({ params, searchParams }) {
  const { shopId, productId } = await params;
  const query = await searchParams;

  const result = await fetchShop(shopId, `/products/${encodeURIComponent(productId)}`, {
    basis: query.basis,
    from: query.from,
    to: query.to,
  });
  const problem = apiProblem(result, {
    what: "this product",
    notFound: "That product was not found.",
  });
  if (problem) return problem;

  /** @type {import("@/lib/api-types").components["schemas"]["ProductDetail"]} */
  const d = result.data;
  const p = d.product;
  const perUnit = /** @type {{ units: number, sections: any[] }} */ (d.per_unit);
  const stock = d.stock;
  const [stateLabel, stateTone] = stock
    ? (STOCK_STATE[stock.state] ?? [stock.state, "quiet"])
    : ["", "quiet"];

  const sections = /** @type {any[]} */ (d.sections);
  return (
    <section>
      <header className="page-head">
        <p className="crumb"><Link href={`/shops/${shopId}/products`}>Products</Link></p>
        <h1>{p.title || p.tiktok_product_id || "Untitled product"}</h1>
        <p>
          {p.units} {p.units === 1 ? "unit" : "units"} sold in this period
          {stock ? `. ${stock.on_shelf} on the shelf. ` : ". "}
          {stock && <span className={chipClass(stateTone)}>{stateLabel}</span>}
        </p>
      </header>

      <div className="stack">
        <div className="card">
          <h2>One unit, pound by pound</h2>
          <p className="card__why">Where the money from one sale of this product goes.</p>
          {perUnit.sections.length === 0 ? (
            <p className="muted">Nothing sold in this period, so there is no unit to break down.</p>
          ) : (
            <ul className="rows">
              {perUnit.sections.flatMap((s) =>
                s.lines.map((/** @type {any} */ l, /** @type {number} */ i) => (
                  <li key={`${s.key}-${l.category}-${i}`}>
                    <span>{l.label}</span>
                    <Figure amount={l.amount} />
                  </li>
                )),
              )}
            </ul>
          )}
        </div>

        <div className="card hero">
          <p className="hero__label">Gross profit after returns</p>
          <p className="hero__value"><Figure amount={p.kept} reason={p.kept_reason} /></p>
          <p className="hero__line">{p.kept ? BEFORE_OVERHEADS : p.kept_reason}</p>
        </div>

        <div className="card">
          <h2>This period</h2>
          <p className="card__why">Every sale of this product, and what came off it.</p>
          <ul className="rows">
            {sections.flatMap((s) => [
              ...s.lines.map((/** @type {any} */ l, /** @type {number} */ i) => (
                <li key={`${s.key}-${l.category}-${i}`}>
                  <span>{l.label}</span>
                  <Figure amount={l.amount} />
                </li>
              )),
              <li key={`${s.key}-total`} className="rows__total">
                <span>{s.subtotal_label ?? "Subtotal"}</span>
                <Figure amount={s.subtotal} />
              </li>,
            ])}
          </ul>
        </div>

        <div className="card">
          <h2>Product cost</h2>
          <p className="card__why">What one unit costs you. It drives every profit figure here.</p>
          <ul className="rows">
            {(d.skus ?? []).map((s) => (
              <li key={s.sku_id} style={{ flexWrap: "wrap" }}>
                <span>
                  <Link className="rowlink" href={`/shops/${shopId}/stock/${s.sku_id}`}>
                    {s.variant_label || s.seller_sku || "Variant"}
                  </Link>
                  <div className="rows__sub">
                    {s.seller_sku ?? "No seller SKU. Add a cost on this screen."}
                  </div>
                </span>
                <Figure amount={s.cost} reason="Not provided" />
                {s.sku_id && (
                  <div style={{ flexBasis: "100%" }}>
                    <CostForm shopId={shopId} skuId={s.sku_id}
                              currency={s.cost?.currency ?? p.gross_sales.currency ?? "GBP"} />
                  </div>
                )}
              </li>
            ))}
          </ul>
        </div>
      </div>

      <p className="footnote">
        TikTok reports its deductions per order, not per product. Where an order held more than
        one product, its deductions are shared across them in proportion, and the shares add up
        to the order exactly.
      </p>
    </section>
  );
}
