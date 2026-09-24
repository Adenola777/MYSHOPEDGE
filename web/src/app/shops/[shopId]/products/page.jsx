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

export const metadata = { title: "Products" };

/** @param {{ params: Promise<{ shopId: string }>, searchParams: Promise<Record<string,string>> }} props */
export default async function ProductsPage({ params, searchParams }) {
  const { shopId } = await params;
  const query = await searchParams;

  const result = await fetchProducts(shopId, {
    measure: query.measure,
    from: query.from,
    to: query.to,
  });

  if (result.unreachable) {
    return (
      <Problem
        title="We cannot reach your figures right now."
        note={
          result.reason === "timeout"
            ? "The request took too long. Nothing is wrong with your data."
            : "This is a problem at our end, not with your shop. Your data is untouched."
        }
        retry
      />
    );
  }

  if (result.status === 401) {
    return (
      <Problem
        title="Please sign in again."
        note="Your session has expired. Signing in again brings you straight back here."
      />
    );
  }

  if (result.status === 403 || result.status === 404) {
    return (
      <Problem
        title="That shop is not on your account."
        note="Check the address, or pick a shop from your connections."
      />
    );
  }

  if (!result.ok || !result.data) {
    return (
      <Problem
        title="Your products could not be loaded."
        note="MyShopEdge did not answer, so no figures are shown rather than wrong ones. Try again in a moment."
        retry
      />
    );
  }

  /** @typedef {import("@/lib/api-types").components["schemas"]["ProductRow"]} ProductRow */
  /** @type {{ products: ProductRow[], total?: any, measure?: string, others?: { count: number, amount: any } }} */
  const { products = [], total, measure, others } = result.data;

  if (products.length === 0) {
    return (
      <section className="state">
        <h1>No products in this period yet.</h1>
        <p>
          Once orders come through, every product you sell appears here ranked by what you
          kept after TikTok&rsquo;s deductions, your costs and any returns.
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
          Ranked by what you kept, not by what sold. The figure at the top of a column is
          what reached you after TikTok&rsquo;s deductions, your own costs and any returns.
        </p>
      </header>

      {missingCosts > 0 && (
        <div className="note note--warn" role="status">
          <p>
            {missingCosts === 1
              ? "One product has no cost price yet, so its profit is unknown rather than zero."
              : `${missingCosts} products have no cost price yet, so their profit is unknown rather than zero.`}{" "}
            <Link href={`/shops/${shopId}/costs`}>Add your cost prices</Link> and these fill
            in on their own.
          </p>
        </div>
      )}

      <div className="card">
        <div className="table-scroll">
          <table>
            <caption>
              Every product sold in this period. Measured by {measure ?? "what you kept"}.
            </caption>
            <thead>
              <tr>
                <th scope="col">Product</th>
                <th scope="col" className="num">Units</th>
                <th scope="col" className="num">Returned</th>
                <th scope="col" className="num">Sales</th>
                <th scope="col" className="num">After TikTok</th>
                <th scope="col" className="num">You kept</th>
              </tr>
            </thead>
            <tbody>
              {products.map((p) => (
                <tr key={p.product_id}>
                  <th scope="row">
                    <Link href={`/shops/${shopId}/products/${p.product_id}`}>
                      {p.title || p.tiktok_product_id || "Untitled product"}
                    </Link>
                  </th>
                  <td className="num">{p.units}</td>
                  <td className="num">{p.returns_units || 0}</td>
                  <td className="num"><Figure amount={p.gross_sales} /></td>
                  <td className="num"><Figure amount={p.net_proceeds} /></td>
                  <td className="num">
                    <Figure amount={p.kept} reason={p.kept_reason} />
                  </td>
                </tr>
              ))}
            </tbody>
            {total && (
              <tfoot>
                <tr>
                  <th scope="row">Total</th>
                  <td className="num" colSpan={4} />
                  <td className="num"><Figure amount={total} /></td>
                </tr>
              </tfoot>
            )}
          </table>
        </div>
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

/** @param {{ title: string, note: string, retry?: boolean }} props */
function Problem({ title, note, retry }) {
  return (
    <section className="state">
      <h1>{title}</h1>
      <p>{note}</p>
      {retry && (
        <p>
          <a className="btn btn--quiet" href="">
            Try again
          </a>
        </p>
      )}
    </section>
  );
}
