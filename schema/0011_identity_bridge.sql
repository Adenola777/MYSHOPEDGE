-- 0011_identity_bridge.sql
--
-- Connects accounts.auth_subject to the identity provider record.
--
-- The provider is Neon Auth, which runs on Stack Auth and maintains a synchronised
-- copy of its user records in neon_auth.users_sync on this branch. users_sync.id is
-- the JWT subject claim, which is what accounts.auth_subject has always held.
--
-- No foreign key is declared from accounts.auth_subject to neon_auth.users_sync.id.
-- users_sync is written by the provider's sync process, and a constraint on it would
-- break that sync the first time a user was deleted at the provider. The relationship
-- is therefore checked by the view below rather than enforced by the database.
--
-- app_account_id() is unchanged. The application still sets app.account_id with
-- set_config('app.account_id', $1, true) after verifying the JWT against the provider's
-- JWKS endpoint. It never takes a subject from a client without verifying it first.

grant usage on schema neon_auth to mse_app, mse_analytics;
grant select on neon_auth.users_sync to mse_app, mse_analytics;

create view account_identity as
select a.id           as account_id,
       a.auth_subject,
       a.email        as account_email,
       u.email        as provider_email,
       u.name         as provider_name,
       u.created_at   as provider_created_at,
       u.deleted_at   as provider_deleted_at,
       (u.id is null) as provider_record_missing
from accounts a
left join neon_auth.users_sync u on u.id = a.auth_subject;

comment on view account_identity is
  'Bridges accounts.auth_subject to the identity provider record in neon_auth.users_sync. '
  'No foreign key is declared, because users_sync is maintained by the provider sync and a '
  'constraint would break it. provider_record_missing true means an account exists with no '
  'matching identity, which is a defect and must raise a discrepancy. The application sets '
  'app.account_id from the verified JWT subject; it never trusts a subject sent by a client.';

grant select on account_identity to mse_app, mse_analytics;
