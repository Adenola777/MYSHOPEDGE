-- MyShopEdge v0.2 migration 0009: TikTok identifiers and reconciliation.
--
-- The order number was already held on orders.tiktok_order_id. The invoice number was
-- not held at all: section 3.5 of the API Integration document kept it "in the raw
-- payload", and section 4.6 purges raw_events 90 days after processing. A seller
-- reclaiming input VAT on TikTok's fees needs those invoice numbers for six years.
--
-- This migration promotes every reconciliation identifier to a first-class column,
-- adds the invoice record itself, and takes invoice data out of the 90-day purge.

-- ---------------------------------------------------------------- invoices
create table tiktok_invoices (
  id uuid primary key default gen_random_uuid(),
  shop_id uuid not null references shops(id),
  tiktok_invoice_number text not null,
  invoice_type text not null,               -- TikTok's own label, kept verbatim
  issued_on date not null,
  period_start date,
  period_end date,
  net_minor bigint not null,
  vat_minor bigint not null default 0,
  gross_minor bigint not null,
  vat_rate_bp integer,                      -- basis points, so 20% is 2000
  currency char(3) not null default 'GBP',
  supplier_vat_number text,                 -- TikTok's VAT number, from the invoice
  buyer_vat_number text,                    -- the seller's, where shown
  document_url text,                        -- TikTok's link, which may expire
  document_fetched_at timestamptz,
  settlement_id uuid references settlements(id),
  source_ref text,
  created_at timestamptz not null default now(),
  unique (shop_id, tiktok_invoice_number),
  check (gross_minor = net_minor + vat_minor)
);
create index tiktok_invoices_issued_idx on tiktok_invoices (shop_id, issued_on);
create index tiktok_invoices_settlement_idx on tiktok_invoices (settlement_id);

comment on table tiktok_invoices is
  'TikTok fee invoices, held for VAT. The check constraint makes the arithmetic on the '
  'invoice self-verifying: gross must equal net plus VAT, every time.';
comment on column tiktok_invoices.invoice_type is
  'TikTok''s own label, for example Platform Service Fee. Kept verbatim rather than '
  'mapped, so a new invoice type cannot be silently absorbed.';
comment on column tiktok_invoices.document_url is
  'TikTok''s link expires. document_fetched_at records when a copy was taken, because '
  'the seller needs the document itself, not a dead link, at an HMRC enquiry.';

-- ---------------------------------------------------------------- the ledger carries both
alter table ledger_entries
  add column tiktok_invoice_number text,
  add column invoice_id uuid references tiktok_invoices(id);
create index ledger_invoice_idx on ledger_entries (shop_id, tiktok_invoice_number);
comment on column ledger_entries.tiktok_invoice_number is
  'The invoice the fee was billed on. Kept as text as well as a foreign key, so a fee '
  'that arrives before its invoice is still reconcilable when the invoice lands.';

-- ---------------------------------------------------------------- settlements
alter table settlements
  add column tiktok_invoice_number text,
  add column settlement_reference text;
comment on column settlements.settlement_reference is
  'The reference the seller will see on their bank statement, which is what makes a '
  'payout reconcilable against the bank rather than only against TikTok.';

-- ---------------------------------------------------------------- returns
alter table returns
  add column tiktok_credit_note_number text,
  add column tiktok_refund_reference text;
comment on column returns.tiktok_credit_note_number is
  'Where TikTok issues a credit note reversing a fee on a refunded order. Needed to '
  'reconcile the fee reversal, which is otherwise invisible against the original fee.';

-- ---------------------------------------------------------------- retention
-- Invoice data is deliberately excluded from the 90-day raw_events purge. UK VAT
-- records are kept for six years, so these rows outlive everything else in the pack
-- except the account itself.
comment on table tiktok_invoices is
  'TikTok fee invoices, held for VAT. Retained for 6 years from the end of the VAT '
  'period, not 90 days. Deleted only with the account under ACC-4, and the deletion '
  'record notes that the seller was told to take their invoices first.';

-- ---------------------------------------------------------------- reconciliation views
-- Payment reconciliation: a payout, the orders it settled, and the invoices billed
-- against it, in one place.
create view settlement_reconciliation as
select s.id                                as settlement_id,
       s.shop_id,
       s.tiktok_statement_id,
       s.tiktok_payment_id,
       s.settlement_reference,
       s.paid_at,
       s.statement_amount_minor,
       (select count(*) from order_settlements os where os.settlement_id = s.id)
                                           as orders_settled,
       coalesce((select sum(le.amount_minor) from ledger_entries le
                 where le.settlement_id = s.id and le.entry_type <> 'payout'), 0)
                                           as net_proceeds_minor,
       coalesce((select sum(i.gross_minor) from tiktok_invoices i
                 where i.settlement_id = s.id), 0)
                                           as invoiced_gross_minor,
       s.statement_amount_minor
         - coalesce((select sum(le.amount_minor) from ledger_entries le
                     where le.settlement_id = s.id and le.entry_type <> 'payout'), 0)
                                           as unexplained_minor
from settlements s;

comment on view settlement_reconciliation is
  'REC-1. unexplained_minor must be zero. Anything else is a payout that does not '
  'agree with the orders behind it, and raises a discrepancy under DSC-1.';

-- Returns reconciliation: the return, the refund, the fee reversal and the stock
-- movement, side by side, so a return that moved money but not stock is visible.
create view return_reconciliation as
select r.id                                 as return_id,
       r.shop_id,
       r.tiktok_return_id,
       o.tiktok_order_id,
       r.kind,
       r.tiktok_credit_note_number,
       r.refund_completed_at,
       r.refund_minor,
       coalesce((select sum(le.amount_minor) from ledger_entries le
                 where le.return_id = r.id and le.entry_type = 'refund'), 0)
                                            as refund_posted_minor,
       coalesce((select sum(le.amount_minor) from ledger_entries le
                 where le.return_id = r.id and le.entry_type = 'return_cost'), 0)
                                            as return_cost_minor,
       coalesce((select sum(le.amount_minor) from ledger_entries le
                 where le.return_id = r.id and le.entry_type = 'write_off'), 0)
                                            as write_off_minor,
       (select count(*) from return_items ri
        where ri.return_id = r.id and ri.seller_check_status = 'pending')
                                            as items_awaiting_check,
       (select count(*) from stock_movements sm
        where sm.return_id = r.id)          as stock_movements
from returns r
join orders o on o.id = r.order_id;

comment on view return_reconciliation is
  'REC-2. A refund_only return must show stock_movements of zero. A return_refund that '
  'has been checked must show exactly one. Any other combination is a defect.';

grant select on tiktok_invoices to mse_app, mse_analytics;
grant insert, update on tiktok_invoices to mse_app;
grant select on settlement_reconciliation, return_reconciliation to mse_app, mse_analytics;

alter table tiktok_invoices enable row level security;
alter table tiktok_invoices force  row level security;
create policy tiktok_invoices_own on tiktok_invoices
  using      (shop_id in (select id from shops where account_id = app_account_id()))
  with check (shop_id in (select id from shops where account_id = app_account_id()));
