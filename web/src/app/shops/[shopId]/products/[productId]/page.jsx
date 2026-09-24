/**
 * S10 Product detail. Whether one product makes money.
 *
 * `getProduct` serves the calculator for the product over the period, the same calculator
 * per unit, the stock position, and each variant with its cost. The screen lays them out
 * and computes nothing. A18.2 requires the screen to say that the figures are allocated,
 * because TikTok reports deductions per order, not per product.
 *
 * A cost is set per variant through `putSkuCost` (S21). Not yet here: the rule based insight,
 * because nothing serves one; and the return rate, which the contract does not carry for a
 * product. The stock block appears only for a product with a single variant, which is what
 * the service serves (products.py records why).
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

  return (
    <section>
      <header className="page-head">
        <p><Link href={`/shops/${shopId}/products`}>Products</Link></p>
        <h1>{p.title || p.tiktok_product_id || "Untitled product"}</h1>
        <p>
          {p.units} {p.units === 1 ? "unit" : "units"} sold in this period.
          {stock && (
            <>
              {" "}{stock.on_shelf} in stock.{" "}
              <span className={chipClass(stateTone)}>{stateLabel}</span>
            </>
          )}
        </p>
      </header>

      <div className="note note--info">
        <p>
          TikTok reports its deductions per order, not per product. Where an order held
          more than one product, its deductions are shared across the products in
          proportion, and the shares add up to the order exactly.
        </p>
      </div>

      <div className="stack">
        <div className="card">
          <h2>One unit, pound by pound</h2>
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

        {d.sections.map((s) => (
          <div className="card" key={s.key}>
            <h2>{s.label}</h2>
            <ul className="rows">
              {s.lines.map((l, i) => (
                <li key={`${l.category}-${i}`}>
                  <span>{l.label}</span>
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
          <p className="hero__value"><Figure amount={p.kept} reason={p.kept_reason} /></p>
          <p className="muted">{p.kept ? BEFORE_OVERHEADS : p.kept_reason}</p>
        </div>

        <div className="card">
          <h2>Variants and their costs</h2>
          <ul className="rows">
            {(d.skus ?? []).map((s) => (
              <li key={s.sku_id} style={{ flexWrap: "wrap" }}>
                <span>
                  <Link href={`/shops/${shopId}/stock/${s.sku_id}`}>
                    {s.variant_label || s.seller_sku || "Variant"}
                  </Link>
                  <div className="rows__sub">
                    {s.seller_sku ?? "No seller SKU. A cost for it can be added by hand."}
                  </div>
                </span>
                <Figure amount={s.cost} reason="No cost price yet" />
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
    </section>
  );
}
