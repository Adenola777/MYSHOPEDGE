# A12. Data requirements for the initial test

Prepared 22 September 2026. This action states exactly what has to exist before the first
integration test, what the shop owner must supply, what TikTok must return, and what no
shop can produce without help.

## A12.1 What 100 per cent coverage means here

The schema has 32 tables, 146 enumerated values across its check constraints, and a set of
conditional checks that only fire in particular circumstances. Covering it fully means all
five of the following, not just the first.

1. Every table holds at least one row.
2. Every enumerated value appears at least once.
3. Every nullable column that changes behaviour appears both null and populated.
4. Every conditional check is exercised on both sides, including the ones designed to
   reject.
5. Every view returns rows, and the two reconciliation views return the value that proves
   the system is correct rather than merely running.

**The uncomfortable part.** A live UK shop, however busy, produces roughly 60 per cent of
this. The remaining 40 per cent is either an action the seller takes inside MyShopEdge, or
a failure state no healthy shop ever reaches. Both have to be engineered. Any test plan
that assumes a real shop exercises the schema will leave the error handling untested, and
the error handling is where a bookkeeping product loses a seller's trust.

## A12.2 Source A: what the TikTok shop must contain

This is the shopping list. Each row is a real order, return or settlement the shop owner
needs to have in their history, or to create in a sandbox.

### Orders

| # | Order must be | Exercises |
|---|---|---|
| 1 | Single unit, delivered, settled, no discount | The baseline. `gross_sales`, `platform_commission`, `transaction_fee`, `settlement`, `attribution = direct` |
| 2 | **Three units of the same SKU** | TikTok returns one line item per unit. This is the order that proves the ingestion groups or does not group, and it is the single most important row in this table |
| 3 | Two different SKUs in one order | `attribution = allocated`. The largest-remainder split across lines, with no residual pence |
| 4 | With a seller-funded discount | `seller_discount` |
| 5 | Sold through a creator's affiliate link | `affiliate_commission` |
| 6 | Sold through an affiliate ad | `affiliate_ads_commission`, which is a separate line from #5 |
| 7 | Placed but not yet dispatched | `order_settlements.status = waiting_delivery` |
| 8 | Delivered, settlement not yet issued | `order_settlements.status = delivered_awaiting_settlement` |
| 9 | Dispatched during a promotion | `smart_promotions_fee` |
| 10 | **Created between 23:00 and 00:00 UTC, during British Summer Time** | The BST boundary. `basis_day` must fall on the following London day while the TikTok statement counts it in the previous UTC day. Nothing else tests this, and getting it wrong misdates a VAT return |
| 11 | Created in a previous calendar month and settled in this one | The month boundary, and `basis_month` against `settlement_month` |
| 12 | Fulfilled by TikTok, if the seller uses FBT | `fbt_operations_fee`, `fbt_shipping_fee`, `fbt_storage_fee`. Omit only if the seller never uses FBT, and record that those three categories are then untested |

### Returns and cancellations

All three kinds are needed, and they behave differently on purpose.

| # | Must be | Exercises |
|---|---|---|
| 13 | Cancelled before dispatch | `returns.kind = cancellation`. Stock returns without a refund of shipping |
| 14 | **Refunded with no goods coming back** | `returns.kind = refund_only`. Must produce **zero** stock movements. This is the REC-2 test, and a system that creates a movement here is silently inventing stock |
| 15 | Returned, goods arrived, resellable | `return_refund`, `return_resellable`, exactly one stock movement |
| 16 | Returned, goods arrived, damaged | `write_off`, `stock_written_off`, and no stock movement back to the shelf |
| 17 | A return where the seller paid the postage | `return_shipping` |
| 18 | A return where TikTok charged the return handling fee | `return_handling_fee` |
| 19 | A return that generated a TikTok credit note | `tiktok_credit_note_number`, and the fee reversal matching the original fee |

### Settlements

| # | Must be | Exercises |
|---|---|---|
| 20 | A statement already paid | `payment_status = PAID`, green |
| 21 | A statement still processing | `payment_status = PROCESSING`, amber |
| 22 | A statement carrying a non-zero `adjustment_amount` | The adjustment path, and the discrepancy raised because the statement gives no reason for it |
| 23 | At least two statements on consecutive days | `activity_date`, and that two statements do not collide |
| 24 | One TikTok fee invoice | `tiktok_invoices`, and the `gross = net + VAT` check |

### Products and stock

| # | Must be | Exercises |
|---|---|---|
| 25 | A product with two or more variants | `skus`, `variant_label` |
| 26 | **A SKU with the seller SKU field left blank** | The empty `seller_sku` found on the sandbox shop. Proves the cost matching fallback |
| 27 | A SKU with a seller SKU set | The normal matching path |
| 28 | A product with stock on hand | `stock_positions` |
| 29 | A product that has sold out | The `out` state, and `days_left` returning null rather than dividing by zero |

**Minimum viable shop:** roughly 20 orders, 7 returns, 3 statements, 6 products with 10
SKUs. It does not need to be a large shop. It needs to be a varied one.

## A12.3 Source B: what the shop owner must supply or do

None of this comes from TikTok. All of it is required.

**Credentials and access**

1. The UK shop authorises the MyShopEdge app, producing `id`, `cipher`, `region` and
   `seller_type` from `GET /authorization/202309/shops`.
2. `region` must be `GB` and `seller_type` must be `LOCAL`. A cross-border seller returns
   import VAT and customs fields in place of `local_vat_amount`, which is a different
   mapping and a separate test.
3. The app's granted scopes, including `seller.finance.info`.

**Files**

4. A real cost file, in whatever shape the seller actually keeps it. Not a template we
   wrote. The point of the test is to find out what real files look like.
5. A second cost file containing a duplicate row and a SKU that does not exist, so
   `rows_duplicate` and `rows_unmatched` are non-zero.

**Answers**

6. Business structure: sole trader, limited company, or not sure.
7. Whether they are VAT registered, and if so from what date.
8. Their gross income for the prior tax year, including anything outside TikTok.
9. Any sales on other channels, by month, for the last twelve months.

**Actions inside MyShopEdge**

10. Check at least one returned item as resellable and one as unsellable.
11. Record one manual stock adjustment with a reason.
12. Resolve one discrepancy each way: accept TikTok, correct their own figure, and explain.
13. Change an alert threshold from its default.
14. Request one export on a sales basis and one on a cash basis.

**The question nobody has answered**

15. Log into Seller Center and tell us whether a fee invoice number appears, where, and
    whether the document can be downloaded. Four API endpoints do not carry it. Until this
    is answered, `tiktok_invoices` has no confirmed population path and item 24 above may
    be impossible.

## A12.4 Source C: states no healthy shop produces

These must be engineered. A test plan without them leaves the failure paths untested.

| State | How to produce it |
|---|---|
| `shops.connection_status = needs_reconnect` | Revoke the authorisation at TikTok while the app holds a token |
| `shops.connection_status = disconnected` | Disconnect through the product |
| `sync_runs.status = failed`, `retry_wait`, `needs_reconnect` | Fault injection: force a 429, a timeout and a 401 from the TikTok client |
| `raw_events.status = failed`, `ignored` | Feed a malformed payload and a duplicate payload |
| `ledger_entries.category = unmapped_fee` | Remove one fee from the mapping table in the test configuration and re-ingest. This also proves `tiktok_fee_type` keeps TikTok's name verbatim |
| `stock_movements.movement_type = adjustment_absorbed` | Raise TikTok's stock figure without a matching sale or return, within the tolerance |
| An absorption above tolerance | Raise it beyond `absorption_tolerance_units` and confirm a discrepancy is raised instead of a silent absorption |
| All six `discrepancies.kind` values | Construct one of each. `product_code`, `order_reference`, `transaction_reference`, `amount`, `return_unmatched`, `duplicate` |
| `settlements.payment_status = FAILED` | Unlikely on a real shop. Seed it directly and record that it was seeded |
| `accounts.status = suspended`, `deleted` | Administrative action |
| `exports.status = failed`, `expired` | Fail one export job and let one expire |
| `ledger_attribution_chk` rejecting | Attempt a non-payout entry with no `order_line_id` and confirm it is refused. The constraint is `NOT VALID`, so it guards new rows only |
| Append-only enforcement | Attempt `UPDATE` and `DELETE` on `ledger_entries` as `mse_app` and confirm both are refused |
| Tenant isolation | Create a second account with its own shop and confirm neither can see the other |

## A12.5 The coverage matrix

Where each table gets its rows.

| Table | TikTok | Seller | System | Engineered |
|---|:--:|:--:|:--:|:--:|
| `accounts` | | ● | | ● |
| `shops` | ● | ● | | ● |
| `tiktok_connections` | ● | ● | | ● |
| `sync_runs` | | | ● | ● |
| `raw_events` | ● | | ● | ● |
| `products`, `skus` | ● | | | |
| `cost_uploads` | | ● | | ● |
| `product_costs` | | ● | | |
| `orders`, `order_lines` | ● | | | |
| `settlements` | ● | | | ● |
| `order_settlements` | ● | | ● | |
| `returns`, `return_items` | ● | ● | | |
| `ledger_entries` | ● | ● | ● | ● |
| `stock_positions` | ● | | ● | |
| `stock_movements` | ● | ● | ● | ● |
| `discrepancies` | | ● | ● | ● |
| `notifications` | | ● | ● | |
| `alert_settings` | | ● | | |
| `tax_profiles` | | ● | | |
| `other_channel_sales` | | ● | | |
| `reference_rules` | | | ● | |
| `change_log`, `audit_log` | | | ● | |
| `exports`, `export_schedules` | | ● | ● | ● |
| `feed_tokens` | | ● | | |
| `daily_metrics` | | | ● | |
| `tiktok_invoices` | ● | | | ● |
| `product_events` | | | ● | |

Eleven of the 32 tables receive nothing at all from TikTok. Four receive nothing without
deliberate fault injection.

## A12.6 The five assertions that decide whether the test passed

Running without error is not the same as being correct. These five are the test.

1. **`settlement_reconciliation.unexplained_minor` is zero on every settlement.** A payout
   that does not agree with the orders behind it is the defect this product exists to catch.
2. **`return_reconciliation` shows zero stock movements for every `refund_only` return, and
   exactly one for every checked `return_refund`.** Any other combination is a defect.
3. **`ledger_basis_month_mismatch` returns no rows.** Every entry's `basis_month` agrees
   with its Europe/London month.
4. **`settlement_totals_check.difference_minor` is zero, and `region_mapping_conflict` is
   false on every row.** The statement agrees with its own components, and the region
   branch chose correctly.
5. **The calculator's subtotals equal the sum of their lines, to the penny, on every
   screen.** Order 2, the three-unit order, and order 3, the two-SKU order, are where this
   breaks if the allocation is wrong.

## A12.7 What will remain untested, and why

Stated here so it is a known gap rather than a discovered one.

- **FBT fees**, if the seller does not use Fulfilled by TikTok. Three categories untested.
- **`tiktok_invoices`**, until the Seller Center question in A12.3 item 15 is answered.
- **Cross-border sellers.** Deliberately out of scope for this test, and a different field
  mapping.
- **`payment_status = FAILED`**, which will be seeded rather than observed.
- **Multi-shop and multi-user**, excluded by PRD 6.2. The schema supports them, the test
  does not cover them, and the interface must not expose them.
