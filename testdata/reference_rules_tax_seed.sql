-- Reference rules for tax dates and income thresholds. External facts, sourced and dated.
-- Load as mse_migrator. mse_app holds SELECT only. Values verified 27 September 2026 from
-- gov.uk. These power getTaxDates (TAX-4) and quarterlyCheck (TAX-5).
--
-- Self Assessment key dates. A UK tax year Y runs 6 April Y to 5 April Y+1. Each value
-- gives the month, day and the number of years after Y the date falls on, plus its label.
insert into reference_rules
  (rule_set, rule_key, value, effective_from, source_url, reviewed_by, reviewed_at)
values
  ('income_tax', 'date.tax_year_end',
   '{"label": "End of the tax year", "month": 4, "day": 5, "year_offset": 1}',
   '2020-04-06', 'https://www.gov.uk/self-assessment-tax-returns/deadlines',
   'HMRC Self Assessment deadlines', '2026-09-27'),
  ('income_tax', 'date.paper_return_deadline',
   '{"label": "Paper tax return deadline", "month": 10, "day": 31, "year_offset": 1}',
   '2020-04-06', 'https://www.gov.uk/self-assessment-tax-returns/deadlines',
   'HMRC Self Assessment deadlines', '2026-09-27'),
  ('income_tax', 'date.online_return_deadline',
   '{"label": "Online tax return and balancing payment deadline", "month": 1, "day": 31, "year_offset": 2}',
   '2020-04-06', 'https://www.gov.uk/self-assessment-tax-returns/deadlines',
   'HMRC Self Assessment deadlines', '2026-09-27'),
  ('income_tax', 'date.first_payment_on_account',
   '{"label": "First payment on account", "month": 1, "day": 31, "year_offset": 2}',
   '2020-04-06', 'https://www.gov.uk/understand-self-assessment-bill/payments-on-account',
   'HMRC payments on account', '2026-09-27'),
  ('income_tax', 'date.second_payment_on_account',
   '{"label": "Second payment on account", "month": 7, "day": 31, "year_offset": 2}',
   '2020-04-06', 'https://www.gov.uk/understand-self-assessment-bill/payments-on-account',
   'HMRC payments on account', '2026-09-27')
on conflict (rule_set, rule_key, effective_from) do update set
  value = excluded.value, source_url = excluded.source_url,
  reviewed_by = excluded.reviewed_by, reviewed_at = excluded.reviewed_at;

-- Making Tax Digital for Income Tax Self Assessment threshold. Mandatory for self-employment
-- and property income over GBP 50,000 from 6 April 2026.
insert into reference_rules
  (rule_set, rule_key, value, effective_from, source_url, reviewed_by, reviewed_at)
values
  ('mtd', 'threshold.itsa',
   '{"label": "Making Tax Digital for Income Tax", "amount_minor": 5000000, "currency": "GBP"}',
   '2026-04-06', 'https://www.gov.uk/guidance/check-if-youre-eligible-for-making-tax-digital-for-income-tax',
   'HMRC Making Tax Digital for Income Tax', '2026-09-27')
on conflict (rule_set, rule_key, effective_from) do update set
  value = excluded.value, source_url = excluded.source_url,
  reviewed_by = excluded.reviewed_by, reviewed_at = excluded.reviewed_at;
