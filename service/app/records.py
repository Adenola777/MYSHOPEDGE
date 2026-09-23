"""Records behind a figure.

A18.5 states the rule this endpoint exists for. Every figure a seller sees can be opened,
and what opens is the ledger rows that produced it, not a recalculation. If the rows do not
add up to the figure, the figure is wrong, and the seller should be the one who finds that
out rather than an accountant nine months later.

Two totals are returned and they are not the same thing.

    total         every entry matching the filter, across all pages
    shown_total   the sum of the entries on this page

A screen that shows only the page sum next to a headline figure invites the seller to think
the headline is wrong when they are simply on page one of four. Both are returned so the
screen never has to choose.

The basis decides which date column filters the period. `sales` recognises money when the
sale happens and reads `basis_day`. `cash` recognises it when TikTok pays out and reads
`settlement_month`. A figure without a basis is meaningless, which is why the parameter has
a default rather than being optional in effect.

Counted on the development branch, 23 September 2026: 119 entries
across seventeen type and category combinations, including the three new categories that
A18.5 required, `platform_adjustment`, `unmapped_fee` and `reserve_withheld`.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from .auth import Account, require_account
from .db import tenant
from .money import Money, money
from .settlements import MAX_LIMIT, decode_cursor, encode_cursor
from .shops import require_shop

router = APIRouter(tags=["Records"])


class LedgerEntry(BaseModel):
    id: UUID
    entry_type: str
    category: str | None = None
    tiktok_fee_type: str | None = None
    amount: Money
    occurred_at: datetime
    basis_day: date
    basis_month: date
    source: str
    source_ref: str | None = None
    attribution: str | None = None
    order_id: UUID | None = None
    tiktok_order_id: str | None = None
    sku_id: UUID | None = None
    tiktok_invoice_number: str | None = None
    reverses_entry_id: UUID | None = None
    reason: str | None = None


class RecordsPage(BaseModel):
    entries: list[LedgerEntry]
    total: Money
    shown_total: Money
    next_cursor: str | None = None


COLUMNS = """
  le.id, le.entry_type, le.category, le.tiktok_fee_type, le.amount_minor, le.currency,
  le.occurred_at, le.basis_day, le.basis_month, le.source, le.source_ref, le.attribution,
  le.order_id, o.tiktok_order_id, le.sku_id, le.tiktok_invoice_number,
  le.reverses_entry_id, le.reason
"""


@router.get("/shops/{shopId}/records", response_model=RecordsPage)
def get_records(
    account: Annotated[Account, Depends(require_account)],
    shop_id: Annotated[UUID, Depends(require_shop)],
    basis: Annotated[str, Query(pattern="^(sales|cash)$")] = "sales",
    period_from: Annotated[date | None, Query(alias="from")] = None,
    period_to: Annotated[date | None, Query(alias="to")] = None,
    category: Annotated[str | None, Query()] = None,
    entry_type: Annotated[str | None, Query()] = None,
    sku_id: Annotated[UUID | None, Query()] = None,
    product_id: Annotated[UUID | None, Query()] = None,
    order_id: Annotated[UUID | None, Query()] = None,
    return_id: Annotated[UUID | None, Query()] = None,
    settlement_id: Annotated[UUID | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = 20,
    cursor: Annotated[str | None, Query()] = None,
) -> RecordsPage:
    where = ["le.shop_id = %s"]
    args: list[Any] = [str(shop_id)]

    # The period column follows the basis. Filtering a cash figure by the day the sale
    # happened would answer a different question from the one the screen asked.
    date_column = "le.basis_day" if basis == "sales" else "le.settlement_month"
    if period_from:
        where.append(f"{date_column} >= %s")
        args.append(period_from)
    if period_to:
        where.append(f"{date_column} <= %s")
        args.append(period_to)

    for column, value in (
        ("le.category", category),
        ("le.entry_type", entry_type),
        ("le.sku_id", sku_id),
        ("le.order_id", order_id),
        ("le.return_id", return_id),
        ("le.settlement_id", settlement_id),
    ):
        if value is not None:
            where.append(f"{column} = %s")
            args.append(str(value))

    if product_id is not None:
        # The ledger carries a sku_id, not a product_id. A product is its variants, so this
        # is a join rather than a column, and A18.2 needs it for the per-product calculator.
        where.append("le.sku_id in (select id from skus where product_id = %s)")
        args.append(str(product_id))

    clause = " and ".join(where)

    with tenant(account.id) as conn:
        # The figure being drilled into, over every matching entry rather than this page.
        totals = conn.execute(
            f"select coalesce(sum(le.amount_minor), 0), "
            f"       coalesce(max(le.currency), 'GBP') "
            f"  from ledger_entries le where {clause}",
            args,
        ).fetchone()

        page_args = list(args)
        page_where = list(where)
        if cursor:
            c_time, c_id = decode_cursor(cursor)
            page_where.append("(le.occurred_at, le.id) < (%s::timestamptz, %s::uuid)")
            page_args += [c_time, c_id]
        page_args.append(limit + 1)

        cur = conn.execute(
            f"select {COLUMNS} from ledger_entries le "
            f"  left join orders o on o.id = le.order_id "
            f" where {' and '.join(page_where)} "
            f" order by le.occurred_at desc, le.id desc limit %s",
            page_args,
        )
        cols = [d.name for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]

    next_cursor = None
    if len(rows) > limit:
        rows = rows[:limit]
        next_cursor = encode_cursor(rows[-1]["occurred_at"], rows[-1]["id"])

    currency = totals[1]
    entries = [
        LedgerEntry(
            id=r["id"],
            entry_type=r["entry_type"],
            category=r["category"],
            tiktok_fee_type=r["tiktok_fee_type"],
            amount=money(r["amount_minor"], r["currency"]),
            occurred_at=r["occurred_at"],
            basis_day=r["basis_day"],
            basis_month=r["basis_month"],
            source=r["source"],
            source_ref=r["source_ref"],
            attribution=r["attribution"],
            order_id=r["order_id"],
            tiktok_order_id=r["tiktok_order_id"],
            sku_id=r["sku_id"],
            tiktok_invoice_number=r["tiktok_invoice_number"],
            reverses_entry_id=r["reverses_entry_id"],
            reason=r["reason"],
        )
        for r in rows
    ]

    return RecordsPage(
        entries=entries,
        total=money(int(totals[0]), currency),
        shown_total=money(sum(r["amount_minor"] for r in rows), currency),
        next_cursor=next_cursor,
    )
