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
| Schema | Through 0019 on staging and development, 20 migrations recorded on each. Production holds through 0016 plus the 0019 security fix |
| Backend | 6 of 58 routes. Health, billing, settlements, records |
| Authentication | ES256 verified against the provider's fetched JWKS, email read from `users_sync`, 9 tests passing. No handler has ever been invoked by a test |
| Billing | Screens built. The three products and prices exist in the live Stripe account as of 23 September. Nothing is wired to them yet |
| TikTok integration | **Does not exist as code**, but the connection is proved. 23 September: no file calls a TikTok host, and the two connection handlers in the contract have no implementation. Three live calls were made by hand through the Partner Center testing tool and all returned `code: 0`. The authorised shop is a sandbox test shop in region ID, not GB. See A19 |
| Front end | 2 pages of 39 screens |
| Figma | 18 screens drawn, 20 pending, blocked on the Starter plan call limit |
| Deployment | Vercel chosen for the front end. Nothing deployed. The Python service has no host |

The honest summary is that the thinking is done and the building has started.

## The documents

`A2` to `A18` are the rulings, one file per action. They are decisions rather than notes, so
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
5. **The test data covers two months, not twelve.** July and August 2026. Nothing yet tests
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
| Where the Python service runs | A decision nobody has taken. It also decides where `DATABASE_URL` lives |
| Whether single factor authentication is acceptable at launch | A commercial and risk decision. Neon Auth offers no second factor and none can be added |

## What is next in the code

The reading endpoints, in this order: `listProducts`, `getProduct`, `getMoney`, `getToday`,
then stock, movements and discrepancies. `settlements.py` and `records.py` are the pattern to
follow. Both use keyset pagination rather than offset, both return RFC 9457 problem details,
and both answer a request for another tenant's row with the same 404 as a row that does not
exist.
