#!/usr/bin/env bash
# Idempotent local database bootstrap for the Emergent pod. NOT production.
#
# Postgres data lives under /app/.pgdata so it survives pod restarts (unlike
# /var/lib/postgresql). This script:
#   1. Creates the cluster in /app/.pgdata if it does not exist (initdb).
#   2. Starts the postmaster on 127.0.0.1:5432 if it is not already running.
#   3. Ensures the four roles, the myshopedge database, the base schema, all migrations
#      and the seed. Roles/db/schema are only created when missing; the seed loads only
#      when the accounts table is empty, so re-running is safe.
set -euo pipefail

PGDATA=/app/.pgdata
PGBIN=/usr/lib/postgresql/15/bin
PORT=5432
MIG="postgresql://mse_migrator@127.0.0.1:${PORT}/myshopedge"

mkdir -p "$PGDATA"
chown postgres:postgres "$PGDATA"
chmod 700 "$PGDATA"

# 1. initdb if empty
if [ ! -f "$PGDATA/PG_VERSION" ]; then
  echo "[bootstrap] initdb $PGDATA"
  su postgres -c "$PGBIN/initdb -D $PGDATA -A trust --encoding=UTF8" >/dev/null
  # Trust auth on localhost so password drift can never break the local harness.
  cat > "$PGDATA/pg_hba.conf" <<'HBA'
local   all   all                  trust
host    all   all   127.0.0.1/32   trust
host    all   all   ::1/128        trust
HBA
  echo "listen_addresses = '127.0.0.1'" >> "$PGDATA/postgresql.conf"
  echo "port = ${PORT}" >> "$PGDATA/postgresql.conf"
fi

# 2. start if not running
if ! su postgres -c "$PGBIN/pg_ctl -D $PGDATA status" >/dev/null 2>&1; then
  echo "[bootstrap] starting postgres"
  su postgres -c "$PGBIN/pg_ctl -D $PGDATA -l $PGDATA/server.log -o '-p ${PORT}' -w start"
fi

# 3. roles
su postgres -c "psql -p ${PORT} -v ON_ERROR_STOP=1 -f /app/scripts/00_superuser.sql" >/dev/null

# 3b. database
if ! su postgres -c "psql -p ${PORT} -tAc \"select 1 from pg_database where datname='myshopedge'\"" | grep -q 1; then
  echo "[bootstrap] creating database"
  su postgres -c "createdb -p ${PORT} myshopedge -O mse_migrator"
  su postgres -c "psql -p ${PORT} -v ON_ERROR_STOP=1 -d myshopedge -f /app/scripts/01_dbsetup.sql" >/dev/null
fi

# 3c. migrations + seed (only when accounts is empty / absent)
NEED_MIGRATE=0
su postgres -c "psql -p ${PORT} -d myshopedge -tAc \"select to_regclass('public.accounts')\"" | grep -q accounts || NEED_MIGRATE=1
if [ "$NEED_MIGRATE" = "1" ]; then
  echo "[bootstrap] running migrations + seed"
  cd /app && python3 scripts/local_migrate.py
else
  COUNT=$(su postgres -c "psql -p ${PORT} -d myshopedge -tAc 'select count(*) from accounts'" | tr -d '[:space:]')
  if [ "$COUNT" = "0" ]; then
    echo "[bootstrap] accounts empty, running migrations + seed"
    cd /app && python3 scripts/local_migrate.py
  else
    echo "[bootstrap] database already seeded ($COUNT accounts), skipping"
  fi
fi

# 3d. reference rules (idempotent upserts, safe to re-run every boot)
su postgres -c "psql -p ${PORT} -d myshopedge -v ON_ERROR_STOP=1 -q -f /app/testdata/reference_rules_seed.sql" >/dev/null 2>&1 || true
su postgres -c "psql -p ${PORT} -d myshopedge -v ON_ERROR_STOP=1 -q -f /app/testdata/reference_rules_tax_seed.sql" >/dev/null 2>&1 || true

echo "[bootstrap] done"
