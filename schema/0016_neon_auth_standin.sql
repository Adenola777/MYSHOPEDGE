-- 0016. A stand-in for neon_auth.users_sync on branches the provider does not reach.
--
-- Neon Auth is provisioned per project and bound to the project's default branch. A branch
-- forked before provisioning never receives the neon_auth schema, and it cannot be added
-- afterwards because the integration already exists for the project. That is exactly what
-- happened to the development branch on 22 September 2026, and it is why migration 0011
-- could not be applied there.
--
-- This migration creates the schema and a table of identical shape ONLY where the provider
-- has not already created one. On the default branch it does nothing at all, because the
-- real table is present and is maintained by Neon's sync.
--
-- The stand-in is empty and stays empty unless a test fills it. That is the correct
-- behaviour: account_identity.provider_record_missing then reads true for every account,
-- which is the state the view was written to detect, and a test can prove the detection
-- works without touching the provider.
--
-- The shape below is copied from the provisioned table on the default branch, read on
-- 22 September 2026. If Neon changes that shape, this file is wrong and the branches will
-- disagree again. The check at the end of this file is what will catch it.

create schema if not exists neon_auth;

do $$
begin
  if to_regclass('neon_auth.users_sync') is null then
    create table neon_auth.users_sync (
      raw_json   jsonb       not null,
      id         text        not null,
      name       text,
      email      text,
      created_at timestamptz,
      updated_at timestamptz,
      deleted_at timestamptz
    );

    comment on table neon_auth.users_sync is
      'Development stand-in, created by migration 0016. On the project default branch this '
      'table is created and maintained by Neon Auth and this migration does nothing. Here '
      'it exists so that account_identity can be created and exercised. It is not synced '
      'with the identity provider and must never be treated as authoritative.';
  end if;
end $$;

grant usage on schema neon_auth to mse_app, mse_analytics;
grant select on neon_auth.users_sync to mse_app, mse_analytics;

-- If the provider's shape ever stops matching this file, fail loudly here rather than
-- letting account_identity be created against a table that no longer has these columns.
do $$
declare
  missing text;
begin
  select string_agg(c, ', ') into missing
  from unnest(array['raw_json','id','name','email','created_at','updated_at','deleted_at']) as c
  where c not in (
    select column_name from information_schema.columns
     where table_schema = 'neon_auth' and table_name = 'users_sync'
  );
  if missing is not null then
    raise exception 'neon_auth.users_sync is missing columns this migration expects: %', missing;
  end if;
end $$;
