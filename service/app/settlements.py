"""Settlements. What TikTok said, what it held back, and what reached the bank.

Three figures on this screen are not the same number, and A18.3 is explicit about why
that matters:

    net proceeds    sales less every deduction
    reserve         money TikTok is holding, released later
    payout          what actually arrives

A seller who reads net proceeds as the amount landing in their account will believe TikTok
short-paid them by the reserved amount. All three are returned, always, even when the
reserve is zero, so the front end never has to decide whether to show a field.

The reserve is stored negative, because it is a deduction from the ledger's point of view.
It is returned exactly as stored. Presenting it as "£10.00 held" rather than "-£10.00" is
the screen's job, and doing it here would mean the API returning a sign that contradicts
the ledger.

Verified against the seeded seller on the development branch, 23 September 2026. Statement
202608A-0002: net proceeds 14750, reserve 1000 withheld, payout 13750. All three
settlements reconcile with nothing unexplained, and the four components sum exactly to the
statement amount on each.
"""

from __future__ import annotations

import base64
import json
from datetime import date, datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from .auth import Account, require_account
from .db import tenant
from .money import Money, money
from .problems import Problem
from .shops import require_shop

router = APIRouter(tags=["Settlements"])

MAX_LIMIT = 100


def encode_cursor(statement_time: datetime, settlement_id: UUID) -> str:
    raw = json.dumps({"t": statement_time.isoformat(), "i": str(settlement_id)})
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def decode_cursor(cursor: str) -> tuple[str, str]:
    """Opaque to the caller, and refused rather than guessed at if it is malformed.

    A cursor that cannot be decoded is a client error, not a reason to silently return the
    first page. Silently restarting a pagination loop is how a caller ends up reading the
    same page forever.
    """
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        data = json.loads(base64.urlsafe_b64decode(padded))
        return data["t"], data["i"]
    except Exception as exc:
        raise Problem(400, "invalid_cursor", "That page cursor is not valid.") from exc


class Settlement(BaseModel):
    id: UUID
    tiktok_statement_id: str
    tiktok_payment_id: str | None = None
    settlement_reference: str | None = None
    statement_time: datetime
    activity_date: date
    paid_at: datetime | None = None
    payment_status: str
    statement_amount: Money
    total_reserve: Money
    payable_amount: Money
    tiktok_invoice_number: str | None = None


class SettlementPage(BaseModel):
    settlements: list[Settlement]
    next_cursor: str | None = None


class SettlementComponents(BaseModel):
    net_sales: Money
    fees: Money
    shipping_cost: Money
    adjustments: Money
    difference: Money
    region_mapping_conflict: bool = False


class SettlementReconciliation(BaseModel):
    orders_settled: int
    net_proceeds: Money
    invoiced_gross: Money | None = None
    unexplained: Money


class SettledOrder(BaseModel):
    order_id: UUID
    tiktok_order_id: str
    settled: Money | None = None


class SettlementDetail(BaseModel):
    settlement: Settlement
    components: SettlementComponents
    reconciliation: SettlementReconciliation
    orders: list[SettledOrder]


def _settlement(row: dict[str, Any]) -> Settlement:
    cur = row["currency"]
    return Settlement(
        id=row["id"],
        tiktok_statement_id=row["tiktok_statement_id"],
        tiktok_payment_id=row["tiktok_payment_id"],
        settlement_reference=row["settlement_reference"],
        statement_time=row["statement_time"],
        activity_date=row["activity_date"],
        paid_at=row["paid_at"],
        payment_status=row["payment_status"],
        statement_amount=money(row["statement_amount_minor"], cur),
        total_reserve=money(row["total_reserve_amount_minor"] or 0, cur),
        payable_amount=money(
            row["payable_amount_minor"]
            if row["payable_amount_minor"] is not None
            else row["statement_amount_minor"],
            cur,
        ),
        tiktok_invoice_number=row["tiktok_invoice_number"],
    )


SETTLEMENT_COLUMNS = """
  id, tiktok_statement_id, tiktok_payment_id, settlement_reference,
  statement_time, activity_date, paid_at, payment_status, currency,
  statement_amount_minor, payable_amount_minor, total_reserve_amount_minor,
  tiktok_invoice_number
"""


@router.get("/shops/{shopId}/settlements", response_model=SettlementPage)
def list_settlements(
    account: Annotated[Account, Depends(require_account)],
    shop_id: Annotated[UUID, Depends(require_shop)],
    period_from: Annotated[date | None, Query(alias="from")] = None,
    period_to: Annotated[date | None, Query(alias="to")] = None,
    payment_status: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = 50,
    cursor: Annotated[str | None, Query()] = None,
) -> SettlementPage:
    where = ["shop_id = %s"]
    args: list[Any] = [str(shop_id)]

    if period_from:
        where.append("activity_date >= %s")
        args.append(period_from)
    if period_to:
        where.append("activity_date <= %s")
        args.append(period_to)
    if payment_status:
        where.append("payment_status = %s")
        args.append(payment_status)
    if cursor:
        # Keyset rather than offset. An offset shifts under a caller when a new statement
        # arrives mid-pagination, which on a finance screen means a settlement silently
        # skipped rather than a row appearing twice.
        c_time, c_id = decode_cursor(cursor)
        where.append("(statement_time, id) < (%s::timestamptz, %s::uuid)")
        args += [c_time, c_id]

    args.append(limit + 1)
    sql = (
        f"select {SETTLEMENT_COLUMNS} from settlements where {' and '.join(where)} "
        "order by statement_time desc, id desc limit %s"
    )

    with tenant(account.id) as conn:
        cur = conn.execute(sql, args)
        cols = [d.name for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]

    next_cursor = None
    if len(rows) > limit:
        rows = rows[:limit]
        last = rows[-1]
        next_cursor = encode_cursor(last["statement_time"], last["id"])

    return SettlementPage(
        settlements=[_settlement(r) for r in rows], next_cursor=next_cursor
    )


@router.get(
    "/shops/{shopId}/settlements/{settlementId}", response_model=SettlementDetail
)
def get_settlement(
    account: Annotated[Account, Depends(require_account)],
    shop_id: Annotated[UUID, Depends(require_shop)],
    settlementId: UUID,
) -> SettlementDetail:
    with tenant(account.id) as conn:
        cur = conn.execute(
            f"select {SETTLEMENT_COLUMNS}, net_sales_minor, fee_minor, "
            "shipping_cost_minor, adjustment_minor "
            "from settlements where id = %s and shop_id = %s",
            (str(settlementId), str(shop_id)),
        )
        cols = [d.name for d in cur.description]
        row = cur.fetchone()
        if row is None:
            # Same answer as a settlement on another account, for the reason in shops.py.
            raise Problem(404, "settlement_not_found", "That settlement was not found.")
        s = dict(zip(cols, row))

        rec = conn.execute(
            "select orders_settled, net_proceeds_minor, invoiced_gross_minor, "
            "unexplained_minor from settlement_reconciliation where settlement_id = %s",
            (str(settlementId),),
        ).fetchone()

        orders = conn.execute(
            "select o.id, o.tiktok_order_id, "
            "       sum(le.amount_minor) filter (where le.entry_type = 'sale') as settled "
            "  from ledger_entries le "
            "  join orders o on o.id = le.order_id "
            " where le.settlement_id = %s "
            " group by o.id, o.tiktok_order_id "
            # min() because order_created_at is not in the GROUP BY and Postgres will not
            # accept it bare. Caught by running the query rather than by reading it.
            " order by min(o.order_created_at)",
            (str(settlementId),),
        ).fetchall()

    currency = s["currency"]
    net_sales = s["net_sales_minor"] or 0
    fees = s["fee_minor"] or 0
    shipping = s["shipping_cost_minor"] or 0
    adjustments = s["adjustment_minor"] or 0

    components = SettlementComponents(
        net_sales=money(net_sales, currency),
        fees=money(fees, currency),
        shipping_cost=money(shipping, currency),
        adjustments=money(adjustments, currency),
        # What TikTok's own four components fail to explain about its own total. Zero on
        # every seeded statement. A non-zero value here is TikTok disagreeing with itself,
        # which is worth surfacing rather than absorbing.
        difference=money(
            s["statement_amount_minor"] - (net_sales + fees + shipping + adjustments),
            currency,
        ),
    )

    reconciliation = SettlementReconciliation(
        orders_settled=int(rec[0]) if rec else 0,
        net_proceeds=money(int(rec[1]) if rec else 0, currency),
        invoiced_gross=money(int(rec[2]), currency) if rec and rec[2] is not None else None,
        unexplained=money(int(rec[3]) if rec else 0, currency),
    )

    return SettlementDetail(
        settlement=_settlement(s),
        components=components,
        reconciliation=reconciliation,
        orders=[
            SettledOrder(
                order_id=o[0],
                tiktok_order_id=o[1],
                settled=money(int(o[2]), currency) if o[2] is not None else None,
            )
            for o in orders
        ],
    )
