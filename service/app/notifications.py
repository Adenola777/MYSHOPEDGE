"""Notifications. `listNotifications` and `updateNotification`, tracing NTF-1.

Notifications belong to the account, not to one shop, so both operations are scoped by
`tenant()` alone and take no shop id. The row level security policy on `notifications` is
`account_id = app_account_id()`, checked on the development branch on 24 September.

`unread_count` counts every unread notification on the account, whatever the page's
filters, for the reason `open_count` does on discrepancies: a count that fell when the
seller filtered would read as problems dealt with.

THE ONE WAY TRANSITION

The contract says a notification cannot return to unread. **Derived, not ruled:** the order
unread, read, done is treated as one way throughout, so done cannot go back to read either,
because the contract's reason ("a seller cannot lose track of what they have already dealt
with") applies to done at least as much as to read. Setting the status a notification
already has is accepted and changes nothing, so a repeated request is harmless.

Nothing writes notifications yet. The development branch holds none, so these operations
return an empty list there until the sweep that raises them is built.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel, Field

from .auth import Account, require_account
from .db import tenant
from .problems import Problem
from .settlements import MAX_LIMIT, decode_cursor, encode_cursor

router = APIRouter(tags=["Notifications"])

ORDER = {"unread": 0, "read": 1, "done": 2}


class Notification(BaseModel):
    id: UUID
    shop_id: UUID | None = None
    type: str
    severity: Literal["info", "warning", "critical"]
    title: str
    body: str | None = None
    entity_type: str | None = None
    entity_id: UUID | None = None
    status: Literal["unread", "read", "done"]
    created_at: datetime


class NotificationPage(BaseModel):
    notifications: list[Notification]
    unread_count: int = Field(ge=0)
    next_cursor: str | None = None


class NotificationUpdate(BaseModel):
    status: Literal["read", "done"]


COLUMNS = "id, shop_id, type, severity, title, body, entity_type, entity_id, status, created_at"


@router.get("/notifications", response_model=NotificationPage)
def list_notifications(
    account: Annotated[Account, Depends(require_account)],
    status: Annotated[Literal["unread", "read", "done"] | None, Query()] = None,
    severity: Annotated[Literal["info", "warning", "critical"] | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = 50,
    cursor: Annotated[str | None, Query()] = None,
) -> NotificationPage:
    where = ["account_id = %s"]
    args: list[Any] = [str(account.id)]
    if status:
        where.append("status = %s")
        args.append(status)
    if severity:
        where.append("severity = %s")
        args.append(severity)
    if cursor:
        c_time, c_id = decode_cursor(cursor)
        where.append("(created_at, id) < (%s::timestamptz, %s::uuid)")
        args += [c_time, c_id]
    args.append(limit + 1)

    with tenant(account.id) as conn:
        cur = conn.execute(
            f"select {COLUMNS} from notifications where {' and '.join(where)} "
            "order by created_at desc, id desc limit %s",
            args,
        )
        cols = [d.name for d in cur.description]
        rows = [dict(zip(cols, r, strict=True)) for r in cur.fetchall()]
        unread = conn.execute(
            "select count(*) from notifications where account_id = %s and status = 'unread'",
            (str(account.id),),
        ).fetchone()

    next_cursor = None
    if len(rows) > limit:
        rows = rows[:limit]
        next_cursor = encode_cursor(rows[-1]["created_at"], rows[-1]["id"])
    return NotificationPage(
        notifications=[Notification(**r) for r in rows],
        unread_count=int(unread[0]) if unread else 0,
        next_cursor=next_cursor,
    )


@router.patch("/notifications/{notificationId}", response_model=Notification)
def update_notification(
    body: NotificationUpdate,
    account: Annotated[Account, Depends(require_account)],
    notification_id: Annotated[UUID, Path(alias="notificationId")],
) -> Notification:
    with tenant(account.id) as conn:
        row = conn.execute(
            "select status from notifications where id = %s and account_id = %s for update",
            (str(notification_id), str(account.id)),
        ).fetchone()
        if row is None:
            raise Problem(404, "notification_not_found", "That notification was not found.")
        if ORDER[body.status] < ORDER[row[0]]:
            raise Problem(
                422, "validation_failed",
                f"A notification that is {row[0]} cannot go back to {body.status}.",
            )
        cur = conn.execute(
            f"update notifications set status = %s where id = %s and account_id = %s "
            f"returning {COLUMNS}",
            (body.status, str(notification_id), str(account.id)),
        )
        cols = [d.name for d in cur.description]
        return Notification(**dict(zip(cols, cur.fetchone(), strict=True)))
