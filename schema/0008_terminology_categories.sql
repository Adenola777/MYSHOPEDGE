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
