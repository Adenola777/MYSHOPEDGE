/**
 * S13 Notifications, from wireframe sheet 08: the title, how many need the seller, an Open
 * and Resolved switch, and one row per notice with its chip.
 *
 * Open is every notice not yet `done` and Resolved is those that are. Both are filtered by
 * the service (`status=open` and `status=done`) and paged by its cursor, so a seller with a
 * long history of resolved notices never has an open one pushed off the page. Until
 * 25 September 2026 this screen fetched one page of everything and filtered it here.
 *
 * Each open notice can be marked read or done, one way, as `notifications.py` allows. The
 * page then refreshes, and so does the bell, whose count is the service's `unread_count`.
 * The owner asked on 25 September for notifications to work properly after QA found that
 * nothing could mark one read, so the bell's count could never fall.
 *
 * **Not yet as the wireframe says.** WFW section 4 says tapping a notice opens the relevant
 * screen. A Notification carries `entity_type` and `entity_id` but no address, and working
 * out an address here from a type would be a rule the service does not state, so a row is
 * not yet a link.
 */

import Link from "next/link";
import { api, formatDate } from "@/lib/api";
import { apiProblem } from "@/components/ApiProblem";
import { MarkAllRead, NotificationActions } from "@/components/NotificationActions";
import { chipClass, SEVERITY_TONE } from "@/lib/terms";

export const metadata = { title: "Notifications" };

/** @type {Record<string, string>} */
const SEVERITY_WORD = { critical: "Urgent", warning: "Check", info: "Note" };

/**
 * @param {{
 *   params: Promise<{ shopId: string }>,
 *   searchParams: Promise<Record<string, string>>,
 * }} props
 */
export default async function NotificationsPage({ params, searchParams }) {
  const { shopId } = await params;
  const query = await searchParams;
  const resolved = query.show === "resolved";

  const q = new URLSearchParams({ status: resolved ? "done" : "open", limit: "50" });
  if (query.cursor) q.set("cursor", query.cursor);
  const result = await api(`/notifications?${q}`, { cache: "no-store" });
  const problem = apiProblem(result, { what: "your notifications" });
  if (problem) return problem;

  /** @type {{ notifications: import("@/lib/api-types").components["schemas"]["Notification"][], unread_count: number, next_cursor?: string | null }} */
  const { notifications, unread_count, next_cursor } = result.data;
  const base = `/shops/${shopId}/notifications`;
  const unreadHere = notifications.filter((n) => n.status === "unread").map((n) => n.id);

  return (
    <section>
      <header className="page-head">
        <h1>Notifications</h1>
        <p>{unread_count === 0 ? "Nothing new." : `${unread_count} unread`}</p>
      </header>

      <nav className="switch" aria-label="Show">
        <Link href={base} aria-current={!resolved ? "true" : undefined}>Open</Link>
        <Link href={`${base}?show=resolved`} aria-current={resolved ? "true" : undefined}>Resolved</Link>
      </nav>

      {!resolved && <MarkAllRead ids={unreadHere} all={unreadHere.length === unread_count} />}

      {notifications.length === 0 ? (
        <section className="state">
          <h2>{resolved ? "Nothing resolved yet." : "Nothing needs you."}</h2>
          <p>Notices appear here when something in your shop changes or needs a decision.</p>
        </section>
      ) : (
        <div className="card">
          <ul className="rows">
            {notifications.map((n) => (
              <li key={n.id}>
                <span>
                  {n.status === "unread" ? <strong>{n.title}</strong> : n.title}
                  <div className="rows__sub">
                    {[n.status === "unread" ? "New" : null, n.body?.replace(/\.\s*$/, ""), formatDate(n.created_at)]
                      .filter(Boolean).join(". ")}
                  </div>
                  <NotificationActions id={n.id} status={n.status} title={n.title} />
                </span>
                <span className={chipClass(SEVERITY_TONE[n.severity] ?? "quiet")}>
                  {SEVERITY_WORD[n.severity] ?? "Note"}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {next_cursor && (
        <p className="pager">
          <Link
            className="btn btn--quiet"
            href={`${base}?${new URLSearchParams({ ...(resolved ? { show: "resolved" } : {}), cursor: next_cursor })}`}
          >
            Older notices
          </Link>
        </p>
      )}
    </section>
  );
}
