/**
 * Where a signed-in seller lands. `listShops` returns the shops on the account, and the MVP
 * allows one (CON-3), so a seller with one shop goes straight to its Today screen. Before
 * 24 September nothing gave a seller their shop id, so no shop screen could be reached
 * except by typing its address.
 */

import Link from "next/link";
import { redirect } from "next/navigation";
import { api } from "@/lib/api";
import { apiProblem } from "@/components/ApiProblem";
import { ConnectTikTok } from "@/components/ConnectTikTok";

export const metadata = { title: "Your shops" };

export default async function ShopsPage() {
  const result = await api("/shops", { cache: "no-store" });
  const problem = apiProblem(result, { what: "your shops" });
  if (problem) return problem;

  /** @type {import("@/lib/api-types").components["schemas"]["Shop"][]} */
  const shops = result.data.shops ?? [];
  const only = shops.length === 1 ? shops[0] : undefined;
  if (only) redirect(`/shops/${only.id}/today`);

  if (shops.length === 0) {
    // S1 Connect TikTok Shop, from wireframe sheet 02. Two lines of the wireframe are left
    // out because nothing behind them exists: disconnecting from Settings (neither the
    // Settings screen nor disconnectShop is built), and the step dots of an onboarding flow
    // whose other steps are not built either. "Not kept" for buyer details rests on SYN-7 and
    // the schema's own header, which rule that buyer data is dropped before anything is
    // written.
    return (
      <section>
        <header className="page-head">
          <h1>Connect your TikTok Shop</h1>
          <p>Read-only. MyShopEdge never changes anything in your shop.</p>
        </header>
        <div className="stack">
          <div className="card">
            <h2>What we read</h2>
            <ul className="rows">
              <li><span>Orders and sales</span><strong>Read</strong></li>
              <li><span>Products and stock</span><strong>Read</strong></li>
              <li><span>Payments and fees</span><strong>Read</strong></li>
              <li><span>Returns and refunds</span><strong>Read</strong></li>
            </ul>
          </div>
          <div className="card">
            <h2>What we do not keep</h2>
            <ul className="rows">
              <li><span>Buyer names and addresses</span><strong>Not kept</strong></li>
            </ul>
          </div>
          <ConnectTikTok />
        </div>
      </section>
    );
  }

  return (
    <section>
      <header className="page-head"><h1>Your shops</h1></header>
      <div className="card">
        <ul className="rows">
          {shops.map((s) => (
            <li key={s.id}>
              <Link href={`/shops/${s.id}/today`}>{s.shop_name ?? s.tiktok_shop_id}</Link>
              <span className="rows__sub">{s.region}</span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
