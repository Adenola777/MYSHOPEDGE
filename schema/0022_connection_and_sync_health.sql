-- 0022. Enough to tell a healthy connection and a healthy sync from broken ones. A29.4, A29.5.
--
-- The owner ruled on 24 September 2026 that Needs you must distinguish an expiring
-- connection, an expired one, a revoked one, a failed refresh and a missing scope, and that
-- a partial sync must be distinguishable from a successful one. It also ruled that no
-- condition may be shown without a persisted source behind it.
--
-- WHAT WAS ALREADY THERE
--
-- `tiktok_connections` held both expiries, `revoked_at` and the granted `scopes`. `sync_runs`
-- held a status per shop and domain, with `failed` and `needs_reconnect` among its values, and
-- `records_read`, `records_written` and `error`. Nothing recorded a refresh, nothing recorded
-- which scopes are required, and no sync could say it was partial.
--
-- REQUIRED SCOPES START EMPTY, DELIBERATELY
--
-- A24 records that whether `{seller.finance.info,seller.order.info}` is the minimal set "has
-- never been checked against the screens". The required list is not decided, so the column
-- defaults to empty and the missing scope condition cannot fire until someone writes the
-- decided list into it. An invented list here would raise a critical alert on every shop.
--
-- NOT YET APPLIED. Written and checked on 24 September inside a transaction that was rolled
-- back on the development branch. It reaches a branch only through scripts/migrate.py.

alter table tiktok_connections
  add column required_scopes text[] not null default '{}',
  add column refresh_attempted_at timestamptz,
  add column refresh_succeeded_at timestamptz,
  add column refresh_failure_code text,
  add column refresh_failure_reason text;

comment on column tiktok_connections.required_scopes is
  'Scopes the product needs. Empty until decided (A24, A29.4). Compared with scopes.';
comment on column tiktok_connections.refresh_failure_code is
  'TikTok''s own code from the last failed refresh, verbatim. Null once a refresh succeeds.';

alter table sync_runs drop constraint sync_runs_status_check;
alter table sync_runs add constraint sync_runs_status_check
  check (status in ('scheduled','fetching','persisting','processing','completed','partial',
                    'retry_wait','failed','needs_reconnect'));

alter table sync_runs add column records_failed integer not null default 0
  check (records_failed >= 0);
