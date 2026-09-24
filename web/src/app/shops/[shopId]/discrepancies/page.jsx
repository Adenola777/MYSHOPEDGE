/**
 * S14 Discrepancies. Where TikTok and the seller's record disagree, and which value is in
 * use meanwhile.
 *
 * The contract has no endpoint for one discrepancy, so each discrepancy is shown in full on
 * this list rather than on a page of its own. `open_count` is the shop's whole open count,
 * whatever the filter, as TC-DSC-05 requires.
 *
 * An unmapped fee is not a disagreement. It has only TikTok's side (A18.4), so it is
 * explained as a fee MyShopEdge does not recognise, and it says plainly that the seller has
 * done nothing wrong and that the money is counted.
 *
 * The three actions on the wireframe (accept TikTok's value, correct my record, mark as
 * explained) go through `resolveDiscrepancy`. "Correct my record" appears only where the
 * service says the fact is the seller's own (`correctable`).
 */

import Link from "next/link";
import { fetchShop, formatDate } from "@/lib/api";
import { apiProblem } from "@/components/ApiProblem";
import { DISCREPANCY_KIND, RESOLUTION, chipClass } from "@/lib/terms";
import { ResolveActions } from "@/components/ResolveActions";

export const metadata = { title: "Discrepancies" };

/**
 * @param {{
 *   params: Promise<{ shopId: string }>,
 *   searchParams: Promise<Record<string, string>>,
 * }} props
 */
export default async function DiscrepanciesPage({ params, searchParams }) {
  const { shopId } = await params;
  const query = await searchParams;
  const status = query.status === "resolved" ? "resolved" : "open";

  const result = await fetchShop(shopId, "/discrepancies", {
    status,
    kind: query.kind,
    cursor: query.cursor,
  });
  const problem = apiProblem(result, { what: "your discrepancies" });
  if (problem) return problem;

  /** @type {{ discrepancies: import("@/lib/api-types").components["schemas"]["Discrepancy"][], open_count: number, next_cursor: string | null }} */
  const { discrepancies, open_count, next_cursor } = result.data;
  const base = `/shops/${shopId}/discrepancies`;

  return (
    <section>
      <header className="page-head">
        <h1>Discrepancies</h1>
        <p>
          {open_count === 0
            ? "No discrepancy is open right now."
            : `${open_count} ${open_count === 1 ? "discrepancy is" : "discrepancies are"} open. While one is open, totals use TikTok's value.`}
        </p>
      </header>

      <nav className="switch" aria-label="Show">
        <Link href={`${base}?status=open`} aria-current={status === "open" ? "true" : undefined}>Open</Link>
        <Link href={`${base}?status=resolved`} aria-current={status === "resolved" ? "true" : undefined}>
          Resolved
        </Link>
      </nav>

      {discrepancies.length === 0 ? (
        <section className="state">
          <h2>{status === "open" ? "No open discrepancies." : "No resolved discrepancies yet."}</h2>
        </section>
      ) : (
        <div className="stack">
          {discrepancies.map((d) => (
            <article className="card" key={d.id}>
              <h2>
                {DISCREPANCY_KIND[d.kind] ?? d.kind}{" "}
                <span className={chipClass(d.status === "open" ? "warn" : "good")}>
                  {d.status === "open" ? "Open" : (RESOLUTION[d.resolution ?? ""] ?? "Resolved")}
                </span>
              </h2>
              <p className="rows__sub">
                On a {d.entity_type}{d.field ? `, field ${d.field}` : ""}. Opened{" "}
                {formatDate(d.opened_at)}
                {d.resolved_at ? `, resolved ${formatDate(d.resolved_at)}` : ""}.
              </p>

              {d.kind === "unmapped_fee" ? (
                <p>
                  TikTok charged a fee under a name MyShopEdge does not recognise:{" "}
                  <strong>{d.tiktok_value}</strong>. You have done nothing wrong. The money is
                  counted in full and reduces your net proceeds, under the name TikTok gave it.
                </p>
              ) : (
                <ul className="rows">
                  <li><span>TikTok</span><strong>{d.tiktok_value ?? "Nothing recorded"}</strong></li>
                  <li><span>Your record</span><strong>{d.seller_value ?? "Nothing recorded"}</strong></li>
                  <li className="rows__total"><span>We are using</span><strong>{d.applied_value ?? "Nothing yet"}</strong></li>
                </ul>
              )}
              {d.note && <p className="rows__sub" style={{ marginTop: "var(--space-3)" }}>{d.note}</p>}
              {d.status === "open" && (
                <ResolveActions shopId={shopId} id={d.id} correctable={Boolean(d.correctable)} />
              )}
            </article>
          ))}
        </div>
      )}

      {next_cursor && (
        <p className="pager">
          <Link
            className="btn btn--quiet"
            href={`${base}?${new URLSearchParams({ status, ...(query.kind ? { kind: query.kind } : {}), cursor: next_cursor })}`}
          >
            Next page
          </Link>
        </p>
      )}
    </section>
  );
}
