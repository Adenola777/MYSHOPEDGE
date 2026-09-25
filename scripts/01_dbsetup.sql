-- Run inside the myshopedge database as superuser. Local QA harness only.
create extension if not exists pgcrypto;
create extension if not exists citext;
alter schema public owner to mse_migrator;
grant all on schema public to mse_migrator;

-- Pre-create the neon_auth stand-in so migration 0011 (which references it) can apply
-- before 0016 (which would otherwise create it). Shape copied from migration 0016.
create schema if not exists neon_auth authorization mse_migrator;
create table if not exists neon_auth.users_sync (
  raw_json   jsonb       not null,
  id         text        not null,
  name       text,
  email      text,
  created_at timestamptz,
  updated_at timestamptz,
  deleted_at timestamptz
);
alter table neon_auth.users_sync owner to mse_migrator;
grant usage on schema neon_auth to mse_app, mse_analytics;
grant select on neon_auth.users_sync to mse_app, mse_analytics;
