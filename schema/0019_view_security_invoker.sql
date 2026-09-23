-- 0019. Closing a cross-tenant leak in every view, and adding the order counter.
--
-- Found on 23 September 2026 while looking for somewhere to count orders for the A16 quota.
--
-- THE FAULT
--
-- A PostgreSQL view executes against its base tables as the VIEW'S OWNER, not as the role
-- that queried it, unless the view is created with security_invoker = true. Every view in
-- this schema is owned by mse_migrator, and mse_migrator carries BYPASSRLS so that it can
-- run migrations against tables whose row level security is FORCEd.
--
-- The two facts together defeat the entire tenancy model. Row level security on the base
-- tables is correct and was verified empirically on 22 September. The views go round it.
--
-- Demonstrated on the development branch, as mse_app, with app.account_id set to an account
-- that owns nothing:
--
--     settlements                 via base table     0    correct
--     orders                      via base table     0    correct
--     settlement_reconciliation   via view           3    another account's rows
--     settlement_totals_check     via view           3    another account's rows
--     return_reconciliation       via view           7    another account's rows
--
-- Three of the seven views are granted to mse_app, and all three leaked. This is the exact
-- failure the schema's row level security exists to prevent, and it would not have shown up
-- in any single-tenant test, which is why it survived a day of testing with one account.
--
-- THE FIX
--
-- security_invoker = true makes a view evaluate its base tables with the privileges and the
-- row level security context of the caller. The policies then apply as they were written,
-- and app_account_id() resolves per transaction as it already does everywhere else.
--
-- Set on every view rather than only the three that are granted, because a grant is one
-- line away and the next person to add one should inherit a safe default.

alter view account_identity            set (security_invoker = true);
alter view ledger_basis_month_mismatch set (security_invoker = true);
alter view return_reconciliation       set (security_invoker = true);
alter view settlement_reconciliation   set (security_invoker = true);
alter view settlement_totals_check     set (security_invoker = true);

comment on view settlement_reconciliation is
  'Reconciles each settlement against the ledger. security_invoker is true, set by '
  'migration 0019: without it this view runs as mse_migrator, which holds BYPASSRLS, and '
  'returns every account''s settlements to any caller. Never create a view in this schema '
  'without it.';

-- The order counter for the soft quota ruled in A16.3.
--
-- The limits themselves are not here. 100, 500 and 2,000 live in service/app/plans.py and
-- are quoted on the price sheet, and a commercial number written in two places drifts. This
-- view answers how many orders fall in the current billing period, and the service applies
-- the limit.
--
-- The period is the subscription's billing period rather than the calendar month, because a
-- seller who signs up on the 20th does not get a fresh allowance eleven days later.

create view order_quota
  with (security_invoker = true)
as
select
  s.account_id,
  s.plan_slug,
  s.status,
  s.current_period_start,
  s.current_period_end,
  (select count(*)
     from orders o
     join shops sh on sh.id = o.shop_id
    where sh.account_id = s.account_id
      and s.current_period_start is not null
      and s.current_period_end is not null
      and o.order_created_at >= s.current_period_start
      and o.order_created_at <  s.current_period_end) as orders_in_period
from subscriptions s;

alter view order_quota owner to mse_migrator;
grant select on order_quota to mse_app, mse_analytics;

-- The guard. This fault survived a day of testing because it is invisible with one account
-- and because nothing checked. Any view added later without security_invoker now stops the
-- migration rather than quietly reopening the leak.

do $$
declare
  leaky text;
begin
  select string_agg(c.relname, ', ' order by c.relname) into leaky
    from pg_class c
    join pg_namespace n on n.oid = c.relnamespace
   where c.relkind = 'v'
     and n.nspname = 'public'
     and coalesce((select option_value from pg_options_to_table(c.reloptions)
                    where option_name = 'security_invoker'), 'false') <> 'true';

  if leaky is not null then
    raise exception 'views without security_invoker would bypass row level security: %', leaky
      using hint = 'Add "with (security_invoker = true)" to the view definition.';
  end if;
end $$;

comment on view order_quota is
  'Orders created within the current billing period, per account, for the soft quota in '
  'A16.3. A cancelled order still counts, because the work of reading, allocating and '
  'reconciling it was done either way. The plan limits are not here: they live in '
  'service/app/plans.py, so the commercial numbers have one home.';
