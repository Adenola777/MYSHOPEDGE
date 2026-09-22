-- 0015. The migration ledger.
--
-- Added 22 September 2026, after the development and production branches were found to
-- have diverged in both directions. Development was forked from production thirty-three
-- seconds before Neon Auth was provisioned, so it never received the neon_auth schema and
-- migration 0011 could only be applied to production. Everything built afterwards went to
-- development. The result was one branch holding the data and the corrected schema with no
-- identity bridge, and another holding the identity bridge four migrations behind.
--
-- Nothing in either database recorded which migrations had been applied. Fourteen
-- migrations had been applied by hand, to two branches, and the only record was the set of
-- filenames and a conversation. That is why the divergence went unnoticed, and it is the
-- defect this migration closes.
--
-- The table is owned by mse_migrator and is not readable by mse_app. The application has
-- no business knowing its own schema version, and an endpoint that behaves differently
-- depending on it would be hiding a deployment problem rather than reporting one.

create table if not exists schema_migrations (
  filename     text primary key,
  checksum     text        not null,
  applied_at   timestamptz not null default now(),
  applied_by   text        not null default current_user,
  -- Set when a migration is recorded after the fact rather than applied by the runner.
  -- The fourteen that predate this table are all backfilled, and saying so is more honest
  -- than a row that claims the runner applied them.
  backfilled   boolean     not null default false
);

comment on table schema_migrations is
  'One row per applied migration. The runner refuses to apply a filename that is already '
  'present, and refuses to start at all if a recorded checksum no longer matches the file '
  'on disk, because an edited migration means two branches can never be compared again.';

comment on column schema_migrations.checksum is
  'sha256 of the file contents at the moment it was applied.';

revoke all on schema_migrations from public;
grant select, insert on schema_migrations to mse_migrator;
