-- MyShopEdge v0.2 migration 0001: roles and grants.
-- Closes the gap where the pack names a restricted database role (LED-1, TC-LED-04)
-- without defining one anywhere.

-- Three roles, and no others. The application uses exactly one of them.

-- Roles are cluster-wide, not per database, so this migration is idempotent and is run
-- once per cluster. Running it again against a second database must not fail.
do $$
begin
  -- Owns every object. No login. Migrations are run by a role granted this one.
  if not exists (select 1 from pg_roles where rolname = 'mse_owner') then
    create role mse_owner nologin;
  end if;
  -- The only role the application connects as. Subject to row-level security.
  -- It must never own an object and must never be granted BYPASSRLS.
  if not exists (select 1 from pg_roles where rolname = 'mse_app') then
    create role mse_app login nobypassrls;
  end if;
  -- Read-only, for analysis. Subject to row-level security.
  if not exists (select 1 from pg_roles where rolname = 'mse_analytics') then
    create role mse_analytics login nobypassrls;
  end if;
  -- Runs migrations. Granted ownership and allowed past row-level security so that
  -- backfills can reach every shop. Never used by the application or by a person.
  if not exists (select 1 from pg_roles where rolname = 'mse_migrator') then
    create role mse_migrator login bypassrls;
  end if;
end $$;
grant mse_owner to mse_migrator;
grant mse_app, mse_analytics to mse_migrator;

-- The role that bootstraps the database must be able to assume mse_app, or the
-- verification harness cannot test tenant isolation over a single connection.
-- On a managed platform there is no superuser, so this cannot be assumed.
do $$
begin
  execute format('grant mse_owner, mse_app, mse_analytics to %I', current_user);
end $$;

-- Objects belong to the owner, not to whoever happened to run the script.
alter schema public owner to mse_owner;

-- Connection and usage.
grant usage on schema public to mse_app, mse_analytics;
revoke all on schema public from public;

-- The application reads and writes.
grant select, insert, update, delete on all tables in schema public to mse_app;
grant usage, select on all sequences in schema public to mse_app;

-- Analysis reads only.
grant select on all tables in schema public to mse_analytics;

-- Anything added later inherits the same grants.
alter default privileges for role mse_owner in schema public
  grant select, insert, update, delete on tables to mse_app;
alter default privileges for role mse_owner in schema public
  grant select on tables to mse_analytics;
alter default privileges for role mse_owner in schema public
  grant usage, select on sequences to mse_app;

-- The account identity is set per transaction, never per session, so a leaked
-- connection from a pool cannot carry one seller's identity into another's request.
comment on function app_account_id() is
  'Reads app.account_id. The application must set it with set_config(''app.account_id'', $1, true), '
  'where true makes the setting local to the transaction. A session-level setting is a defect.';

-- reference_rules is deliberately not tenant-scoped. It holds the shared tax thresholds,
-- allowances, rates and dates that TAX-6 requires, with their correct-as-at dates, and
-- every seller reads the same rows. It therefore carries no row-level security policy.
-- It must still be read-only to the application: a rule change is a deployment, made by
-- the migrator, not something a seller's session can reach.
revoke insert, update, delete, truncate on reference_rules from mse_app;
comment on table reference_rules is
  'Shared reference data (TAX-6). No row-level security by design, because every seller '
  'reads the same rules. Read-only to mse_app; changed only by mse_migrator.';
