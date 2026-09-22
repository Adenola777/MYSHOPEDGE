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
