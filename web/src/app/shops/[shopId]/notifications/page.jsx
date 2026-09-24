/**
 * S13 Notifications, from wireframe sheet 08: the title, how many need the seller, an Open
 * and Resolved switch, and one row per notice with its chip.
 *
 * `listNotifications` is served. Open is every notice not yet `done`, and Resolved is those
 * that are, which is how `notifications.py` moves a notice, one way, from unread to read to
 * done. `unread_count` is the service's own count and is shown as it came.
 *
 * **Not yet as the wireframe says.** WFW section 4 says tapping a notice opens the relevant
 * screen. A Notification carries `entity_type` and `entity_id` but no address, and working
 * out an address here from a type would be a rule the service does not state, so a row is
 * not yet a link.
 */

import { api, formatDate } from "@/lib/api";
import { apiProblem } from "@/components/ApiProblem";
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

  const result = await api(`/notifications?limit=100${resolved ? "&status=done" : ""}`, { cache: "no-store" });
  const problem = apiProblem(result, { what: "your notifications" });
  if (problem) return problem;

  /** @type {{ notifications: any[], unread_count: number }} */
  const { notifications, unread_count } = result.data;
  const rows = resolved ? notifications : notifications.filter((n) => n.status !== "done");
  const base = `/shops/${shopId}/notifications`;

  return (
    <section>
      <header className="page-head">
        <h1>Notifications</h1>
        <p>{unread_count === 0 ? "Nothing new." : `${unread_count} unread`}</p>
      </header>

      <nav className="switch" aria-label="Show">
        <a href={base} aria-current={!resolved ? "true" : undefined}>Open</a>
        <a href={`${base}?show=resolved`} aria-current={resolved ? "true" : undefined}>Resolved</a>
      </nav>

      {rows.length === 0 ? (
        <section className="state">
          <h2>{resolved ? "Nothing resolved yet." : "Nothing needs you."}</h2>
          <p>Notices appear here when something in your shop changes or needs a decision.</p>
        </section>
      ) : (
        <div className="card">
          <ul className="rows">
            {rows.map((n) => (
              <li key={n.id}>
                <span>
                  {n.status === "unread" ? <strong>{n.title}</strong> : n.title}
                  <div className="rows__sub">
                    {n.body ? `${n.body} ` : ""}
                    {formatDate(n.created_at)}
                  </div>
                </span>
                <span className={chipClass(SEVERITY_TONE[n.severity] ?? "quiet")}>
                  {SEVERITY_WORD[n.severity] ?? "Note"}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
