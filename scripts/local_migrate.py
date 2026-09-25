"""Local QA build: backfill 0001-0009, run migrations, load seed. Not production."""
from __future__ import annotations
import hashlib, os, subprocess, sys
from pathlib import Path
import psycopg

ROOT = Path("/app")
SCHEMA = ROOT / "schema"
SERVICE = ROOT / "service"
MIG_URL = "postgresql://mse_migrator:migpw_local@127.0.0.1:5432/myshopedge"

LEDGER = """
create table if not exists schema_migrations (
  filename   text primary key,
  checksum   text        not null,
  applied_at timestamptz not null default now(),
  applied_by text        not null default current_user,
  backfilled boolean     not null default false
)"""

def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()

def main() -> int:
    # 1. Ledger + backfill 0001-0009 (their effects are already in the base schema).
    backfill = sorted(
        p for p in SCHEMA.glob("*.sql")
        if p.name[0].isdigit() and int(p.name[:4]) <= 9
    )
    with psycopg.connect(MIG_URL, autocommit=True) as conn:
        conn.execute(LEDGER)
        for p in backfill:
            conn.execute(
                "insert into schema_migrations (filename, checksum, backfilled) "
                "values (%s, %s, true) on conflict (filename) do nothing",
                (p.name, sha(p)),
            )
        print(f"backfilled {len(backfill)} migrations: {[p.name for p in backfill]}")

    # 2. Run the real migration runner as mse_migrator. It applies the base schema, then
    #    0010..0024 (0001-0009 are skipped as already recorded).
    env = {**os.environ, "DATABASE_URL": MIG_URL}
    r = subprocess.run([sys.executable, "scripts/migrate.py"], cwd=SERVICE, env=env)
    if r.returncode != 0:
        return r.returncode

    # 3. The seed omits two NOT NULL bytea columns on tiktok_connections (known fault 6).
    #    Drop the constraints on this throwaway database so the seed loads.
    with psycopg.connect(MIG_URL, autocommit=True) as conn:
        conn.execute("alter table tiktok_connections alter column access_token_enc drop not null")
        conn.execute("alter table tiktok_connections alter column refresh_token_enc drop not null")
    print("relaxed tiktok_connections NOT NULL for the seed")

    # 4. Load the seed as mse_migrator (bypasses row level security).
    seed = ROOT / "testdata" / "seed.sql"
    env2 = {**os.environ, "PGPASSWORD": "migpw_local"}
    r = subprocess.run(
        ["psql", MIG_URL, "-v", "ON_ERROR_STOP=1", "-q", "-f", str(seed)],
        env=env2,
    )
    if r.returncode != 0:
        return r.returncode
    print("seed loaded")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
