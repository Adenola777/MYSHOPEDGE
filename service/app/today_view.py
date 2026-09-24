"""The Today screen, S6. The hero figure, the month, Shop Money and what needs the seller.

Every figure here is either the Money calculator for a period or a count read live from
the tables. Nothing is estimated in this file. The rules below were decided by the owner on
24 September 2026, because DSH-1, DSH-2 and DSH-10 left them open.

**Labels follow A8.** The hero is `gross_profit_after_returns` when every product sold
today has a cost, and `net_proceeds` otherwise. A8 withdrew both "You keep" and "Left after
TikTok", so neither appears. The value is null only if the calculator cannot produce the
figure the label names.

**The day is Europe/London.** A5 defines Today as the current local date in Europe/London
from midnight to the as-at time. The month is the calendar month that day falls in.

**Shop Money covers all time**, and it reconciles to what TikTok actually paid (A29.7).
Generated is the same net proceeds the calculator reaches, over every ledger entry the shop
holds. Return postage TikTok deducted in its statements, the `return_shipping` entries
carrying TikTok's field `return_shipping_fee_amount`, is stated as `return_postage`. Paid out
is everything on entries TikTok has settled, postage included, so it equals the payout.
Awaiting is the rest, broken down by TikTok's own sub-statuses in `order_settlements`. Paid
out plus awaiting equals generated plus return postage, by construction. Postage the seller
paid outside TikTok never passes through a statement and is outside Shop Money.

**Freshness**, A29.3. Under 6 hours since the last successful sync is `fresh`, 6 to 24
hours inclusive is `getting_old`, and over 24 hours or never synced is `stale`. `stale` is
true exactly when the status is `stale`.

**Needs you** is counted live on every request and ordered critical, then warning, then
info, then by the amount at stake, then by count. The items are counts rather than events,
so they carry no single time, and the tie ends at the count. A29.6 holds the full table.
Four severities are derived from the owner's definitions rather than named by him: open
discrepancies, unmapped fees and returns to check as warnings, out of stock as info.

**Requires migration 0022**, which adds the refresh and scope columns and the `partial`
sync status. Until 0022 is applied, this handler fails on the query that reads them. The
missing scope item cannot fire until `required_scopes` holds a decided list (A29.4).
`COST_PRICE_UPDATE_RECOMMENDED` is not served, because nothing records when a cost is stale.

**Verified by the smoke test only.** The queries were run on the development branch, as
recorded in the pull request. The handler itself has not run against a real database.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from .auth import Account, require_account
from .dates import business_today, now_utc
from .db import tenant
from .money import Money, money
from .money_view import TIKTOK_FEES, calculate
from .shops import require_shop

router = APIRouter(tags=["Money"])

STALE_AFTER = timedelta(hours=24)
GETTING_OLD_AFTER = timedelta(hours=6)
EXPIRING_WITHIN = timedelta(days=14)
SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}
AWAITING_STATUSES = ("waiting_delivery", "waiting_return_refund", "delivered_awaiting_settlement")

# The categories whose sum is net proceeds, as the calculator defines it.
NET_PROCEEDS_CATEGORIES = ("gross_sales", "seller_discount", "refund") + TIKTOK_FEES

SHOP_MONEY_SQL = """
select case when le.settlement_id is not null then 'settled'
            else coalesce(os.status, 'unknown') end as status,
       sum(le.amount_minor) as amount_minor,
       sum(le.amount_minor) filter (where le.category = 'return_shipping') as postage_minor,
       count(distinct le.order_id) as orders,
       coalesce(max(le.currency), 'GBP') as currency
  from ledger_entries le
  left join order_settlements os on os.order_id = le.order_id
 where le.shop_id = %(shop)s
   and (le.category = any(%(np)s)
        or (le.category = 'return_shipping'
            and le.tiktok_fee_type = 'return_shipping_fee_amount'))
 group by 1
"""

NEEDS_YOU_SQL = """
select
  (select count(*) from return_items
    where shop_id = %(shop)s and seller_check_status = 'pending') as returns_to_check,
  (select count(*) from discrepancies
    where shop_id = %(shop)s and status = 'open') as open_discrepancies,
  (select count(*) from stock_positions
    where shop_id = %(shop)s and on_shelf <= 0) as out_of_stock,
  (select count(distinct le.sku_id) from ledger_entries le
    where le.shop_id = %(shop)s and le.category = 'gross_sales' and le.sku_id is not null
      and not exists (select 1 from product_costs pc
                       where pc.sku_id = le.sku_id and pc.superseded_at is null)) as missing_costs,
  (select count(*) from ledger_entries
    where shop_id = %(shop)s and category = 'unmapped_fee'
      and basis_day >= %(month_start)s and basis_day <= %(today)s) as unmapped_fees,
  (select coalesce(-sum(amount_minor), 0) from ledger_entries
    where shop_id = %(shop)s and category = 'unmapped_fee'
      and basis_day >= %(month_start)s and basis_day <= %(today)s) as unmapped_fee_minor,
  (select last_synced_at from shops where id = %(shop)s) as last_synced_at,
  (select connection_status from shops where id = %(shop)s) as connection_status,
  (select access_expires_at from tiktok_connections where shop_id = %(shop)s) as access_expires_at,
  (select refresh_expires_at from tiktok_connections where shop_id = %(shop)s) as refresh_expires_at,
  (select revoked_at from tiktok_connections where shop_id = %(shop)s) as revoked_at,
  (select count(*) from tiktok_connections where shop_id = %(shop)s) as connections,
  (select refresh_failure_code from tiktok_connections where shop_id = %(shop)s) as refresh_failure_code,
  (select refresh_attempted_at from tiktok_connections where shop_id = %(shop)s) as refresh_attempted_at,
  (select refresh_succeeded_at from tiktok_connections where shop_id = %(shop)s) as refresh_succeeded_at,
  (select array(select unnest(required_scopes) except select unnest(scopes))
     from tiktok_connections where shop_id = %(shop)s) as missing_scopes,
  (select array_agg(status order by domain) from (
     select distinct on (domain) domain, status from sync_runs
      where shop_id = %(shop)s order by domain, created_at desc) latest) as latest_sync_statuses
"""


class Hero(BaseModel):
    label: str
    value: Money | None = None
    confidence: str
    cost_coverage: float


class Month(BaseModel):
    period: dict[str, Any]
    gross: Money
    net_proceeds: Money
    kept: Money | None = None
    kept_reason: str | None = None


class Awaiting(BaseModel):
    status: str
    amount: Money
    orders: int


class ShopMoney(BaseModel):
    generated: Money
    paid_out: Money
    awaiting: Money
    return_postage: Money
    awaiting_breakdown: list[Awaiting]


class NeedsYouItem(BaseModel):
    type: str
    count: int
    severity: str
    label: str | None = None
    amount_at_stake: Money | None = None
    href: str | None = None


class Freshness(BaseModel):
    status: str
    last_synced_at: datetime | None = None


def freshness(last_synced_at: datetime | None, now: datetime) -> Freshness:
    """A29.3. Under 6 hours fresh, 6 to 24 inclusive getting old, over 24 or never stale."""
    if last_synced_at is None:
        return Freshness(status="stale", last_synced_at=None)
    age = now - last_synced_at
    if age < GETTING_OLD_AFTER:
        status = "fresh"
    elif age <= STALE_AFTER:
        status = "getting_old"
    else:
        status = "stale"
    return Freshness(status=status, last_synced_at=last_synced_at)


class TodayView(BaseModel):
    as_of: datetime
    stale: bool
    freshness: Freshness
    hero: Hero
    month: Month
    shop_money: ShopMoney
    needs_you: list[NeedsYouItem]


def _plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def _needs_you(r: dict[str, Any], now: datetime, currency: str) -> tuple[bool, list[NeedsYouItem]]:
    items: list[NeedsYouItem] = []

    def add(kind: str, count: int, severity: str, label: str, at_stake: int | None = None):
        if count > 0:
            items.append(NeedsYouItem(
                type=kind, count=count, severity=severity, label=label,
                amount_at_stake=money(at_stake, currency) if at_stake else None,
            ))

    # The connection, A29.4.
    if r["connections"]:
        broken = (
            r["revoked_at"] is not None
            or r["connection_status"] in ("needs_reconnect", "disconnected")
            or (r["access_expires_at"] is not None and r["access_expires_at"] <= now)
            or (r["refresh_expires_at"] is not None and r["refresh_expires_at"] <= now)
        )
        refresh_failed = r["refresh_failure_code"] is not None and (
            r["refresh_succeeded_at"] is None
            or (r["refresh_attempted_at"] is not None
                and r["refresh_attempted_at"] > r["refresh_succeeded_at"])
        )
        missing = [m for m in (r["missing_scopes"] or []) if m]
        if broken:
            add("connection_action_required", 1, "critical",
                "Your TikTok Shop needs reconnecting")
        if refresh_failed:
            add("refresh_failed", 1, "critical",
                f"TikTok refused to refresh the connection ({r['refresh_failure_code']})")
        if missing:
            add("missing_scope", len(missing), "critical",
                "TikTok has not granted " + ", ".join(sorted(missing)))
        if (not broken and r["refresh_expires_at"] is not None
                and r["refresh_expires_at"] - now <= EXPIRING_WITHIN):
            days = max((r["refresh_expires_at"] - now).days, 0)
            add("connection_expiring", 1, "warning",
                f"Your TikTok connection expires in {_plural(days, 'day', 'days')}")

    # Sync health, A29.5. The latest run for each domain.
    latest = list(r["latest_sync_statuses"] or [])
    add("sync_needs_reconnect", latest.count("needs_reconnect"), "critical",
        "A sync stopped because TikTok needs reconnecting")
    add("sync_failed", latest.count("failed"), "warning",
        _plural(latest.count("failed"), "part of the last sync failed",
                "parts of the last sync failed"))
    add("sync_partial", latest.count("partial"), "warning",
        _plural(latest.count("partial"), "part of the last sync was incomplete",
                "parts of the last sync were incomplete"))

    last = r["last_synced_at"]
    stale = freshness(last, now).status == "stale"
    if last is None:
        add("first_sync_pending", 1, "info", "Your first sync has not finished yet")
    elif stale:
        hours = int((now - last).total_seconds() // 3600)
        add("stale_data", 1, "warning",
            f"Figures may be out of date. Last synced {hours} hours ago")

    add("open_discrepancies", int(r["open_discrepancies"]), "warning",
        _plural(int(r["open_discrepancies"]), "figure disagrees with TikTok",
                "figures disagree with TikTok"))
    add("unmapped_fees", int(r["unmapped_fees"]), "warning",
        _plural(int(r["unmapped_fees"]), "fee this month has no category",
                "fees this month have no category"),
        int(r["unmapped_fee_minor"]))
    add("returns_to_check", int(r["returns_to_check"]), "warning",
        _plural(int(r["returns_to_check"]), "return to check", "returns to check"))
    add("missing_costs", int(r["missing_costs"]), "info",
        _plural(int(r["missing_costs"]), "product variant has no cost",
                "product variants have no cost"))
    add("out_of_stock", int(r["out_of_stock"]), "info",
        _plural(int(r["out_of_stock"]), "product variant is out of stock",
                "product variants are out of stock"))

    items.sort(key=lambda i: (
        SEVERITY_ORDER[i.severity],
        -(i.amount_at_stake.amount_minor if i.amount_at_stake else 0),
        -i.count,
    ))
    return stale, items


@router.get("/shops/{shopId}/today", response_model=TodayView)
def get_today(
    account: Annotated[Account, Depends(require_account)],
    shop_id: Annotated[UUID, Depends(require_shop)],
    basis: Annotated[str, Query(pattern="^(sales|cash)$")] = "sales",
) -> TodayView:
    now = now_utc()
    today = business_today(now)
    month_start = today.replace(day=1)

    with tenant(account.id) as conn:
        day = calculate(conn, shop_id, today, today, basis)
        month = calculate(conn, shop_id, month_start, today, basis)

        cur = conn.execute(SHOP_MONEY_SQL, {"shop": str(shop_id),
                                            "np": list(NET_PROCEEDS_CATEGORIES)})
        cols = [d.name for d in cur.description]
        settlement = [dict(zip(cols, r, strict=True)) for r in cur.fetchall()]

        cur = conn.execute(NEEDS_YOU_SQL, {"shop": str(shop_id),
                                           "month_start": month_start, "today": today})
        cols = [d.name for d in cur.description]
        needs = dict(zip(cols, cur.fetchone(), strict=True))

    currency = month.totals.net_proceeds.currency

    # The hero. A8's labels, and the figure the label names.
    complete = day.cost_coverage == 1.0
    gpar = day.totals.gross_profit_after_returns
    hero = Hero(
        label="gross_profit_after_returns" if complete else "net_proceeds",
        value=gpar if complete else day.totals.net_proceeds,
        confidence=day.confidence,
        cost_coverage=day.cost_coverage,
    )

    # A29.7. Paid out and awaiting include the return postage TikTok deducted, so paid out
    # is what TikTok paid. Generated stays A8's net proceeds, and the postage is stated on its
    # own, so paid out plus awaiting equals generated plus return postage.
    postage = sum(int(s["postage_minor"] or 0) for s in settlement)
    paid = sum(int(s["amount_minor"]) for s in settlement if s["status"] == "settled")
    waiting = [s for s in settlement if s["status"] != "settled"]
    shop_money = ShopMoney(
        generated=money(sum(int(s["amount_minor"]) for s in settlement) - postage, currency),
        paid_out=money(paid, currency),
        awaiting=money(sum(int(s["amount_minor"]) for s in waiting), currency),
        return_postage=money(postage, currency),
        # Only TikTok's own sub-statuses are listed, as the contract requires. An unsettled
        # entry whose order has no settlement row counts towards `awaiting` but cannot be
        # given a status, so the breakdown can then sum to less than the total. None exists
        # on the development branch.
        awaiting_breakdown=[
            Awaiting(status=s["status"], amount=money(int(s["amount_minor"]), currency),
                     orders=int(s["orders"]))
            for s in sorted(waiting, key=lambda s: s["status"])
            if s["status"] in AWAITING_STATUSES
        ],
    )

    stale, items = _needs_you(needs, now, currency)

    return TodayView(
        as_of=now,
        stale=stale,
        freshness=freshness(needs["last_synced_at"], now),
        hero=hero,
        month=Month(
            period=month.period,
            gross=month.totals.gross_sales,
            net_proceeds=month.totals.net_proceeds,
            kept=month.kept,
            kept_reason=month.kept_reason,
        ),
        shop_money=shop_money,
        needs_you=items,
    )
