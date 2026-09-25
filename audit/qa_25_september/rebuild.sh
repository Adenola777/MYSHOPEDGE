#!/bin/bash
# Rebuilds the local QA database from the repository's migrations and the patched seed.
set -e
S=/tmp/claude-0/-home-user-My-ShopEdge/4022bda9-b4f8-509d-a2b4-4172db8dfff3/scratchpad; R=/home/user/My-ShopEdge
P="psql -h /tmp -p 5439 -U postgres -v ON_ERROR_STOP=1 -q"
$P -c "select pg_terminate_backend(pid) from pg_stat_activity where datname='myshopedge' and pid<>pg_backend_pid()" >/dev/null
$P -c "drop database if exists myshopedge" -c "create database myshopedge"
$P -d myshopedge -f $R/schema/MyShopEdge_MVP_schema_v0.2.sql >/dev/null
$P -d myshopedge -c "create table schema_migrations (filename text primary key, checksum text not null, applied_at timestamptz not null default now(), applied_by text not null default current_user, backfilled boolean not null default false)"
$P -d myshopedge -c "insert into schema_migrations(filename,checksum,backfilled) values ('MyShopEdge_MVP_schema_v0.2.sql','$(sha256sum $R/schema/MyShopEdge_MVP_schema_v0.2.sql|cut -d' ' -f1)',true)"
for f in $R/schema/000[1-9]_*.sql; do $P -d myshopedge -c "insert into schema_migrations(filename,checksum,backfilled) values ('$(basename $f)','$(sha256sum $f|cut -d' ' -f1)',true)"; done
$P -d myshopedge -c "create schema neon_auth; create table neon_auth.users_sync (raw_json jsonb not null, id text not null, name text, email text, created_at timestamptz, updated_at timestamptz, deleted_at timestamptz)"
DATABASE_URL="postgresql://postgres@/myshopedge?host=/tmp&port=5439" $S/venv/bin/python $R/service/scripts/migrate.py | tail -1
$P -d myshopedge --single-transaction -f $S/seed_local.sql
$P -d myshopedge -tAc "select count(*), sum(amount_minor) from ledger_entries"
# Neon runs migrations as mse_migrator, so every table, view and project function belongs to it.
$P -d myshopedge -c "do \$\$ declare r record; begin
 for r in select c.relname, c.relkind from pg_class c join pg_namespace n on n.oid=c.relnamespace where n.nspname='public' and c.relkind in ('r','v') loop
  execute format('alter %s public.%I owner to mse_migrator', case r.relkind when 'v' then 'view' else 'table' end, r.relname); end loop;
 for r in select p.oid::regprocedure as sig from pg_proc p join pg_namespace n on n.oid=p.pronamespace left join pg_depend d on d.objid=p.oid and d.deptype='e' where n.nspname='public' and d.objid is null and pg_get_userbyid(p.proowner)='postgres' loop
  execute format('alter function %s owner to mse_migrator', r.sig); end loop; end \$\$"
$P -d myshopedge -tAc "select pg_get_userbyid(c.relowner), c.relkind, count(*) from pg_class c join pg_namespace n on n.oid=c.relnamespace where n.nspname='public' and c.relkind in ('r','v') group by 1,2 union all select 'fn:'||pg_get_userbyid(p.proowner),'f',count(*) from pg_proc p join pg_namespace n on n.oid=p.pronamespace left join pg_depend d on d.objid=p.oid and d.deptype='e' where n.nspname='public' and d.objid is null group by 1"
