-- 0012. Allow statement-level ledger entries.
--
-- Found by the payload-based ingestion test of 22 September 2026. A TikTok
-- statement carries adjustment_amount at statement level. It belongs to no order
-- and to no order line, and the statement gives no reason for it. The original
-- ledger_attribution_chk permitted only two shapes, a payout with no line or a
-- non-payout with a line, so the adjustment could not be recorded at all.
--
-- The two workarounds were both rejected. Recording it as a payout would file a
-- fee as a cash movement and corrupt the payout total. Allocating it across the
-- statement's order lines would invent an allocation basis TikTok never supplied.
--
-- The third branch below is deliberately narrow. It admits an entry only when
-- that entry is tied to a settlement and to nothing else. An entry with no line
-- and no settlement is still refused, which is the case the constraint was
-- written to catch.

alter table ledger_entries drop constraint ledger_attribution_chk;

alter table ledger_entries add constraint ledger_attribution_chk check (
     (entry_type =  'payout' and order_line_id is null and attribution = 'none')
  or (entry_type <> 'payout' and order_line_id is null and attribution = 'none'
      and order_id is null and settlement_id is not null)
  or (entry_type <> 'payout' and order_line_id is not null
      and attribution in ('direct','allocated'))
) not valid;

comment on constraint ledger_attribution_chk on ledger_entries is
  'Three shapes only: a payout, a statement-level entry carrying no order, or an '
  'order-line entry. NOT VALID, so it guards new rows only.';
