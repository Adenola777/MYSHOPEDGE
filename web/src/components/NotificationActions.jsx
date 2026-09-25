"use client";

/**
 * The actions on S13. `updateNotification` moves a notice one way, from unread to read to
 * done (notifications.py), so each row offers only the steps still ahead of it. After a
 * change the page is refreshed, which also refreshes the bell's count in the top bar,
 * because that count is the service's `unread_count` and nothing here computes it.
 */

import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";

/**
 * @param {string} id
 * @param {"read" | "done"} status
 */
function update(id, status) {
  return api(`/notifications/${encodeURIComponent(id)}`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
}

/** @param {{ unreachable?: boolean, data?: any }} r */
function failure(r) {
  return r.unreachable
    ? "MyShopEdge could not be reached, so nothing was changed."
    : (r.data?.detail ?? "That did not go through.");
}

/** @param {{ id: string, status: "unread" | "read" | "done", title: string }} props */
export function NotificationActions({ id, status, title }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(/** @type {string | null} */ (null));

  /** @param {"read" | "done"} next */
  async function send(next) {
    setBusy(true);
    setError(null);
    const r = await update(id, next);
    setBusy(false);
    if (!r.ok) {
      setError(failure(r));
      return;
    }
    router.refresh();
  }

  if (status === "done") return null;
  return (
    <div className="notice__actions">
      {status === "unread" && (
        <button className="btn btn--quiet btn--small" disabled={busy} onClick={() => send("read")}
                aria-label={`Mark as read: ${title}`}>
          Mark as read
        </button>
      )}
      <button className="btn btn--quiet btn--small" disabled={busy} onClick={() => send("done")}
              aria-label={`Mark as done: ${title}`}>
        Done
      </button>
      {error && <p className="form-error" role="alert">{error}</p>}
    </div>
  );
}

/**
 * Marks every unread notice on this page as read, one request each, because the contract
 * has no bulk operation. It says "all" only when every unread notice is on the page.
 *
 * @param {{ ids: string[], all: boolean }} props
 */
export function MarkAllRead({ ids, all }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(/** @type {string | null} */ (null));

  async function send() {
    setBusy(true);
    setError(null);
    for (const id of ids) {
      const r = await update(id, "read");
      if (!r.ok) {
        setBusy(false);
        setError(failure(r));
        router.refresh();
        return;
      }
    }
    setBusy(false);
    router.refresh();
  }

  if (ids.length === 0) return null;
  return (
    <p>
      <button className="btn btn--quiet" disabled={busy} onClick={send}>
        {busy ? "Marking as read" : all ? "Mark all as read" : `Mark these ${ids.length} as read`}
      </button>
      {error && <span className="form-error" role="alert"> {error}</span>}
    </p>
  );
}
