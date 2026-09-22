-- 0010_statement_identity_and_totals.sql
--
-- Closes the gaps found when the official Get Statements documentation was read
-- against the schema (/finance/202309/statements, scope seller.finance.info).
--
-- Three problems are addressed.
--
-- 1. The statement carries a single timestamp, statement_time, which the schema had
--    nowhere to put. period_start and period_end were being derived from something
--    the database never stored, so the derivation could not be audited.
--
-- 2. statement_time is stamped the day AFTER the activity it covers. TikTok generates
--    statements daily at 00:00 UTC covering the previous day, and its own worked
--    example confirms it: to read activity for 5 to 10 October you query statement_time
--    from 6 October 00:00 to 11 October. Storing statement_time as the period would
--    misdate every statement by exactly one day.
--
-- 3. The statement's own four component amounts were not stored, so there was no way
--    to check TikTok's arithmetic against the ledger entries behind it.

alter table settlements
  add column statement_time timestamptz,

  -- The UTC day the statement actually describes. Derived, never entered, so the
  -- off-by-one is applied once here rather than in every query that needs it.
  add column activity_date date generated always as
    (((statement_time at time zone 'UTC') - interval '1 day')::date) stored,

  -- The statement's own figures, exactly as TikTok reports them. Which of these is
  -- populated depends on the seller's region (see the comments below), so they are
  -- all nullable and none of them is assumed.
  add column net_sales_minor     bigint,
  add column fee_minor           bigint,
  add column shipping_cost_minor bigint,
  add column adjustment_minor    bigint,
  add column revenue_minor       bigint;

create index settlements_statement_time_idx on settlements (shop_id, statement_time);
create index settlements_activity_date_idx  on settlements (shop_id, activity_date);

comment on column settlements.statement_time is
  'TikTok''s statement_time, stored raw. Statements are generated daily at 00:00 UTC '
  'and cover the previous day, so this is one day AFTER the activity it describes. '
  'Never display it as the statement period. Use activity_date.';

comment on column settlements.activity_date is
  'The UTC day the statement covers, being statement_time minus one day. This is a UTC '
  'day, not a Europe/London day. During British Summer Time a TikTok statement day runs '
  '01:00 to 01:00 London, so it does not align with ledger_entries.basis_day. Statement '
  'level reconciliation is unaffected. Any daily comparison between a TikTok statement '
  'and a MyShopEdge day must state this difference on screen rather than leave the '
  'seller to discover it.';

comment on column settlements.period_start is
  'Retained for statements that genuinely cover a range. For the daily statements '
  'returned by /finance/202309/statements, activity_date is the correct field.';

comment on column settlements.net_sales_minor is
  'TikTok net_sales_amount. Applicable only to local sellers outside the SEA region, '
  'which includes the UK. Null for a SEA seller, where revenue_minor carries the figure '
  'instead.';

comment on column settlements.revenue_minor is
  'TikTok revenue_amount. Applicable to all regions EXCEPT the UK and the US. A UK '
  'seller will always have this null and net_sales_minor populated. If both are '
  'populated on one row, the region mapping is wrong.';

comment on column settlements.shipping_cost_minor is
  'TikTok shipping_cost_amount. Applicable only to local sellers outside the SEA region. '
  'For a SEA seller shipping is folded into fee_minor instead, which is why the two can '
  'never be summed blindly across regions.';

comment on column settlements.fee_minor is
  'TikTok fee_amount. Excludes shipping for every region except SEA local sellers, where '
  'shipping is included. The breakdown behind this figure is not in the statement and '
  'must be read from the statement transactions endpoint.';

comment on column settlements.adjustment_minor is
  'TikTok adjustment_amount. The statement gives no reason for it. The reason is only '
  'available from the statement transactions endpoint, so an adjustment that arrives '
  'without an explanation is posted as unmapped_fee and raises a discrepancy.';

-- TikTok returns exactly three payment states, which are the three states the
-- settlement column shows: PAID is green, PROCESSING is amber, FAILED is red.
alter table settlements
  add constraint settlements_payment_status_chk
  check (payment_status is null or payment_status in ('PAID','PROCESSING','FAILED'));

comment on column settlements.payment_status is
  'TikTok''s own value, kept verbatim. PAID, PROCESSING or FAILED. These map directly '
  'onto the settled, pending and not paid colours, so the traffic light is TikTok''s '
  'state machine rather than an invention on top of it.';

-- Whether the four component amounts sum to settlement_amount is stated nowhere in
-- TikTok's documentation, and the worked example in that documentation does not
-- satisfy it. So this is a view that reports the difference, not a check constraint
-- that rejects the row. It becomes a constraint only once real UK statements prove
-- the equation holds.
create view settlement_totals_check as
select s.id                     as settlement_id,
       s.shop_id,
       s.tiktok_statement_id,
       s.statement_time,
       s.activity_date,
       s.payment_status,
       s.statement_amount_minor,
       coalesce(s.net_sales_minor, s.revenue_minor, 0)
         + coalesce(s.fee_minor, 0)
         + coalesce(s.shipping_cost_minor, 0)
         + coalesce(s.adjustment_minor, 0)          as components_sum_minor,
       s.statement_amount_minor
         - (coalesce(s.net_sales_minor, s.revenue_minor, 0)
            + coalesce(s.fee_minor, 0)
            + coalesce(s.shipping_cost_minor, 0)
            + coalesce(s.adjustment_minor, 0))      as difference_minor,
       (s.net_sales_minor is not null and s.revenue_minor is not null)
                                                    as region_mapping_conflict
from settlements s;

comment on view settlement_totals_check is
  'Checks TikTok''s statement against its own component amounts. difference_minor is '
  'expected to be zero. region_mapping_conflict is true when both net_sales_minor and '
  'revenue_minor are populated, which cannot happen for a correctly mapped seller and '
  'means the region branch in the ingestion code is wrong.';

grant select on settlement_totals_check to mse_app, mse_analytics;
