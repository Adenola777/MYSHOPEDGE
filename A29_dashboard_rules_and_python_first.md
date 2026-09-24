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

## 29.8 VAT

**Not changed, and recorded as open.** The amendment asked for `sales.vat` on Today. Three
facts stand against doing it now.

- A8.4 renames the wireframe's "VAT line" to "VAT registration threshold". The contract
  already serves that as `GET /shops/{shopId}/tax/vat`, `getVatMonitor`.
- That endpoint's contract says it "does not account for VAT on behalf of a registered
  seller. PRD 6.2 excludes both."
- The VAT the repository holds, `tiktok_invoices.vat_minor`, is VAT on TikTok's own fee
  invoices, not VAT inside the seller's sales. Nothing ingests VAT on sales.

The amendment's own condition was "where the relevant source data supports the
calculation", and it does not yet. Adding VAT on sales would reverse PRD 6.2 and needs its
own decision.

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
