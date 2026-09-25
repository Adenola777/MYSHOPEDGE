# End to end quality assurance, 24 and 25 September 2026

The owner asked whether every endpoint returns the right values and whether the front end
shows the right screen and works. This records what was run, what it found, and what is
still open. Every result below came from executing something. The scripts and their raw
results are in `audit/qa_25_september/`.

## Result

| Suite | What it checks | First run | After the fixes |
|---|---|---|---|
| Reads | Every read operation, compared with independent SQL on the ledger | 101 of 102 | 108 of 108 |
| Writes | Authentication, a second seller, the four writes, outside services | 68 of 68 | 68 of 68 |
| Screens | Every screen in Chromium, its figures against the API, and writes made through the forms | 112 of 113 | 129 of 129 |

The first run's two failures and the notification gap went to the owner, who ruled on all
three on 25 September. The section "Settled on 25 September" says what changed. The
results in `audit/qa_25_september/` are from the run after the fixes, each suite on a
freshly built database.

## How it was run

The plan was to run the service against a throwaway Neon branch. That branch was created as
`qa-throwaway-2026-09-24` with a temporary role `qa_tmp`. The container could not reach it:
Postgres traffic does not leave this sandbox, and the HTTPS route to Neon's SQL endpoint was
refused by the session's safety check. That refusal was respected rather than worked round.

The service therefore ran against a local PostgreSQL 16 built from this repository alone:
the base schema, every numbered migration through `service/scripts/migrate.py`, and
`testdata/seed.sql`. Before any figure was trusted, the local copy was compared with the Neon
branch.

- The schema fingerprint (every column, type and nullability in `public`) matched exactly:
  `24848c3fac8ea5b0730115b6368c73d7` on both.
- The ledger matched exactly: 119 entries summing to minus £318.24 on both.
- Ownership matched after one correction: 35 tables, 6 views and 9 project functions owned
  by `mse_migrator` on both.

The local copy differs from development in one respect, and it is the known fault 5 in
`CLAUDE.md`. It carries `settlement_month` on 88 entries, because the rebuilt seed includes
it, while development carries it on none. The cash basis was therefore testable here and is
not testable on development.

The real service (`uvicorn app.main:app`) ran with its own authentication code. Tokens were
signed with an ES256 key made for the run and served from a local JWKS, exactly as the
service reads the provider's. The front end was a production build (`next build`,
`next start`). A small proxy added the test seller's token to each request, standing in for
Stack's cookie, because Stack's servers cannot be reached from the sandbox.

The Neon branch and its role were deleted on 25 September, as the owner approved. Only
production, staging and development remain.

## What passed, in substance

**Money** (July and August, sales basis). Every line equals the ledger by category to the
penny: gross sales £862.00, seller discounts, each TikTok fee under TikTok's own name, the
£5.00 platform penalty, refunds £274.00, return postage £4.50, stock written off £51.00, the
£10.00 reserve and the £453.88 payout. The chain adds up: net sales £857.00, net proceeds
£495.38, gross profit £298.66, gross profit after returns £243.16.

Cost of goods reads £196.72 while the ledger's cost entries sum to £294.24. That is correct.
`money_view.py` computes it as A4.1 requires, units sold less units returned at cost, and
the arithmetic confirms it: £294.24 for every unit sold, less £97.52 for the 7 units that
came back.

**Money, cash basis.** Every line equals the ledger filtered by `settlement_month`, and the
confidence reads confirmed.

**Today.** Shop Money reads net proceeds £495.38, paid out £453.88, return postage £4.50 and
awaiting £37.00, and these reconcile. The awaiting breakdown sums to the awaiting figure.

**Products.** Units, gross sales and returned units match the order lines and the ledger for
all six products. Each product's detail matches its row, and per-unit gross times units
equals gross sales.

**Settlements, records, returns, stock, discrepancies, Needs you, cost coverage.** All match.
Records walked through the cursor return all 119 entries once each, summing to minus £318.24.

**Authentication.** No token, a tampered signature, a wrong audience, a wrong issuer, an
expired token and `alg: none` are all refused with 401. An expired token says
`token_expired`. `emailVerified: false` is refused with 403.

**A second seller.** A new token created a new account on first sign in, with no shops. On
every one of the 15 shop routes, the first seller's shop and a shop that does not exist
returned the same 403 `forbidden_shop`, so a shop id reveals nothing. That seller could not
set a cost, adjust stock, resolve a discrepancy, see a notification or mark one, and nothing
was written.

**Writes.** A cost is stored. A negative cost and a foreign currency are refused. A stock
adjustment is created once, a replay with the same `Idempotency-Key` returns the first answer
without writing again, and the same key with a different body is refused. A keyless
adjustment is accepted, which is what the contract says, because the key is optional there.
Resolving a discrepancy stores it and takes it off Needs you. Marking a notification read
stores it and brings the unread count to zero.

**Outside services.** Billing refuses with `billing_unconfigured` when Stripe is not set. An
unsigned Stripe webhook is refused with 400. A TikTok callback with a forged state is
refused with 400 `state_invalid`. Authorising TikTok needs a signed in seller and refuses a
return address on another site.

**Screens.** Today, Products (three measures), Product detail, Money (sales and cash, a day
and this month), Stock (all and three filters), a variant, Records, Discrepancies,
Notifications and Start all load with no error state, no console error and no sideways
scroll at 390 pixels. Each shows the figures the API returned. Every deduction on every
screen is drawn in #B3261E, as the owner ruled on 24 September. The bell shows one unread
notification. A cost, a stock adjustment and a discrepancy resolution were each made through
the screen and confirmed in the database, and Today dropped the discrepancy afterwards.

## Settled on 25 September

The owner ruled on the three findings below. Each change went into the contract first, then
the service with smoke cases, then the screen, and each was checked against the local copy
of development.

- **Money tied to no product has its own line.** `listProducts` now returns `unattributed`,
  the period's ledger entries that carry no variant, named as Money names them, and
  `shop_total`, which is `total` plus those lines. The categories come from Money's own
  chain in `money_view.py`, so the two screens cannot disagree about what a figure holds.
  For July and August the shop total is £243.16 on the sales basis and £263.64 on the cash
  basis, and for net proceeds and gross sales it is £495.38 and £862.00. Each equals
  Money. `shop_total` is null while a product sold in the period has no cost price. The
  screen shows the products' total, then "For the whole shop, not one product" with the
  TikTok adjustment, then "Total for the shop".
- **The movements page names the variant.** `getStockMovements` now returns `sku`, with
  the product title, variant label, seller SKU and TikTok SKU id. The page's heading is the
  product, with the variant and SKU beneath it.
- **Notifications work.** Each open notice offers "Mark as read" while unread and "Done"
  while not done, and the list offers "Mark all as read". The page and the bell refresh
  after each change, and the bell's count falls. `listNotifications` gained `status=open`
  so the Open list is filtered and paged by the service, where it used to take one page of
  everything and filter it in the browser. Older notices are reached through the cursor.

## What the first run found

1. **Settled, see above. The products total does not equal Money.** For July and August the products total is
   £248.16 and Money's gross profit after returns is £243.16. The £5.00 is TikTok's platform
   penalty on the statement, which belongs to no product. The docstring in `products.py`
   says the arithmetic should be "visibly closed" against the money screen, and today it is
   not. Two answers are possible: the products screen states the unallocated £5.00 on its
   own line, or the difference is accepted and explained in a footnote. Either is a ruling.

2. **Settled, see above. The stock movements page never names the variant.** `/shops/{id}/stock/{sku}` carries
   the adjustment form, and it says "Stock movements" without the product or variant. A
   seller could adjust the wrong item without knowing. `getStockMovements` returns no product
   or variant, so the fix starts in the contract: add the product title, variant label and
   seller SKU to that response, then serve and show them.

3. **Settled, see above. No screen marks a notification read.** `PATCH /notifications/{id}` works, but nothing
   calls it, so the bell's count can never fall. A button on S13 would close it.

## Faults in the test tooling, found by running it

4. **`migrate.py` cannot build a database from empty.** The base file already contains
   migrations 0001 to 0009, and 0002 fails on a second run. The Neon branches were built by
   recording those nine as backfilled. `audit/qa_25_september/rebuild.sh` does the same.

5. **Migration 0011 needs `neon_auth.users_sync`, which only 0016 creates** on a branch
   without Neon Auth. Built from empty, 0011 fails. An applied migration is never edited, so
   the fix belongs in the runner or in the build instructions.

6. **`testdata/seed.sql` does not load.** Its `tiktok_connections` row omits
   `access_token_enc` and `refresh_token_enc`, which are `not null`. The commit that rebuilt
   the seed said it had not been loaded anywhere, and this is the first time it was. The row
   on development carries a one byte placeholder in both columns, and the run used the same.

## What the sandbox caused, and is not a fault

- `@stripe/stripe-js` adds Stripe's script to every page when the package is first imported.
  Stripe documents that as intended, for fraud signals. The script failed to load only
  because this sandbox blocks `js.stripe.com`, and the screen checks exclude that one host.
- Next.js prefetches linked pages, and a prefetch cut short by leaving the page is logged as
  a failed request. Those were excluded too.
- The first callback run crashed with a 500 because the local tables belonged to `postgres`
  rather than `mse_migrator`. Neon's branch shows `mse_migrator` owns them, so production
  was never affected. The local ownership was corrected and the case passes.

## Not covered

- Stack's real sign-in. It was verified by the owner's own sign-in on 24 September, and it
  could not be reached from here.
- Billing end to end, which still waits on the sandbox Stripe account.
- Everything that reads TikTok, which waits on a real shop authorisation.
- Behaviour across many months and the clocks changing, because the test data covers July
  and August only (fault 8 in `CLAUDE.md`).
