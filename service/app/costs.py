"""Cost prices. `putSkuCost` and `getCostCoverage`.

A missing cost makes gross profit after returns unknown for that product, and every screen
that shows the figure tells the seller so. These two operations are where the seller acts
on that, one variant at a time.

SETTING A COST NEVER OVERWRITES ONE

The contract (CST-1, CST-4, CST-5) says costs are never overwritten. The current cost is
stamped `superseded_at` and a new row is inserted, inside one transaction. The unique index
`product_costs_current_idx` allows one current cost per variant, so two concurrent writes
cannot both leave a current row: the second fails rather than doubling the cost.

**A known gap, not fixed here.** The contract also says a figure calculated last month
still reconciles against the cost in force at the time. The figure queries in
`products.py` read only the current cost (`superseded_at is null`) for every period, so a
new cost changes past months' gross profit too. Checked on 24 September by reading
`products.SQL` and the product detail query. Fixing it means choosing the cost by
`effective_from` against each sale's date, which changes every profit figure and needs its
own approval.

A cost in a currency other than the shop's is refused. `cost_minor` is summed with sales
in the shop's currency, and adding pence to cents would be a wrong figure presented as a
right one.

COVERAGE, CST-6

The contract defines coverage as the share of sold units whose cost is known, over the
period. Units are order line quantities on orders that were not cancelled, dated in
Europe/London (A29.9), the same way `stock.py` counts its pace. The `top_missing` list is
ordered by gross sales, because the contract describes it as the products whose missing
cost suppresses the most figures, and gross sales is the size of the figure suppressed.

Both queries were run on the development branch, 24 September 2026.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel, Field

from .auth import Account, require_account
from .dates import business_today
from .db import tenant
from .money import Money, money
from .problems import Problem
from .shops import require_shop

router = APIRouter(tags=["Costs"])


class CostIn(BaseModel):
    cost: Money
    packing: Money | None = None
    postage: Money | None = None
    effective_from: date | None = None


class ProductCost(BaseModel):
    sku_id: UUID
    cost: Money
    packing: Money | None = None
    postage: Money | None = None
    source: Literal["upload", "manual"]
    effective_from: date
    supersedes: UUID | None = None


class MissingCost(BaseModel):
    sku_id: UUID
    product_title: str | None = None
    units: int = Field(ge=0)
    gross_sales: Money


class CostCoverage(BaseModel):
    period: dict[str, str]
    coverage: float = Field(ge=0, le=1)
    units_with_cost: int = Field(ge=0)
    units_total: int = Field(ge=0)
    skus_missing_cost: int = Field(ge=0)
    top_missing: list[MissingCost]


def _check_amounts(body: CostIn, currency: str) -> None:
    for name, m in (("cost", body.cost), ("packing", body.packing), ("postage", body.postage)):
        if m is None:
            continue
        if m.amount_minor < 0:
            raise Problem(422, "validation_failed", f"The {name} cannot be negative.")
        if m.currency != currency:
            raise Problem(
                422, "validation_failed",
                f"The {name} is in {m.currency} and this shop sells in {currency}.",
            )


@router.put("/shops/{shopId}/skus/{skuId}/cost", response_model=ProductCost)
def put_sku_cost(
    body: CostIn,
    account: Annotated[Account, Depends(require_account)],
    shop_id: Annotated[UUID, Depends(require_shop)],
    sku_id: Annotated[UUID, Path(alias="skuId")],
) -> ProductCost:
    effective_from = body.effective_from or business_today()

    with tenant(account.id) as conn:
        shop = conn.execute(
            "select trim(s.currency) from skus k join shops s on s.id = k.shop_id "
            "where k.id = %s and k.shop_id = %s",
            (str(sku_id), str(shop_id)),
        ).fetchone()
        if shop is None:
            # The same answer for a variant on another account, for the reason in shops.py.
            raise Problem(404, "sku_not_found", "That product variant was not found.")
        currency = shop[0]
        _check_amounts(body, currency)

        previous = conn.execute(
            "update product_costs set superseded_at = now() "
            "where sku_id = %s and shop_id = %s and superseded_at is null returning id",
            (str(sku_id), str(shop_id)),
        ).fetchone()
        conn.execute(
            "insert into product_costs (shop_id, sku_id, cost_minor, packing_minor, "
            "postage_minor, currency, source, effective_from, created_by) "
            "values (%s, %s, %s, %s, %s, %s, 'manual', %s, %s)",
            (
                str(shop_id), str(sku_id), body.cost.amount_minor,
                body.packing.amount_minor if body.packing else None,
                body.postage.amount_minor if body.postage else None,
                currency, effective_from, str(account.id),
            ),
        )

    return ProductCost(
        sku_id=sku_id,
        cost=money(body.cost.amount_minor, currency),
        packing=money(body.packing.amount_minor, currency) if body.packing else None,
        postage=money(body.postage.amount_minor, currency) if body.postage else None,
        source="manual",
        effective_from=effective_from,
        supersedes=previous[0] if previous else None,
    )


COVERAGE_SQL = """
with sold as (
  select ol.sku_id, sum(ol.quantity) as units,
         sum(ol.quantity * ol.unit_price_minor) as gross_minor
    from order_lines ol
    join orders o on o.id = ol.order_id
   where ol.shop_id = %(shop)s
     and o.cancelled_at is null
     and (o.order_created_at at time zone 'Europe/London')::date between %(from)s and %(to)s
   group by ol.sku_id
),
costed as (
  select sold.*, exists (select 1 from product_costs pc
                          where pc.sku_id = sold.sku_id and pc.superseded_at is null) as has_cost
    from sold
)
select c.sku_id, p.title as product_title, c.units, c.gross_minor, c.has_cost,
       (select trim(currency) from shops where id = %(shop)s) as currency
  from costed c
  join skus k on k.id = c.sku_id
  left join products p on p.id = k.product_id
 order by c.has_cost, c.gross_minor desc, c.sku_id
"""


@router.get("/shops/{shopId}/costs/coverage", response_model=CostCoverage)
def get_cost_coverage(
    account: Annotated[Account, Depends(require_account)],
    shop_id: Annotated[UUID, Depends(require_shop)],
    period_from: Annotated[date | None, Query(alias="from")] = None,
    period_to: Annotated[date | None, Query(alias="to")] = None,
) -> CostCoverage:
    today = business_today()
    start = period_from or today.replace(day=1)
    end = period_to or today
    if start > end:
        raise Problem(422, "validation_failed", "The period starts after it ends.")

    with tenant(account.id) as conn:
        cur = conn.execute(COVERAGE_SQL, {"shop": str(shop_id), "from": start, "to": end})
        cols = [d.name for d in cur.description]
        rows = [dict(zip(cols, r, strict=True)) for r in cur.fetchall()]

    units_total = sum(int(r["units"]) for r in rows)
    units_with_cost = sum(int(r["units"]) for r in rows if r["has_cost"])
    missing = [r for r in rows if not r["has_cost"]]
    # Coverage is a share, not money, so a float is the contract's own type. With no units
    # sold nothing is uncosted, so the gate is open rather than shut.
    coverage = 1.0 if units_total == 0 else units_with_cost / units_total

    return CostCoverage(
        period={"from": start.isoformat(), "to": end.isoformat(), "basis": "sales"},
        coverage=coverage,
        units_with_cost=units_with_cost,
        units_total=units_total,
        skus_missing_cost=len(missing),
        top_missing=[
            MissingCost(
                sku_id=r["sku_id"], product_title=r["product_title"], units=int(r["units"]),
                gross_sales=money(int(r["gross_minor"]), r["currency"] or "GBP"),
            )
            for r in missing[:10]
        ],
    )
