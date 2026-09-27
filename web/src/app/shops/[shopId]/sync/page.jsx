/** S2 First sync, bound to getSyncStatus (SYN-1). */

import Link from "next/link";
import { fetchShop } from "@/lib/api";
import { apiProblem } from "@/components/ApiProblem";
import { SyncProgress } from "@/components/SyncProgress";

export const metadata = { title: "Bringing your shop in" };

/** @param {{ params: Promise<{ shopId: string }> }} props */
export default async function SyncPage({ params }) {
  const { shopId } = await params;
  const result = await fetchShop(shopId, "/sync");
  const problem = apiProblem(result, { what: "your sync status" });
  if (problem) return problem;

  return (
    <section data-testid="sync-screen">
      <header className="page-head">
        <h1>Bringing your shop in</h1>
        <p>We are pulling in your orders, returns and settlements from TikTok.</p>
      </header>
      <SyncProgress shopId={shopId} initial={result.data} />
      <p className="footnote">
        You can leave this screen. <Link href={`/shops/${shopId}/today`}>Go to Today</Link> and
        your figures will fill in as each part arrives.
      </p>
    </section>
  );
}
