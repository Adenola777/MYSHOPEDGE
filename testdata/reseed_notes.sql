-- Re-seeding a development branch.
--
-- ledger_entries carries three triggers that refuse UPDATE, DELETE and TRUNCATE
-- for every role, including the owner. That is the intended behaviour and it is
-- what makes the ledger an audit record rather than a working table. The
-- consequence is that a seeded branch cannot be corrected in place.
--
-- Two ways to re-seed, in order of preference.
--
-- 1. Reset the branch from its parent and replay the migrations and the seed.
--    This is the correct method and the reason the project uses copy-on-write
--    branches. It leaves the append-only guarantee untouched.
--
-- 2. Disable the triggers for the duration of the correction, as below. This is
--    permitted only on a development branch and only to the owner. mse_app
--    cannot do it, because ALTER TABLE requires ownership, and mse_app must
--    never be granted ownership in staging or production.
--
-- Used on 22 September 2026 to attach return_id to the ten entries a return
-- produced, after the ingestion was corrected.

alter table ledger_entries disable trigger ledger_entries_no_update;

update ledger_entries le
   set return_id = r.id
  from returns r
 where r.order_id = le.order_id
   and le.category in ('refund','return_shipping','return_handling_fee')
   and le.return_id is null;

alter table ledger_entries enable trigger ledger_entries_no_update;

-- Confirm the triggers are back before leaving the session.
select tgname, tgenabled from pg_trigger
 where tgrelid = 'ledger_entries'::regclass and not tgisinternal;
