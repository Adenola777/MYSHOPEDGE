# Action 29. The dashboard rules, and Python as the one place they live

24 September 2026. Adenola approved an engineering amendment covering freshness,
connection health, sync health, Needs you, VAT, return postage and the business date, and
asked for the gaps it names to be closed. This records what was ruled, what the repository
said when it was checked, and where the two differed.

## 29.1 Python owns every financial and business rule

The Python service is the only place a financial, accounting, synchronisation, connection,
freshness, date or Needs you rule is implemented. The front end renders what the API returns
and calculates none of it.

Working Python is extended rather than rewritten to standardise the stack. Existing models,
services, fixtures and the ingest pipeline are reused wherever they fit.

## 29.2 The contract changes before the code

When a screen needs a figure the contract does not carry, the order is fixed: the contract
in `api/openapi.yaml` first, then the Pydantic model, then the handler, then a test, then the
front end. This is A13 rule 1 restated, because the amendment arrived with a VAT field and a
freshness field that the contract did not have.

Money stays as A13 rule 3 sets it: integer minor units with the currency beside it. The
amendment's examples used `Decimal` values such as `16920.00`, and those were not adopted.
Field names stay in the contract's snake_case, so `last_synced_at` rather than
`lastSyncedAt`.

## 29.3 Freshness

`TodayView` carries `freshness: {status, last_synced_at}`, and the service computes it.

| Age of the last successful sync | Status |
|---|---|
| Under 6 hours | `fresh` |
| 6 to 24 hours inclusive | `getting_old` |
| Over 24 hours, or never synced | `stale` |

The existing `stale` boolean stays for compatibility and is true exactly when the status is
`stale`.

## 29.4 Connection health

Enough is persisted to tell these states apart: connected, expiring, expired, revoked,
refresh failed and missing scope. Migration `0022` adds the refresh attempt, the last
successful refresh, the failure code and reason, and the required scopes.

| Condition | Severity |
|---|---|
| Refresh token lapses within 14 days, and nothing can refresh it | warning |
| Access or refresh token expired | critical |
| Refresh failed | critical |
| Access revoked, or the shop needs reconnecting | critical |
| A required scope not granted | critical |

**The required scopes are not decided.** A24 records that whether
`{seller.finance.info,seller.order.info}` is the minimal set "has never been checked against
the screens". `tiktok_connections.required_scopes` therefore starts empty, and the missing
scope condition cannot fire until the list is decided and written there. No list was
invented to fill it.

## 29.5 Sync health

`sync_runs` already existed in the base schema, per shop and per domain, with a status,
`started_at`, `finished_at`, `records_read`, `records_written` and `error`. It could not say
`partial`. Migration `0022` adds `partial` to its statuses and a `records_failed` count.

The latest run for each domain is read. A `failed` or `partial` latest run is a warning. A
`needs_reconnect` latest run is critical, because it is a broken connection.

## 29.6 Needs you, DSH-10

Every item carries a type, a severity, a label and, where one applies, an amount at stake.
The order is critical, then warning, then info. Within a severity the item with more money
at stake comes first, then the larger count. The amendment asked for recency last. The
items are counts rather than events, so they carry no single time, and the tie ends at the
count.

| Item | Severity | Basis |
|---|---|---|
| `connection_action_required` | critical | 29.4 |
| `refresh_failed` | critical | 29.4 |
| `missing_scope` | critical | 29.4 |
| `sync_needs_reconnect` | critical | 29.5 |
| `connection_expiring` | warning | 29.4 |
| `stale_data` | warning | 29.3 |
| `sync_failed` | warning | 29.5 |
| `sync_partial` | warning | 29.5 |
| `open_discrepancies` | warning | Derived from the warning definition, not named in the amendment |
| `unmapped_fees` | warning | Derived |
| `returns_to_check` | warning | Derived |
| `missing_costs` | info | Ruled. A missing cost is optional input, not a failure |
| `first_sync_pending` | info | Ruled |
| `out_of_stock` | info | Derived |

The amendment names `COST_PRICE_UPDATE_RECOMMENDED`. Nothing in the schema says when a cost
is out of date, so it is not served.

## 29.7 Return postage is reconciled, and A4.119 is corrected

**Ruled.** Return postage stays in the seller's accounts and is reconciled. It is never
dropped from a figure to make that figure tidy, and no displayed metric is corrected by
subtracting a fixed amount.

**What was found.** A4.119 says return postage "never passes through a TikTok statement".
The real payload in `testdata/real_payloads/statement_transactions_202501.json` carries
`shipping_cost_breakdown.return_shipping_fee_amount` on every transaction, and A11 maps
that field to "Return shipping you paid". So TikTok can settle return postage, and A4.119 is
wrong in that respect. The test ledger agrees: its return postage entry carries a
`settlement_id`, and the payout TikTok made, 453.88, is the settled net proceeds of 458.38
less that 4.50.

**Applied.** Shop Money on Today reconciles to the payout TikTok actually made:

    Net proceeds, settled                     458.38
    less return postage TikTok deducted        -4.50
    = Paid out                                453.88

Net proceeds keeps A8's definition, so `getMoney` and the month on Today are unchanged. Shop
Money states the return postage TikTok deducted as its own figure, which is why paid out
plus awaiting now equals net proceeds less that postage rather than net proceeds alone.
Return postage the seller paid outside TikTok carries no `settlement_id` and is outside Shop
Money, because it never passes through TikTok.

**The owner's ruling on Paid out, 24 September 2026, in his words.**

> Paid Out represents the actual amount successfully paid or credited to the seller by
> TikTok Shop, based on the payout record. Settlement components such as shipping, return
> postage, fees and adjustments remain separately traceable in the settlement ledger and
> must not be added back to Paid Out merely because they are separately classified. Where a
> settlement component is deducted before payout, Paid Out reflects the resulting cash
> amount actually transferred.

So on the development data Paid out is 453.88, and the 4.50 of return postage is stated on
its own line. That is what the code above already serves, and it was checked against the
ledger: the three `settlement` payout entries total 453.88, and the Shop Money query's paid
out on the same branch was 453.88.

**This overrides the master skill.** `instruction-going-further` §16 and §51 say return
postage "is excluded from Paid Out under A4". The owner ruled that this wording mixes the
ledger classification with the cash payout. Where that skill and this section disagree,
this section is the rule for this repository.

## 29.8 VAT

**Ruled by the owner on 24 September 2026: VAT is out of scope for the current TodayView
contract.**

> VAT is out of scope for the current TodayView contract and must not be fabricated,
> inferred or displayed as a financial liability.

Three facts support it. A8.4 renames the wireframe's "VAT line" to "VAT registration
threshold", which the contract serves separately as `getVatMonitor`. That endpoint's
contract says PRD 6.2 excludes accounting for VAT on a registered seller's behalf. The VAT
the repository holds, `tiktok_invoices.vat_minor`, is VAT on TikTok's fee invoices, not VAT
in the seller's sales, and nothing ingests VAT on sales.

VAT may come later as a separately scoped capability, once there is an authoritative VAT
source, a defined method, the seller's business configuration, and a clear line between VAT
included in sales and VAT payable. This overrides the master skill's §19 and §51.

## 29.9 One business date, Europe/London

`service/app/dates.py` holds the only definition of "today": the current date in
Europe/London. Today, `getMoney` and the two product endpoints take their default
period from it. Before this, `getMoney` and the product endpoints used the server's own date, so near midnight a
UTC server and a London seller could name different days. Tests cover the hour either side
of midnight and both clock changes.

## 29.10 The development ledger

`testdata/seed.sql` left `settlement_month` out of its ledger insert, so the cash basis
returned nothing on development (CLAUDE.md, fault 5). It was also a version behind
`testdata/rows.json`: it held an old `unmapped_fee` of -5.00 that `rows.json` replaced with
the `PLATFORM_PENALTY` adjustment, and it lacked the -10.00 reserve. The other 117 entries
agreed on id, amount and category.

The seed's ledger insert is now rebuilt from `rows.json`, 119 entries with 88 carrying both
`settlement_month` and `settlement_id`. **This seed has not been loaded into any database**,
so it is unverified. The other tables in `seed.sql` were not compared with `rows.json`.

**The development branch itself is not reloaded.** The ledger refuses updates by trigger,
and reloading it is a write to append-only tables that needs its own approval.

## 29.11 Which document wins

**Ruled by the owner on 24 September 2026.** The product decisions govern the engineering
skill, not the other way round.

    Level 1, product authority      the problem statement, the PRD, the A rulings
                                    including this one, the canonical contracts, and the
                                    owner's accounting and product decisions
    Level 2, engineering authority  architecture, domain models, the database schema,
                                    api/openapi.yaml, and the tests
    Level 3, provider authority     TikTok, Stripe and Neon's own documentation
    Level 4, conventions            the master engineering skill, recommendations from
                                    Claude, and framework defaults

A provider's documentation governs facts about that provider, such as its endpoints, scopes,
field meanings and settlement mechanics. It never overrides an explicit MyShopEdge product
ruling, such as what Paid out means, whether VAT is shown, or how Needs you is ordered. This
reconciles the skill's §7 with CLAUDE.md rule 7, which says a vendor's documentation is not a
fact about this project.

Working behaviour that already complies with a ruling is not changed to satisfy a generic
skill. The skill is updated to respect the ruling instead.

## 29.12 Why MyShopEdge exists

**Ruled by the owner on 24 September 2026, as a first principle.**

> MyShopEdge is not a TikTok Shop reporting replica. TikTok Shop is the source of
> transactional facts. MyShopEdge transforms those facts into financial clarity,
> reconciliation, explanation and decision support that TikTok does not provide sufficiently
> for the seller. Where TikTok already provides a reliable fact, MyShopEdge reconciles and
> explains it rather than inventing an alternative. Where TikTok provides raw data but not
> useful interpretation, MyShopEdge derives and explains the insight. Where MyShopEdge lacks
> the data to make a reliable calculation, it says so rather than fabricating certainty.

The financial model has three layers. TikTok's facts are orders, sales, refunds,
settlements, fees, shipping, return postage, payouts and adjustments. MyShopEdge's
reconciliation says what was sold, refunded, settled, deducted, paid and still awaited, and
where a discrepancy lies. MyShopEdge's intelligence says what the seller made, which
products earn and which lose, what is stuck, and what needs attention.

## 29.13 Money is integer minor units

**Ruled by the owner on 24 September 2026.** A13 rule 3 stands, and it overrides the master
skill's §29.

> MyShopEdge represents monetary values as integer minor units with an explicit currency.
> Decimal may be used internally where a calculation genuinely requires decimal precision,
> but API and database money representation remains integer minor units.

So 453.88 pounds is `{"amount_minor": 45388, "currency": "GBP"}` in the API and a `bigint`
in the database. Formatting to pounds happens only at the presentation boundary, and no
financial figure passes through a binary float.

## 29.14 The Needs you contract stays as it is

**Ruled by the owner on 24 September 2026.** The contract's `NeedsYouItem` remains
authoritative, and it overrides the master skill's §25.

| Field | Role |
|---|---|
| `type` | The machine-readable classification. The skill's `code` would duplicate it |
| `label` | The seller-facing title. The skill's `title` would duplicate it |
| `severity` | Backend-owned `critical`, `warning` or `info`, as DSH-10 requires. Already required by the contract |
| `amount_at_stake` | The money affected, where one applies |
| `href` | Where the seller acts. An explicit action model waits until an action is not navigation |
| `count` | How many of the item there are. Already required by the contract |

Needs you is a current-state surface, not an event log, so `created_at` is not a public
field. Timestamps and diagnostics may exist internally for detection, audit and observability.

