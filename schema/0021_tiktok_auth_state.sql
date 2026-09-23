-- 0021. Somewhere to keep the authorisation state, which the contract requires and the
-- schema had no room for.
--
-- `/connections/tiktok/authorize` says in the contract that the state value "is single use,
-- expires in ten minutes and is bound to this account", and that "the callback rejects any
-- state it did not issue". A23.5 records TikTok's own recommendation for the same thing.
-- Nothing in the schema could hold one. The two handlers could not be written.
--
-- WHY THIS IS NOT DECORATION
--
-- `/connections/tiktok/callback` carries `security: []` in the contract. It is reached by a
-- browser redirect from TikTok, not by the client application, so it arrives with no bearer
-- token. The only thing that says which seller the callback belongs to is the state.
--
-- A callback that accepts any `code` it is handed, and trusts whatever account the request
-- seems to be for, connects a shop to an account that never asked for it. The seller whose
-- account it lands on then sees somebody else's orders, costs and settlements, which is the
-- one failure this product cannot have.
--
-- THE STATE IS STORED AS A DIGEST
--
-- The raw state travels in a URL. It goes through TikTok, through the seller's browser,
-- into their history, and very likely into a log somewhere. Storing it verbatim means a
-- read of this table hands over working states.
--
-- Only the SHA-256 is kept. The service hashes on the way in and on the way out, so a copy
-- of this table is worth nothing. This is the same reasoning as never storing a password,
-- and it costs one hash call.
--
-- A digest needs no pgcrypto, because the hashing happens in the service.
--
-- CONSUMPTION IS A SECURITY DEFINER FUNCTION, AND DELIBERATELY SO
--
-- Every other read in this service runs inside `tenant()`, which sets `app.account_id` and
-- lets row level security do the rest. The callback cannot, because it has no account yet.
-- Finding the account IS the thing it is trying to do.
--
-- So `consume_tiktok_auth_state` follows `resolve_account` from 0017: it elevates for one
-- narrow statement, takes a digest and nothing else, and returns an account id or nothing.
-- It cannot be induced to return a different account's row, because the digest is the only
-- input and the caller cannot construct one without already holding the state.
--
-- It consumes in the same statement that it reads. A state cannot be spent twice even if
-- two callbacks arrive together, because the UPDATE takes the row lock.

create table if not exists tiktok_auth_state (
  state_sha256 text        primary key,
  account_id   uuid        not null references accounts(id),
  return_to    text,
  created_at   timestamptz not null default now(),
  expires_at   timestamptz not null,
  consumed_at  timestamptz
);

create index if not exists tiktok_auth_state_expires_at_idx
  on tiktok_auth_state (expires_at);

alter table tiktok_auth_state enable row level security;
alter table tiktok_auth_state force row level security;

drop policy if exists tiktok_auth_state_tenant on tiktok_auth_state;
create policy tiktok_auth_state_tenant on tiktok_auth_state
  using (account_id = app_account_id())
  with check (account_id = app_account_id());

grant insert on tiktok_auth_state to mse_app;

comment on table tiktok_auth_state is
  'Single use CSRF state for the TikTok shop authorisation redirect. A row is written by '
  '/connections/tiktok/authorize inside the seller''s own scope, and spent by '
  '/connections/tiktok/callback through consume_tiktok_auth_state, which is the only way '
  'to read it. Rows are short lived by design and carry nothing of value once consumed.';

comment on column tiktok_auth_state.state_sha256 is
  'SHA-256 of the state, never the state. The raw value travels in a URL through TikTok '
  'and the seller''s browser history, so a readable copy here would be a working key.';

comment on column tiktok_auth_state.return_to is
  'Where to send the seller after the callback. The contract requires this to be an '
  'allow-listed MyShopEdge path, and the service checks that before writing the row. An '
  'open redirect on this field is an account takeover, so it is validated on the way in '
  'rather than on the way out.';

-- Spend a state and say whose it was. Returns no row for a state that is unknown, already
-- spent, or past its expiry, and the caller cannot tell those three apart. That is
-- deliberate: distinguishing them tells an attacker which guesses were close.
create or replace function consume_tiktok_auth_state(p_state_sha256 text)
  returns table (account_id uuid, return_to text)
  language sql
  volatile
  security definer
  set search_path = public, pg_temp
as $$
  update tiktok_auth_state
     set consumed_at = now()
   where state_sha256 = p_state_sha256
     and consumed_at is null
     and expires_at > now()
  returning tiktok_auth_state.account_id, tiktok_auth_state.return_to
$$;

alter function consume_tiktok_auth_state(text) owner to mse_migrator;
revoke all on function consume_tiktok_auth_state(text) from public;
grant execute on function consume_tiktok_auth_state(text) to mse_app;

comment on function consume_tiktok_auth_state(text) is
  'Spends one authorisation state and returns the account it was issued to, or no row. '
  'SECURITY DEFINER for the same reason as resolve_account: the TikTok callback carries no '
  'bearer token, so it has no account context, and finding the account is the point of the '
  'call. The digest is the only input. Expired and already spent states are indistinguishable '
  'from unknown ones in the result, on purpose.';

-- Expired rows are rubbish and nothing schedules their removal, because this project has no
-- job runner yet. Deleting a bounded number on each consumption keeps the table from growing
-- without adding infrastructure. It is a small opportunistic sweep and not a guarantee.
create or replace function sweep_tiktok_auth_state()
  returns integer
  language sql
  volatile
  security definer
  set search_path = public, pg_temp
as $$
  with gone as (
    delete from tiktok_auth_state
     where state_sha256 in (
       select state_sha256 from tiktok_auth_state
        where expires_at < now() - interval '1 day'
        limit 500
     )
    returning 1
  )
  select count(*)::integer from gone
$$;

alter function sweep_tiktok_auth_state() owner to mse_migrator;
revoke all on function sweep_tiktok_auth_state() from public;
grant execute on function sweep_tiktok_auth_state() to mse_app;

comment on function sweep_tiktok_auth_state() is
  'Deletes up to 500 states that expired more than a day ago. Called opportunistically by '
  'the callback. A day of grace is kept so that a support question about a failed connection '
  'can still be answered. This is not a substitute for a scheduled job and should be replaced '
  'by one when the service has a host that can run them.';

do $$
begin
  if to_regclass('public.tiktok_auth_state') is null then
    raise exception 'tiktok_auth_state was not created';
  end if;

  if not exists (
    select 1 from pg_class c join pg_namespace n on n.oid = c.relnamespace
     where n.nspname = 'public' and c.relname = 'tiktok_auth_state'
       and c.relrowsecurity and c.relforcerowsecurity
  ) then
    raise exception 'tiktok_auth_state must have row level security enabled and forced';
  end if;
end $$;
