-- MyShopEdge v0.2 migration 0007: the daily cache and exports (Action 5).

-- daily_metrics held no basis at all, so a daily cash-basis view could not be served
-- from it. It also held no return cost or write-off, so You keep could not be computed
-- for a day without going back to the ledger.
alter table daily_metrics
  add column basis text not null default 'sales' check (basis in ('sales','cash')),
  add column return_cost_minor bigint not null default 0,
  add column write_off_minor   bigint not null default 0,
  add column you_keep_minor    bigint;

comment on column daily_metrics.you_keep_minor is
  'Null where cost coverage for the day is incomplete, mirroring the API, which returns '
  'kept: null with a reason rather than a zero.';
comment on column daily_metrics.metric_date is
  'Local date in Europe/London, matching ledger_entries.basis_day.';

drop index daily_metrics_key_idx;
create unique index daily_metrics_key_idx on daily_metrics (
  shop_id,
  coalesce(sku_id, '00000000-0000-0000-0000-000000000000'::uuid),
  metric_date,
  basis
);

-- Exports gain a basis and the transactions kind from Action 2.
alter table exports
  add column basis text not null default 'sales' check (basis in ('sales','cash'));
alter table exports drop constraint exports_kind_check;
alter table exports add constraint exports_kind_check
  check (kind in ('month_summary','ledger','accountant','transactions'));

-- Scheduled exports (MON-8).
create table export_schedules (
  id uuid primary key default gen_random_uuid(),
  shop_id uuid not null references shops(id),
  kind text not null check (kind in ('month_summary','ledger','accountant','transactions')),
  format text not null check (format in ('xlsx','csv')),
  basis text not null default 'sales' check (basis in ('sales','cash')),
  cadence text not null check (cadence in ('weekly','monthly')),
  day_of_week smallint check (day_of_week between 1 and 7),
  day_of_month smallint check (day_of_month between 1 and 28),
  active boolean not null default true,
  last_run_at timestamptz,
  created_at timestamptz not null default now(),
  check ((cadence = 'weekly'  and day_of_week  is not null and day_of_month is null)
      or (cadence = 'monthly' and day_of_month is not null and day_of_week  is null))
);
comment on column export_schedules.day_of_month is
  'Capped at 28 so a monthly schedule never skips February.';

-- Refresh feed links (MON-9). The token is stored only as a hash.
create table feed_tokens (
  id uuid primary key default gen_random_uuid(),
  shop_id uuid not null references shops(id),
  token_hash text not null unique,
  kind text not null check (kind in ('month_summary','ledger','accountant','transactions')),
  basis text not null default 'sales' check (basis in ('sales','cash')),
  created_at timestamptz not null default now(),
  last_used_at timestamptz,
  last_used_ip inet,
  revoked_at timestamptz,
  expires_at timestamptz not null default (now() + interval '90 days')
);
create index feed_tokens_shop_idx on feed_tokens (shop_id) where revoked_at is null;

alter table export_schedules enable row level security;
alter table export_schedules force  row level security;
create policy export_schedules_own on export_schedules
  using      (shop_id in (select id from shops where account_id = app_account_id()))
  with check (shop_id in (select id from shops where account_id = app_account_id()));

alter table feed_tokens enable row level security;
alter table feed_tokens force  row level security;
create policy feed_tokens_own on feed_tokens
  using      (shop_id in (select id from shops where account_id = app_account_id()))
  with check (shop_id in (select id from shops where account_id = app_account_id()));

grant select, insert, update, delete on export_schedules, feed_tokens to mse_app;
grant select on export_schedules, feed_tokens to mse_analytics;
