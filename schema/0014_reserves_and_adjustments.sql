-- 0014. Reserves, platform adjustments, and the correction to 0012.
--
-- Settled 22 September 2026 on the principle that TikTok's identifiers and
-- TikTok's names take precedence over anything the seller or this product
-- invents, because the purpose of the product is to explain TikTok's finance to
-- the seller rather than to restate it in our own vocabulary.
--
-- Three decisions.
--
-- 1. Migration 0012 was wrong. It admitted a statement-level entry only when
--    order_id was null. The finance API returns adjustment_order_id, so an
--    adjustment may name a TikTok order while still belonging to no order line.
--    By the principle above that order ID is recorded, so the branch drops the
--    order_id restriction and keeps the two that matter: no order line, and a
--    settlement.
--
-- 2. Adjustments get their own category rather than being swept into
--    unmapped_fee. The statement transaction type field carries twenty-one
--    documented adjustment values. They are not unrecognised, so treating them
--    as unmapped would be untrue, and migration 0013 makes every unmapped fee
--    raise a discrepancy, which would bury the seller in notices for ordinary
--    platform activity.
--
--    None of the twenty-one is folded into an existing category, even where one
--    looks close. If TikTok shows the seller a platform penalty and we show it
--    inside platform commission, the seller cannot reconcile our figure against
--    TikTok's own screen, which is the one thing this product must never break.
--    tiktok_fee_type carries TikTok's verbatim value and the calculator shows
--    that name.
--
--    unmapped_fee now means what it says: a field or type this mapping does not
--    know. Only unmapped_fee raises a discrepancy.
--
-- 3. Reserves enter the schema now. TikTok withholds part of a settlement under
--    its reserve policy and releases it later. The money that reaches the bank
--    is payable_amount, not settlement_amount. Without this the reconciliation
--    would tell a seller the statement agrees while their bank shows less, which
--    is the failure the product exists to catch.

-- 1. The corrected attribution constraint.

alter table ledger_entries drop constraint ledger_attribution_chk;

alter table ledger_entries add constraint ledger_attribution_chk check (
     (entry_type =  'payout' and order_line_id is null and attribution = 'none')
  or (entry_type <> 'payout' and order_line_id is null and attribution = 'none'
      and settlement_id is not null)
  or (entry_type <> 'payout' and order_line_id is not null
      and attribution in ('direct','allocated'))
) not valid;

comment on constraint ledger_attribution_chk on ledger_entries is
  'Three shapes only: a payout, a statement-level entry that carries a '
  'settlement and no order line, or an order-line entry. A statement-level '
  'entry may carry order_id, because an adjustment or a reserve can name a '
  'TikTok order without belonging to one of its lines. NOT VALID, so it guards '
  'new rows only.';

-- 2. The reserve entry type, and the three new categories.

alter table ledger_entries drop constraint ledger_entries_entry_type_check;
alter table ledger_entries add constraint ledger_entries_entry_type_check check (
  entry_type in ('sale','platform_deduction','refund','payout','return_cost',
                 'write_off','adjustment','reserve')
);

alter table ledger_entries drop constraint ledger_entries_category_check;
alter table ledger_entries add constraint ledger_entries_category_check check (
  category is null or category in (
    'gross_sales','seller_discount','refund',
    'platform_commission','affiliate_commission','transaction_fee',
    'smart_promotions_fee','shipping_fee','return_handling_fee',
    'fbt_operations_fee','fbt_shipping_fee','fbt_storage_fee',
    'platform_adjustment','unmapped_fee',
    'reserve_withheld','reserve_released',
    'cost_of_goods_sold','seller_shipping','return_shipping',
    'stock_written_off','settlement')
);

comment on column ledger_entries.category is
  'platform_adjustment covers the twenty-one documented adjustment types on the '
  'statement transaction, with tiktok_fee_type carrying TikTok''s verbatim '
  'value, which is the name shown to the seller. No adjustment is folded into '
  'another category, so every figure can be reconciled against TikTok''s own '
  'screen. unmapped_fee is reserved for a field or type this mapping does not '
  'know, and it alone raises a discrepancy.';

-- 3. What the statement said, what was withheld, and what is actually paid.

alter table settlements add column payable_amount_minor bigint;
alter table settlements add column total_reserve_amount_minor bigint;

comment on column settlements.payable_amount_minor is
  'The amount TikTok will actually pay, from the statement transactions header. '
  'Differs from statement_amount_minor whenever a reserve is withheld, and it '
  'is the figure the seller will see in their bank. Null on a statement fetched '
  'before this column existed, or where TikTok returned no value.';

comment on column settlements.total_reserve_amount_minor is
  'Negative where funds are withheld from this settlement, positive where '
  'previously reserved funds are released into it.';

-- The reconciliation view gains the two figures, so a seller who is paid less
-- than the statement says can see why without leaving the screen.

create or replace view settlement_reconciliation as
select
  s.id                              as settlement_id,
  s.shop_id,
  s.tiktok_statement_id,
  s.tiktok_payment_id,
  s.settlement_reference,
  s.paid_at,
  s.statement_amount_minor,
  (select count(*) from order_settlements os where os.settlement_id = s.id)
                                    as orders_settled,
  -- A reserve carries its settlement but is not one of the statement's
  -- components. Statement amount is net sales plus fees plus shipping plus
  -- adjustments. The reserve is withheld from that total afterwards, so
  -- counting it here would report a correct statement as unexplained by exactly
  -- the amount withheld. Caught on the seeded reserve, 22 September 2026.
  coalesce((select sum(le.amount_minor) from ledger_entries le
             where le.settlement_id = s.id
               and le.entry_type not in ('payout','reserve')), 0)
                                    as net_proceeds_minor,
  coalesce((select sum(i.gross_minor) from tiktok_invoices i
             where i.settlement_id = s.id), 0)
                                    as invoiced_gross_minor,
  s.statement_amount_minor::numeric
    - coalesce((select sum(le.amount_minor) from ledger_entries le
                 where le.settlement_id = s.id
                   and le.entry_type not in ('payout','reserve')), 0)
                                    as unexplained_minor,
  -- Appended rather than placed beside statement_amount_minor, because CREATE
  -- OR REPLACE VIEW may add columns at the end but may not reorder them.
  s.total_reserve_amount_minor,
  s.payable_amount_minor
from settlements s;

comment on view settlement_reconciliation is
  'unexplained_minor tests the statement against the entries behind it. It does '
  'not test what was paid. A statement can reconcile exactly and still pay less '
  'than it states, because of a reserve, which is why payable_amount_minor sits '
  'beside it.';
