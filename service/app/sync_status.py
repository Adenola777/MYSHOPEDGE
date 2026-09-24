"""Sync status. `getSyncStatus`, tracing SYN-1 and SYN-6.

One entry per sync domain that has run at least once, from `sync_runs`: the latest run's
status and attempt, the records it wrote, and when the domain last completed.

WHAT DECIDES `stale`

The contract calls a domain stale when its newest success is older than the domain's
expected interval. SYN-3 and the Backend Orchestration document poll every domain every 15
minutes, so read literally a domain would be stale whenever one poll ran late. The owner
ruled in A29.3 that figures are stale after 24 hours without a successful sync, and SYN-6
puts the banner at 24 hours. A29.11 ranks that ruling above the contract, so a domain is
stale here when it has never completed or its last completion is over 24 hours old, the
same rule as Today's freshness.

WHAT IS LEFT OUT

`overall` is optional in the contract and is not served. Nothing says how five domain
states combine into one, and a guessed combination would decide what the seller is told.
`backfill_progress` is null, because no run records how many records a backfill expects.
A domain that has never run is not listed, because the contract's statuses describe runs
and inventing `scheduled` for a run nobody scheduled would be wrong.

`partial` was added to the contract's status list on 24 September, because migration 0022
adds it to `sync_runs` (A29.5). This endpoint reads only base columns, so it runs with or
without 0022 applied. Checked on the development branch on 24 September: `sync_runs` is
empty there, so the endpoint returns no domains.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from .auth import Account, require_account
from .dates import now_utc
from .db import tenant
from .shops import require_shop
from .today_view import freshness

router = APIRouter(tags=["Sync"])


class DomainStatus(BaseModel):
    domain: str
    status: str
    last_success_at: datetime | None = None
    stale: bool
    records_written: int = Field(default=0, ge=0)
    attempt: int = Field(default=0, ge=0)
    backfill_progress: float | None = None


class SyncStatus(BaseModel):
    shop_id: UUID
    as_of: datetime
    domains: list[DomainStatus]


SQL = """
select distinct on (r.domain)
       r.domain, r.status, r.attempt, r.records_written,
       (select max(x.finished_at) from sync_runs x
         where x.shop_id = r.shop_id and x.domain = r.domain
           and x.status = 'completed') as last_success_at
  from sync_runs r
 where r.shop_id = %s
 order by r.domain, coalesce(r.started_at, r.created_at) desc, r.id desc
"""


@router.get("/shops/{shopId}/sync", response_model=SyncStatus)
def get_sync_status(
    account: Annotated[Account, Depends(require_account)],
    shop_id: Annotated[UUID, Depends(require_shop)],
) -> SyncStatus:
    now = now_utc()
    with tenant(account.id) as conn:
        cur = conn.execute(SQL, (str(shop_id),))
        cols = [d.name for d in cur.description]
        rows = [dict(zip(cols, r, strict=True)) for r in cur.fetchall()]
    return SyncStatus(
        shop_id=shop_id,
        as_of=now,
        domains=[
            DomainStatus(
                domain=r["domain"],
                status=r["status"],
                last_success_at=r["last_success_at"],
                stale=freshness(r["last_success_at"], now).status == "stale",
                records_written=r["records_written"] or 0,
                attempt=r["attempt"] or 0,
            )
            for r in rows
        ],
    )
