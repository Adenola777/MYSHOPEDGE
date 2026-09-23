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
| Authentication | EdDSA verified against Neon Auth, email read from `users_sync`, 9 tests passing |
| Billing | Screens built. The three Stripe products have never been created |
| TikTok integration | Proved against generated fixtures only. No real shop has been connected |
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
| Identity | Neon Auth, which is Managed Better Auth 1.4.18. It is not Stack Auth |
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
   a provider that signs EdDSA over Ed25519. Every real token would have been refused. The
   old tests passed because the fixtures were signed with the same wrong assumption. There
   is now a regression case asserting `ALGORITHMS == ["EdDSA"]`.
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
| Creating the three Stripe products | The sandbox account reaching a session. The live account is live mode only and must not be used for this |
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
