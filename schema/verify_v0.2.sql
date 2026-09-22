-- MyShopEdge v0.2 schema verification harness.
-- Load MyShopEdge_MVP_schema_v0.2.sql into an empty database, then run this file as a
-- superuser or as mse_migrator. Every test states what it proves. A test that prints an
-- ERROR where the comment says it must is passing.
--
--   createdb mse && psql -d mse -f MyShopEdge_MVP_schema_v0.2.sql
--   psql -d mse -f verify_v0.2.sql
\set ON_ERROR_STOP off

-- ---------------------------------------------------------------- fixtures
insert into accounts (id,email,auth_subject) values
 ('11111111-1111-1111-1111-111111111111','rosie@example.uk','idp|rosie'),
 ('99999999-9999-9999-9999-999999999999','other@example.uk','idp|other');
insert into shops (id,account_id,tiktok_shop_id,shop_name) values
 ('22222222-2222-2222-2222-222222222222','11111111-1111-1111-1111-111111111111','TT1','Pottery'),
 ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa','99999999-9999-9999-9999-999999999999','TT2','Other shop');
insert into products (id,shop_id,tiktok_product_id,title) values
 ('33333333-3333-3333-3333-333333333333','22222222-2222-2222-2222-222222222222','P1','Mug');
insert into skus (id,shop_id,product_id,tiktok_sku_id,seller_sku) values
 ('44444444-4444-4444-4444-444444444444','22222222-2222-2222-2222-222222222222','33333333-3333-3333-3333-333333333333','S1','P006'),
 ('55555555-5555-5555-5555-555555555555','22222222-2222-2222-2222-222222222222','33333333-3333-3333-3333-333333333333','S2','P007');
insert into orders (id,shop_id,tiktok_order_id,status,order_created_at,gross_minor) values
 ('66666666-6666-6666-6666-666666666666','22222222-2222-2222-2222-222222222222','ORD-10001','paid','2026-03-04T10:00:00Z',6150);
insert into order_lines (id,shop_id,order_id,sku_id,tiktok_line_id,quantity,unit_price_minor) values
 ('77777777-7777-7777-7777-777777777777','22222222-2222-2222-2222-222222222222','66666666-6666-6666-6666-666666666666','44444444-4444-4444-4444-444444444444','L1',3,1250),
 ('88888888-8888-8888-8888-888888888888','22222222-2222-2222-2222-222222222222','66666666-6666-6666-6666-666666666666','55555555-5555-5555-5555-555555555555','L2',1,2400);

\echo ''
\echo '=== 1 (LED-9, LED-10) One order-level deduction posts once per line, same source_ref.'
\echo '=== PASS = two rows.'
insert into ledger_entries (shop_id,order_id,order_line_id,sku_id,attribution,entry_type,category,amount_minor,occurred_at,basis_month,source,source_ref) values
 ('22222222-2222-2222-2222-222222222222','66666666-6666-6666-6666-666666666666','77777777-7777-7777-7777-777777777777','44444444-4444-4444-4444-444444444444','allocated','platform_deduction','commission',-188,'2026-03-04T10:00:00Z','2026-03-01','tiktok','TX-1'),
 ('22222222-2222-2222-2222-222222222222','66666666-6666-6666-6666-666666666666','88888888-8888-8888-8888-888888888888','55555555-5555-5555-5555-555555555555','allocated','platform_deduction','commission',-120,'2026-03-04T10:00:00Z','2026-03-01','tiktok','TX-1');
select count(*) as rows_posted from ledger_entries where source_ref='TX-1';

\echo ''
\echo '=== 2 (LED-9) The same TikTok record cannot post twice for the same line.'
\echo '=== PASS = unique violation on ledger_idempotency_idx.'
insert into ledger_entries (shop_id,order_id,order_line_id,sku_id,attribution,entry_type,category,amount_minor,occurred_at,basis_month,source,source_ref) values
 ('22222222-2222-2222-2222-222222222222','66666666-6666-6666-6666-666666666666','77777777-7777-7777-7777-777777777777','44444444-4444-4444-4444-444444444444','allocated','platform_deduction','commission',-188,'2026-03-04T10:00:00Z','2026-03-01','tiktok','TX-1');

\echo ''
\echo '=== 3, 4, 5 (LED-1, TC-LED-04) The ledger is append-only.'
\echo '=== PASS = three errors from enforce_append_only.'
update ledger_entries set amount_minor = -999 where source_ref='TX-1';
delete from ledger_entries where source_ref='TX-1';
truncate ledger_entries;

\echo ''
\echo '=== 6 (LED-9) Only a payout may carry no line. PASS = check constraint violation.'
alter table ledger_entries validate constraint ledger_attribution_chk;
insert into ledger_entries (shop_id,order_line_id,attribution,entry_type,amount_minor,occurred_at,basis_month,source) values
 ('22222222-2222-2222-2222-222222222222','77777777-7777-7777-7777-777777777777','direct','payout',5000,'2026-03-20T10:00:00Z','2026-03-01','tiktok');

\echo ''
\echo '=== 7 (MON-1, G13) Day and week keys derived in Europe/London.'
\echo '=== PASS = A on 11 Jun, B on 1 Jul, C on 10 Dec, weeks starting Monday,'
\echo '=== E and F both on 25 Oct with the same local clock time an hour apart in real time.'
insert into ledger_entries (shop_id,order_id,order_line_id,sku_id,attribution,entry_type,amount_minor,occurred_at,basis_month,source,source_ref) values
 ('22222222-2222-2222-2222-222222222222','66666666-6666-6666-6666-666666666666','77777777-7777-7777-7777-777777777777','44444444-4444-4444-4444-444444444444','direct','sale',1000,'2026-06-10T23:30:00Z','2026-06-01','tiktok','G13-A'),
 ('22222222-2222-2222-2222-222222222222','66666666-6666-6666-6666-666666666666','77777777-7777-7777-7777-777777777777','44444444-4444-4444-4444-444444444444','direct','sale',1000,'2026-06-30T23:30:00Z','2026-07-01','tiktok','G13-B'),
 ('22222222-2222-2222-2222-222222222222','66666666-6666-6666-6666-666666666666','77777777-7777-7777-7777-777777777777','44444444-4444-4444-4444-444444444444','direct','sale',1000,'2026-12-10T23:30:00Z','2026-12-01','tiktok','G13-C'),
 ('22222222-2222-2222-2222-222222222222','66666666-6666-6666-6666-666666666666','77777777-7777-7777-7777-777777777777','44444444-4444-4444-4444-444444444444','direct','sale',1000,'2026-03-29T01:30:00Z','2026-03-01','tiktok','G13-D'),
 ('22222222-2222-2222-2222-222222222222','66666666-6666-6666-6666-666666666666','77777777-7777-7777-7777-777777777777','44444444-4444-4444-4444-444444444444','direct','sale',1000,'2026-10-25T00:30:00Z','2026-10-01','tiktok','G13-E'),
 ('22222222-2222-2222-2222-222222222222','66666666-6666-6666-6666-666666666666','77777777-7777-7777-7777-777777777777','44444444-4444-4444-4444-444444444444','direct','sale',1000,'2026-10-25T01:30:00Z','2026-10-01','tiktok','G13-F');
select source_ref, occurred_at at time zone 'Europe/London' as london_time, basis_day, basis_week
from ledger_entries where source_ref like 'G13%' order by source_ref;

\echo ''
\echo '=== 8 (TC-LED-21) A month derived in UTC is caught, not moved silently.'
\echo '=== PASS = one row, stored June, correct July.'
insert into ledger_entries (shop_id,order_id,order_line_id,sku_id,attribution,entry_type,amount_minor,occurred_at,basis_month,source,source_ref) values
 ('22222222-2222-2222-2222-222222222222','66666666-6666-6666-6666-666666666666','77777777-7777-7777-7777-777777777777','44444444-4444-4444-4444-444444444444','direct','sale',1000,'2026-06-30T23:30:00Z','2026-06-01','tiktok','BAD-UTC');
select l.source_ref, m.basis_month as stored, m.london_month as correct
from ledger_basis_month_mismatch m join ledger_entries l using (id);

\echo ''
\echo '=== 9 (STK-8) adjustment_absorbed is an accepted movement type. PASS = one row.'
insert into stock_positions (shop_id,sku_id,tiktok_stock,adjusted_delta) values
 ('22222222-2222-2222-2222-222222222222','55555555-5555-5555-5555-555555555555',31,3);
insert into stock_movements (shop_id,sku_id,movement_type,quantity,occurred_at,reason) values
 ('22222222-2222-2222-2222-222222222222','55555555-5555-5555-5555-555555555555','adjustment_absorbed',1,now(),'TikTok stock rose to match a resellable return');
select movement_type, quantity from stock_movements where movement_type='adjustment_absorbed';

\echo ''
\echo '=== 10 (STK-4) A manual adjustment without a reason is refused. PASS = check violation.'
insert into stock_movements (shop_id,sku_id,movement_type,quantity,occurred_at) values
 ('22222222-2222-2222-2222-222222222222','55555555-5555-5555-5555-555555555555','manual_adjustment',-4,now());

\echo ''
\echo '=== Tests 11 to 16 must be run as mse_app. Reconnect and run verify_v0.2_as_app.sql.'
