# Action 20. The real settlement payload, measured

23 September 2026. A live call to
`GET /finance/202501/statements/{statement_id}/statement_transactions` returned a real
settlement. Until today every claim this project made about the shape of a settlement came
from a generated fixture that I wrote from my own assumptions.

The response is saved verbatim at `testdata/real_payloads/statement_transactions_202501.json`.
It carries no token and no cipher. It is the reference from here on, and where it disagrees
with anything in the pack, it wins.

Statement `7353560421799937810`, generated 4 April 2024 at 00:00 UTC, currency IDR, status
`SETTLED`, two transactions.

## 20.1 A8 section 3.5 is closed

The question of what a settlement actually contains has been open since the terminology
standard was written. It is now answered by measurement.

| Object | Fields TikTok returns |
|---|---|
| `fee_tax_breakdown.fee` | 57 |
| `shipping_cost_breakdown` | 24 |
| `fee_tax_breakdown.tax` | 17 |
| `revenue_breakdown` | 7 |

Statement level carries `id`, `create_time`, `currency`, `status`, `payable_amount`,
`total_reserve_amount`, `total_settlement_amount`, `total_count`, `next_page_token`, and
`total_settlement_breakdown`.

Transaction level carries `id`, `type`, `order_id`, `order_create_time`, `revenue_amount`,
`fee_tax_amount`, `shipping_cost_amount`, `adjustment_amount` and `settlement_amount`.

## 20.2 What the payload confirms

**A18.3 was right.** The statement carries `payable_amount`, `total_reserve_amount` and
`total_settlement_amount` as three separate figures. A18.3 insisted that net proceeds,
reserve withheld and payout are three different numbers and that a seller who reads one as
another will believe TikTok short-paid them. The API agrees.

**`settlements.py` expects the right four components.** `total_settlement_breakdown` holds
`total_revenue_amount`, `total_fee_tax_amount`, `total_shipping_cost_amount` and
`total_adjustment_amount`. That is exactly the four the settlement detail endpoint already
returns and reconciles.

**A17 was right to pin 202501.** The reserve field is present at statement level.

**TikTok's notice of 22 September is live.** All four growth package fee fields and all four
matching tax fields are present in this response, five weeks after the notice said they
would be. `new_customer_growth_package_fee`, `store_gmv_growth_package_fee`,
`target_product_gmv_growth_package_fee` and `auto_post_shoppable_video_commission_fee` are
all there, returning `"0"`.

## 20.3 What the payload breaks

**The fee map covers 7 of 57 fields.** Fifty fee fields would fall through to
`unmapped_fee`. The arithmetic survives, because `unmapped_fee` maps to
`platform_deduction` and nothing is discarded on the fee side. The product does not survive
as well. MyShopEdge exists to tell a seller what they were charged and why. Fifty distinct
charges collapsed into one undifferentiated line is not that.

**The shipping map covers 5 of 24.**

**The tax map covers 1 of 17, and the other 16 are discarded without record.** This is the
defect recorded in A19.5, now measured rather than predicted. The tax loop drops any field
absent from `TAX_MAP` and does not add it to `UNMAPPED`, so nothing anywhere shows that
sixteen tax fields were seen and thrown away. Among them are `vat_amount` and
`import_vat_amount`, which a UK seller cares about.

**`pence()` has no currency awareness.** It computes `int(round(float(s) * 100))`
unconditionally. This payload is IDR, which is a zero-decimal currency, and the amounts are
whole numbers. For a GBP-only product the multiplier happens to be correct, so nothing is
wrong today, but the function is wrong in principle and now demonstrably wrong against real
data we have seen. It should take the currency and use its minor unit.

**The ingest does not branch on `type`.** Each transaction carries `type`, `ORDER` in this
payload. The specification says a transaction can be an order, an adjustment, or
reserve-related. Treating all three identically is an assumption nobody has tested.

## 20.4 The order is refunded, not empty

Every amount in this statement is `"0"`, which reads at a glance as an empty test record. It
is not. Both transactions are placed-then-fully-refunded orders.

| Field | Value |
|---|---|
| `subtotal_before_discount_amount` | `11111` |
| `refund_subtotal_before_discount_amount` | `-11111` |
| `customer_payment_amount` | `23313` |
| `customer_refund_amount` | `-23313` |
| `platform_discount_amount` | `600` |
| `platform_discount_refund_amount` | `-600` |
| `customer_shipping_fee` | `12802` |
| `refund_customer_shipping_fee` | `-12802` |

That makes it a better test case than a clean sale, because it exercises the refund path and
it proves that a settlement summing to zero is a legitimate outcome rather than a bug. A
reconciliation that treats zero as missing data would raise a false alarm on this statement.

## 20.5 `supplementary_component` appears at two levels

A11.2 rules that `supplementary_component` explains its parents and is never summed, and
`ingest.py` skips it inside `shipping_cost_breakdown`. This payload has a second
`supplementary_component` at transaction level, holding `customer_payment_amount`,
`platform_discount_amount` and eleven others. The ingest never reads that object, so it is
not summed, which is correct by accident rather than by rule. A11.2 should say both.

## 20.6 Two undocumented values

**`status` returns `SETTLED`.** The specification lists `PAID`, `FAILED` and `PROCESSING` as
the values of the `payment_status` filter. The object itself came back `SETTLED`. Code that
maps against the documented three would not recognise it.

**A non-existent order id returns success.** Order ids `001`, `002` and `003` each returned
`code: 0`, `message: "Success"`, zeros and an empty transaction list. No 404 and no error
code. So `code: 0` is not evidence that an order exists. The check is `total_count` and
whether `order_create_time` is zero. This is the same silent-failure shape as `sort_field`
falling back on a typo, recorded in A19.4.

## 20.7 What is still open

The payload is IDR, from an Indonesian sandbox shop. Fee and tax fields vary by region, and
sixteen of the seventeen tax fields in this response are not UK taxes. A GB shop will return
a different subset. So the mapping work this document makes necessary should be done against
a GB payload, not this one.

`GBGBLCRKQTEX`, the real British shop, is approved and has no products, so it has no orders
and no statements. That is the shop whose payload decides the mapping.

## 20.8 The ingest had not parsed since commit 142c3dd

Found while making the corrections above, and it is the worst thing in this document.

`testdata/ingest.py` acquired a stray `e["settlement_month"] = smonth` at the wrong
indentation in two places, in commit `142c3dd` earlier on 23 September. The file has been an
`IndentationError` ever since. It could not be imported, let alone run.

Through that entire period `README_v0.2.md` recorded action 12 as "Built. 118 ledger
entries, five assertions passing", and nothing contradicted it, because nobody ran the file
and the status line was the only evidence anyone consulted.

Repaired and run. It now produces 119 ledger entries across 20 orders, 3 settlements and 7
returns, with one unmapped field, `live_specials_fee_amount`. The count is 119 and not 118,
and the difference has not been investigated, so the previous figure should not be trusted
either.

This is the third instance of the same pattern on this project. Authentication verified the
wrong algorithm and its tests passed because the fixtures shared the assumption. Five views
leaked across tenants while a check that queried base tables reported clean. Now a status
line asserted a passing test suite for a file that did not compile. Rule 7 exists because of
the first two. This one happened after the rule was written.

## 20.9 What was corrected on 23 September

Three defects fixed, all verified by running the file afterwards.

**The tax loop records what it does not recognise.** Any field absent from `TAX_MAP` is now
added to `UNMAPPED` before being skipped, matching what the fee loop already did. Sixteen
real tax fields, `vat_amount` and `import_vat_amount` among them, previously left no trace.

**`pence()` takes a currency.** It multiplied by 100 regardless. `MINOR_UNIT_EXPONENT` holds
GBP alone, because GBP is the only currency verified against a real payload, and an
unverified currency raises rather than guessing. A wrong power of ten does not fail loudly.
It produces plausible numbers that are wrong by a factor of a hundred.

**The syntax error from 20.8.**

One thing deliberately not done. `FEE_MAP` was not expanded from 7 entries to 57. Under A8
an unmapped fee is carried at full value with TikTok's own field name kept in
`tiktok_fee_type`, and index `ledger_unmapped_idx` supports the nightly sweep that raises a
discrepancy for each one under CLR-4. The design anticipated this. Inventing fifty
categories for fields that may be permanently zero for a British seller would be
speculation, which rule 7 forbids. It waits for a payload from `GBGBLCRKQTEX`.

`testdata/check_maps_against_real.py` measures the gap against the real payload on demand,
importing the maps from the ingest rather than restating them so the two cannot drift.
