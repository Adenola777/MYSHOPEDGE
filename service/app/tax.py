"""Tax. The profile, the VAT threshold monitor, and the set-aside estimate.

Traces TAX-1, TAX-2 and TAX-3. This module monitors a threshold and estimates a set-aside.
It does not prepare or submit a VAT return and it does not account for VAT on a registered
seller's behalf, both of which PRD 6.2 excludes.

The VAT registration threshold is not held in code. It is a reference rule, read from
`reference_rules` with its own `reviewed_at`, because a threshold that a release hard-codes
is one a release has to change. The current value, GBP 90,000 from 1 April 2024, is HMRC's
under the Value Added Tax (Increase of Registration Limits) Order 2024.

The set-aside amount needs the income tax and National Insurance reference rules, and a
ruling on the method. Neither exists yet, so the estimate is returned as null with a reason
rather than as a guessed figure. A seller who under-saves on a made-up number has been
failed by the product, which is TAX-3's own warning.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from .auth import Account, require_account
from .dates import business_today, now_utc
from .db import tenant
from .money import Money, money
from .problems import Problem
from .shops import require_shop

router = APIRouter(tags=["Tax"])

Structure = Literal["sole_trader", "company", "not_sure"]
Confidence = Literal["confirmed", "estimated", "incomplete"]


class TaxProfileIn(BaseModel):
    business_structure: Structure | None = None
    vat_registered: bool = False
    vat_registered_from: str | None = None


class TaxProfileOut(TaxProfileIn):
    completed: bool
    updated_at: str | None = None


class MonthTurnover(BaseModel):
    month: str
    tiktok_gross: Money
    other_channels_gross: Money


class VatMonitorOut(BaseModel):
    as_of: str
    rolling_twelve_month_turnover: Money
    threshold: Money
    headroom: Money
    above_threshold: bool
    includes_other_channels: bool
    months: list[MonthTurnover]
    rule_key: str
    reviewed_at: str | None = None


class BasisItem(BaseModel):
    label: str
    amount: Money | None = None
    rule_key: str | None = None


class SetAsideOut(BaseModel):
    as_of: str
    amount: Money | None = None
    unavailable_reason: Literal["incomplete_costs", "no_tax_profile", "insufficient_history"] | None = None
    confidence: Confidence
    basis_of_estimate: list[BasisItem] = []


def _profile_row(account: Account, conn) -> tuple | None:
    return conn.execute(
        "select business_structure, vat_registered, vat_registered_from, updated_at "
        "from tax_profiles where account_id = %s",
        (str(account.id),),
    ).fetchone()


def _profile_out(row: tuple | None) -> TaxProfileOut:
    if row is None:
        return TaxProfileOut(business_structure=None, vat_registered=False,
                             vat_registered_from=None, completed=False, updated_at=None)
    bs, vr, vrf, ua = row
    return TaxProfileOut(
        business_structure=bs,
        vat_registered=vr,
        vat_registered_from=vrf.isoformat() if vrf else None,
        completed=True,
        updated_at=ua.isoformat() if ua else None,
    )


@router.get("/tax-profile", response_model=TaxProfileOut, summary="Read the tax profile")
def get_tax_profile(account: Annotated[Account, Depends(require_account)]) -> TaxProfileOut:
    with tenant(account.id) as conn:
        return _profile_out(_profile_row(account, conn))


@router.put("/tax-profile", response_model=TaxProfileOut, summary="Save the tax profile")
def put_tax_profile(
    body: TaxProfileIn,
    account: Annotated[Account, Depends(require_account)],
) -> TaxProfileOut:
    # A VAT monitor without a registration date cannot say which periods are in scope.
    registered_from: date | None = None
    if body.vat_registered:
        if not body.vat_registered_from:
            raise Problem(422, "vat_date_required", "Tell us the date you registered for VAT.")
        try:
            registered_from = date.fromisoformat(body.vat_registered_from)
        except ValueError as exc:
            raise Problem(422, "vat_date_invalid", "The VAT registration date is not a date.") from exc

    # A full replacement, not a patch. An omitted field is cleared.
    with tenant(account.id) as conn:
        row = conn.execute(
            "insert into tax_profiles "
            "(account_id, business_structure, vat_registered, vat_registered_from, updated_at) "
            "values (%s, %s, %s, %s, now()) "
            "on conflict (account_id) do update set "
            "business_structure = excluded.business_structure, "
            "vat_registered = excluded.vat_registered, "
            "vat_registered_from = excluded.vat_registered_from, "
            "updated_at = now() "
            "returning business_structure, vat_registered, vat_registered_from, updated_at",
            (str(account.id), body.business_structure, body.vat_registered, registered_from),
        ).fetchone()
    return _profile_out(row)


def _twelve_months(today: date) -> list[tuple[int, int]]:
    """The current London month and the eleven before it, oldest first."""
    seq: list[tuple[int, int]] = []
    for i in range(11, -1, -1):
        month = today.month - i
        year = today.year
        while month <= 0:
            month += 12
            year -= 1
        seq.append((year, month))
    return seq


@router.get("/shops/{shopId}/tax/vat", response_model=VatMonitorOut, summary="VAT threshold monitor")
def get_vat_monitor(
    shopId: Annotated[UUID, Depends(require_shop)],
    account: Annotated[Account, Depends(require_account)],
) -> VatMonitorOut:
    today = business_today()
    seq = _twelve_months(today)
    window_start = date(seq[0][0], seq[0][1], 1)

    with tenant(account.id) as conn:
        gross = dict(conn.execute(
            "select to_char(date_trunc('month', (occurred_at at time zone 'Europe/London')), 'YYYY-MM'), "
            "coalesce(sum(amount_minor), 0) from ledger_entries "
            "where shop_id = %s and category = 'gross_sales' "
            "and (occurred_at at time zone 'Europe/London')::date >= %s group by 1",
            (str(shopId), window_start),
        ).fetchall())
        other = dict(conn.execute(
            "select to_char(month, 'YYYY-MM'), coalesce(sum(gross_minor), 0) "
            "from other_channel_sales where shop_id = %s and month >= %s group by 1",
            (str(shopId), window_start),
        ).fetchall())
        has_other = conn.execute(
            "select exists(select 1 from other_channel_sales where shop_id = %s)",
            (str(shopId),),
        ).fetchone()[0]
        rule = conn.execute(
            "select rule_key, value, reviewed_at from reference_rules "
            "where rule_set = 'vat' and rule_key = 'registration_threshold' "
            "and effective_from <= %s and (effective_to is null or effective_to >= %s) "
            "order by effective_from desc limit 1",
            (today, today),
        ).fetchone()

    if rule is None:
        raise Problem(503, "vat_unconfigured",
                      "The VAT registration threshold is not configured, so the monitor "
                      "cannot say where you stand against it.")
    rule_key, value, reviewed_at = rule
    threshold_minor = int(value["amount_minor"])
    currency = value.get("currency", "GBP")

    months: list[MonthTurnover] = []
    tiktok_total = 0
    other_total = 0
    for year, month in seq:
        key = f"{year:04d}-{month:02d}"
        tg = int(gross.get(key, 0))
        og = int(other.get(key, 0))
        tiktok_total += tg
        other_total += og
        months.append(MonthTurnover(
            month=key,
            tiktok_gross=money(tg, currency),
            other_channels_gross=money(og, currency),
        ))
    turnover = tiktok_total + other_total

    return VatMonitorOut(
        as_of=now_utc().isoformat(),
        rolling_twelve_month_turnover=money(turnover, currency),
        threshold=money(threshold_minor, currency),
        headroom=money(threshold_minor - turnover, currency),
        above_threshold=turnover >= threshold_minor,
        includes_other_channels=has_other,
        months=months,
        rule_key=rule_key,
        reviewed_at=reviewed_at.isoformat() if reviewed_at else None,
    )


@router.get("/shops/{shopId}/tax/set-aside", response_model=SetAsideOut, summary="Set-aside estimate")
def get_set_aside(
    shopId: Annotated[UUID, Depends(require_shop)],
    account: Annotated[Account, Depends(require_account)],
) -> SetAsideOut:
    as_of = now_utc().isoformat()
    with tenant(account.id) as conn:
        profile = _profile_row(account, conn)

    if profile is None:
        return SetAsideOut(
            as_of=as_of, amount=None, unavailable_reason="no_tax_profile",
            confidence="incomplete",
            basis_of_estimate=[BasisItem(
                label="Fill in your tax profile so a set-aside can be estimated.")],
        )

    # The profile exists, but the income tax and National Insurance reference rules a
    # set-aside needs are not configured, and the method has not been ruled. No honest
    # amount can be produced, so none is returned.
    return SetAsideOut(
        as_of=as_of, amount=None, unavailable_reason=None, confidence="incomplete",
        basis_of_estimate=[BasisItem(
            label="Set-aside tax rates are not configured yet, so no amount can be produced.")],
    )
