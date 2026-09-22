"""The migration runner.

    DATABASE_URL=postgresql://... python3 scripts/migrate.py --status
    DATABASE_URL=postgresql://... python3 scripts/migrate.py

Why this exists. On 22 September 2026 the development and production branches were found
to have diverged in both directions, because fourteen migrations had been applied by hand
with no record in either database. Nothing could state which branch held what, so nobody
noticed. Every branch now records its own position and this runner is the only thing that
writes to that record.

Three rules it enforces.

1. A migration is applied once. A filename already present is skipped, not re-run.
2. An applied migration is never edited. If a recorded checksum no longer matches the file
   on disk, the runner refuses to do anything at all, because once a migration has changed
   under a branch the branches can never be compared again.
3. Each migration runs in its own transaction, and its ledger row is written inside that
   same transaction. A migration that fails leaves no row, so a retry is safe.

The runner connects as mse_migrator. It does not connect as mse_app, which has no rights
over the ledger and no business changing the schema.
"""

from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

import psycopg

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "schema"

# The base schema first, then every numbered migration in order. Files that are not
# migrations, such as the verification scripts, are excluded by name rather than by
# guesswork, so adding one cannot accidentally make it run.
BASE = "MyShopEdge_MVP_schema_v0.2.sql"
NOT_MIGRATIONS = {"verify_v0.2.sql", "verify_v0.2_as_app.sql"}

LEDGER = """
create table if not exists schema_migrations (
  filename   text primary key,
  checksum   text        not null,
  applied_at timestamptz not null default now(),
  applied_by text        not null default current_user,
  backfilled boolean     not null default false
)
"""


def migration_files() -> list[Path]:
    numbered = sorted(
        p for p in SCHEMA_DIR.glob("*.sql")
        if p.name[0].isdigit() and p.name not in NOT_MIGRATIONS
    )
    base = SCHEMA_DIR / BASE
    return ([base] if base.exists() else []) + numbered


def checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL is not set.", file=sys.stderr)
        return 1

    status_only = "--status" in sys.argv
    files = migration_files()

    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute(LEDGER)
        applied = {
            row[0]: row[1]
            for row in conn.execute("select filename, checksum from schema_migrations")
        }

    # Rule 2, checked before anything is applied.
    changed = [
        p.name for p in files
        if p.name in applied and applied[p.name] != checksum(p)
    ]
    if changed:
        print("Refusing to run. These applied migrations have changed on disk:", file=sys.stderr)
        for name in changed:
            print(f"  {name}", file=sys.stderr)
        print(
            "\nAn applied migration must never be edited. Write a new one that corrects it.",
            file=sys.stderr,
        )
        return 2

    pending = [p for p in files if p.name not in applied]

    if status_only:
        print(f"{len(applied)} applied, {len(pending)} pending")
        for p in pending:
            print(f"  pending  {p.name}")
        return 0

    if not pending:
        print(f"Up to date. {len(applied)} migrations applied.")
        return 0

    for path in pending:
        sql = path.read_text()
        print(f"applying {path.name} ... ", end="", flush=True)
        # Rule 3: the migration and its ledger row share one transaction.
        with psycopg.connect(url) as conn:
            with conn.transaction():
                conn.execute(sql)
                conn.execute(
                    "insert into schema_migrations (filename, checksum) values (%s, %s)",
                    (path.name, checksum(path)),
                )
        print("done")

    print(f"\n{len(pending)} applied.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
