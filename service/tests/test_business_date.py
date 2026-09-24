"""The business date around midnight and across both clock changes. A29.9.

    python3 tests/test_business_date.py
"""

import os, sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.dates import business_today

failures = []

def case(name, utc, expected):
    got = business_today(datetime.fromisoformat(utc).replace(tzinfo=timezone.utc))
    ok = got.isoformat() == expected
    print(f"  {'PASS' if ok else 'FAIL'}  {name}: {utc}Z is {got} in London")
    if not ok:
        failures.append(name)

print("business date")
# British Summer Time, UTC+1. The hour after midnight in London is still yesterday in UTC.
case("summer, 23:30 UTC is already tomorrow in London", "2026-08-31T23:30:00", "2026-09-01")
case("summer, 22:59 UTC is still today in London", "2026-08-31T22:59:00", "2026-08-31")
# Greenwich Mean Time, UTC+0. Midnight is the same instant in both.
case("winter, 23:59 UTC is the same day in London", "2026-12-31T23:59:00", "2026-12-31")
case("winter, 00:00 UTC is the next day in London", "2027-01-01T00:00:00", "2027-01-01")
# The clocks go forward on 29 March 2026 at 01:00 UTC, and back on 25 October 2026 at 01:00 UTC.
case("spring change, the evening before the clocks go forward", "2026-03-28T23:30:00", "2026-03-28")
case("spring change, 23:30 UTC after the clocks went forward", "2026-03-29T23:30:00", "2026-03-30")
case("autumn change, 23:30 UTC before the clocks go back", "2026-10-24T23:30:00", "2026-10-25")
case("autumn change, 23:30 UTC after the clocks went back", "2026-10-25T23:30:00", "2026-10-25")

try:
    business_today(datetime(2026, 8, 31, 23, 30))
    failures.append("naive datetime")
    print("  FAIL  a naive datetime was accepted")
except ValueError:
    print("  PASS  a naive datetime is refused")

print()
if failures:
    print(f"{len(failures)} failure(s)")
    sys.exit(1)
print("every case gave the London date")
