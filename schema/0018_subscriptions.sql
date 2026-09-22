-- 0018. Billing state, in the database.
--
-- Until this migration there was none. S33 takes a card, S34 confirms it, the Stripe
-- webhook route exists, and nothing was ever written down. Three things were broken by
-- that and only one of them was noticed.
--
--   1. The order quota ruled in A16 cannot count anything, because a billing period is
--      the thing it counts within and no billing period was stored.
--   2. S38 has no data source. invoice.payment_failed arrives, and there is nowhere to
--      record that the account is past due, so the screen would have nothing to show.
--   3. accounts.status carries 'suspended' with no route into it, which A14 noted in
--      September and left open.
--
-- One subscription per account, enforced by the unique constraint on account_id. The
-- product sells one shop per account and one plan per shop, ruled in A12.7.

create table subscriptions (
  id                     uuid primary key default gen_random_uuid(),
  account_id             uuid not null unique references accounts(id),
  plan_slug              text not null check (plan_slug in ('starter','growth','pro')),
  status                 text not null check (status in
                           ('trialing','active','past_due','canceled','incomplete')),
  stripe_customer_id     text not null unique,
  stripe_subscription_id text unique,
  trial_end              timestamptz,
  current_period_start   timestamptz,
  current_period_end     timestamptz,
  cancel_at_period_end   boolean not null default false,
  created_at             timestamptz not null default now(),
  updated_at             timestamptz not null default now()
);

comment on table subscriptions is
  'Billing state mirrored from Stripe. Stripe remains the source of truth. This table '
  'exists so the product can answer questions without a network call: which plan, which '
  'period, and whether a payment has failed.';

comment on column subscriptions.current_period_end is
  'The end of the billing period. The order quota in A16 counts within the period rather '
  'than the calendar month, because a seller who signs up on the 20th does not get a new '
  'allowance eleven days later.';

alter table subscriptions enable row level security;
alter table subscriptions force row level security;

create policy subscriptions_tenant on subscriptions
  using (account_id = app_account_id())
  with check (account_id = app_account_id());

grant select on subscriptions to mse_app;
grant select on subscriptions to mse_analytics;

-- The webhook writes through this and through nothing else.
--
-- A Stripe webhook arrives with no account context, because Stripe does not know what an
-- account id is. It carries a customer id. That means the write cannot happen inside
-- db.tenant(), and it must not be allowed to happen as a general INSERT either. The same
-- shape as resolve_account applies: one SECURITY DEFINER function, one statement, scalar
-- arguments only, owned by mse_migrator, pinned search_path, EXECUTE to mse_app.
--
-- mse_app deliberately holds no INSERT, UPDATE or DELETE on this table. A compromised
-- request cannot move itself onto a larger plan or clear its own past_due.

create or replace function apply_subscription_event(
  p_stripe_customer_id     text,
  p_stripe_subscription_id text,
  p_plan_slug              text,
  p_status                 text,
  p_trial_end              timestamptz,
  p_period_start           timestamptz,
  p_period_end             timestamptz,
  p_cancel_at_period_end   boolean
) returns uuid
  language plpgsql
  security definer
  set search_path = public, pg_temp
as $$
declare
  v_account_id uuid;
  v_id         uuid;
begin
  select account_id into v_account_id
    from subscriptions where stripe_customer_id = p_stripe_customer_id;

  if v_account_id is null then
    -- An event for a customer we never recorded. This is not an error to swallow. It
    -- means the checkout wrote nothing, or the event belongs to another environment's
    -- Stripe account, and both need to be seen rather than absorbed.
    raise exception 'unknown_stripe_customer'
      using hint = 'No subscription row carries this customer id.';
  end if;

  update subscriptions set
    stripe_subscription_id = coalesce(p_stripe_subscription_id, stripe_subscription_id),
    plan_slug              = coalesce(p_plan_slug, plan_slug),
    status                 = p_status,
    trial_end              = coalesce(p_trial_end, trial_end),
    current_period_start   = coalesce(p_period_start, current_period_start),
    current_period_end     = coalesce(p_period_end, current_period_end),
    cancel_at_period_end   = coalesce(p_cancel_at_period_end, cancel_at_period_end),
    updated_at             = now()
  where stripe_customer_id = p_stripe_customer_id
  returning id into v_id;

  return v_id;
end
$$;

alter function apply_subscription_event(text, text, text, text, timestamptz, timestamptz,
                                        timestamptz, boolean) owner to mse_migrator;
revoke all on function apply_subscription_event(text, text, text, text, timestamptz,
                                                timestamptz, timestamptz, boolean) from public;
grant execute on function apply_subscription_event(text, text, text, text, timestamptz,
                                                   timestamptz, timestamptz, boolean) to mse_app;

-- Creating the row at checkout, before any webhook can arrive.

create or replace function create_subscription(
  p_account_id         uuid,
  p_plan_slug          text,
  p_stripe_customer_id text
) returns uuid
  language sql
  security definer
  set search_path = public, pg_temp
as $$
  insert into subscriptions (account_id, plan_slug, status, stripe_customer_id)
  values (p_account_id, p_plan_slug, 'incomplete', p_stripe_customer_id)
  on conflict (account_id) do update
    set plan_slug = excluded.plan_slug,
        stripe_customer_id = excluded.stripe_customer_id,
        updated_at = now()
  returning id
$$;

alter function create_subscription(uuid, text, text) owner to mse_migrator;
revoke all on function create_subscription(uuid, text, text) from public;
grant execute on function create_subscription(uuid, text, text) to mse_app;

comment on function create_subscription(uuid, text, text) is
  'Called from the checkout once Stripe has issued a customer id. The conflict clause lets '
  'a seller who abandons the card step and comes back change plan without stranding a row.';
