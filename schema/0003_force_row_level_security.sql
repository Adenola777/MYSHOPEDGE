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
