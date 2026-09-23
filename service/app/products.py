"""Products, ranked by what the seller actually keeps.

This is the screen the product is named for. A2 specifies the per-product grid and A4
specifies the arithmetic, which is reproduced here verbatim rather than reinvented:

    Return Loss              = -( return_cost entries + write_off entries )
    Cost of goods retained   = product cost x ( units sold - units returned )
    Contribution             = Net Proceeds - Cost of goods retained
    You keep                 = Contribution - Return Loss

Three things in that are easy to get wrong and are handled deliberately.

**A returned unit's cost is never counted twice.** A4.1 records the defect. If a unit came
back resellable its cost sits in stock, and if it came back unsellable its cost is a
write-off inside Return Loss. So the cost carried here is the cost of units sold and not
returned, computed per SKU because cost is a SKU-level fact.

**`kept` is null rather than wrong when a cost is missing.** A product with no uploaded cost
cannot have a Contribution, and showing gross sales in that column would read as profit.
`cost_known` says which it is and `kept_reason` says why in words the seller can act on.

**The rows do not have to add up to the shop total, so `others` exists.** A top ten table
whose rows sum to less than the money screen looks like lost money. `total` is every
product and `others` is what the unshown ones came to, so the arithmetic is visibly closed.

Cost of goods is read from `product_costs` rather than from the `cost_of_goods_sold` ledger
entries, because those are posted for every unit sold including the ones that came back.
A4's formula is explicit that retained cost excludes returned units.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from .auth import Account, require_account
from .db import tenant
from .money import Money, money
from .settlements import MAX_LIMIT, decode_cursor, encode_cursor
from .shops import require_shop

router = APIRouter(tags=["Products"])

# Net Proceeds is sales, refunds and platform deductions. It deliberately excludes
# return_cost and write_off, which A4 carries separately through Return Loss, and excludes
# cost_of_goods_sold, which is the seller's own money rather than TikTok's arithmetic.
NET_PROCEEDS_TYPES = ("sale", "refund", "platform_deduction")
RETURN_LOSS_TYPES = ("return_cost", "write_off")

MEASURES = {
    "kept": "kept_minor",
    "net_proceeds": "net_proceeds_minor",
    "gross_sales": "gross_sales_minor",
    "units": "units_sold",
    "returns": "returns_units",
}


class Period(BaseModel):
    from_: date
    to: date
    basis: str

    def model_dump(self, **kw):  # the contract names it `from`, which Python will not
        d = super().model_dump(**kw)
        d["from"] = d.pop("from_")
        return d


class ProductRow(BaseModel):
    product_id: UUID
    tiktok_product_id: str | None = None
    title: str | None = None
    units: int
    gross_sales: Money
    net_proceeds: Money
    kept: Money | None = None
    kept_reason: str | None = None
    returns_units: int = 0
    cost_known: bool = False


class Others(BaseModel):
    count: int
    amount: Money


class ProductRanking(BaseModel):
    period: dict[str, Any]
    measure: str
    products: list[ProductRow]
    total: Money
    shown_total: Money
    others: Others | None = None
    next_cursor: str | None = None


# One row per product. Every figure is derived here rather than in Python, so the database
# does the arithmetic once instead of the service doing it per row.
SQL = """
with scoped as (
  select le.*, s.product_id
    from ledger_entries le
    join skus s on s.id = le.sku_id
   where le.shop_id = %(shop)s
     and {date_column} >= %(from)s
     and {date_column} <= %(to)s
),
led as (
  select product_id,
         coalesce(sum(amount_minor) filter (where entry_type = any(%(np)s)), 0) as net_proceeds_minor,
         coalesce(sum(amount_minor) filter (where entry_type = any(%(rl)s)), 0) as return_entries_minor,
         coalesce(sum(amount_minor) filter (where category = 'gross_sales'), 0) as gross_sales_minor,
         coalesce(max(currency), 'GBP') as currency
    from scoped group by product_id
),
-- Units follow the same period and basis as the money, because a unit counted in one
-- month and its money in another is how a per-product table stops reconciling.
sold as (
  select s.product_id, s.id as sku_id, sum(ol.quantity) as units
    from (select distinct order_line_id from scoped where category = 'gross_sales'
           and order_line_id is not null) g
    join order_lines ol on ol.id = g.order_line_id
    join skus s on s.id = ol.sku_id
   group by s.product_id, s.id
),
returned as (
  select s.product_id, s.id as sku_id, sum(ri.quantity) as units
    from return_items ri
    join returns r on r.id = ri.return_id
    join skus s on s.id = ri.sku_id
   where ri.shop_id = %(shop)s
     and coalesce(r.refund_completed_at, r.requested_at)::date >= %(from)s
     and coalesce(r.refund_completed_at, r.requested_at)::date <= %(to)s
   group by s.product_id, s.id
),
-- The cost in force for the SKU, which is the latest not-superseded row.
cost as (
  select distinct on (sku_id) sku_id, cost_minor
    from product_costs
   where shop_id = %(shop)s and superseded_at is null
   order by sku_id, effective_from desc
),
-- A4: retained cost is cost x (sold - returned), per SKU, floored at zero because more
-- returns than sales in a period is possible at a month boundary and negative cost is not.
retained as (
  select sd.product_id,
         sum(c.cost_minor * greatest(sd.units - coalesce(rt.units, 0), 0)) as cost_retained_minor,
         count(*) filter (where c.cost_minor is null) as skus_without_cost
    from sold sd
    left join returned rt on rt.sku_id = sd.sku_id
    left join cost c on c.sku_id = sd.sku_id
   group by sd.product_id
),
units as (
  select product_id, sum(units) as units_sold from sold group by product_id
),
rets as (
  select product_id, sum(units) as returns_units from returned group by product_id
)
select p.id as product_id, p.tiktok_product_id, p.title,
       coalesce(u.units_sold, 0) as units_sold,
       coalesce(rr.returns_units, 0) as returns_units,
       led.gross_sales_minor, led.net_proceeds_minor, led.currency,
       -- Return Loss is positive money lost. Both entry types are negative in the ledger.
       -led.return_entries_minor as return_loss_minor,
       rt.cost_retained_minor,
       coalesce(rt.skus_without_cost, 0) as skus_without_cost,
       case when coalesce(rt.skus_without_cost, 1) = 0
            then led.net_proceeds_minor - rt.cost_retained_minor + led.return_entries_minor
       end as kept_minor
  from led
  join products p on p.id = led.product_id
  left join units u on u.product_id = led.product_id
  left join rets rr on rr.product_id = led.product_id
  left join retained rt on rt.product_id = led.product_id
"""


@router.get("/shops/{shopId}/products", response_model=ProductRanking)
def list_products(
    account: Annotated[Account, Depends(require_account)],
    shop_id: Annotated[UUID, Depends(require_shop)],
    basis: Annotated[str, Query(pattern="^(sales|cash)$")] = "sales",
    period_from: Annotated[date | None, Query(alias="from")] = None,
    period_to: Annotated[date | None, Query(alias="to")] = None,
    measure: Annotated[str, Query(pattern="^(kept|net_proceeds|gross_sales|units|returns)$")] = "kept",
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = 20,
    cursor: Annotated[str | None, Query()] = None,
) -> ProductRanking:
    today = date.today()
    start = period_from or today.replace(day=1)
    end = period_to or today

    date_column = "le.basis_day" if basis == "sales" else "le.settlement_month"
    sql = SQL.format(date_column=date_column)
    args = {
        "shop": str(shop_id),
        "from": start,
        "to": end,
        "np": list(NET_PROCEEDS_TYPES),
        "rl": list(RETURN_LOSS_TYPES),
    }

    with tenant(account.id) as conn:
        cur = conn.execute(sql, args)
        cols = [d.name for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]

    currency = rows[0]["currency"] if rows else "GBP"

    # Ranking happens here rather than in SQL because `kept` can be null, and a null sorts
    # unpredictably across databases. A product with an unknown cost ranks last on `kept`
    # rather than first, which is what a seller would expect.
    column = MEASURES[measure]
    def sort_key(r: dict[str, Any]):
        v = r.get(column)
        return (v is None, -(v or 0))

    rows.sort(key=sort_key)

    # The total is every product, computed before the page is cut.
    total_minor = sum(
        (r[column] or 0) if column not in ("units_sold", "returns_units") else 0
        for r in rows
    )
    if column in ("units_sold", "returns_units"):
        # A count is not money. The contract still requires a Money total, so it carries
        # the kept figure, which is the money a units ranking is ultimately about.
        total_minor = sum(r["kept_minor"] or 0 for r in rows)

    offset = 0
    if cursor:
        _, raw = decode_cursor(cursor)
        offset = int(raw)

    page = rows[offset:offset + limit]
    next_cursor = (
        encode_cursor_offset(offset + limit) if offset + limit < len(rows) else None
    )

    products = [
        ProductRow(
            product_id=r["product_id"],
            tiktok_product_id=r["tiktok_product_id"],
            title=r["title"],
            units=int(r["units_sold"]),
            gross_sales=money(int(r["gross_sales_minor"]), currency),
            net_proceeds=money(int(r["net_proceeds_minor"]), currency),
            kept=money(int(r["kept_minor"]), currency) if r["kept_minor"] is not None else None,
            kept_reason=(
                None if r["kept_minor"] is not None
                else f"{int(r['skus_without_cost'])} variant(s) have no cost uploaded"
            ),
            returns_units=int(r["returns_units"]),
            cost_known=r["kept_minor"] is not None,
        )
        for r in page
    ]

    shown_minor = sum(
        (r["kept_minor"] or 0) if column in ("units_sold", "returns_units") else (r[column] or 0)
        for r in page
    )
    unshown = [r for r in rows if r not in page]

    return ProductRanking(
        period={"from": start.isoformat(), "to": end.isoformat(), "basis": basis},
        measure=measure,
        products=products,
        total=money(int(total_minor), currency),
        shown_total=money(int(shown_minor), currency),
        others=(
            Others(
                count=len(unshown),
                amount=money(int(total_minor - shown_minor), currency),
            )
            if unshown else None
        ),
        next_cursor=next_cursor,
    )


def encode_cursor_offset(offset: int) -> str:
    """Offset rather than keyset, and the reason is worth stating.

    `settlements.py` uses keyset pagination because a settlement list changes under the
    caller as new statements arrive. A product ranking is computed over a closed period and
    re-sorted in Python on every request, so there is no stable key to page by. The offset
    is honest about that rather than pretending to a guarantee it cannot make.
    """
    from datetime import datetime, timezone
    return encode_cursor(datetime.now(timezone.utc), str(offset))
