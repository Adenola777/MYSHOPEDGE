-- 0023. Somewhere to keep an Idempotency-Key, so that a repeated write returns its first
-- result rather than acting twice.
--
-- The contract's IdempotencyKey parameter promises exactly that: "A repeat with the same key
-- returns the first result rather than acting twice. Keys are retained for 24 hours." No
-- table held a key, so until this migration the promise could not be kept. It matters most
-- for a stock adjustment, where a request retried after a dropped connection would otherwise
-- move the count twice.
--
-- The stored response is the body the first request returned. A repeat carrying the same key
-- with a different body is refused, because answering it with the first result would tell
-- the caller that a different request succeeded.
--
-- Keys are per account and per operation, so two operations can never collide on a key. A
-- key older than 24 hours is deleted when it is next presented, which is why `mse_app` holds
-- delete here and nowhere on the ledger.
--
-- NOT YET APPLIED. Written 24 September 2026. It reaches a branch only through
-- scripts/migrate.py. Until it is applied, resolveDiscrepancy and createStockAdjustment fail
-- on the first request that carries a key.

create table idempotency_keys (
  account_id uuid not null references accounts(id),
  operation text not null,
  key text not null check (length(key) between 8 and 128),
  request_hash text not null,
  status_code integer not null,
  response jsonb not null,
  created_at timestamptz not null default now(),
  primary key (account_id, operation, key)
);

create index idempotency_keys_created_at_idx on idempotency_keys (created_at);

alter table idempotency_keys enable row level security;
alter table idempotency_keys force row level security;

create policy idempotency_keys_own on idempotency_keys
  using (account_id = app_account_id())
  with check (account_id = app_account_id());

grant select, insert, delete on idempotency_keys to mse_app;

comment on table idempotency_keys is
  'The first response to a write that carried an Idempotency-Key, kept 24 hours, as the '
  'IdempotencyKey parameter in api/openapi.yaml promises.';

do $$
begin
  if not exists (
    select 1 from pg_class c join pg_namespace n on n.oid = c.relnamespace
     where n.nspname = 'public' and c.relname = 'idempotency_keys'
       and c.relrowsecurity and c.relforcerowsecurity
  ) then
    raise exception 'idempotency_keys must have row level security enabled and forced';
  end if;
end $$;
