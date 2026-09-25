/**
 * S9 Products, drawn to wireframe sheet 06 (redrawn 24 September after the design audit).
 *
 * The sheet: the title and what the ranking is by; a measure switch; one row per product
 * with its figure on the right; uncosted products below the ranked ones with "Add cost".
 *
 * The measure switch is served, because `listProducts` takes `measure`. The ranking comes
 * from the service in its order (A29.1). Uncosted products are listed after the ranked
 * ones, as the sheet shows, by the `cost_known` flag the service returns.
 *
 * **Not yet as the sheet shows.** Each row on the sheet carries a pence-in-the-pound bar
 * split into stock, postage, TikTok and what is left. That split is a financial rule, so it
 * belongs in the service and waits for phase 3 of the audit, which adds it to the contract.
 *
 * A product with no cost shows no profit, never £0.00: `Figure` renders the reason.
 *
 * **Money tied to no product has its own line**, as the owner ruled on 25 September 2026.
 * A platform adjustment TikTok applies to a whole statement belongs to the shop and to no
 * product, so the products alone do not add up to Money. The service returns those lines
 * as `unattributed` and the sum as `shop_total`, and the screen shows both beneath the
 * products, so the last figure on this screen is the one Money shows for the same period.
 */

import Link from "next/link";
import { fetchProducts } from "@/lib/api";
import { Figure } from "@/components/Figure";
import { apiProblem } from "@/components/ApiProblem";
import { LineLabel } from "@/components/LineLabel";
import { BEFORE_OVERHEADS } from "@/lib/terms";

export const metadata = { title: "Products" };

/** The switch on the sheet, in A8's words. */
const SWITCH = [
  ["kept", "Gross profit"],
  ["units", "Units"],
  ["returns", "Returns"],
];

/** @type {Record<string, string>} */
const RANKED_BY = {
  kept: "Ranked by gross profit after returns",
  net_proceeds: "Ranked by net proceeds",
  gross_sales: "Ranked by gross sales",
  units: "Ranked by units sold",
  returns: "Ranked by units returned",
};

/** @param {{ params: Promise<{ shopId: string }>, searchParams: Promise<Record<string,string>> }} props */
export default async function ProductsPage({ params, searchParams }) {
  const { shopId } = await params;
  const query = await searchParams;

  const result = await fetchProducts(shopId, { measure: query.measure, from: query.from, to: query.to });
  const problem = apiProblem(result, { what: "your products" });
  if (problem) return problem;

  /** @typedef {import("@/lib/api-types").components["schemas"]["ProductRow"]} ProductRow */
  /** @typedef {import("@/lib/api-types").components["schemas"]["ProductRanking"]} Ranking */
  /** @type {{ products: ProductRow[], total?: any, measure?: string, others?: { count: number, amount: any }, unattributed?: Ranking["unattributed"], shop_total?: any }} */
  const { products = [], total, measure = "kept", others, unattributed, shop_total } = result.data;
  const base = `/shops/${shopId}/products`;

  const ranked = products.filter((p) => p.cost_known || measure !== "kept");
  const uncosted = measure === "kept" ? products.filter((p) => !p.cost_known) : [];

  return (
    <section>
      <header className="page-head">
        <h1>Products</h1>
        <p>{RANKED_BY[measure] ?? "Ranked"}</p>
      </header>

      <nav className="switch" aria-label="Rank by">
        {SWITCH.map(([value, label]) => (
          <Link key={value} href={value === "kept" ? base : `${base}?measure=${value}`}
                aria-current={measure === value ? "true" : undefined}>
            {label}
          </Link>
        ))}
      </nav>

      {products.length === 0 ? (
        <section className="state">
          <h2>No products sold in this period yet.</h2>
          <p>Once orders come through, every product you sell appears here, ranked.</p>
        </section>
      ) : (
        <div className="card">
          <ul className="rows rows--products">
            {ranked.map((p) => (
              <li key={p.product_id}>
                <span>
                  <Link className="rowlink" href={`${base}/${p.product_id}`}>
                    {p.title || p.tiktok_product_id || "Untitled product"}
                  </Link>
                  <div className="rows__sub">
                    {p.units} sold{p.returns_units ? `, ${p.returns_units} returned` : ""}. Net proceeds{" "}
                    <Figure amount={p.net_proceeds} />
                  </div>
                </span>
                {measure === "units" ? <strong className="money">{p.units}</strong>
                  : measure === "returns" ? <strong className="money">{p.returns_units || 0}</strong>
                  : <Figure amount={p.kept} reason={p.kept_reason} />}
              </li>
            ))}
            {uncosted.map((p) => (
              <li key={p.product_id}>
                <span>
                  <Link className="rowlink" href={`${base}/${p.product_id}`}>
                    {p.title || p.tiktok_product_id || "Untitled product"}
                  </Link>
                  <div className="rows__sub">Product cost: not provided. Net proceeds <Figure amount={p.net_proceeds} /></div>
                </span>
                <Link className="chip chip--strong" href={`${base}/${p.product_id}`}>Add cost</Link>
              </li>
            ))}
            {total && measure === "kept" && (
              <li className="rows__total">
                <span>{unattributed ? "Total across products" : "Total"}</span>
                <Figure amount={total} />
              </li>
            )}
            {unattributed && measure === "kept" && (
              <>
                <li className="rows__group"><span>For the whole shop, not one product</span></li>
                {unattributed.lines.map((l) => (
                  <li key={`${l.category}-${l.tiktok_fee_type ?? ""}`}>
                    <LineLabel line={l} />
                    <Figure amount={l.amount} />
                  </li>
                ))}
                <li className="rows__total">
                  <span>Total for the shop</span>
                  <Figure amount={shop_total} reason="Not known until every product sold has a cost price." />
                </li>
              </>
            )}
          </ul>
          {others && others.count > 0 && (
            <p className="rows__sub" style={{ marginTop: "var(--space-2)" }}>
              {others.count} further {others.count === 1 ? "product" : "products"}, together{" "}
              <Figure amount={others.amount} />.
            </p>
          )}
        </div>
      )}

      {measure === "kept" && (
        <p className="footnote">
          {BEFORE_OVERHEADS}
          {unattributed ? " The total for the shop is the figure Money shows for the same period." : ""}
        </p>
      )}
    </section>
  );
}
