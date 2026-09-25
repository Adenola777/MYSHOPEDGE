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

## Remediation programme, agreed 26 June 2026

The owner approved a phased plan to make the application fully functional. It is executed
inside a local harness built from this repository (local PostgreSQL, local ES256 tokens,
the platform Stripe test sandbox), so no live infrastructure is touched, and each phase is
verified before the next begins.

Owner decisions on record: use the local harness; test Stripe with the platform test
sandbox; cost file storage to be settled at its phase, S3 style recommended over Vercel
Blob because a Python service cannot do Vercel Blob signed uploads (A10.8); sign-in on
preview URLs wanted, owner to set a stable custom preview domain; Render cold start to be
handled with a keep-warm ping.

### Phase 0, local harness. Done 26 June 2026.
Scripts under `/app/scripts` build the database (`00_superuser.sql`, `01_dbsetup.sql`,
`local_migrate.py`) and run the service (`run_service.sh`). The build backfills 0001-0009,
pre-creates the `neon_auth` stand-in so 0011 applies before 0016, and relaxes two NOT NULL
columns the seed omits. The service runs on 127.0.0.1:8801 against the seeded seller, with
row level security proven by `/me` and `/shops`.

### Phase 1, Stripe billing end to end. Done 26 June 2026.
The trial, the SetupIntent, the `GET /billing/subscription` endpoint and the webhook run
against the platform Stripe test sandbox and the real Postgres. The subscriptions row moves
incomplete to trialing to past_due to active to canceled through signed webhook events, the
replay is idempotent, an unknown customer is accepted with 200, and a forged signature is
refused with 400. Verified by the testing agent, 9 of 9, `/app/test_reports/iteration_1.json`,
and by `/app/service/tests/test_billing_local_harness.py`. The owner runs the same
`setup_stripe.py` step against the live account to go live, which is theirs by rule 3.

### Remaining phases, in order
2. Access and hosting. Owner confirms sign-in on the used domain and the keep-warm ping.
3. TikTok ingestion, token refresh and expected payouts. Needs the owner's Seller Developer
   custom app credentials on GBGBLCRKQTEX. Cannot be verified live from the harness.
4. Cost file uploads, seven operations, once storage is chosen.
5. Tax features. VAT monitor and tax profile done 26 June 2026; set-aside amount pending rules.
6. Analytics reads and the export worker.
7. Account and shop management, the order quota, and account suspension. Needs the four
   `checkReturnItem` rulings.
8. The remaining screens, and the privacy and terms pages.
9. Test data across months and the clock change, the three tooling faults, and the data
   protection confirmations.

### Phase 5 progress, tax. Done 26 June 2026 (VAT monitor, tax profile).
`service/app/tax.py` adds getTaxProfile, putTaxProfile, getVatMonitor and getSetAside, to
the contract. The VAT threshold is read from `reference_rules`, not hard-coded; the rule was
seeded from HMRC (GBP 90,000, effective 1 April 2024) by `testdata/reference_rules_seed.sql`.
Verified against the real stack: the rolling twelve-month turnover reads GBP 862.00, which
reconciles with the Money screen; the threshold, headroom and month buckets are correct; a
VAT-registered profile without a date is refused with 422; a forbidden shop returns 403.
Set-aside returns `no_tax_profile` with no profile, and null with a basis note once a profile
exists, because the income-tax and NI reference rules and the set-aside method are not yet
ruled. Two owner inputs remain for the numbers: the income-tax and NI reference values, and
the set-aside method.
