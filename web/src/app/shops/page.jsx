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
    return (
      <section className="state">
        <h1>No TikTok Shop is connected yet.</h1>
        <p>Once a shop is connected, its figures appear here.</p>
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
