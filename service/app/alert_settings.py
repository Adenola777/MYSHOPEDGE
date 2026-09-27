"""Alert settings, S27. The thresholds behind the stock states and the absorption ceiling.

`getAlertSettings` (STK-3) and `putAlertSettings` (STK-3, STK-8). Both run inside the
seller's own scope through `tenant()`, so the settings are bound to the shop by row-level
security and never taken from the request.

Defaults are served when no row exists, so a shop that has never set thresholds still reads
a complete answer rather than a 404. The defaults are the table's own column defaults
(14 low-stock days, 7 coming-back days, 20 units of absorption tolerance), so the answer
before a save matches the behaviour the stock endpoints already apply.

A PUT is a full replacement. The ranges are enforced by the request model, so a value
outside them is a 422 before any row is touched.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from .auth import Account, require_account
from .db import tenant
from .shops import require_shop

router = APIRouter(tags=["Settings"])

DEFAULTS = {"low_stock_days": 14, "coming_back_days": 7, "absorption_tolerance_units": 20}


class AlertSettingsInput(BaseModel):
    low_stock_days: int = Field(default=14, ge=1, le=365)
    coming_back_days: int = Field(default=7, ge=1, le=365)
    absorption_tolerance_units: int = Field(default=20, ge=0, le=1000)


class AlertSettings(AlertSettingsInput):
    shop_id: UUID
    updated_at: datetime


@router.get("/shops/{shopId}/alert-settings", response_model=AlertSettings,
            summary="Read alert thresholds")
def get_alert_settings(
    account: Annotated[Account, Depends(require_account)],
    shop_id: Annotated[UUID, Depends(require_shop)],
) -> AlertSettings:
    with tenant(account.id) as conn:
        row = conn.execute(
            "select low_stock_days, coming_back_days, absorption_tolerance_units, updated_at "
            "from alert_settings where shop_id = %s",
            (str(shop_id),),
        ).fetchone()
    if row is None:
        # The defaults are the table's own, so this matches what the stock endpoints apply
        # for a shop that has never saved settings. updated_at is the moment of the answer,
        # because nothing has been written yet.
        return AlertSettings(shop_id=shop_id, updated_at=datetime.now(),  # noqa: DTZ005
                             **DEFAULTS)
    return AlertSettings(
        shop_id=shop_id, low_stock_days=row[0], coming_back_days=row[1],
        absorption_tolerance_units=row[2], updated_at=row[3],
    )


@router.put("/shops/{shopId}/alert-settings", response_model=AlertSettings,
            summary="Change alert thresholds")
def put_alert_settings(
    body: AlertSettingsInput,
    account: Annotated[Account, Depends(require_account)],
    shop_id: Annotated[UUID, Depends(require_shop)],
) -> AlertSettings:
    with tenant(account.id) as conn:
        row = conn.execute(
            "insert into alert_settings "
            "(shop_id, low_stock_days, coming_back_days, absorption_tolerance_units, updated_at) "
            "values (%s, %s, %s, %s, now()) "
            "on conflict (shop_id) do update set "
            "low_stock_days = excluded.low_stock_days, "
            "coming_back_days = excluded.coming_back_days, "
            "absorption_tolerance_units = excluded.absorption_tolerance_units, "
            "updated_at = now() "
            "returning low_stock_days, coming_back_days, absorption_tolerance_units, updated_at",
            (str(shop_id), body.low_stock_days, body.coming_back_days,
             body.absorption_tolerance_units),
        ).fetchone()
    return AlertSettings(
        shop_id=shop_id, low_stock_days=row[0], coming_back_days=row[1],
        absorption_tolerance_units=row[2], updated_at=row[3],
    )
