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
