/**
 * S3/S4 Product costs. Upload a spreadsheet of costs, or add them by hand on each product.
 * A cost drives every profit figure for its product, so this is where a seller turns "net
 * proceeds" into "gross profit after returns".
 */

import Link from "next/link";
import { fetchShop } from "@/lib/api";
import { apiProblem } from "@/components/ApiProblem";
import { CostUploadFlow } from "@/components/CostUploadFlow";

export const metadata = { title: "Product costs" };

/** @param {{ params: Promise<{ shopId: string }> }} props */
export default async function CostsPage({ params }) {
  const { shopId } = await params;
  // A cheap read that proves the shop is the caller's before the upload flow renders.
  const coverage = await fetchShop(shopId, "/costs/coverage");
  const problem = apiProblem(coverage, { what: "your cost coverage" });
  if (problem) return problem;

  const c = coverage.data;
  const pct = Math.round((c.coverage ?? 0) * 100);

  return (
    <section data-testid="costs-screen">
      <header className="page-head">
        <h1>Product costs</h1>
        <p>Add what your products cost you, so MyShopEdge can show profit, not just proceeds.</p>
      </header>

      <div className="card" data-testid="cost-coverage">
        <h2>Coverage</h2>
        <p className="card__why">The share of sold units that have a cost.</p>
        <p className="hero__value">{pct}%</p>
        <p className="hero__line">
          {c.units_with_cost} of {c.units_total} sold units have a cost.
          {c.skus_missing_cost > 0 ? ` ${c.skus_missing_cost} products still need one.` : ""}
        </p>
      </div>

      <CostUploadFlow shopId={shopId} />

      <div className="card">
        <h2>Prefer to type them?</h2>
        <p className="card__why">You can add a cost by hand on any product.</p>
        <p><Link className="rowlink" href={`/shops/${shopId}/products`}>Go to Products</Link></p>
      </div>
    </section>
  );
}
