"""The Money screen, S11. The calculator for the whole shop.

The order of the calculator is A8.5's, and it is fixed:

    Gross sales, less seller discounts           = Net sales
    less TikTok fees                             = Net proceeds before refunds
    less refunds to customers                    = Net proceeds
    less cost of goods sold and your postage     = Gross profit
    less return shipping and stock written off   = Gross profit after returns

Four things the rulings left open were decided by the owner on 24 September 2026, and each
is applied here as decided rather than inferred.

1. **Platform adjustments sit inside TikTok fees**, each on its own line under TikTok's own
   adjustment type. A8.5 had no place for them. They carry no SKU, which is why the product
   endpoints never met them.
2. **Reserves and the payout are a final section**, after the chain. A18.3 wants net
   proceeds, reserve withheld and payout shown in that order, and MoneyView has no field
   for them, so they travel in the existing CalculatorSection shape and the contract is
   unchanged. The amounts are the ledger's own, signs included: a payout is recorded as
   money leaving the ledger for the bank, so it is negative. Whether the screen shows it
   with its sign flipped is a presentation question that is still open.
3. **`cost_coverage` is a share of products.** Products sold in the period with a cost for
   every variant, divided by products sold. That is the "N of M products" half of CST-6.
4. **Confidence follows the basis.** Cash basis counts settled money only, so it is
   confirmed. Sales basis is estimated when any sale, refund or TikTok deduction in the
   period has no settlement yet. Either is incomplete when a sold product lacks a cost,
   because the figure that needs the cost is then null.

Cost of goods sold is computed, not read. It is the product cost times units sold less
units returned, per SKU, which is A4's retained cost and the same arithmetic the product
endpoints use. The `cost_of_goods_sold` ledger entries are posted for every unit including
the ones that came back, so reading them would count a returned unit twice (A4.1).

When costs are incomplete the chain stops at Net proceeds. The two cost sections still
appear, each with its own total under A8.5's section labels, and gross profit is null
rather than a figure that silently leaves the goods out.

`granularity` is accepted and echoed. MoneyView carries no series, so nothing is bucketed
by it. What the parameter should change on this response is not stated in the contract or
in any ruling, and it is recorded here as unanswered rather than guessed.

**Verified by the smoke test only.** The handler has run against canned rows. It has not
run against the development branch, whose ledger has `settlement_month` empty on every
row because `testdata/seed.sql` omits that column, so the cash basis there returns nothing.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Response
from pydantic import BaseModel

from .auth import Account, require_account
from .db import tenant
from .money import Money, money
from .products import NET_PROCEEDS_TYPES, RETURN_LOSS_TYPES, SQL as PRODUCTS_SQL
from .shops import require_shop

router = APIRouter(tags=["Money"])

TIKTOK_FEES = (
    "platform_commission", "affiliate_commission", "transaction_fee",
    "smart_promotions_fee", "shipping_fee", "return_handling_fee",
    "fbt_operations_fee", "fbt_shipping_fee", "fbt_storage_fee",
    "unmapped_fee", "platform_adjustment",
)

# (key, label, label of the running figure it reaches, categories). A8.5's order.
CHAIN: list[tuple[str, str, str, tuple[str, ...]]] = [
    ("revenue", "Sales", "Net sales", ("gross_sales", "seller_discount")),
    ("tiktok_fees", "TikTok fees", "Net proceeds before refunds", TIKTOK_FEES),
    ("refunds", "Refunds", "Net proceeds", ("refund",)),
    ("your_costs", "Your costs", "Gross profit", ("seller_shipping",)),
    ("return_costs", "Return costs", "Gross profit after returns",
     ("return_shipping", "stock_written_off")),
]
# A8.5's section totals, used instead of the running figure when costs are incomplete.
SECTION_TOTALS = {"your_costs": "Total your costs", "return_costs": "Total return costs"}
PAYOUT = ("payout", "Held and paid out", ("reserve_withheld", "reserve_released", "settlement"))

# A8.5's line names. A fee TikTok names that we do not recognise, and every platform
# adjustment, is shown under TikTok's own name instead.
LABELS = {
    "gross_sales": "Gross sales (GMV)",
    "seller_discount": "Seller discounts",
    "platform_commission": "Platform commission",
    "affiliate_commission": "Affiliate commission",
    "transaction_fee": "Transaction fee",
    "smart_promotions_fee": "Smart Promotions fee",
    "shipping_fee": "Shipping fee",
    "return_handling_fee": "Return handling fee",
    "fbt_operations_fee": "FBT operations fee",
    "fbt_shipping_fee": "FBT shipping fee",
    "fbt_storage_fee": "FBT storage fee",
    "unmapped_fee": "Fee TikTok did not name in a way we recognise",
    "platform_adjustment": "TikTok adjustment",
    "refund": "Refunds to customers",
    "cost_of_goods_sold": "Cost of goods sold",
    "seller_shipping": "Shipping and packaging you pay",
    "return_shipping": "Return shipping you paid",
    "stock_written_off": "Stock written off",
    # A18.3's names for the three figures that are not the same.
    "reserve_withheld": "Reserve withheld",
    "reserve_released": "Reserve released",
    "settlement": "Payout",
}
VERBATIM = ("unmapped_fee", "platform_adjustment")

# Money TikTok settles. Return costs and write-offs never pass through a statement (A4),
# and cost of goods is the seller's own, so none of those can make a figure an estimate.
SETTLED_BY_TIKTOK = NET_PROCEEDS_TYPES

LINES_SQL = """
select le.category, le.tiktok_fee_type,
       sum(le.amount_minor) as amount_minor,
       count(*) as entries,
       count(*) filter (where le.settlement_id is null
                          and le.entry_type = any(%(settled)s)) as unsettled,
       coalesce(max(le.currency), 'GBP') as currency
  from ledger_entries le
 where le.shop_id = %(shop)s
   and {date_column} >= %(from)s
   and {date_column} <= %(to)s
   and le.category is distinct from 'cost_of_goods_sold'
 group by le.category, le.tiktok_fee_type
 order by le.category, le.tiktok_fee_type
"""


class CalculatorLine(BaseModel):
    label: str
    amount: Money
    category: str | None = None
    tiktok_field: str | None = None
    tiktok_fee_type: str | None = None


class CalculatorSection(BaseModel):
    key: str
    label: str
    lines: list[CalculatorLine]
    subtotal: Money
    subtotal_label: str | None = None


class Totals(BaseModel):
    gross_sales: Money
    net_sales: Money
    net_proceeds: Money
    cost_of_goods_sold: Money | None = None
    gross_profit: Money | None = None
    gross_profit_after_returns: Money | None = None


class MoneyView(BaseModel):
    as_of: datetime
    period: dict[str, Any]
    granularity: str
    sections: list[CalculatorSection]
    totals: Totals
    kept: Money | None = None
    kept_reason: str | None = None
    cost_coverage: float
    confidence: str
    unmapped_fee_count: int


def _line(row: dict[str, Any], currency: str) -> CalculatorLine:
    """One ledger group as one line.

    `ledger_entries.tiktok_fee_type` holds TikTok's field name for a fee, for example
    `affiliate_ads_commission_amount`, and TikTok's adjustment type for a platform
    adjustment, for example `PLATFORM_PENALTY`. Checked on the development branch on 24
    September 2026. So it is the contract's `tiktok_field` for every fee, and its
    `tiktok_fee_type` for the two categories the contract says carry one. Two fees in the
    same category arrive as two lines, because no fee is merged with another.
    """
    category = row["category"]
    raw = row["tiktok_fee_type"]
    label = LABELS.get(category, category)
    if category in VERBATIM and raw:
        label = raw
    return CalculatorLine(
        label=label,
        amount=money(int(row["amount_minor"]), currency),
        category=category,
        tiktok_field=raw if category != "platform_adjustment" else None,
        tiktok_fee_type=raw if category in VERBATIM else None,
    )


def _etag(view: MoneyView) -> str:
    """A hash of everything but `as_of`, which changes on every request by definition."""
    body = view.model_dump(mode="json", exclude_unset=True)
    body.pop("as_of", None)
    digest = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
    return f'"{digest[:32]}"'


@router.get(
    "/shops/{shopId}/money",
    response_model=MoneyView,
    response_model_exclude_unset=True,
)
def get_money(
    response: Response,
    account: Annotated[Account, Depends(require_account)],
    shop_id: Annotated[UUID, Depends(require_shop)],
    basis: Annotated[str, Query(pattern="^(sales|cash)$")] = "sales",
    period_from: Annotated[date | None, Query(alias="from")] = None,
    period_to: Annotated[date | None, Query(alias="to")] = None,
    granularity: Annotated[str, Query(pattern="^(day|week|month)$")] = "month",
    if_none_match: Annotated[str | None, Header()] = None,
):
    today = date.today()
    start = period_from or today.replace(day=1)
    end = period_to or today
    # The same columns the product endpoints use, so the two screens cannot disagree.
    date_column = "le.basis_day" if basis == "sales" else "le.settlement_month"
    args = {
        "shop": str(shop_id), "from": start, "to": end,
        "settled": list(SETTLED_BY_TIKTOK),
        "np": list(NET_PROCEEDS_TYPES), "rl": list(RETURN_LOSS_TYPES),
    }

    with tenant(account.id) as conn:
        cur = conn.execute(LINES_SQL.format(date_column=date_column), args)
        cols = [d.name for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]

        cur = conn.execute(PRODUCTS_SQL.format(date_column=date_column), args)
        cols = [d.name for d in cur.description]
        products = [dict(zip(cols, r)) for r in cur.fetchall()]

    currency = rows[0]["currency"] if rows else "GBP"
    by_category: dict[str, int] = {}
    for r in rows:
        by_category[r["category"]] = by_category.get(r["category"], 0) + int(r["amount_minor"])

    def total(categories: tuple[str, ...]) -> int:
        return sum(by_category.get(c, 0) for c in categories)

    # Cost coverage, as a share of the products sold in the period.
    sold = [p for p in products if int(p["units_sold"]) > 0]
    costed = [p for p in sold if int(p["skus_without_cost"]) == 0]
    coverage = (len(costed) / len(sold)) if sold else 1.0
    costs_complete = len(costed) == len(sold)
    cogs_minor = (
        -sum(int(p["cost_retained_minor"] or 0) for p in sold) if costs_complete else None
    )

    sections: list[CalculatorSection] = []
    running = 0
    for key, label, reached, categories in CHAIN:
        lines = [
            _line(r, currency) for r in rows
            if r["category"] in categories and int(r["amount_minor"]) != 0
        ]
        # Every platform adjustment and unrecognised fee stays on its own line, in the
        # order the categories are listed, never merged into its neighbour.
        lines.sort(key=lambda l: categories.index(l.category))
        if key == "your_costs" and cogs_minor:
            lines.insert(0, CalculatorLine(
                label=LABELS["cost_of_goods_sold"],
                amount=money(cogs_minor, currency),
                category="cost_of_goods_sold",
            ))
        own = sum(l.amount.amount_minor for l in lines)
        running += own
        if not lines:
            continue
        incomplete_stage = key in SECTION_TOTALS and not costs_complete
        sections.append(CalculatorSection(
            key=key, label=label, lines=lines,
            subtotal=money(own if incomplete_stage else running, currency),
            subtotal_label=SECTION_TOTALS[key] if incomplete_stage else reached,
        ))

    key, label, categories = PAYOUT
    payout_lines = [
        _line(r, currency) for r in rows
        if r["category"] in categories and int(r["amount_minor"]) != 0
    ]
    if payout_lines:
        payout_lines.sort(key=lambda l: categories.index(l.category))
        sections.append(CalculatorSection(
            key=key, label=label, lines=payout_lines,
            subtotal=money(sum(l.amount.amount_minor for l in payout_lines), currency),
        ))

    gross_sales = total(("gross_sales",))
    net_sales = gross_sales + total(("seller_discount",))
    net_proceeds = net_sales + total(TIKTOK_FEES) + total(("refund",))
    gross_profit = gross_profit_after = None
    if costs_complete:
        gross_profit = net_proceeds + (cogs_minor or 0) + total(("seller_shipping",))
        gross_profit_after = gross_profit + total(("return_shipping", "stock_written_off"))

    totals = Totals(
        gross_sales=money(gross_sales, currency),
        net_sales=money(net_sales, currency),
        net_proceeds=money(net_proceeds, currency),
        gross_profit=money(gross_profit, currency) if gross_profit is not None else None,
        gross_profit_after_returns=(
            money(gross_profit_after, currency) if gross_profit_after is not None else None
        ),
    )
    # The contract types cost of goods as Money, not nullable, so it is left out rather
    # than sent as null when a cost is missing.
    if cogs_minor is not None:
        totals.cost_of_goods_sold = money(cogs_minor, currency)

    if not sold:
        kept_reason = "no_sales"
    elif not costs_complete:
        kept_reason = "incomplete_costs"
    else:
        kept_reason = None

    unsettled = sum(int(r["unsettled"]) for r in rows)
    if not costs_complete:
        confidence = "incomplete"
    elif basis == "sales" and unsettled:
        confidence = "estimated"
    else:
        confidence = "confirmed"

    view = MoneyView(
        as_of=datetime.now(timezone.utc),
        period={"from": start.isoformat(), "to": end.isoformat(), "basis": basis},
        granularity=granularity,
        sections=sections,
        totals=totals,
        kept=(
            money(gross_profit_after, currency)
            if kept_reason is None and gross_profit_after is not None else None
        ),
        kept_reason=kept_reason,
        cost_coverage=coverage,
        confidence=confidence,
        unmapped_fee_count=sum(
            int(r["entries"]) for r in rows if r["category"] == "unmapped_fee"
        ),
    )

    etag = _etag(view)
    if if_none_match is not None and if_none_match == etag:
        return Response(status_code=304, headers={"ETag": etag})
    response.headers["ETag"] = etag
    return view
