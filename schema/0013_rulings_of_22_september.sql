-- 0013. The rulings taken on 22 September 2026.
--
-- Three rulings, each recorded here so the schema states the decision rather
-- than leaving it to the application.
--
-- 1. An unmapped fee must be able to raise a discrepancy. The comment on
--    ledger_unmapped_idx already promised a nightly sweep that raises one, and
--    discrepancies.kind had no value the sweep could use, so the sweep could not
--    insert its row. A seventh kind is added.
--
-- 2. The accountant feed is out of the MVP. Export stays. feed_tokens is dropped
--    and 'accountant' is removed from both export kind constraints.
--
-- 3. Where TikTok and the seller disagree about a fact TikTok owns, TikTok's
--    value is recorded. The rule is enforced in the application because it
--    depends on which entity the discrepancy concerns, so it is documented here
--    rather than constrained.

-- Ruling 1. The unmapped fee discrepancy.

alter table discrepancies drop constraint discrepancies_kind_check;

alter table discrepancies add constraint discrepancies_kind_check check (
  kind in ('product_code','order_reference','transaction_reference',
           'amount','return_unmatched','duplicate','unmapped_fee')
);

comment on column discrepancies.kind is
  'unmapped_fee is raised by the nightly sweep over ledger_unmapped_idx when '
  'TikTok charges a fee the mapping table does not recognise. tiktok_value '
  'carries TikTok''s verbatim field name and seller_value is null, because the '
  'seller has no competing figure.';

-- Ruling 2. The accountant feed leaves the MVP.

drop table if exists feed_tokens;

alter table exports drop constraint exports_kind_check;
alter table exports add constraint exports_kind_check check (
  kind in ('month_summary','ledger','transactions')
);

alter table export_schedules drop constraint export_schedules_kind_check;
alter table export_schedules add constraint export_schedules_kind_check check (
  kind in ('month_summary','ledger','transactions')
);

-- Ruling 3. TikTok precedence, recorded against the columns it governs.

comment on column discrepancies.applied_value is
  'Defaults to tiktok_value for any fact TikTok owns, which is orders, order '
  'lines, quantities, fees, refunds, statements and TikTok''s stock count. The '
  'seller may add a note but may not overwrite those. Facts the seller alone '
  'holds, which are product costs, other-channel sales and the tax profile, '
  'have no TikTok side and raise no discrepancy.';

comment on column discrepancies.resolution is
  'corrected_seller is available only where the disputed fact is the seller''s '
  'own. On a TikTok-owned fact the seller may accept or explain, not correct.';
