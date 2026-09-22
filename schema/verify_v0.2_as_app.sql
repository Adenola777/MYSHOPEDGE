-- MyShopEdge v0.2 verification, part two. Run as mse_app, after verify_v0.2.sql.
--   psql -d mse -U mse_app -f verify_v0.2_as_app.sql
\set ON_ERROR_STOP off

\echo ''
\echo '=== 11 (ACC-3) With no account set the session sees nothing. PASS = 0.'
select count(*) as visible_rows from ledger_entries;

\echo ''
\echo '=== 12 (ACC-3) A seller sees their own rows. PASS = a non-zero count and one shop.'
select set_config('app.account_id','11111111-1111-1111-1111-111111111111',false) is not null as set_ok;
select count(*) as rosie_ledger_rows from ledger_entries;
select count(*) as rosie_shops from shops;

\echo ''
\echo '=== 13 (ACC-3) Another seller sees none of them. PASS = 0.'
select set_config('app.account_id','99999999-9999-9999-9999-999999999999',false) is not null as set_ok;
select count(*) as other_sees_rosie from ledger_entries;

\echo ''
\echo '=== 14 (ACC-3) Another seller cannot write into this shop. PASS = RLS violation.'
insert into ledger_entries (shop_id,order_id,order_line_id,sku_id,attribution,entry_type,amount_minor,occurred_at,basis_month,source)
values ('22222222-2222-2222-2222-222222222222','66666666-6666-6666-6666-666666666666','77777777-7777-7777-7777-777777777777','44444444-4444-4444-4444-444444444444','direct','sale',999999,'2026-03-04T10:00:00Z','2026-03-01','seller');

\echo ''
\echo '=== 15 (LED-1) The application has no UPDATE privilege. PASS = permission denied.'
select set_config('app.account_id','11111111-1111-1111-1111-111111111111',false) is not null as set_ok;
update ledger_entries set amount_minor=1 where source_ref='TX-1';

\echo ''
\echo '=== 16 (LED-1) The maintenance flag does not help the application, because the'
\echo '=== privilege layer refuses before the trigger is reached. PASS = permission denied.'
select set_config('app.allow_ledger_maintenance','on',false) is not null as set_ok;
update ledger_entries set amount_minor=1 where source_ref='TX-1';

\echo ''
\echo '=== 17 (TAX-6) Reference rules are readable and not writable. PASS = true, false.'
select has_table_privilege('mse_app','reference_rules','select') as can_read,
       has_table_privilege('mse_app','reference_rules','insert') as can_write;
