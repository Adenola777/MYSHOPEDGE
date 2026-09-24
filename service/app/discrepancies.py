"""Discrepancies. Where TikTok and the seller disagree, and what was used meanwhile.

`listDiscrepancies`, tracing DSC-5. TC-DSC-05 leaves two discrepancies open and expects the
dashboard to show 2, so `open_count` counts every open discrepancy on the shop whatever the
page's own filters are. A count that shrank when the seller filtered by kind would read as
problems being fixed when they had only been hidden.

`applied_value` is returned as stored. Ruling 3 of migration 0013 says TikTok's value is
recorded while a discrepancy is open, and it is enforced where the discrepancy is raised,
not here.

The seventh kind, `unmapped_fee`, was added to the database by ruling 1 of 0013 on 22
September. The contract did not list it until 24 September, when it was added to both the
query parameter and the schema so a real row could be served.

Checked on the development branch, 24 September 2026: one discrepancy, open, kind `amount`,
on a settlement, TikTok's value -5.00 recorded as PLATFORM_PENALTY with no further reason.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from .auth import Account, require_account
from .db import tenant
from .settlements import MAX_LIMIT, decode_cursor, encode_cursor
from .shops import require_shop

router = APIRouter(tags=["Integrity"])

Kind = Literal[
    "product_code", "order_reference", "transaction_reference", "amount",
    "return_unmatched", "duplicate", "unmapped_fee",
]


class Discrepancy(BaseModel):
    id: UUID
    kind: Kind
    entity_type: str
    entity_id: UUID | None = None
    field: str | None = None
    tiktok_value: str | None = None
    seller_value: str | None = None
    applied_value: str | None = None
    status: Literal["open", "resolved"]
    resolution: Literal["accepted_tiktok", "corrected_seller", "explained"] | None = None
    note: str | None = None
    effect: dict[str, Any] | None = None
    opened_at: datetime
    resolved_at: datetime | None = None


class DiscrepancyPage(BaseModel):
    discrepancies: list[Discrepancy]
    open_count: int
    next_cursor: str | None = None


COLUMNS = """
  id, kind, entity_type, entity_id, field, tiktok_value, seller_value, applied_value,
  status, resolution, note, effect, opened_at, resolved_at
"""


@router.get("/shops/{shopId}/discrepancies", response_model=DiscrepancyPage)
def list_discrepancies(
    account: Annotated[Account, Depends(require_account)],
    shop_id: Annotated[UUID, Depends(require_shop)],
    status: Annotated[Literal["open", "resolved"] | None, Query()] = None,
    kind: Annotated[Kind | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = 50,
    cursor: Annotated[str | None, Query()] = None,
) -> DiscrepancyPage:
    where = ["shop_id = %s"]
    args: list[Any] = [str(shop_id)]
    if status:
        where.append("status = %s")
        args.append(status)
    if kind:
        where.append("kind = %s")
        args.append(kind)
    if cursor:
        c_time, c_id = decode_cursor(cursor)
        where.append("(opened_at, id) < (%s::timestamptz, %s::uuid)")
        args += [c_time, c_id]
    args.append(limit + 1)

    with tenant(account.id) as conn:
        cur = conn.execute(
            f"select {COLUMNS} from discrepancies where {' and '.join(where)} "
            "order by opened_at desc, id desc limit %s",
            args,
        )
        cols = [d.name for d in cur.description]
        rows = [dict(zip(cols, r, strict=True)) for r in cur.fetchall()]
        open_row = conn.execute(
            "select count(*) from discrepancies where shop_id = %s and status = 'open'",
            (str(shop_id),),
        ).fetchone()

    next_cursor = None
    if len(rows) > limit:
        rows = rows[:limit]
        next_cursor = encode_cursor(rows[-1]["opened_at"], rows[-1]["id"])

    return DiscrepancyPage(
        discrepancies=[Discrepancy(**r) for r in rows],
        open_count=int(open_row[0]) if open_row else 0,
        next_cursor=next_cursor,
    )
