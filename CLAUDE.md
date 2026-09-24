# MyShopEdge. Instructions for Claude Code

Written 23 September 2026, when the project moved from a hosted session to Claude Code
running on Adenola's own machine. Everything a new session needs is here, so no previous
transcript has to be read.

## What this is

MyShopEdge is a bookkeeping and finance application for UK TikTok Shop sellers. It reads a
seller's orders, returns and settlement statements from TikTok, holds them in a double entry
ledger, and shows the seller what they actually earned rather than what TikTok paid out.

The owner is Adenola Adegbesan, trading through Inspirecraft Global Limited, Leicester.

## How to work on it

These are standing instructions from the owner. They hold until he changes them.

1. **One action at a time, and get approval before proceeding.** He lifted this for a
   defined batch once. Treat it as in force unless he lifts it again for a named batch.
2. **No secret is ever typed into the conversation.** Not the TikTok app secret, not a
   database password, not a Stripe key. Secrets travel through environment variables or
   through his own terminal.
3. **Never create products or prices in the live Stripe account `acct_1RtsbgKUYBix7r5t`**
   without an explicit instruction. Stripe prices are immutable once created.
4. **Write in his house style.** Every sentence carries a subject and a verb. No em dashes
   and no en dashes. No clipped marketing phrases. Modest things are described honestly
   rather than inflated. Nobody is praised by diminishing anybody else.
5. **Do not end a reply with a next steps recommendation.** Answer what was asked and stop.
   He sets the agenda.
6. **Run the query rather than reading the code.** Every serious fault on this project was
   found by executing something, and none were found by reading. The list is in the section
   on faults below.
7. **No assumption coding. Facts only.** This is a hard rule and it outranks speed.

   A fact is something that was read from the file, returned by the query, printed by the
   call, or written in the vendor's own documentation. Everything else is an assumption,
   including a recollection of what a file contains, a reasonable inference about how an
   API behaves, and a memory of a decision taken earlier in the project.

   In practice this means five things.

   - Before stating what code does, open it. Do not describe a function from its name.
   - Before stating what an API returns, call it or cite the vendor's page. A field is not
     present because it would be sensible for it to be present.
   - Before stating what a table holds, query it. A migration having been written is not
     evidence that it was applied.
   - When a fact cannot be obtained, say so plainly and name what is unknown. An unanswered
     question recorded as unanswered is worth more than a plausible guess, because the guess
     gets built on.
   - Mark unverified work as unverified, in the file itself rather than in a message. A
     script that has never run says so at the top.
   - **A vendor's documentation is not a fact about this project.** It describes what the
     vendor generally does. What this installation runs is in its own configuration, and
     reading that costs one call. On 23 September a documentation page was taken as
     evidence about this project twice, and both times the configuration said something
     different. The second time it would have stopped every seller signing in. See A25.

   The reason is on the record. Authentication verified the wrong signing algorithm for a
   day, and its tests passed because the fixtures were generated from the same assumption.
   Five views leaked across tenants while a row level security check that queried base
   tables reported clean. The settlement endpoint was pinned to an API version that omits
   every reserve field, on the strength of a document rather than a call. None of these were
   careless. Each was a reasonable assumption that nobody checked.

## The contract is the source of truth

`api/openapi.yaml` holds 58 operations across 53 paths. Rule 1 of A13 says the service
implements the contract and never the other way round. A test enforces it:

```
cd service && python3 tests/test_contract_conformance.py
```

It generates the schema from the actual FastAPI handlers and fails if anything is served
that the contract does not document. It does not check the reverse, because most paths are
not built yet and that is expected.

## Where the build actually stands

The specification is close to complete. The application is not. As of 23 September:

| Layer | State |
|---|---|
| Rulings, terminology, screens, data model, API contract | Done |
| Schema | Through 0024 on all three branches, 25 migrations recorded on each, and the three schema fingerprints match exactly (checked 24 September). 0022, 0023 and 0024 were applied on 24 September with the owner's authority through the Neon connection, which runs as `mse_migrator`, rather than through `migrate.py`, so that no connection string entered the session. Each migration and its `schema_migrations` row went in one transaction with the file's SHA-256, as the runner does, so `migrate.py --status` reads them as applied. The notes inside 0022 and 0023 saying "not yet applied" are stale and stay, because an applied migration is never edited. See the Data API section below for 0024 |
| Backend | 27 of 53 contract paths. Added on 24 September: me, shops, a variant's cost, cost coverage, resolving a discrepancy, a stock adjustment, Needs you, sync status, the returns list, return metrics, and listing and updating notifications. Cost uploads, exports and expected payouts are not served, for the reasons in the blocked table below |
| Authentication | ES256 verified against the provider's fetched JWKS, email read from `users_sync`, 15 tests passing. `NEON_AUTH_ISSUER` and `NEON_AUTH_AUDIENCE` are not set on Render, because no real token has been seen. Until they are, the service answers 503 `auth_unconfigured` and logs the `iss` and `aud` of any token whose signature checks out, and nothing else from it |
| Billing | Screens built. The three products and prices exist in the live Stripe account as of 23 September. Nothing is wired to them yet |
| TikTok integration | Authorisation is built end to end. `app/connections.py` holds both endpoints, the signing algorithm, AES-256-GCM token storage and the state store in migration 0021. Fourteen smoke cases cover it. `_sign` has never made a live call, so the first real request is its test. See A23, A27 and A28 |
| Front end | 13 screens of 36 built: S6, S7, S9, S10, S11, S14 with its actions, S17, S21, S22, S25, S26, S33 and S34, plus `/shops`, which takes a seller to their shop, and `/handler`, Stack's own sign-in pages. `web/src/lib/api.js` attaches the signed in seller's token to every request since 24 September. No real sign-in has happened yet, so that path is unverified. S17 lacks the privacy notice and terms links A14 requires, because neither page exists. `SCREENS.md` is the register |
| Figma | Unreadable. The Starter plan call limit refuses every read of the file, on 22 and 24 September. It holds frames that predate A15, so it is out of date whatever it holds. `SCREENS.md` explains. The wireframes are committed at `design/wireframes/` |
| Deployment | The front end is live on Vercel production and redeploys on every merge to `main`, checked 24 September. It has no API behind it: `/billing` was checked and shows its error state. The Python service has no host |

The honest summary is that the thinking is done and the building has started.

## The documents

`A2` to `A29` are the rulings, one file per action. A29 holds the dashboard rules and the
rule that Python owns every financial and business rule. **A29.11 sets which document wins:
the product rulings and the contract govern the master engineering skill, and a provider's
documentation governs only facts about that provider.** A29.12 states why MyShopEdge exists. They are decisions rather than notes, so
a ruling is changed by editing its document rather than by remembering a conversation.

`README_v0.2.md` carries the running status, the open items by owner, and the account wiring.
Update it when a decision changes, because it is the file he reads first.

`RUNBOOK_tiktok_connection.md` is the five step procedure for connecting a real shop. It is
written to be followed once.

## The infrastructure

| Piece | Value |
|---|---|
| Database | Neon project `super-mouse-64697125`, PostgreSQL 16, `aws-eu-west-2`, London |
| Branches | production `br-plain-sea-zaphlsmw`, staging `br-little-rice-zatxxnda`, development `br-little-mode-zagjq5bg` |
| Neon account | The direct account under adenola.adegbesan@gmail.com |
| Identity | Neon Auth provisioning **Stack Auth**. `auth_provider: stack` in the project's own configuration. JWKS on `api.stack-auth.com`, signing **ES256** |
| GitHub | `Adenola777/My-ShopEdge` is the one Vercel is wired to. `MyShopEdge-` also exists |
| Vercel | team `coterie448-8267's projects`, project `my-shop-edge`, root `web`, functions in `lhr1` |
| Stripe | live `acct_1RtsbgKUYBix7r5t`, sandbox `acct_1Rtsby4GHrXoTk1L` |

**The account split matters.** GitHub and Vercel sit under coterie448@gmail.com. Neon sits
under adenola.adegbesan@gmail.com. A third Neon project, `holy-glitter-85206770`, was
provisioned through the Vercel Marketplace and therefore lives in a Neon organisation that
Vercel creates and manages, which is why a direct account API key cannot see it. It holds
none of the work. The product runs on `super-mouse-64697125`.

The Next.js front end never touches the database. It calls the API over HTTP through
`NEXT_PUBLIC_API_BASE_URL`. Any `DATABASE_URL` sitting on the Vercel project is inert.

## The database rules that are easy to break

Four hand rolled roles exist: `mse_owner`, `mse_app`, `mse_analytics`, `mse_migrator`.
`FORCE ROW LEVEL SECURITY` is on, and `app_account_id()` scopes every tenant query.

**Every view must carry `security_invoker = true`.** Without it a view runs as its owner.
`mse_migrator` holds `BYPASSRLS`, so a view without that setting bypasses row level security
entirely. Migration 0019 fixed five views that leaked across tenants and added a `DO` block
that raises if any public view lacks the setting. Adding a view without it will fail that
check, and that is deliberate.

## The Neon Data API is off, and must stay off

On 24 September the Neon Data API was found active on production, exposing `public` over
HTTP to any signed in Stack user as the role `authenticated`. A default privilege on
`mse_migrator` granted that role every right on every new table, sequence and function.
Tenant tables held, because a Data API client cannot set `app.account_id`, but
`schema_migrations` and `reference_rules` were writable and the six SECURITY DEFINER
functions were callable, including `create_subscription` and `apply_subscription_event`.
Production held no accounts, so nothing was harmed.

The Data API on production was deleted the same day, and migration 0024 revoked every right
`authenticated` and `anonymous` held in `public`, removed the default privileges, and dropped
Neon's sample table `playing_with_neon`. Its closing check raises if either role regains a
table right or a SECURITY DEFINER function. The product never uses the Data API: the front
end calls the service and the service connects as `mse_app`. Do not switch it back on.

## Faults that cost real time, so they are not repeated

Each of these was found by running something, and each survived reading.

1. **Five views leaked across accounts.** Proven by scoping to an account owning nothing.
   The base tables returned 0 and 0. `settlement_reconciliation` returned 3,
   `settlement_totals_check` returned 3 and `return_reconciliation` returned 7. The leak
   was invisible with one account, and the earlier check had queried base tables.
2. **Authentication verified the wrong algorithm.** The code checked ES256 and RS256 against
   a provider that signs ES256. It was then "corrected" to EdDSA, which was also wrong, and
   the tests were rewritten to share the new assumption and passed again. Every real token
   would have been refused either way. The
   old tests passed because the fixtures were signed with the same wrong assumption. There
   test now asserts `ALGORITHMS` against a recorded copy of the provider's real JWKS, so
   changing it without refetching fails in either direction.
3. **Settlement detail was pinned to the wrong API version.** A11 said finance `202309`,
   which returns 69 fields. The reserve fields exist only in `202501`, which returns 131.
   Using 202309 would have dropped every reserve. A17 corrects it.
4. **A GROUP BY fault in the settled orders query.** It ordered by `o.order_created_at`,
   which is not in the GROUP BY. Fixed to `order by min(o.order_created_at)`.
5. **The development ledger has no cash basis.** Found 24 September by querying it.
   `settlement_month` is empty on all 119 ledger entries, including the 88 that carry a
   `settlement_id`, because `testdata/seed.sql` left the column out. The seed is now rebuilt
   from `rows.json` (A29.10), but the development branch has not been reloaded. The ledger
   is append-only, so reloading it needs the owner's approval.
6. **A4.119 was wrong about return postage.** It said return postage never passes through
   a TikTok statement. The real payload carries `return_shipping_fee_amount` on every
   transaction, and the test payout of 453.88 is settled net proceeds of 458.38 less 4.50 of
   postage. The owner ruled that postage is reconciled, not dropped (A29.7), and Shop Money
   on Today now reads a Paid out of 453.88 with the postage stated on its own line.
7. **The test data parsed money through `float`.** Found 24 September by the new lint and a
   search. `testdata/ingest.py`, `ingest_order_export.py` and `generate_payloads.py` computed
   pence as `round(float(s) * 100)`, which A13 rule 3 forbids. On three-decimal inputs such as
   "1.005" it gives 100 where `Decimal` gives 101. All 81 distinct amounts in the payloads give
   the same pence either way, so `rows.json` and every payload regenerated byte for byte after
   the change to `Decimal`.
8. **The test data covers two months, not twelve.** July and August 2026. Nothing yet tests
   behaviour across many months or across the British Summer Time boundary.

## Commercial rulings worth knowing before touching billing

- The three prices are **exclusive of VAT**. Starter £9.99, Growth £24.99, Pro £49.99, each
  plus VAT. Stripe needs `tax_behavior: "exclusive"` and it has to be right first time.
- **History is twenty four months on every plan**, not tiered.
- **The order limit is enforced softly.** The count appears at eighty per cent and at a
  hundred per cent, the larger plan is offered, and nothing stops. No month closes, no
  export is withheld, no figure stops updating.
- **Cost files are Excel and CSV only.** Word and PDF carry no columns, so reading a cost
  from one means guessing, and a wrong cost is worse than a missing one.
- Bank reconciliation is out of scope, so `settlements.settlement_reference` has no
  automatic source.

## The Stripe products, created 23 September 2026

These live in `acct_1RtsbgKUYBix7r5t`, which is the live account. `plans.py` reads the price
identifier from an environment variable and never from a browser, so these three values are
what those variables hold. A price identifier is not a secret, because Stripe Checkout sends
it from the client by design.

| Plan | Product | Price | Environment variable |
|---|---|---|---|
| Starter | `prod_VJS0gANslYxL4f` | `price_1UIp77KUYBix7r5t8CZvvdaj` | `STRIPE_PRICE_STARTER` |
| Growth | `prod_VJS0v6ZFvMl3if` | `price_1UIp7CKUYBix7r5tVgIsyIfC` | `STRIPE_PRICE_GROWTH` |
| Pro | `prod_VJS1MeCHyH5b6b` | `price_1UIp7EKUYBix7r5t8LIvxFd6` | `STRIPE_PRICE_PRO` |

Each price is GBP, recurring monthly at `interval_count` 1, `usage_type` licensed, and
`tax_behavior` exclusive. The amounts are 999, 2499 and 4999 in minor units, which matches
`price_minor` in `plans.py`. The tax code on all three is `txcd_10103101`.

**One older object is in the account and must not be used.** `prod_VIt8w0nPWOoQEv`, named
plainly MyShopEdge, carries `price_1UIHMSKUYBix7r5tDtHTJgvl`. That price is one time rather
than recurring and it has no amount, because it was created as a customer chooses the amount
price. It charges nothing and it cannot be edited into shape. Archive it rather than reuse
it.

## Running things

The service needs Python 3.10 or later and the packages in `service/requirements.txt`.

```
cd service
pip install -r requirements.txt
python3 tests/test_auth_verification.py
python3 tests/test_contract_conformance.py
uvicorn app.main:app --reload
```

Neither test needs a database, credentials or the network.

The front end:

```
cd web
npm install
npm run dev
```

The database connection string belongs in the environment as `DATABASE_URL` and never in a
file inside this repository. `.gitignore` already excludes `.env` and its variants.

## What is blocked, and on what

| Item | Blocked on |
|---|---|
| Testing billing end to end | The sandbox account reaching a session. Only the live account is reachable, so no test charge can be made |
| Every claim the TikTok ingestion makes | A real shop authorisation. The runbook covers it |
| Whether twenty four months of statements exist | The same shop authorisation |
| The literal column labels on a settlement export | The same shop authorisation |
| The remaining 20 Figma screens | The Figma Starter plan call limit |
| Where the Python service runs | Decided in A28.4: a long-lived container in London, not serverless, because the connection pool and the token refresh both need a process that outlives a request |
| Whether single factor authentication is acceptable at launch | A commercial and risk decision. Neon Auth offers no second factor and none can be added |
| The encryption key for `tiktok_connections.access_token_enc`, `refresh_token_enc` and `shop_cipher_enc` | Where the Python service runs. The host decides where a key can live and how it is rotated. `key_version` exists as a column and resolves to nothing, so no code should write a number there and treat it as meaningful |
| Whether `authorization_expires_at` is the refresh token's expiry | One real TikTok authorisation. The contract serves the field and `tiktok_connections.refresh_expires_at` looks like the same instant. Nobody has checked, so 0020 adds no column for it |
| Refreshing an access token before it lapses | Deploying the service. A28.4 chose a long-lived container so the refresh has somewhere to run. The access token lives seven days (A23.4) |
| Deploying the service | The environment variables in A28.4, which carry four secrets. The commits it also waited on reached GitHub on 24 September 2026, when `main` was restored to `555cd16` with 58 commits. The service also reads `ALLOWED_ORIGINS`, the front end's origins, and sends no CORS headers without it, so a browser write fails until it is set |
| Signing in from the front end | `NEXT_PUBLIC_STACK_PROJECT_ID` and `NEXT_PUBLIC_STACK_PUBLISHABLE_CLIENT_KEY` on Vercel, then one real sign-in, whose `iss` and `aud` the service logs for `NEON_AUTH_ISSUER` and `NEON_AUTH_AUDIENCE` on Render. The code is built |
| The four cost upload operations and `createExport` | How a file reaches Vercel Blob (A10.8). Vercel documents signed upload URLs only for its JavaScript SDK (`issueSignedToken`, `presignUrl`), not as an HTTP call or a signing scheme a Python service can follow. The parser and matcher are built and tested in `cost_files.py`. `createExport` also needs a worker, because it answers 202 |
| `checkReturnItem` | Four rulings, because it writes to the append-only ledger. A4 says what a check does, and not: (1) which order line a write-off or return postage attaches to, since the ledger requires one and the test ingest uses the order's first line rather than the returned variant's; (2) whether a write-off uses the cost in force today or when the unit sold; (3) which date the entries carry, the check or the refund; (4) whether a check takes units off `coming_back`, which nothing yet adds to. `returns.py` says so |
| `getExpectedPayouts` | A source for TikTok's unsettled orders. The contract says it is read from that endpoint, nothing ingests it, and the ledger holds the week a sale happened, not the week TikTok will pay |
| Profit figures for past months after a cost changes | A ruling. The figure queries read only a variant's current cost, so a new cost changes past months too. The contract says they should not. `costs.py` records it |

## What is next in the code

On 24 September the seller's own routes, costs, the two actions and Needs you were built.
The next pieces of code are unblocked only as the blocked table above clears, except for the
contract's remaining reading operations (returns, tax, notifications, alert settings and
account deletion). `settlements.py` and `records.py` remain the pattern: keyset
pagination, RFC 9457 problem details, and the same 404 for another tenant's row as for one
that does not exist. A write follows `stock.create_stock_adjustment`: the Idempotency-Key
through `idempotency.py`, the write and its key in one transaction, and a smoke case that
replays the key. Every write is checked on the development branch as `mse_app` inside a
transaction that ends in a rollback.
