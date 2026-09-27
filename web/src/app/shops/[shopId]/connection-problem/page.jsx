/**
 * S28 Connection problem. Shown when a shop's connection has lapsed or failed. It reads the
 * shop's `connection_status` from `/shops` and, when the connection is not healthy, tells the
 * seller plainly what it means for their figures and how to put it right. A healthy shop is
 * sent back to Today, so the screen is never a dead end.
 */

import Link from "next/link";
import { redirect } from "next/navigation";
import { api } from "@/lib/api";
import { apiProblem } from "@/components/ApiProblem";

export const metadata = { title: "Connection problem" };

const MESSAGE = {
  disconnected: {
    head: "Your shop is disconnected",
    body: "MyShopEdge has stopped reading from TikTok, so your figures will not update. Your records are safe and reconnecting resumes against them.",
  },
  error: {
    head: "There is a problem with your connection",
    body: "The last attempt to reach TikTok did not work, so your figures may be out of date.",
  },
  expired: {
    head: "Your TikTok authorisation has lapsed",
    body: "TikTok asks sellers to re-authorise from time to time. Until you do, new orders and settlements will not arrive.",
  },
};

/** @param {{ params: Promise<{ shopId: string }> }} props */
export default async function ConnectionProblemPage({ params }) {
  const { shopId } = await params;
  const result = await api("/shops", { cache: "no-store" });
  const problem = apiProblem(result, { what: "this shop" });
  if (problem) return problem;

  const shop = (result.data?.shops ?? []).find((/** @type {any} */ s) => s.id === shopId);
  const status = shop?.connection_status ?? "error";
  if (status === "connected") redirect(`/shops/${shopId}/today`);

  const m = MESSAGE[status] ?? MESSAGE.error;

  return (
    <section data-testid="connection-problem-screen">
      <header className="page-head">
        <h1>{m.head}</h1>
        <p>{shop?.shop_name ?? "Your shop"}</p>
      </header>
      <div className="note note--warn" role="status" data-testid="connection-status">
        <p>{m.body}</p>
      </div>
      <div className="card">
        <h2>Put it right</h2>
        <p className="card__why">Reconnect your shop to start bringing figures in again.</p>
        <p>
          <Link className="btn btn--primary" data-testid="reconnect-link" href={`/shops/${shopId}/settings`}>
            Reconnect this shop
          </Link>
        </p>
        <p className="card__foot">
          Your ledger, costs and saved figures are untouched while the connection is down.
        </p>
      </div>
    </section>
  );
}
