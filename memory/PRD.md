# MyShopEdge. Product record

MyShopEdge is a bookkeeping and finance application for UK TikTok Shop sellers. It reads a
seller's orders, returns and settlement statements from TikTok, holds them in a double
entry ledger, and shows what the seller earned rather than what TikTok paid out.

The authoritative documents live in the repository root: `CLAUDE.md` holds the standing
instructions, `README_v0.2.md` holds the running status, and `A2` to `A29` hold the
rulings. `api/openapi.yaml` is the single source of truth for the API. This file is a short
platform record and does not replace them.

## Stack

- API service: FastAPI in `service/`, Python, the official `stripe` SDK, `psycopg` to Neon.
- Database: PostgreSQL on Neon, with hand rolled roles and row level security.
- Front end: Next.js in `web/`, JavaScript, Stack Auth for identity.

## Billing, completed 25 June 2026

The Stripe subscription flow was scaffolded and is now wired end to end.

- `service/app/billing.py`
  - `POST /v1/billing/subscription` now writes the `subscriptions` row through the
    `create_subscription` function before it creates the Stripe subscription, and it writes
    the returned subscription's state through the one write path at once, so the row does
    not sit at `incomplete` while it waits for a webhook.
  - `GET /v1/billing/subscription` is served, to the contract's `Subscription` schema. It
    reads the seller's own row under row level security. A row still marked `incomplete` is
    refreshed from Stripe once and written through the same path the webhook uses.
  - `POST /v1/webhooks/stripe` handles `customer.subscription.created`,
    `customer.subscription.updated`, `customer.subscription.deleted` and
    `invoice.payment_failed`. Each writes the subscription's current state, so a repeated
    event lands the same value twice. An event for a customer with no row is logged and
    accepted with a 200.
- `service/app/db.py` gained `create_subscription_row`, `apply_subscription_event` and
  `get_subscription_row`. Every billing write goes through the two SECURITY DEFINER
  functions from migration 0018 and through nothing else. `mse_app` holds no direct write
  on the `subscriptions` table.
- Front end screens S33 (`web/src/app/(site)/billing/`) and S34 (`.../billing/confirmed/`)
  were already built. They choose a plan, confirm the card's SetupIntent in the browser for
  Strong Customer Authentication, and read `GET /v1/billing/subscription` on return. They
  now have the endpoint they depended on.

### How it was verified

The verification that runs without a database, credentials or the network, per CLAUDE.md:

- `service/tests/test_contract_conformance.py`: every served route is in the contract, 27
  of 53 built.
- `service/tests/test_auth_verification.py`: 15 cases pass.
- `service/tests/test_handlers_smoke.py`: every handler executes and returns its model.
- Targeted unit checks of the Stripe mapping: status mapping, plan slug from metadata and
  from the price identifier fallback, period extraction at both the subscription and the
  item level, and event dispatch through a stubbed write path.

### Not verified here, and why

A live trial cannot be driven in this environment. The Neon connection string and the
Stripe keys are not present, and billing end to end is blocked on a Stripe session, which
`CLAUDE.md` records. The service runs on Render and the front end on Vercel, so a real
sign in, card confirmation and webpage delivery happen there rather than in this container.

## Rules that bind billing work

- Never create products or prices in the live Stripe account `acct_1RtsbgKUYBix7r5t`
  without an explicit instruction. Stripe prices are immutable once created.
- No secret is typed into the conversation. Secrets travel through environment variables.
- The prices are exclusive of VAT. Starter GBP 9.99, Growth GBP 24.99, Pro GBP 49.99.
- The contract governs the service. A route is not served unless the contract documents it.

## Remaining, by the repository's own record

The blocked table in `CLAUDE.md` is the authority. The order quota ruled in A16 counts
within a billing period and the period is now stored, so counting is unblocked. Account
suspension on a sustained `past_due` has a data source now that the status is written, and
the route into `accounts.status = 'suspended'` is still to be built.
