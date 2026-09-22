-- MyShopEdge MVP schema v0.2 (PostgreSQL 15+). Document MSE-BOS-001.
-- Consolidated: the v0.1 base schema followed by the v0.2 migrations, in order.
-- Verified by loading into PostgreSQL 16 from empty and running the test harness in
-- verify_v0.2.sql. Roles: mse_owner, mse_app, mse_analytics, mse_migrator.
-- Changes from v0.1: append-only enforcement (LED-1), forced row-level security
-- (ACC-3), per-line attribution (LED-9 to LED-12), stock absorption (STK-8),
-- Europe/London day and week keys (MON-1), daily cache basis, scheduled exports
-- and feed tokens (MON-8, MON-9).
-- MyShopEdge MVP schema (PostgreSQL 15+). Document MSE-BOS-001. Draft for review.
-- Conventions: money is stored as integer minor units (pence) with a currency code;
-- ledger_entries is append-only; every shop-scoped table carries shop_id and is protected by
-- row-level security keyed on the signed-in account; no buyer personal data is stored.

create extension if not exists pgcrypto;
create extension if not exists citext;

create function app_account_id() returns uuid language sql stable as
$$ select nullif(current_setting('app.account_id', true), '')::uuid $$;

create table accounts (
  id uuid primary key default gen_random_uuid(),
  email citext not null unique,
  auth_subject text not null unique,
  display_name text,
  locale text not null default 'en-GB',
  timezone text not null default 'Europe/London',
  status text not null default 'active' check (status in ('active','suspended','deleted')),
  created_at timestamptz not null default now(),
  deleted_at timestamptz
);

create table shops (
  id uuid primary key default gen_random_uuid(),
  account_id uuid not null references accounts(id),
  platform text not null default 'tiktok_shop',
  tiktok_shop_id text not null,
  shop_name text,
  region text not null default 'GB',
  currency char(3) not null default 'GBP',
  connection_status text not null default 'pending'
    check (connection_status in ('pending','connected','needs_reconnect','disconnected')),
  first_synced_at timestamptz,
  last_synced_at timestamptz,
  created_at timestamptz not null default now(),
  unique (platform, tiktok_shop_id)
);
create index shops_account_idx on shops (account_id);

create table tiktok_connections (
  shop_id uuid primary key references shops(id),
  access_token_enc bytea not null,
  refresh_token_enc bytea not null,
  shop_cipher_enc bytea,
  access_expires_at timestamptz,
  refresh_expires_at timestamptz,
  scopes text[] not null default '{}',
  key_version integer not null default 1,
  authorised_at timestamptz not null default now(),
  revoked_at timestamptz
);

create table sync_runs (
  id uuid primary key default gen_random_uuid(),
  shop_id uuid not null references shops(id),
  kind text not null check (kind in ('backfill','incremental','webhook','reconcile')),
  domain text not null check (domain in ('orders','products','inventory','finance','returns')),
  status text not null default 'scheduled'
    check (status in ('scheduled','fetching','persisting','processing','completed','retry_wait','failed','needs_reconnect')),
  cursor jsonb,
  attempt integer not null default 0,
  started_at timestamptz,
  finished_at timestamptz,
  records_read integer not null default 0,
  records_written integer not null default 0,
  error jsonb,
  created_at timestamptz not null default now()
);
create index sync_runs_shop_idx on sync_runs (shop_id, domain, created_at desc);

create table raw_events (
  id uuid primary key default gen_random_uuid(),
  shop_id uuid not null references shops(id),
  source text not null check (source in ('webhook','poll')),
  domain text not null,
  external_id text,
  idempotency_key text not null,
  payload jsonb not null,
  payload_hash text,
  received_at timestamptz not null default now(),
  processed_at timestamptz,
  status text not null default 'received' check (status in ('received','processed','failed','ignored')),
  unique (shop_id, idempotency_key)
);
create index raw_events_status_idx on raw_events (shop_id, status, received_at);

create table products (
  id uuid primary key default gen_random_uuid(),
  shop_id uuid not null references shops(id),
  tiktok_product_id text not null,
  title text,
  status text,
  first_seen_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (shop_id, tiktok_product_id)
);

create table skus (
  id uuid primary key default gen_random_uuid(),
  shop_id uuid not null references shops(id),
  product_id uuid not null references products(id),
  tiktok_sku_id text not null,
  seller_sku text,
  variant_label text,
  updated_at timestamptz not null default now(),
  unique (shop_id, tiktok_sku_id)
);
create index skus_seller_sku_idx on skus (shop_id, seller_sku);

create table cost_uploads (
  id uuid primary key default gen_random_uuid(),
  shop_id uuid not null references shops(id),
  filename text not null,
  storage_key text not null,
  status text not null default 'uploaded' check (status in ('uploaded','mapped','confirmed','applied','failed')),
  column_mapping jsonb,
  rows_total integer,
  rows_matched integer,
  rows_unmatched integer,
  rows_duplicate integer,
  confirmed_at timestamptz,
  created_by uuid references accounts(id),
  created_at timestamptz not null default now()
);

create table product_costs (
  id uuid primary key default gen_random_uuid(),
  shop_id uuid not null references shops(id),
  sku_id uuid not null references skus(id),
  cost_minor bigint not null check (cost_minor >= 0),
  packing_minor bigint check (packing_minor >= 0),
  postage_minor bigint check (postage_minor >= 0),
  currency char(3) not null default 'GBP',
  source text not null check (source in ('upload','manual')),
  cost_upload_id uuid references cost_uploads(id),
  effective_from date not null default current_date,
  superseded_at timestamptz,
  created_by uuid references accounts(id),
  created_at timestamptz not null default now()
);
create unique index product_costs_current_idx on product_costs (sku_id) where superseded_at is null;

create table orders (
  id uuid primary key default gen_random_uuid(),
  shop_id uuid not null references shops(id),
  tiktok_order_id text not null,
  status text not null,
  order_created_at timestamptz not null,
  delivered_at timestamptz,
  cancelled_at timestamptz,
  currency char(3) not null default 'GBP',
  gross_minor bigint not null,
  sales_channel text not null default 'tiktok_shop',
  last_event_at timestamptz,
  created_at timestamptz not null default now(),
  unique (shop_id, tiktok_order_id)
);
create index orders_created_idx on orders (shop_id, order_created_at);

create table order_lines (
  id uuid primary key default gen_random_uuid(),
  shop_id uuid not null references shops(id),
  order_id uuid not null references orders(id) on delete cascade,
  sku_id uuid references skus(id),
  tiktok_line_id text not null,
  quantity integer not null check (quantity > 0),
  unit_price_minor bigint not null,
  seller_discount_minor bigint not null default 0,
  unique (order_id, tiktok_line_id)
);

create table settlements (
  id uuid primary key default gen_random_uuid(),
  shop_id uuid not null references shops(id),
  tiktok_statement_id text not null,
  period_start date,
  period_end date,
  statement_amount_minor bigint not null,
  currency char(3) not null default 'GBP',
  payment_status text,
  tiktok_payment_id text,
  payout_reference text,
  paid_at timestamptz,
  created_at timestamptz not null default now(),
  unique (shop_id, tiktok_statement_id)
);

create table order_settlements (
  order_id uuid primary key references orders(id) on delete cascade,
  shop_id uuid not null references shops(id),
  status text not null check (status in ('waiting_delivery','waiting_return_refund','delivered_awaiting_settlement','settled')),
  est_settlement_date date,
  settlement_id uuid references settlements(id),
  updated_at timestamptz not null default now()
);
create index order_settlements_status_idx on order_settlements (shop_id, status, est_settlement_date);

create table returns (
  id uuid primary key default gen_random_uuid(),
  shop_id uuid not null references shops(id),
  order_id uuid not null references orders(id),
  tiktok_return_id text not null,
  kind text not null check (kind in ('cancellation','refund_only','return_refund')),
  status text not null,
  requested_at timestamptz,
  refund_completed_at timestamptz,
  refund_minor bigint,
  reason_code text,
  created_at timestamptz not null default now(),
  unique (shop_id, tiktok_return_id)
);

create table return_items (
  id uuid primary key default gen_random_uuid(),
  shop_id uuid not null references shops(id),
  return_id uuid not null references returns(id) on delete cascade,
  sku_id uuid references skus(id),
  quantity integer not null check (quantity > 0),
  seller_check_status text not null default 'pending'
    check (seller_check_status in ('pending','resellable','unsellable','not_applicable')),
  checked_at timestamptz,
  checked_by uuid references accounts(id),
  return_postage_minor bigint check (return_postage_minor >= 0),
  created_at timestamptz not null default now()
);

create table ledger_entries (
  id uuid primary key default gen_random_uuid(),
  shop_id uuid not null references shops(id),
  order_id uuid references orders(id),
  return_id uuid references returns(id),
  settlement_id uuid references settlements(id),
  entry_type text not null check (entry_type in ('sale','platform_deduction','refund','payout','return_cost','write_off','adjustment')),
  category text,
  amount_minor bigint not null,
  currency char(3) not null default 'GBP',
  occurred_at timestamptz not null,
  basis_month date not null,
  settlement_month date,
  source text not null check (source in ('tiktok','seller','system')),
  source_ref text,
  reverses_entry_id uuid references ledger_entries(id),
  reason text,
  created_at timestamptz not null default now()
);
create unique index ledger_idempotency_idx on ledger_entries (shop_id, source, source_ref, entry_type, coalesce(category, ''))
  where source_ref is not null;
create index ledger_basis_idx on ledger_entries (shop_id, basis_month);
create index ledger_order_idx on ledger_entries (order_id);

create table stock_positions (
  sku_id uuid primary key references skus(id),
  shop_id uuid not null references shops(id),
  tiktok_stock integer not null default 0,
  adjusted_delta integer not null default 0,
  sold_not_posted integer not null default 0,
  coming_back integer not null default 0,
  written_off integer not null default 0,
  on_shelf integer generated always as (tiktok_stock + adjusted_delta) stored,
  as_of timestamptz not null default now()
);

create table stock_movements (
  id uuid primary key default gen_random_uuid(),
  shop_id uuid not null references shops(id),
  sku_id uuid not null references skus(id),
  movement_type text not null check (movement_type in ('sale_reserved','posted','cancelled','return_resellable','write_off','manual_adjustment')),
  quantity integer not null,
  occurred_at timestamptz not null default now(),
  order_id uuid references orders(id),
  return_id uuid references returns(id),
  return_item_id uuid references return_items(id),
  reason text,
  created_by uuid references accounts(id),
  created_at timestamptz not null default now(),
  check (movement_type <> 'manual_adjustment' or reason is not null)
);
create unique index stock_movements_return_once_idx on stock_movements (return_item_id, movement_type)
  where return_item_id is not null;
create index stock_movements_sku_idx on stock_movements (sku_id, occurred_at);

create table discrepancies (
  id uuid primary key default gen_random_uuid(),
  shop_id uuid not null references shops(id),
  kind text not null check (kind in ('product_code','order_reference','transaction_reference','amount','return_unmatched','duplicate')),
  entity_type text not null,
  entity_id uuid,
  field text,
  tiktok_value text,
  seller_value text,
  applied_value text,
  status text not null default 'open' check (status in ('open','resolved')),
  resolution text check (resolution in ('accepted_tiktok','corrected_seller','explained')),
  note text,
  effect jsonb,
  opened_at timestamptz not null default now(),
  resolved_at timestamptz,
  resolved_by uuid references accounts(id),
  check (status = 'open' or resolution is not null)
);
create index discrepancies_open_idx on discrepancies (shop_id, status);

create table notifications (
  id uuid primary key default gen_random_uuid(),
  account_id uuid not null references accounts(id),
  shop_id uuid references shops(id),
  type text not null,
  severity text not null default 'info' check (severity in ('info','warning','critical')),
  title text not null,
  body text,
  entity_type text,
  entity_id uuid,
  status text not null default 'unread' check (status in ('unread','read','done')),
  dedupe_key text,
  created_at timestamptz not null default now(),
  unique (account_id, dedupe_key)
);

create table alert_settings (
  shop_id uuid primary key references shops(id),
  low_stock_days integer not null default 14 check (low_stock_days > 0),
  coming_back_days integer not null default 7 check (coming_back_days > 0),
  updated_at timestamptz not null default now()
);

create table tax_profiles (
  account_id uuid primary key references accounts(id),
  business_structure text check (business_structure in ('sole_trader','company','not_sure')),
  vat_registered boolean not null default false,
  vat_registered_from date,
  prior_year_gross jsonb not null default '{}',
  updated_at timestamptz not null default now()
);

create table other_channel_sales (
  id uuid primary key default gen_random_uuid(),
  shop_id uuid not null references shops(id),
  channel text not null,
  month date not null check (extract(day from month) = 1),
  gross_minor bigint not null check (gross_minor >= 0),
  entered_at timestamptz not null default now(),
  unique (shop_id, channel, month)
);

create table reference_rules (
  id uuid primary key default gen_random_uuid(),
  rule_set text not null check (rule_set in ('vat','income_tax','national_insurance','mtd')),
  rule_key text not null,
  value jsonb not null,
  effective_from date not null,
  effective_to date,
  source_url text,
  reviewed_by text,
  reviewed_at date,
  unique (rule_set, rule_key, effective_from)
);

create table change_log (
  id uuid primary key default gen_random_uuid(),
  shop_id uuid not null references shops(id),
  entity_type text not null,
  entity_id uuid,
  changed_at timestamptz not null default now(),
  reason_code text not null,
  old_value jsonb,
  new_value jsonb,
  source text not null check (source in ('tiktok','seller','system'))
);
create index change_log_entity_idx on change_log (shop_id, entity_type, entity_id);

create table audit_log (
  id uuid primary key default gen_random_uuid(),
  account_id uuid references accounts(id),
  actor text not null,
  action text not null,
  entity_type text,
  entity_id uuid,
  occurred_at timestamptz not null default now()
);

create table exports (
  id uuid primary key default gen_random_uuid(),
  shop_id uuid not null references shops(id),
  kind text not null check (kind in ('month_summary','ledger','accountant')),
  period_start date,
  period_end date,
  format text not null check (format in ('xlsx','csv')),
  status text not null default 'queued' check (status in ('queued','ready','failed','expired')),
  storage_key text,
  created_at timestamptz not null default now(),
  expires_at timestamptz
);

create table daily_metrics (
  id uuid primary key default gen_random_uuid(),
  shop_id uuid not null references shops(id),
  sku_id uuid references skus(id),
  metric_date date not null,
  orders integer not null default 0,
  units integer not null default 0,
  gross_minor bigint not null default 0,
  refunds_minor bigint not null default 0,
  deductions_minor bigint not null default 0,
  net_proceeds_minor bigint not null default 0,
  product_cost_minor bigint,
  contribution_minor bigint,
  cost_coverage_units integer not null default 0,
  returns_units integer not null default 0,
  computed_at timestamptz not null default now()
);
create unique index daily_metrics_key_idx on daily_metrics (shop_id, coalesce(sku_id, '00000000-0000-0000-0000-000000000000'::uuid), metric_date);

create table product_events (
  id uuid primary key default gen_random_uuid(),
  account_id uuid references accounts(id),
  name text not null,
  props jsonb not null default '{}',
  occurred_at timestamptz not null default now()
);

-- Row-level security
alter table accounts enable row level security;
create policy accounts_own on accounts using (id = app_account_id());
alter table shops enable row level security;
create policy shops_own on shops using (account_id = app_account_id());
alter table tiktok_connections enable row level security;
create policy tiktok_connections_own on tiktok_connections using (shop_id in (select id from shops where account_id = app_account_id()));
alter table sync_runs enable row level security;
create policy sync_runs_own on sync_runs using (shop_id in (select id from shops where account_id = app_account_id()));
alter table raw_events enable row level security;
create policy raw_events_own on raw_events using (shop_id in (select id from shops where account_id = app_account_id()));
alter table products enable row level security;
create policy products_own on products using (shop_id in (select id from shops where account_id = app_account_id()));
alter table skus enable row level security;
create policy skus_own on skus using (shop_id in (select id from shops where account_id = app_account_id()));
alter table cost_uploads enable row level security;
create policy cost_uploads_own on cost_uploads using (shop_id in (select id from shops where account_id = app_account_id()));
alter table product_costs enable row level security;
create policy product_costs_own on product_costs using (shop_id in (select id from shops where account_id = app_account_id()));
alter table orders enable row level security;
create policy orders_own on orders using (shop_id in (select id from shops where account_id = app_account_id()));
alter table order_lines enable row level security;
create policy order_lines_own on order_lines using (shop_id in (select id from shops where account_id = app_account_id()));
alter table settlements enable row level security;
create policy settlements_own on settlements using (shop_id in (select id from shops where account_id = app_account_id()));
alter table order_settlements enable row level security;
create policy order_settlements_own on order_settlements using (shop_id in (select id from shops where account_id = app_account_id()));
alter table returns enable row level security;
create policy returns_own on returns using (shop_id in (select id from shops where account_id = app_account_id()));
alter table return_items enable row level security;
create policy return_items_own on return_items using (shop_id in (select id from shops where account_id = app_account_id()));
alter table ledger_entries enable row level security;
create policy ledger_entries_own on ledger_entries using (shop_id in (select id from shops where account_id = app_account_id()));
alter table stock_positions enable row level security;
create policy stock_positions_own on stock_positions using (shop_id in (select id from shops where account_id = app_account_id()));
alter table stock_movements enable row level security;
create policy stock_movements_own on stock_movements using (shop_id in (select id from shops where account_id = app_account_id()));
alter table discrepancies enable row level security;
create policy discrepancies_own on discrepancies using (shop_id in (select id from shops where account_id = app_account_id()));
alter table notifications enable row level security;
create policy notifications_own on notifications using (account_id = app_account_id());
alter table alert_settings enable row level security;
create policy alert_settings_own on alert_settings using (shop_id in (select id from shops where account_id = app_account_id()));
alter table tax_profiles enable row level security;
create policy tax_profiles_own on tax_profiles using (account_id = app_account_id());
alter table other_channel_sales enable row level security;
create policy other_channel_sales_own on other_channel_sales using (shop_id in (select id from shops where account_id = app_account_id()));
alter table change_log enable row level security;
create policy change_log_own on change_log using (shop_id in (select id from shops where account_id = app_account_id()));
alter table audit_log enable row level security;
create policy audit_log_own on audit_log using (account_id = app_account_id());
alter table exports enable row level security;
create policy exports_own on exports using (shop_id in (select id from shops where account_id = app_account_id()));
alter table daily_metrics enable row level security;
create policy daily_metrics_own on daily_metrics using (shop_id in (select id from shops where account_id = app_account_id()));
alter table product_events enable row level security;
create policy product_events_own on product_events using (account_id = app_account_id());

-- ============================================================================
-- v0.2 migrations
-- ============================================================================

-- ---------- 0001_roles_and_grants.sql
-- MyShopEdge v0.2 migration 0001: roles and grants.
-- Closes the gap where the pack names a restricted database role (LED-1, TC-LED-04)
-- without defining one anywhere.

-- Three roles, and no others. The application uses exactly one of them.

-- Roles are cluster-wide, not per database, so this migration is idempotent and is run
-- once per cluster. Running it again against a second database must not fail.
do $$
begin
  -- Owns every object. No login. Migrations are run by a role granted this one.
  if not exists (select 1 from pg_roles where rolname = 'mse_owner') then
    create role mse_owner nologin;
  end if;
  -- The only role the application connects as. Subject to row-level security.
  -- It must never own an object and must never be granted BYPASSRLS.
  if not exists (select 1 from pg_roles where rolname = 'mse_app') then
    create role mse_app login nobypassrls;
  end if;
  -- Read-only, for analysis. Subject to row-level security.
  if not exists (select 1 from pg_roles where rolname = 'mse_analytics') then
    create role mse_analytics login nobypassrls;
  end if;
  -- Runs migrations. Granted ownership and allowed past row-level security so that
  -- backfills can reach every shop. Never used by the application or by a person.
  if not exists (select 1 from pg_roles where rolname = 'mse_migrator') then
    create role mse_migrator login bypassrls;
  end if;
end $$;
grant mse_owner to mse_migrator;

-- Objects belong to the owner, not to whoever happened to run the script.
alter schema public owner to mse_owner;

-- Connection and usage.
grant usage on schema public to mse_app, mse_analytics;
revoke all on schema public from public;

-- The application reads and writes.
grant select, insert, update, delete on all tables in schema public to mse_app;
grant usage, select on all sequences in schema public to mse_app;

-- Analysis reads only.
grant select on all tables in schema public to mse_analytics;

-- Anything added later inherits the same grants.
alter default privileges for role mse_owner in schema public
  grant select, insert, update, delete on tables to mse_app;
alter default privileges for role mse_owner in schema public
  grant select on tables to mse_analytics;
alter default privileges for role mse_owner in schema public
  grant usage, select on sequences to mse_app;

-- The account identity is set per transaction, never per session, so a leaked
-- connection from a pool cannot carry one seller's identity into another's request.
comment on function app_account_id() is
  'Reads app.account_id. The application must set it with set_config(''app.account_id'', $1, true), '
  'where true makes the setting local to the transaction. A session-level setting is a defect.';

-- reference_rules is deliberately not tenant-scoped. It holds the shared tax thresholds,
-- allowances, rates and dates that TAX-6 requires, with their correct-as-at dates, and
-- every seller reads the same rows. It therefore carries no row-level security policy.
-- It must still be read-only to the application: a rule change is a deployment, made by
-- the migrator, not something a seller's session can reach.
revoke insert, update, delete, truncate on reference_rules from mse_app;
comment on table reference_rules is
  'Shared reference data (TAX-6). No row-level security by design, because every seller '
  'reads the same rules. Read-only to mse_app; changed only by mse_migrator.';

-- ---------- 0002_append_only.sql
-- MyShopEdge v0.2 migration 0002: append-only ledger and logs.
-- LED-1 requires that no ledger row can be updated or deleted by the application.
-- v0.1 stated the rule and enforced nothing. Two layers now enforce it.

-- Layer one: privileges. The application cannot ask for an update or a delete.
revoke update, delete, truncate on ledger_entries from mse_app;
revoke update, delete, truncate on change_log    from mse_app;
revoke update, delete, truncate on audit_log     from mse_app;

-- Layer two: a trigger, which holds whatever role is connected, including the owner
-- and the migrator. Maintenance that genuinely must rewrite history sets a local
-- flag, which is visible in the logs and cannot be set by accident.
create or replace function enforce_append_only() returns trigger
language plpgsql as $$
begin
  if coalesce(current_setting('app.allow_ledger_maintenance', true), 'off') = 'on' then
    return case tg_op when 'DELETE' then old else new end;
  end if;
  raise exception
    '% is append-only: % is not permitted (LED-1). Post a correcting adjustment entry instead.',
    tg_table_name, tg_op
    using errcode = '42501';
end $$;

create or replace function enforce_append_only_stmt() returns trigger
language plpgsql as $$
begin
  if coalesce(current_setting('app.allow_ledger_maintenance', true), 'off') = 'on' then
    return null;
  end if;
  raise exception '% is append-only: TRUNCATE is not permitted (LED-1).', tg_table_name
    using errcode = '42501';
end $$;

create trigger ledger_entries_no_update before update on ledger_entries
  for each row execute function enforce_append_only();
create trigger ledger_entries_no_delete before delete on ledger_entries
  for each row execute function enforce_append_only();
create trigger ledger_entries_no_truncate before truncate on ledger_entries
  for each statement execute function enforce_append_only_stmt();

create trigger change_log_no_update before update on change_log
  for each row execute function enforce_append_only();
create trigger change_log_no_delete before delete on change_log
  for each row execute function enforce_append_only();

create trigger audit_log_no_update before update on audit_log
  for each row execute function enforce_append_only();
create trigger audit_log_no_delete before delete on audit_log
  for each row execute function enforce_append_only();

-- Retention still works. Section 4.6 purges raw_events and expired exports, neither of
-- which is append-only. Ledger retention, where it is ever needed, deletes the whole
-- account under ACC-4 rather than individual rows.

-- ---------- 0003_force_row_level_security.sql
-- MyShopEdge v0.2 migration 0003: force row-level security.
-- ENABLE ROW LEVEL SECURITY is bypassed by the table owner. ACC-3 depends on the
-- policies holding for every role, so every shop-scoped table is forced.

do $$
declare t text;
begin
  foreach t in array array[
    'accounts','shops','tiktok_connections','sync_runs','raw_events','products','skus',
    'cost_uploads','product_costs','orders','order_lines','settlements','order_settlements',
    'returns','return_items','ledger_entries','stock_positions','stock_movements',
    'discrepancies','notifications','alert_settings','tax_profiles','other_channel_sales',
    'change_log','audit_log','exports','daily_metrics','product_events'
  ]
  loop
    execute format('alter table %I force row level security', t);
  end loop;
end $$;

-- The existing policies are declared FOR ALL with a USING clause and no WITH CHECK.
-- PostgreSQL applies USING as WITH CHECK in that case, so an insert for another
-- seller's shop is already refused. The WITH CHECK is written out anyway, so that a
-- later edit to one clause cannot silently open the other.

alter policy ledger_entries_own on ledger_entries
  using      (shop_id in (select id from shops where account_id = app_account_id()))
  with check (shop_id in (select id from shops where account_id = app_account_id()));

alter policy orders_own on orders
  using      (shop_id in (select id from shops where account_id = app_account_id()))
  with check (shop_id in (select id from shops where account_id = app_account_id()));

alter policy order_lines_own on order_lines
  using      (shop_id in (select id from shops where account_id = app_account_id()))
  with check (shop_id in (select id from shops where account_id = app_account_id()));

alter policy stock_positions_own on stock_positions
  using      (shop_id in (select id from shops where account_id = app_account_id()))
  with check (shop_id in (select id from shops where account_id = app_account_id()));

alter policy exports_own on exports
  using      (shop_id in (select id from shops where account_id = app_account_id()))
  with check (shop_id in (select id from shops where account_id = app_account_id()));

-- A session with no app.account_id set reads nothing, because app_account_id() returns
-- null and every policy compares against it. Failing closed is the intended behaviour.

-- ---------- 0004_ledger_line_attribution.sql
-- MyShopEdge v0.2 migration 0004: per-line attribution on the ledger (Action 2).
-- Supports LED-9 to LED-12 and the product transactions grid.

alter table ledger_entries
  add column order_line_id uuid references order_lines(id),
  add column sku_id        uuid references skus(id),
  add column attribution   text not null default 'none'
    check (attribution in ('direct','allocated','none'));

create index ledger_sku_basis_idx on ledger_entries (shop_id, sku_id, basis_month);
create index ledger_line_idx      on ledger_entries (shop_id, order_line_id);

-- The idempotency index must include the line. One order-level deduction now posts one
-- entry per line, and every one of those entries carries the same TikTok source_ref, so
-- the v0.1 index would reject the second line.
drop index ledger_idempotency_idx;
create unique index ledger_idempotency_idx on ledger_entries
  (shop_id, source, source_ref, entry_type, coalesce(category, ''),
   coalesce(order_line_id, '00000000-0000-0000-0000-000000000000'::uuid))
  where source_ref is not null;

-- Added as not valid so that the backfill can run against existing rows first.
alter table ledger_entries
  add constraint ledger_attribution_chk check (
    (entry_type = 'payout' and order_line_id is null and attribution = 'none')
    or (entry_type <> 'payout' and order_line_id is not null
        and attribution in ('direct','allocated'))
  ) not valid;

-- Step 1 of the backfill: single-line orders attribute directly.
-- This touches existing append-only rows once, deliberately, so it sets the maintenance
-- flag. The flag is local to the transaction and mse_app cannot use it: the privilege
-- layer refuses the update before the trigger is reached.
select set_config('app.allow_ledger_maintenance', 'on', true);

update ledger_entries le
set order_line_id = ol.id,
    sku_id        = ol.sku_id,
    attribution   = 'direct'
from order_lines ol
where ol.order_id = le.order_id
  and le.entry_type <> 'payout'
  and le.order_line_id is null
  and (select count(*) from order_lines x where x.order_id = le.order_id) = 1;

select set_config('app.allow_ledger_maintenance', 'off', true);

-- Step 2, the multi-line allocation, runs in the application under LED-10 rather than
-- in SQL, so that one implementation of the rule is used for both backfill and live
-- posting. Step 3 validates the constraint once step 2 reports zero remaining rows:
--   alter table ledger_entries validate constraint ledger_attribution_chk;

-- ---------- 0005_stock_absorption.sql
-- MyShopEdge v0.2 migration 0005: stock absorption (Action 4, STK-8).
-- Stops a returned unit being counted twice when the seller also restores it in TikTok.

-- The v0.1 column is movement_type, and its existing check already enforces STK-4's
-- rule that a manual adjustment carries a reason. Only the new kind is added.
alter table stock_movements drop constraint stock_movements_movement_type_check;
alter table stock_movements add constraint stock_movements_movement_type_check
  check (movement_type = any (array[
    'sale_reserved','posted','cancelled','return_resellable','write_off',
    'manual_adjustment','adjustment_absorbed']));

comment on constraint stock_movements_movement_type_check on stock_movements is
  'adjustment_absorbed records STK-8: an unexplained rise in TikTok stock taken out of '
  'the seller adjustment so the same unit is not counted twice. quantity is the number '
  'of units absorbed and on_shelf does not move.';

-- The tolerance above which a rise is treated as a restock rather than a duplicate.
alter table alert_settings
  add column absorption_tolerance_units integer not null default 20
    check (absorption_tolerance_units between 0 and 1000);

comment on column alert_settings.absorption_tolerance_units is
  'STK-8. An unexplained rise in TikTok stock above this many units is not absorbed. '
  'It raises a discrepancy under DSC-1 instead, because absorbing a large figure '
  'silently would do more damage than the duplicate it prevents.';

-- ---------- 0006_ledger_day_week_keys.sql
-- MyShopEdge v0.2 migration 0006: day and week keys (Action 5).
-- Every date key is derived in Europe/London. Deriving in UTC puts a sale at 23:30 on
-- 30 June 2026 into June, when in London it is 00:30 on 1 July. That is the difference
-- between a correct and an incorrect VAT return.

alter table ledger_entries
  add column basis_day date generated always as
    (((occurred_at at time zone 'Europe/London')::date)) stored,
  add column basis_week date generated always as
    ((date_trunc('week', (occurred_at at time zone 'Europe/London'))::date)) stored;

create index ledger_basis_day_idx  on ledger_entries (shop_id, basis_day);
create index ledger_basis_week_idx on ledger_entries (shop_id, basis_week);

comment on column ledger_entries.basis_day is
  'Local date in Europe/London. date_trunc(''week'', ...) starts on Monday, which is the '
  'British convention and matches ISO 8601.';

-- Check, do not move. basis_month was written without a stated timezone. Any row whose
-- month changes under the corrected derivation is reported, because a month already
-- exported to an accountant must not shift without the seller being told.
create view ledger_basis_month_mismatch as
select id, shop_id, order_id, occurred_at, basis_month,
       date_trunc('month', (occurred_at at time zone 'Europe/London'))::date as london_month
from ledger_entries
where basis_month <> date_trunc('month', (occurred_at at time zone 'Europe/London'))::date;

comment on view ledger_basis_month_mismatch is
  'Migration check for TC-LED-21. Must be empty before v0.2 is released. Any row here is '
  'reported to the seller and corrected by a dated adjustment, never by an in-place update.';

-- ---------- 0007_daily_metrics_and_exports.sql
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

-- ---------- 0008_terminology_categories.sql
-- MyShopEdge v0.2 migration 0008: ledger categories follow the terminology standard.
-- Every TikTok fee is named as TikTok names it. Nothing is merged, and there is no
-- silent "other" bucket.

alter table ledger_entries drop constraint if exists ledger_entries_category_check;
alter table ledger_entries add constraint ledger_entries_category_check check (
  category is null or category in (
    -- money in
    'gross_sales', 'seller_discount', 'refund',
    -- TikTok fees, each named as TikTok names it
    'platform_commission', 'affiliate_commission', 'transaction_fee',
    'smart_promotions_fee', 'shipping_fee', 'return_handling_fee',
    'fbt_operations_fee', 'fbt_shipping_fee', 'fbt_storage_fee',
    -- a TikTok fee type the system does not recognise. Carried at full value and
    -- raised as a discrepancy under DSC-1. Never a silent bucket.
    'unmapped_fee',
    -- seller costs and returns
    'cost_of_goods_sold', 'seller_shipping', 'return_shipping', 'stock_written_off',
    -- settlement
    'settlement'
  )
);

alter table ledger_entries add column tiktok_fee_type text;
comment on column ledger_entries.tiktok_fee_type is
  'The fee type string exactly as TikTok supplied it, kept verbatim so a category '
  'mapping can be audited and an unmapped_fee investigated without a re-sync. The '
  'literal settlement labels are still to be confirmed in the integration spike.';

create index ledger_unmapped_idx on ledger_entries (shop_id, occurred_at)
  where category = 'unmapped_fee';
comment on index ledger_unmapped_idx is
  'CLR-4. Supports the nightly sweep that raises a discrepancy for every unmapped fee.';

-- ---------- 0009_identifiers_and_reconciliation.sql
-- MyShopEdge v0.2 migration 0009: TikTok identifiers and reconciliation.
--
-- The order number was already held on orders.tiktok_order_id. The invoice number was
-- not held at all: section 3.5 of the API Integration document kept it "in the raw
-- payload", and section 4.6 purges raw_events 90 days after processing. A seller
-- reclaiming input VAT on TikTok's fees needs those invoice numbers for six years.
--
-- This migration promotes every reconciliation identifier to a first-class column,
-- adds the invoice record itself, and takes invoice data out of the 90-day purge.

-- ---------------------------------------------------------------- invoices
create table tiktok_invoices (
  id uuid primary key default gen_random_uuid(),
  shop_id uuid not null references shops(id),
  tiktok_invoice_number text not null,
  invoice_type text not null,               -- TikTok's own label, kept verbatim
  issued_on date not null,
  period_start date,
  period_end date,
  net_minor bigint not null,
  vat_minor bigint not null default 0,
  gross_minor bigint not null,
  vat_rate_bp integer,                      -- basis points, so 20% is 2000
  currency char(3) not null default 'GBP',
  supplier_vat_number text,                 -- TikTok's VAT number, from the invoice
  buyer_vat_number text,                    -- the seller's, where shown
  document_url text,                        -- TikTok's link, which may expire
  document_fetched_at timestamptz,
  settlement_id uuid references settlements(id),
  source_ref text,
  created_at timestamptz not null default now(),
  unique (shop_id, tiktok_invoice_number),
  check (gross_minor = net_minor + vat_minor)
);
create index tiktok_invoices_issued_idx on tiktok_invoices (shop_id, issued_on);
create index tiktok_invoices_settlement_idx on tiktok_invoices (settlement_id);

comment on table tiktok_invoices is
  'TikTok fee invoices, held for VAT. The check constraint makes the arithmetic on the '
  'invoice self-verifying: gross must equal net plus VAT, every time.';
comment on column tiktok_invoices.invoice_type is
  'TikTok''s own label, for example Platform Service Fee. Kept verbatim rather than '
  'mapped, so a new invoice type cannot be silently absorbed.';
comment on column tiktok_invoices.document_url is
  'TikTok''s link expires. document_fetched_at records when a copy was taken, because '
  'the seller needs the document itself, not a dead link, at an HMRC enquiry.';

-- ---------------------------------------------------------------- the ledger carries both
alter table ledger_entries
  add column tiktok_invoice_number text,
  add column invoice_id uuid references tiktok_invoices(id);
create index ledger_invoice_idx on ledger_entries (shop_id, tiktok_invoice_number);
comment on column ledger_entries.tiktok_invoice_number is
  'The invoice the fee was billed on. Kept as text as well as a foreign key, so a fee '
  'that arrives before its invoice is still reconcilable when the invoice lands.';

-- ---------------------------------------------------------------- settlements
alter table settlements
  add column tiktok_invoice_number text,
  add column settlement_reference text;
comment on column settlements.settlement_reference is
  'The reference the seller will see on their bank statement, which is what makes a '
  'payout reconcilable against the bank rather than only against TikTok.';

-- ---------------------------------------------------------------- returns
alter table returns
  add column tiktok_credit_note_number text,
  add column tiktok_refund_reference text;
comment on column returns.tiktok_credit_note_number is
  'Where TikTok issues a credit note reversing a fee on a refunded order. Needed to '
  'reconcile the fee reversal, which is otherwise invisible against the original fee.';

-- ---------------------------------------------------------------- retention
-- Invoice data is deliberately excluded from the 90-day raw_events purge. UK VAT
-- records are kept for six years, so these rows outlive everything else in the pack
-- except the account itself.
comment on table tiktok_invoices is
  'TikTok fee invoices, held for VAT. Retained for 6 years from the end of the VAT '
  'period, not 90 days. Deleted only with the account under ACC-4, and the deletion '
  'record notes that the seller was told to take their invoices first.';

-- ---------------------------------------------------------------- reconciliation views
-- Payment reconciliation: a payout, the orders it settled, and the invoices billed
-- against it, in one place.
create view settlement_reconciliation as
select s.id                                as settlement_id,
       s.shop_id,
       s.tiktok_statement_id,
       s.tiktok_payment_id,
       s.settlement_reference,
       s.paid_at,
       s.statement_amount_minor,
       (select count(*) from order_settlements os where os.settlement_id = s.id)
                                           as orders_settled,
       coalesce((select sum(le.amount_minor) from ledger_entries le
                 where le.settlement_id = s.id and le.entry_type <> 'payout'), 0)
                                           as net_proceeds_minor,
       coalesce((select sum(i.gross_minor) from tiktok_invoices i
                 where i.settlement_id = s.id), 0)
                                           as invoiced_gross_minor,
       s.statement_amount_minor
         - coalesce((select sum(le.amount_minor) from ledger_entries le
                     where le.settlement_id = s.id and le.entry_type <> 'payout'), 0)
                                           as unexplained_minor
from settlements s;

comment on view settlement_reconciliation is
  'REC-1. unexplained_minor must be zero. Anything else is a payout that does not '
  'agree with the orders behind it, and raises a discrepancy under DSC-1.';

-- Returns reconciliation: the return, the refund, the fee reversal and the stock
-- movement, side by side, so a return that moved money but not stock is visible.
create view return_reconciliation as
select r.id                                 as return_id,
       r.shop_id,
       r.tiktok_return_id,
       o.tiktok_order_id,
       r.kind,
       r.tiktok_credit_note_number,
       r.refund_completed_at,
       r.refund_minor,
       coalesce((select sum(le.amount_minor) from ledger_entries le
                 where le.return_id = r.id and le.entry_type = 'refund'), 0)
                                            as refund_posted_minor,
       coalesce((select sum(le.amount_minor) from ledger_entries le
                 where le.return_id = r.id and le.entry_type = 'return_cost'), 0)
                                            as return_cost_minor,
       coalesce((select sum(le.amount_minor) from ledger_entries le
                 where le.return_id = r.id and le.entry_type = 'write_off'), 0)
                                            as write_off_minor,
       (select count(*) from return_items ri
        where ri.return_id = r.id and ri.seller_check_status = 'pending')
                                            as items_awaiting_check,
       (select count(*) from stock_movements sm
        where sm.return_id = r.id)          as stock_movements
from returns r
join orders o on o.id = r.order_id;

comment on view return_reconciliation is
  'REC-2. A refund_only return must show stock_movements of zero. A return_refund that '
  'has been checked must show exactly one. Any other combination is a defect.';

grant select on tiktok_invoices to mse_app, mse_analytics;
grant insert, update on tiktok_invoices to mse_app;
grant select on settlement_reconciliation, return_reconciliation to mse_app, mse_analytics;

alter table tiktok_invoices enable row level security;
alter table tiktok_invoices force  row level security;
create policy tiktok_invoices_own on tiktok_invoices
  using      (shop_id in (select id from shops where account_id = app_account_id()))
  with check (shop_id in (select id from shops where account_id = app_account_id()));
