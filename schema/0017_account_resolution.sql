-- 0017. Turning a verified identity into an account.
--
-- The policy on accounts is `id = app_account_id()`, and row level security is FORCED, so
-- it applies to the table owner as well. At the moment a request arrives there is no
-- account id yet, which means the one lookup that has to happen first is the one lookup
-- the policy forbids.
--
-- The way out is a SECURITY DEFINER function owned by mse_migrator, which carries
-- BYPASSRLS. That makes these two functions the only code in the system that reads outside
-- tenant scope, so they are written to be as small as they can be. Each takes scalar
-- arguments, each contains one statement, and neither can express anything else. mse_app
-- receives EXECUTE and nothing more.
--
-- search_path is pinned on both. A SECURITY DEFINER function without a pinned search_path
-- can be redirected to a caller's own table of the same name, which would hand the caller
-- the definer's rights.

-- Resolve. The only input is the subject from a verified JWT.

create or replace function resolve_account(p_subject text)
  returns uuid
  language sql
  stable
  security definer
  set search_path = public, pg_temp
as $$
  select id from accounts where auth_subject = p_subject and status = 'active'
$$;

alter function resolve_account(text) owner to mse_migrator;
revoke all on function resolve_account(text) from public;
grant execute on function resolve_account(text) to mse_app;

comment on function resolve_account(text) is
  'Returns the account for a verified provider subject, or null. A suspended or deleted '
  'account returns null, so suspension takes effect on the next request rather than at the '
  'next sign in. The caller must have verified the JWT before calling this. Nothing that '
  'reaches this function may come from a header, a body or a query string.';

-- Create, on a first sign in.
--
-- A seller can hold a valid token and have no account row, because the identity provider
-- and this database are separate systems. Ruled 22 September 2026: the account is created
-- on the first verified sign in rather than by a separate sign-up call, because the
-- alternative leaves that seller authenticated with no way in.

create or replace function create_account(
  p_subject      text,
  p_email        text,
  p_display_name text
) returns uuid
  language plpgsql
  security definer
  set search_path = public, pg_temp
as $$
declare
  v_id uuid;
begin
  -- The conflict clause makes two simultaneous first requests produce one account rather
  -- than one account and one error. The no-op update is what allows RETURNING to give back
  -- the existing row's id.
  insert into accounts (auth_subject, email, display_name, locale, timezone, status)
  values (p_subject, p_email, p_display_name, 'en-GB', 'Europe/London', 'active')
  on conflict (auth_subject) do update set auth_subject = excluded.auth_subject
  returning id into v_id;

  return v_id;
exception
  when unique_violation then
    -- The email is already held by a different subject. This happens when a seller signs
    -- up with a password and later with a social provider, or the reverse. It is a real
    -- situation with a real answer, which is to link the identities, and it is not
    -- something to paper over by creating a second account.
    raise exception 'email_already_linked_to_another_identity'
      using errcode = 'unique_violation',
            hint = 'Sign in with the method used originally, then link the new one.';
end
$$;

alter function create_account(text, text, text) owner to mse_migrator;
revoke all on function create_account(text, text, text) from public;
grant execute on function create_account(text, text, text) to mse_app;

comment on function create_account(text, text, text) is
  'Creates an account for a verified subject on first sign in, or returns the existing one. '
  'Every value comes from verified JWT claims. Never call it with anything a client sent.';
