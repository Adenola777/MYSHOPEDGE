"""Stock. What is on the shelf, how long it lasts, and every movement behind the count.

Two operations, `getStock` and `getStockMovements`, tracing STK-1, STK-2 and STK-4.

WHAT IS STORED AND WHAT IS DERIVED

`stock_positions` stores TikTok's count, the seller's adjustment and three counters. The
database computes `on_shelf` as TikTok stock plus the adjustment, and this module returns it
as stored. Two figures are derived here: `days_left` and `state`.

DAYS LEFT, STK-2

The PRD's user story US-08 asks for Days left "on a 14-day pace". The QA document's worked
example G8 divides by thirty days instead (438 sold in 30 days, 14.6 a day, 5.6 days). The
PRD is product authority under A29.11, so the pace here is fourteen days. The conflict is
recorded rather than resolved silently, and the window is one constant.

    days_left = on_shelf / (units sold in the last 14 London days / 14)

Units sold are the quantities on order lines of orders that were not cancelled, dated by
`business_today()` in Europe/London (A29.9). Days left is null when nothing sold in the
window, and null when nothing is on the shelf, which is the A12 row 29 requirement that a
sold out product returns null rather than a division.

**Unverified against the rule in one respect.** TC-STK-02 excludes days on which the SKU
had no stock from the average. Nothing in the schema records a daily stock level, so the
exclusion cannot be applied. For a SKU that was out of stock for part of the window, the
rate here is lower than the rule's and Days left is therefore longer than it should be.
Returned units are not subtracted from the pace either, because no document says whether
they should be.

STATE

The contract names four states and no document orders them. The order applied here is
derived, not ruled:

    out          on_shelf is zero or below
    low          days_left is below the seller's low stock threshold
    coming_back  units are on their way back from a return
    healthy      none of the above

The threshold is `alert_settings.low_stock_days`, and 14 when the seller has never set one,
which is the column's own default. Out is first because it is the state a seller must act
on. Low comes before coming back because units in transit do not stop a shelf emptying.

Checked on the development branch, 24 September 2026. Ten positions, one of them GIFT-DEF
at 0 and therefore out. Every seeded order falls in July or August, so no SKU sold in the
fourteen days to 24 September, every `days_left` is null, and the other nine are healthy.
That is correct for the data and it means the low state has not yet been seen on real rows.
"""

from __future__ import annotations

import base64
import json
from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Path, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .auth import Account, require_account
from .dates import business_today, now_utc
from .db import tenant
from .idempotency import record, replay, request_hash
from .problems import Problem
from .settlements import MAX_LIMIT, decode_cursor, encode_cursor
from .shops import require_shop

router = APIRouter(tags=["Stock"])

PACE_DAYS = 14
DEFAULT_LOW_STOCK_DAYS = 14

State = Literal["healthy", "low", "out", "coming_back"]


class StockPosition(BaseModel):
    sku_id: UUID
    tiktok_sku_id: str | None = None
    seller_sku: str | None = None
    product_title: str | None = None
    tiktok_stock: int
    adjusted_delta: int
    on_shelf: int
    sold_not_posted: int
    coming_back: int
    written_off: int
    state: State
    days_left: float | None = None
    as_of: datetime


class StockPage(BaseModel):
    as_of: datetime
    items: list[StockPosition]
    next_cursor: str | None = None


class StockMovement(BaseModel):
    id: UUID
    movement_type: str
    quantity: int
    occurred_at: datetime
    order_id: UUID | None = None
    return_id: UUID | None = None
    reason: str | None = None
    created_by: UUID | None = None


class MovementSku(BaseModel):
    """Which variant the movements belong to. Added 25 September 2026 at the owner's
    instruction, because QA found the screen that adjusts a variant's stock named nothing."""
    sku_id: UUID
    product_id: UUID
    product_title: str | None = None
    variant_label: str | None = None
    seller_sku: str | None = None
    tiktok_sku_id: str | None = None


class MovementPage(BaseModel):
    sku: MovementSku
    movements: list[StockMovement]
    next_cursor: str | None = None


def _encode_sku_cursor(sku_id: UUID) -> str:
    raw = json.dumps({"i": str(sku_id)})
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def _decode_sku_cursor(cursor: str) -> str:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        return str(UUID(json.loads(base64.urlsafe_b64decode(padded))["i"]))
    except Exception as exc:
        raise Problem(400, "invalid_cursor", "That page cursor is not valid.") from exc


# The state is computed in SQL rather than in Python so that the `state` filter and the
# keyset cursor act on the same rows. Filtering after the page is cut would return short
# pages and a cursor that skips rows.
STOCK_SQL = """
with settings as (
  select coalesce(
    (select low_stock_days from alert_settings where shop_id = %(shop)s),
    %(default_low)s
  ) as low_days
),
pace as (
  select ol.sku_id, sum(ol.quantity) as units
    from order_lines ol
    join orders o on o.id = ol.order_id
   where ol.shop_id = %(shop)s
     and o.cancelled_at is null
     and (o.order_created_at at time zone 'Europe/London')::date
         between %(today)s::date - (%(pace)s - 1) and %(today)s::date
   group by ol.sku_id
),
pos as (
  select sp.sku_id, k.tiktok_sku_id, k.seller_sku, p.title as product_title,
         sp.tiktok_stock, sp.adjusted_delta, sp.on_shelf, sp.sold_not_posted,
         sp.coming_back, sp.written_off, sp.as_of,
         case when sp.on_shelf > 0 and coalesce(pace.units, 0) > 0
              then round(sp.on_shelf::numeric * %(pace)s / pace.units, 1)
         end as days_left
    from stock_positions sp
    join skus k on k.id = sp.sku_id
    left join products p on p.id = k.product_id
    left join pace on pace.sku_id = sp.sku_id
   where sp.shop_id = %(shop)s
     and (%(product)s::uuid is null or k.product_id = %(product)s::uuid)
     and (%(sku)s::uuid is null or sp.sku_id = %(sku)s::uuid)
),
stated as (
  select pos.*,
         case when pos.on_shelf <= 0 then 'out'
              when pos.days_left is not null and pos.days_left < s.low_days then 'low'
              when pos.coming_back > 0 then 'coming_back'
              else 'healthy'
         end as state
    from pos cross join settings s
)
select * from stated
 where (%(state)s::text is null or state = %(state)s::text)
   and (%(after)s::uuid is null or sku_id > %(after)s::uuid)
 order by sku_id
 limit %(limit)s
"""


def positions(
    conn: Any,
    shop_id: UUID,
    *,
    state: str | None = None,
    after: str | None = None,
    limit: int | None = None,
    product_id: UUID | None = None,
    sku_id: UUID | None = None,
) -> list[StockPosition]:
    """Every stock position with its state and days left, computed once, here.

    `getStock` pages through it and `getProduct` reads one product's positions from it, so
    the two screens cannot disagree about whether a SKU is low. A29.1 puts each rule in one
    place. Until 24 September the product detail wrote its own state, `in_stock` or
    `out_of_stock`, which the contract does not allow.
    """
    params = {
        "shop": str(shop_id),
        "default_low": DEFAULT_LOW_STOCK_DAYS,
        "today": business_today(),
        "pace": PACE_DAYS,
        "state": state,
        "after": after,
        "product": str(product_id) if product_id else None,
        "sku": str(sku_id) if sku_id else None,
        # LIMIT NULL is no limit in Postgres.
        "limit": limit,
    }
    cur = conn.execute(STOCK_SQL, params)
    cols = [d.name for d in cur.description]
    rows = [dict(zip(cols, r, strict=True)) for r in cur.fetchall()]
    return [
        StockPosition(
            **{k: r[k] for k in cols if k != "days_left"},
            days_left=float(r["days_left"]) if r["days_left"] is not None else None,
        )
        for r in rows
    ]


@router.get("/shops/{shopId}/stock", response_model=StockPage)
def get_stock(
    account: Annotated[Account, Depends(require_account)],
    shop_id: Annotated[UUID, Depends(require_shop)],
    state: Annotated[State | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = 50,
    cursor: Annotated[str | None, Query()] = None,
) -> StockPage:
    after = _decode_sku_cursor(cursor) if cursor else None
    with tenant(account.id) as conn:
        items = positions(conn, shop_id, state=state, after=after, limit=limit + 1)
        latest = conn.execute(
            "select max(as_of) from stock_positions where shop_id = %s", (str(shop_id),)
        ).fetchone()

    next_cursor = None
    if len(items) > limit:
        items = items[:limit]
        next_cursor = _encode_sku_cursor(items[-1].sku_id)

    # The page's own as_of is the newest count held for the shop. A shop with no positions
    # yet has no count to date, so the moment of the answer is used instead.
    as_of = latest[0] if latest and latest[0] is not None else now_utc()
    return StockPage(as_of=as_of, items=items, next_cursor=next_cursor)


@router.get("/shops/{shopId}/stock/{skuId}/movements", response_model=MovementPage)
def get_stock_movements(
    account: Annotated[Account, Depends(require_account)],
    shop_id: Annotated[UUID, Depends(require_shop)],
    sku_id: Annotated[UUID, Path(alias="skuId")],
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = 50,
    cursor: Annotated[str | None, Query()] = None,
) -> MovementPage:
    where = ["shop_id = %s", "sku_id = %s"]
    args: list[Any] = [str(shop_id), str(sku_id)]
    if cursor:
        c_time, c_id = decode_cursor(cursor)
        where.append("(occurred_at, id) < (%s::timestamptz, %s::uuid)")
        args += [c_time, c_id]
    args.append(limit + 1)

    with tenant(account.id) as conn:
        known = conn.execute(
            "select k.id, k.product_id, p.title, k.variant_label, k.seller_sku, k.tiktok_sku_id "
            "from skus k join products p on p.id = k.product_id "
            "where k.id = %s and k.shop_id = %s",
            (str(sku_id), str(shop_id)),
        ).fetchone()
        if known is None:
            # The same answer for a SKU on another account as for one that does not exist,
            # for the reason in shops.py.
            raise Problem(404, "sku_not_found", "That product variant was not found.")
        cur = conn.execute(
            "select id, movement_type, quantity, occurred_at, order_id, return_id, "
            f"reason, created_by from stock_movements where {' and '.join(where)} "
            "order by occurred_at desc, id desc limit %s",
            args,
        )
        cols = [d.name for d in cur.description]
        rows = [dict(zip(cols, r, strict=True)) for r in cur.fetchall()]

    next_cursor = None
    if len(rows) > limit:
        rows = rows[:limit]
        next_cursor = encode_cursor(rows[-1]["occurred_at"], rows[-1]["id"])

    return MovementPage(
        sku=MovementSku(
            sku_id=known[0], product_id=known[1], product_title=known[2],
            variant_label=known[3], seller_sku=known[4], tiktok_sku_id=known[5],
        ),
        movements=[StockMovement(**r) for r in rows],
        next_cursor=next_cursor,
    )


# --- createStockAdjustment, STK-4 ----------------------------------------------------------
#
# The adjustment moves `adjusted_delta` in MyShopEdge only. PRD 6.2 excludes writing stock
# back to TikTok, and TikTok's own figure is left untouched. A reason is required here and
# by the database (`stock_movements_check`), as STK-4 requires.
#
# **Derived, not ruled.** An adjustment of zero is refused, because it records nothing. An
# adjustment that would take stock on hand below zero is refused, because a negative shelf
# cannot be counted and would read as a sale that never happened. A variant with no stock
# position yet is refused, because a position arrives with the first sync and inventing one
# here would give it a TikTok count of zero that TikTok never reported.


class AdjustmentIn(BaseModel):
    quantity: int
    reason: str = Field(min_length=1, max_length=500)


class AdjustmentOut(BaseModel):
    movement: StockMovement
    position: StockPosition


@router.post("/shops/{shopId}/stock/{skuId}/adjustments", status_code=201,
             response_model=AdjustmentOut)
def create_stock_adjustment(
    body: AdjustmentIn,
    account: Annotated[Account, Depends(require_account)],
    shop_id: Annotated[UUID, Depends(require_shop)],
    sku_id: Annotated[UUID, Path(alias="skuId")],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    reason = body.reason.strip()
    if not reason:
        raise Problem(422, "validation_failed", "An adjustment needs a reason.")
    if body.quantity == 0:
        raise Problem(422, "validation_failed", "An adjustment of zero units changes nothing.")

    op = "createStockAdjustment"
    digest = request_hash(str(shop_id), str(sku_id), body.quantity, reason)
    with tenant(account.id) as conn:
        again = replay(conn, account.id, op, idempotency_key, digest)
        if again:
            return JSONResponse(status_code=again[0], content=again[1])

        pos = conn.execute(
            "select sp.on_shelf from stock_positions sp join skus k on k.id = sp.sku_id "
            "where sp.sku_id = %s and sp.shop_id = %s for update of sp",
            (str(sku_id), str(shop_id)),
        ).fetchone()
        if pos is None:
            known = conn.execute(
                "select 1 from skus where id = %s and shop_id = %s", (str(sku_id), str(shop_id))
            ).fetchone()
            if known is None:
                raise Problem(404, "sku_not_found", "That product variant was not found.")
            raise Problem(
                422, "no_stock_position",
                "This variant has no stock count yet. It arrives with the next sync.",
            )
        if pos[0] + body.quantity < 0:
            raise Problem(
                422, "validation_failed",
                f"That would take stock on hand below zero. {pos[0]} are on hand now.",
            )

        cur = conn.execute(
            "insert into stock_movements (shop_id, sku_id, movement_type, quantity, reason, "
            "created_by) values (%s, %s, 'manual_adjustment', %s, %s, %s) "
            "returning id, movement_type, quantity, occurred_at, order_id, return_id, "
            "reason, created_by",
            (str(shop_id), str(sku_id), body.quantity, reason, str(account.id)),
        )
        cols = [d.name for d in cur.description]
        movement = StockMovement(**dict(zip(cols, cur.fetchone(), strict=True)))
        conn.execute(
            "update stock_positions set adjusted_delta = adjusted_delta + %s "
            "where sku_id = %s and shop_id = %s",
            (body.quantity, str(sku_id), str(shop_id)),
        )
        position = positions(conn, shop_id, sku_id=sku_id)[0]
        out = AdjustmentOut(movement=movement, position=position)
        record(conn, account.id, op, idempotency_key, digest, 201, out.model_dump(mode="json"))
    return out
