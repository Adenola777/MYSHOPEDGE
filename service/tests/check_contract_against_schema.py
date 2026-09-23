"""Check that the database can hold every field the contract serves.

    DATABASE_URL=postgresql://... python3 tests/check_contract_against_schema.py

Written on 23 September 2026, after the contract was found to declare two properties on
`Shop` that the `shops` table had no column for. `tiktok_shop_code` and `seller_type` were
both documented, and the callback handler was documented as storing the seller type, and
there was nowhere to put it. Migration 0020 added them.

Nothing caught that, because the two sides were never compared. `test_contract_conformance`
compares the contract to the FastAPI handlers and never reaches the database.
`verify_v0.2.sql` checks the schema against itself. The gap between them is exactly where
this defect lived.

**Rule 1 of A13 decides the direction.** The service implements the contract, so a property
the contract serves and the table cannot hold is a defect in the table, never a reason to
quietly drop the property from the contract.

**Derived properties are declared here, by name, with a reason.** A response field that is
computed rather than stored is legitimate, and silence about which ones those are is how a
missing column disguises itself as a deliberate choice. Adding a name to DERIVED is a
decision that has to be written down and defended, which is the point.

This check needs a database. It is not part of the three test suites, which need nothing.

**Partly unverified, 23 September 2026.** `contract_properties` has been executed against
the real contract and returns the twelve properties of `Shop`, and its output was compared
by hand against the columns read from the development branch, which is how the result below
is known. The `psycopg` connection in `main` has never run, because doing so needs
`DATABASE_URL` and that has to come from Adenola's own terminal. It follows the same
pattern as `scripts/migrate.py`, which does run. Treat the first clean run as the check on
this file rather than as a check on the schema.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "api" / "openapi.yaml"

# Contract schema -> the table that has to be able to hold it.
CHECKED = {"Shop": "shops"}

# Properties served but not stored, each with the reason it is not a missing column.
DERIVED: dict[tuple[str, str], str] = {
    ("Shop", "authorization_expires_at"):
        "Derived by the handler. tiktok_connections.refresh_expires_at may be the same "
        "instant and nobody has verified that, so 0020 deliberately added no column. One "
        "real TikTok authorisation settles it. Recorded as open in CLAUDE.md.",
}


def contract_properties(schema_name: str) -> list[str]:
    """Read one schema's property names out of the contract.

    Deliberately literal. The contract is hand written with a stable two-space layout, and
    a YAML parser is not a dependency this check should carry to read a list of keys.
    """
    lines = CONTRACT.read_text().splitlines()
    try:
        start = next(i for i, l in enumerate(lines) if l == f"    {schema_name}:")
    except StopIteration:
        raise SystemExit(f"{schema_name} is not in {CONTRACT.name}. The contract moved.")

    end = next(
        (i for i, l in enumerate(lines[start + 1:], start + 1)
         if re.match(r"^    [A-Za-z]", l)),
        len(lines),
    )

    props, inside = [], False
    for line in lines[start:end]:
        if line == "      properties:":
            inside = True
            continue
        if inside:
            m = re.match(r"^        ([a-z_]+):$", line)
            if m:
                props.append(m.group(1))
    if not props:
        raise SystemExit(f"Read no properties for {schema_name}. The layout changed.")
    return props


def main() -> int:
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL is not set. This check needs a database.", file=sys.stderr)
        return 2

    import psycopg

    problems: list[str] = []
    with psycopg.connect(url) as conn:
        for schema_name, table in CHECKED.items():
            props = contract_properties(schema_name)
            columns = {
                r[0] for r in conn.execute(
                    "select column_name from information_schema.columns "
                    "where table_schema = 'public' and table_name = %s",
                    (table,),
                )
            }
            if not columns:
                problems.append(f"{table} does not exist on this branch.")
                continue

            derived, missing = [], []
            for p in props:
                if p in columns:
                    continue
                if (schema_name, p) in DERIVED:
                    derived.append(p)
                else:
                    missing.append(p)

            print(f"{schema_name} -> {table}")
            print(f"  {len(props)} properties, {len(props) - len(missing) - len(derived)} stored, "
                  f"{len(derived)} derived, {len(missing)} missing")
            for p in derived:
                print(f"  derived  {p}")
            for p in missing:
                problems.append(
                    f"{schema_name}.{p} is served by the contract and {table} cannot hold "
                    f"it. Write a migration, or add it to DERIVED with the reason."
                )

    print()
    for p in problems:
        print(f"FAIL  {p}")
    if problems:
        return 1
    print("the database can hold everything the contract serves")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
