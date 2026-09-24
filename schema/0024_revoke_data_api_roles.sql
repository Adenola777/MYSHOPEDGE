-- 0024. Take back every right the Neon Data API roles held in public, and drop Neon's sample
-- table.
--
-- WHAT WAS FOUND, 24 SEPTEMBER 2026, BY QUERYING PRODUCTION
--
-- The Neon Data API was active on production and exposed the public schema over HTTP. It
-- hands every signed-in Stack user the database role `authenticated`. A default privilege on
-- `mse_migrator` granted that role select, insert, update and delete on every table the
-- migrator creates, usage on every sequence and execute on every function. So:
--
-- - `authenticated` could write `schema_migrations`, the ledger this runner trusts, and
--   `reference_rules`, the shared tax rules that only `mse_migrator` may change. Neither has
--   row level security.
-- - `authenticated` could call the six SECURITY DEFINER functions. They run as
--   `mse_migrator`, which bypasses row level security. `create_subscription` overwrites any
--   account's plan and Stripe customer, and with `apply_subscription_event` a signed-in user
--   could give themselves an active plan. `create_account` could claim a seller's email before
--   the seller signed up.
-- - Tenant tables returned 0 rows as `authenticated`, because a Data API client cannot set
--   `app.account_id`. Row level security held there.
--
-- Production held 0 accounts and 0 subscriptions, so nothing was harmed. Staging and
-- development have no `authenticated` role. Whether the functions were reachable over HTTP
-- was never tested, because that needs a real token; the grants and the active Data API were
-- established by query.
--
-- The product never uses the Data API. The front end calls the Python service and the service
-- connects as `mse_app`. The Data API on production was deleted on 24 September 2026 before
-- this migration was written. This migration removes the rights, so that switching the Data
-- API back on would expose nothing.
--
-- WHAT IT DOES
--
-- On a branch where `authenticated` or `anonymous` exists, it revokes every right that role
-- holds on tables, sequences and functions in public, and removes `mse_migrator`'s default
-- privileges for it. Where neither role exists it changes nothing. Usage on the schema itself
-- comes from PUBLIC and is left alone. It then drops `playing_with_neon`, Neon's sample table,
-- which only production held (10 rows) and which nothing in the product reads. The check at
-- the end raises if either role still holds any table right or can call any SECURITY DEFINER
-- function in public.

do $$
declare
  r text;
begin
  foreach r in array array['authenticated', 'anonymous'] loop
    if exists (select 1 from pg_roles where rolname = r) then
      execute format('revoke all on all tables in schema public from %I', r);
      execute format('revoke all on all sequences in schema public from %I', r);
      execute format('revoke all on all functions in schema public from %I', r);
      execute format(
        'alter default privileges for role mse_migrator in schema public revoke all on tables from %I', r);
      execute format(
        'alter default privileges for role mse_migrator in schema public revoke all on sequences from %I', r);
      execute format(
        'alter default privileges for role mse_migrator in schema public revoke all on functions from %I', r);
    end if;
  end loop;
end $$;

drop table if exists playing_with_neon;

do $$
declare
  r text;
begin
  foreach r in array array['authenticated', 'anonymous'] loop
    if exists (select 1 from pg_roles where rolname = r) then
      if exists (
        select 1 from information_schema.role_table_grants
         where table_schema = 'public' and grantee = r
      ) then
        raise exception 'role % still holds a right on a table in public', r;
      end if;
      if exists (
        select 1 from pg_proc p join pg_namespace n on n.oid = p.pronamespace
         where n.nspname = 'public' and p.prosecdef
           and has_function_privilege(r, p.oid, 'EXECUTE')
      ) then
        raise exception 'role % can still call a SECURITY DEFINER function in public', r;
      end if;
      if exists (
        select 1 from pg_default_acl d
         where d.defaclrole = 'mse_migrator'::regrole
           and d.defaclacl::text like '%' || r || '=%'
      ) then
        raise exception 'mse_migrator still grants % by default', r;
      end if;
    end if;
  end loop;
end $$;
