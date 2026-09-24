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

import json
from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Path, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, computed_field

from .auth import Account, require_account
from .db import tenant
from .money import Money
from .idempotency import record, replay, request_hash
from .problems import Problem
from .settlements import MAX_LIMIT, decode_cursor, encode_cursor
from .shops import require_shop

router = APIRouter(tags=["Integrity"])

# Kinds about a fact TikTok owns. Derived, and explained above resolve_discrepancy below.
TIKTOK_OWNED_KINDS = {"amount", "unmapped_fee"}

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

    @computed_field
    @property
    def correctable(self) -> bool:
        return self.status == "open" and self.kind not in TIKTOK_OWNED_KINDS


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


# --- resolveDiscrepancy, DSC-4 -------------------------------------------------------------
#
# What the rulings say, and therefore what this does.
#
# - Ruling 3 of migration 0013: while a discrepancy is open, the value in use is TikTok's for
#   any fact TikTok owns. The seller may accept or explain such a fact, never correct it.
# - The same ruling: `corrected_seller` is available only where the disputed fact is the
#   seller's own.
# - TC-DSC-04: resolving closes the flag, writes a log entry each time, and a correction
#   changes only the seller field.
#
# So no resolution moves money under the current rulings, and `adjustment_posted` is always
# null. Accepting leaves TikTok's value in use, which it already was. Explaining adds a note.
# Correcting writes the seller's own record, `seller_value`, and leaves `applied_value`.
# The request field the contract names `applied_value` is therefore stored as the seller's
# value, because TC-DSC-04 says the correction changes only the seller field.
#
# **Derived, not ruled: which kinds concern a fact TikTok owns.** `amount` and
# `unmapped_fee` are about statement amounts and fees, which 0013 lists as TikTok's. The
# other five kinds compare the seller's own record (a product code, a reference, a return
# they confirmed) with TikTok's, so the seller may correct their side.
#
# The log entry goes to `change_log`, which refuses updates and deletes by trigger.



class ResolveIn(BaseModel):
    resolution: Literal["accepted_tiktok", "corrected_seller", "explained"]
    note: str | None = Field(default=None, max_length=1000)
    applied_value: str | None = None


class AdjustmentPosted(BaseModel):
    ledger_entry_id: UUID
    amount: Money


class ResolveOut(BaseModel):
    discrepancy: Discrepancy
    adjustment_posted: AdjustmentPosted | None = None


@router.post("/shops/{shopId}/discrepancies/{discrepancyId}/resolve", response_model=ResolveOut)
def resolve_discrepancy(
    body: ResolveIn,
    account: Annotated[Account, Depends(require_account)],
    shop_id: Annotated[UUID, Depends(require_shop)],
    discrepancy_id: Annotated[UUID, Path(alias="discrepancyId")],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    corrected = (body.applied_value or "").strip()
    if body.resolution == "corrected_seller" and not corrected:
        raise Problem(422, "validation_failed", "A correction needs the corrected value.")

    op = "resolveDiscrepancy"
    digest = request_hash(str(shop_id), str(discrepancy_id), body.model_dump())
    with tenant(account.id) as conn:
        again = replay(conn, account.id, op, idempotency_key, digest)
        if again:
            return JSONResponse(status_code=again[0], content=again[1])

        cur = conn.execute(
            f"select {COLUMNS}, seller_value as old_seller from discrepancies "
            "where id = %s and shop_id = %s for update",
            (str(discrepancy_id), str(shop_id)),
        )
        cols = [d.name for d in cur.description]
        row = cur.fetchone()
        if row is None:
            raise Problem(404, "discrepancy_not_found", "That discrepancy was not found.")
        old = dict(zip(cols, row, strict=True))
        if old["status"] != "open":
            raise Problem(422, "already_resolved", "That discrepancy is already resolved.")
        if body.resolution == "corrected_seller" and old["kind"] in TIKTOK_OWNED_KINDS:
            raise Problem(
                422, "not_correctable",
                "This figure is TikTok's own, so it can be accepted or explained but not corrected.",
            )

        seller_value = corrected if body.resolution == "corrected_seller" else old["seller_value"]
        note = (body.note or "").strip() or old["note"]
        cur = conn.execute(
            "update discrepancies set status = 'resolved', resolution = %s, seller_value = %s, "
            "note = %s, resolved_at = now(), resolved_by = %s "
            f"where id = %s and shop_id = %s returning {COLUMNS}",
            (body.resolution, seller_value, note, str(account.id),
             str(discrepancy_id), str(shop_id)),
        )
        cols = [d.name for d in cur.description]
        new = dict(zip(cols, cur.fetchone(), strict=True))
        conn.execute(
            "insert into change_log (shop_id, entity_type, entity_id, reason_code, old_value, "
            "new_value, source) values (%s, 'discrepancy', %s, 'discrepancy_resolved', "
            "%s::jsonb, %s::jsonb, 'seller')",
            (
                str(shop_id), str(discrepancy_id),
                json.dumps({"status": old["status"], "seller_value": old["seller_value"],
                            "note": old["note"]}),
                json.dumps({"status": "resolved", "resolution": body.resolution,
                            "seller_value": seller_value, "note": note}),
            ),
        )
        out = ResolveOut(discrepancy=Discrepancy(**new), adjustment_posted=None)
        record(conn, account.id, op, idempotency_key, digest, 200, out.model_dump(mode="json"))
    return out
