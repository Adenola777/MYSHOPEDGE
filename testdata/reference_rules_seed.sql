-- Reference rules seed. Values are external facts, sourced and dated, not policy choices.
-- Load as mse_migrator or a superuser. mse_app holds SELECT only on this table.
--
-- UK VAT registration threshold: GBP 90,000, effective 1 April 2024, under the Value Added
-- Tax (Increase of Registration Limits) Order 2024. Verified 26 June 2026.
insert into reference_rules
  (rule_set, rule_key, value, effective_from, source_url, reviewed_by, reviewed_at)
values
  ('vat', 'registration_threshold',
   '{"amount_minor": 9000000, "currency": "GBP"}',
   '2024-04-01',
   'https://www.gov.uk/register-for-vat',
   'HMRC, Value Added Tax (Increase of Registration Limits) Order 2024',
   '2026-06-26')
on conflict (rule_set, rule_key, effective_from) do update set
  value = excluded.value,
  source_url = excluded.source_url,
  reviewed_by = excluded.reviewed_by,
  reviewed_at = excluded.reviewed_at;
