"""Sales made outside TikTok Shop, S24. `listOtherChannelSales` and `putOtherChannelSales`.

Traces MON-3. These figures never enter the ledger and never appear in a money view. They
exist only so the VAT threshold monitor measures total turnover rather than TikTok turnover
alone, which `tax.get_vat_monitor` already reads from `other_channel_sales`.

Both run inside the seller's own scope. A month is stored as the first day of the London
month, which the table's own CHECK enforces. Money is minor units and never a float.

The list groups by month and sums every channel, because the screen shows the total a month
carries and the monitor sums the same rows. The PUT is per channel within a month and is an
upsert on `(shop_id, channel, month)`, so re-entering a channel's figure corrects it rather
than adding a second row.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel

from .auth import Account, require_account
from .db import tenant
from .money import Money, money
from .problems import Problem
from .shops import require_shop

router = APIRouter(tags=["Money"])


class OtherChannelMonth(BaseModel):
    month: date
    amount: Money
    updated_at: datetime | None = None


class OtherChannelMonthList(BaseModel):
    months: list[OtherChannelMonth]


class OtherChannelSalesInput(BaseModel):
    channel: str
    gross: Money


class OtherChannelSales(BaseModel):
    month: str
    channel: str
    gross: Money
    entered_at: datetime


def _month_first(month: str) -> date:
    year, mon = int(month[:4]), int(month[5:7])
    return date(year, mon, 1)


@router.get("/shops/{shopId}/other-sales", response_model=OtherChannelMonthList,
            summary="Monthly sales entered from outside TikTok")
def list_other_channel_sales(
    account: Annotated[Account, Depends(require_account)],
    shop_id: Annotated[UUID, Depends(require_shop)],
    period_from: Annotated[date | None, Query(alias="from")] = None,
    period_to: Annotated[date | None, Query(alias="to")] = None,
) -> OtherChannelMonthList:
    where = ["shop_id = %s"]
    args: list[object] = [str(shop_id)]
    if period_from:
        where.append("month >= %s")
        args.append(period_from.replace(day=1))
    if period_to:
        where.append("month <= %s")
        args.append(period_to.replace(day=1))
    with tenant(account.id) as conn:
        currency = (conn.execute(
            "select trim(currency) from shops where id = %s", (str(shop_id),)
        ).fetchone() or ["GBP"])[0] or "GBP"
        cur = conn.execute(
            "select month, coalesce(sum(gross_minor), 0) as gross_minor, "
            "max(entered_at) as updated_at "
            f"from other_channel_sales where {' and '.join(where)} "
            "group by month order by month",
            args,
        )
        cols = [d.name for d in cur.description]
        rows = [dict(zip(cols, r, strict=True)) for r in cur.fetchall()]
    return OtherChannelMonthList(months=[
        OtherChannelMonth(
            month=r["month"],
            amount=money(int(r["gross_minor"]), currency),
            updated_at=r["updated_at"],
        )
        for r in rows
    ])


@router.put("/shops/{shopId}/other-sales/{month}", response_model=OtherChannelSales,
            summary="Enter a monthly total from another channel")
def put_other_channel_sales(
    body: OtherChannelSalesInput,
    account: Annotated[Account, Depends(require_account)],
    shop_id: Annotated[UUID, Depends(require_shop)],
    month: Annotated[str, Path(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")],
) -> OtherChannelSales:
    channel = body.channel.strip()
    if not channel:
        raise Problem(422, "validation_failed", "A channel name is required.")
    if len(channel) > 100:
        raise Problem(422, "validation_failed", "The channel name is too long.")
    if body.gross.amount_minor < 0:
        raise Problem(422, "validation_failed", "A monthly total cannot be negative.")

    first = _month_first(month)
    with tenant(account.id) as conn:
        row = conn.execute(
            "insert into other_channel_sales (shop_id, channel, month, gross_minor, entered_at) "
            "values (%s, %s, %s, %s, now()) "
            "on conflict (shop_id, channel, month) do update set "
            "gross_minor = excluded.gross_minor, entered_at = now() "
            "returning gross_minor, entered_at",
            (str(shop_id), channel, first, body.gross.amount_minor),
        ).fetchone()
    return OtherChannelSales(
        month=month, channel=channel,
        gross=money(int(row[0]), body.gross.currency), entered_at=row[1],
    )
