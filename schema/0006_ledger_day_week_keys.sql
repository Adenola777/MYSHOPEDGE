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
