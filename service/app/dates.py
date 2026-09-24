"""The business date. The one definition of "today" in the service, A29.9.

A seller's day is a London day, and a VAT quarter is a London quarter (A5). A server runs
in UTC, so `date.today()` on it names the wrong day for the hour after midnight in summer.
Every endpoint that needs "today" calls `business_today()` rather than asking the server.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

LONDON = ZoneInfo("Europe/London")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def business_today(now: datetime | None = None) -> date:
    """The current date in Europe/London. `now` must be timezone-aware when given."""
    moment = now or now_utc()
    if moment.tzinfo is None:
        raise ValueError("A naive datetime has no timezone, so it cannot name a London day.")
    return moment.astimezone(LONDON).date()
