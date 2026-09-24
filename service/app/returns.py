"""Returns. `listReturns` and `getReturnMetrics`, tracing RET-1 and RET-6.

`checkReturnItem` is not served. A4 rules what a check does (a resellable unit makes one
stock movement, an unsellable unit a write-off, a refund-only item neither), but four things
it must write to the append-only ledger are not ruled, and a wrong entry there cannot be
removed. CLAUDE.md lists the four questions.

LISTING

Each return carries its money from `return_reconciliation`, which is `security_invoker`, so
row level security holds through it. `refund` is TikTok's refund as stored. `return_cost`
is the return costs of A4.2 posted against the return: return postage and write-offs,
returned as the positive amount lost, which is how A4 writes the formula. Null when
nothing was posted, so an unchecked return does not read as costing nothing.

`awaiting_check_count` counts items awaiting a check across the shop, the same count Today
uses for "returns to check", so the two screens cannot disagree.

METRICS, RET-6

- Returned units are return item quantities, dated by when the refund completed and
  otherwise when it was requested, in Europe/London. This is the same rule the product
  ranking uses, so the rate and the Products screen count the same units.
- Units sold are the units behind gross sales in the period, the ranking's own count.
- Return costs and write-offs are A4.2's formula, −(return_cost + write_off entries),
  dated by `basis_day`.

**Derived, not ruled.** The contract bounds `return_rate` to 0 to 1, and more units can come
back in a month than were sold in it, because a return follows its sale. The rate is
therefore capped at 1, and `returns_units` beside it shows the true count. With nothing
sold the rate is 0.

Both queries were run on the development branch, 24 September 2026.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from .auth import Account, require_account
from .dates import business_today
from .db import tenant
from .money import Money, money
from .problems import Problem
from .settlements import MAX_LIMIT, decode_cursor, encode_cursor
from .shops import require_shop

router = APIRouter(tags=["Returns"])

LONDON_DAY = "((coalesce(r.refund_completed_at, r.requested_at)) at time zone 'Europe/London')::date"


class ReturnSummary(BaseModel):
    id: UUID
    tiktok_return_id: str
    tiktok_order_id: str
    tiktok_credit_note_number: str | None = None
    kind: Literal["cancellation", "refund_only", "return_refund"]
    status: str
    reason_code: str | None = None
    refund: Money | None = None
    requested_at: datetime | None = None
    refund_completed_at: datetime | None = None
    items_awaiting_check: int = Field(default=0, ge=0)
    return_cost: Money | None = None


class ReturnPage(BaseModel):
    returns: list[ReturnSummary]
    awaiting_check_count: int = Field(ge=0)
    next_cursor: str | None = None


LIST_SQL = """
select r.id, r.tiktok_return_id, rr.tiktok_order_id, r.tiktok_credit_note_number, r.kind,
       r.status, r.reason_code, r.refund_minor, r.requested_at, r.refund_completed_at,
       rr.items_awaiting_check, rr.return_cost_minor, rr.write_off_minor,
       (select count(*) from ledger_entries le where le.return_id = r.id
         and le.entry_type in ('return_cost', 'write_off')) as cost_entries,
       coalesce(r.requested_at, r.created_at) as sort_at,
       (select trim(currency) from shops where id = r.shop_id) as currency
  from returns r
  join return_reconciliation rr on rr.return_id = r.id
 where {where}
 order by coalesce(r.requested_at, r.created_at) desc, r.id desc
 limit %s
"""


@router.get("/shops/{shopId}/returns", response_model=ReturnPage)
def list_returns(
    account: Annotated[Account, Depends(require_account)],
    shop_id: Annotated[UUID, Depends(require_shop)],
    kind: Annotated[Literal["cancellation", "refund_only", "return_refund"] | None, Query()] = None,
    awaiting_check: Annotated[bool | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = 50,
    cursor: Annotated[str | None, Query()] = None,
) -> ReturnPage:
    where = ["r.shop_id = %s"]
    args: list[Any] = [str(shop_id)]
    if kind:
        where.append("r.kind = %s")
        args.append(kind)
    if awaiting_check is not None:
        where.append("rr.items_awaiting_check " + ("> 0" if awaiting_check else "= 0"))
    if cursor:
        c_time, c_id = decode_cursor(cursor)
        where.append("(coalesce(r.requested_at, r.created_at), r.id) < (%s::timestamptz, %s::uuid)")
        args += [c_time, c_id]
    args.append(limit + 1)

    with tenant(account.id) as conn:
        cur = conn.execute(LIST_SQL.format(where=" and ".join(where)), args)
        cols = [d.name for d in cur.description]
        rows = [dict(zip(cols, r, strict=True)) for r in cur.fetchall()]
        waiting = conn.execute(
            "select count(*) from return_items where shop_id = %s "
            "and seller_check_status = 'pending'",
            (str(shop_id),),
        ).fetchone()

    next_cursor = None
    if len(rows) > limit:
        rows = rows[:limit]
        next_cursor = encode_cursor(rows[-1]["sort_at"], rows[-1]["id"])

    out = []
    for r in rows:
        cur_code = r["currency"] or "GBP"
        lost = -int(r["return_cost_minor"] or 0) - int(r["write_off_minor"] or 0)
        out.append(ReturnSummary(
            id=r["id"], tiktok_return_id=r["tiktok_return_id"],
            tiktok_order_id=r["tiktok_order_id"],
            tiktok_credit_note_number=r["tiktok_credit_note_number"], kind=r["kind"],
            status=r["status"], reason_code=r["reason_code"],
            refund=money(int(r["refund_minor"]), cur_code) if r["refund_minor"] is not None else None,
            requested_at=r["requested_at"], refund_completed_at=r["refund_completed_at"],
            items_awaiting_check=int(r["items_awaiting_check"] or 0),
            return_cost=money(lost, cur_code) if int(r["cost_entries"]) > 0 else None,
        ))
    return ReturnPage(returns=out, awaiting_check_count=int(waiting[0]) if waiting else 0,
                      next_cursor=next_cursor)


class MostReturned(BaseModel):
    product_id: UUID
    title: str | None = None
    units: int = Field(ge=0)
    cost: Money


class ReturnMetrics(BaseModel):
    period: dict[str, str]
    return_rate: float = Field(ge=0, le=1)
    returns_units: int = Field(ge=0)
    total_return_cost: Money
    write_off_total: Money
    most_returned: list[MostReturned]


METRICS_SQL = f"""
with returned as (
  select s.product_id, sum(ri.quantity) as units
    from return_items ri
    join returns r on r.id = ri.return_id
    join skus s on s.id = ri.sku_id
   where ri.shop_id = %(shop)s
     and {LONDON_DAY} between %(from)s and %(to)s
   group by s.product_id
),
sold as (
  select coalesce(sum(ol.quantity), 0) as units
    from (select distinct order_line_id from ledger_entries
           where shop_id = %(shop)s and category = 'gross_sales'
             and order_line_id is not null
             and basis_day between %(from)s and %(to)s) g
    join order_lines ol on ol.id = g.order_line_id
),
costs as (
  select s.product_id,
         -coalesce(sum(le.amount_minor) filter (where le.entry_type in ('return_cost','write_off')), 0) as lost,
         -coalesce(sum(le.amount_minor) filter (where le.entry_type = 'write_off'), 0) as written_off
    from ledger_entries le
    left join skus s on s.id = le.sku_id
   where le.shop_id = %(shop)s
     and le.entry_type in ('return_cost', 'write_off')
     and le.basis_day between %(from)s and %(to)s
   group by s.product_id
)
select 'product' as row_kind, p.id as product_id, p.title, rt.units, coalesce(c.lost, 0) as lost,
       null::bigint as sold_units, null::numeric as written_off
  from returned rt
  join products p on p.id = rt.product_id
  left join costs c on c.product_id = rt.product_id
union all
select 'totals', null, null,
       (select coalesce(sum(units), 0) from returned),
       (select coalesce(sum(lost), 0) from costs),
       (select units from sold),
       (select coalesce(sum(written_off), 0) from costs)
"""


@router.get("/shops/{shopId}/returns/metrics", response_model=ReturnMetrics)
def get_return_metrics(
    account: Annotated[Account, Depends(require_account)],
    shop_id: Annotated[UUID, Depends(require_shop)],
    period_from: Annotated[date | None, Query(alias="from")] = None,
    period_to: Annotated[date | None, Query(alias="to")] = None,
) -> ReturnMetrics:
    today = business_today()
    start = period_from or today.replace(day=1)
    end = period_to or today
    if start > end:
        raise Problem(422, "validation_failed", "The period starts after it ends.")

    with tenant(account.id) as conn:
        cur = conn.execute(METRICS_SQL, {"shop": str(shop_id), "from": start, "to": end})
        cols = [d.name for d in cur.description]
        rows = [dict(zip(cols, r, strict=True)) for r in cur.fetchall()]
        currency = conn.execute(
            "select trim(currency) from shops where id = %s", (str(shop_id),)
        ).fetchone()[0]

    totals = next(r for r in rows if r["row_kind"] == "totals")
    products = sorted((r for r in rows if r["row_kind"] == "product"),
                      key=lambda r: (-int(r["units"]), -int(r["lost"]), str(r["product_id"])))
    returned, sold = int(totals["units"]), int(totals["sold_units"] or 0)
    rate = 0.0 if sold == 0 else min(1.0, returned / sold)

    return ReturnMetrics(
        period={"from": start.isoformat(), "to": end.isoformat(), "basis": "sales"},
        return_rate=rate,
        returns_units=returned,
        total_return_cost=money(int(totals["lost"]), currency),
        write_off_total=money(int(totals["written_off"]), currency),
        most_returned=[
            MostReturned(product_id=r["product_id"], title=r["title"], units=int(r["units"]),
                         cost=money(int(r["lost"]), currency))
            for r in products[:5]
        ],
    )
