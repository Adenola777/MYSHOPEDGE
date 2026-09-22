# A11. Statement ingestion, confirmed TikTok fields, and the scope ruling

Prepared 22 September 2026. This action replaces section 3.5 of the API Integration
document, *Field mapping (to validate)*, and records three scope decisions.

## A11.1 The statement dating rule

TikTok generates statements daily at 00:00 UTC, and each statement covers the previous
day. Its own documented example confirms it: to read activity for 5 to 10 October, the
query filters `statement_time` from 6 October 00:00 to 11 October.

**`statement_time` is therefore one day after the activity it describes.** Treating it as
the period would misdate every statement by exactly one day.

There is a second, smaller problem stacked on it. The cut is at 00:00 UTC, while
`ledger_entries.basis_day` is derived in Europe/London. From late March to late October a
TikTok statement day runs 01:00 to 01:00 London. A statement day and a MyShopEdge day are
not the same twenty-four hours for roughly seven months of the year.

| Requirement | Statement |
|---|---|
| LED-22 | The system shall store TikTok's `statement_time` unaltered and shall derive the statement's activity date as `statement_time` minus one day in UTC. Acceptance: a statement stamped 1 July 00:00 UTC reports an activity date of 30 June. Priority: Must |
| CLR-6 | Where a daily figure taken from a TikTok statement is shown beside a daily figure derived from `basis_day`, the screen shall state that the two cover different hours. Acceptance: no screen presents the two as directly comparable without that statement. Priority: Must |

Migration 0010 implements LED-22 as a stored generated column, `settlements.activity_date`,
so the rule is applied once in the database rather than in every query.

## A11.2 Confirmed TikTok field names

These replace the placeholder categories in the v0.1 mapping table, which read
*Commission, creator commission, shipping, promotion, other*. They are taken from TikTok's
published specification for
`GET /finance/202501/orders/{order_id}/statement_transactions`.

The breakdown exists only inside `sku_transactions[]`. The four money fields on the `data`
object are merged totals.

**Build rule.** MyShopEdge never reads the top-level `fee_and_tax_amount`,
`revenue_amount`, `shipping_cost_amount` or `settlement_amount`. It reads the SKU array and
sums the breakdown itself. If the array is empty while the summary is not, that is a
discrepancy under DSC-1, not a figure to display.

### Revenue, from `sku_transactions[].revenue_breakdown`

| MyShopEdge term | TikTok field |
|---|---|
| Gross sales | `subtotal_before_discount_amount` |
| Seller discounts | `seller_discount_amount` |
| Gross sales refunded | `refund_subtotal_before_discount_amount` |
| Discounts returned on refund | `seller_discount_refund_amount` |
| Net sales | `revenue_amount` |

TikTok's own documentation describes `subtotal_before_discount_amount` as the shop's gross
sales and `revenue_amount` as the net sales amount, which confirms the terminology standard
in A8.

### Fees, from `sku_transactions[].fee_tax_breakdown.fee`

The object carries 33 named fees. Six apply to a UK seller.

| MyShopEdge category | TikTok field |
|---|---|
| `platform_commission` | `platform_commission_amount`, documented as UK only |
| `affiliate_commission` | `affiliate_commission_amount` |
| `affiliate_commission` | `affiliate_ads_commission_amount` |
| `affiliate_commission` | `affiliate_partner_commission_amount` |
| `transaction_fee` | `transaction_fee_amount` |
| `return_handling_fee` | `refund_administration_fee_amount` |

The three affiliate fields are charged on different grounds and are shown as separate lines
on the calculator. They share a ledger category because they are all commission paid to a
creator or partner.

Any fee field not in this table posts as `unmapped_fee` with the TikTok field name kept
verbatim in `ledger_entries.tiktok_fee_type`, and raises a discrepancy under CLR-4. The
remaining 27 fees are specific to Indonesia, Mexico, Brazil, Vietnam or the United States
and are not expected on a UK statement.

### Taxes, from `sku_transactions[].fee_tax_breakdown.tax`

`local_vat_amount` is the field a UK local seller sees. The other ten are cross-border or
non-UK.

### Shipping, from `sku_transactions[].shipping_cost_breakdown`

Sixteen fields. **Return shipping is three of them, not one**, which corrects the v0.2
return detail screen:

| Line | TikTok field |
|---|---|
| Return shipping you paid | `return_shipping_fee_amount` |
| Return label fee collected from the customer | `return_shipping_label_fee_amount` |
| Platform-funded portion of free returns | `free_return_subsidy_amount` |

**`supplementary_component` is not summed.** Its twelve fields explain what is already
inside `actual_shipping_fee_amount` and `shipping_fee_discount_amount`. Adding them to the
parent figures double-counts. One of them, `fbt_fulfillment_fee_reimbursement_amount`, is
deprecated and returns an empty string.

| Requirement | Statement |
|---|---|
| LED-23 | The system shall not include any `supplementary_component` field in a sum contributing to `shipping_cost_amount`. Acceptance: a golden dataset carrying populated supplementary fields produces the same shipping total as one with them empty. Priority: Must |

## A11.3 Region-conditional fields

TikTok returns a different field set by region, and the differences are not cosmetic.

| Field | Applies to | UK seller |
|---|---|---|
| `net_sales_amount` | Local sellers outside SEA | Populated |
| `shipping_cost_amount` | Local sellers outside SEA | Populated |
| `revenue_amount` | All regions except the UK and the US | Always null |
| `fee_amount` | All regions, shipping excluded except SEA | Populated, shipping excluded |

| Requirement | Statement |
|---|---|
| DSC-6 | Where a statement returns both `net_sales_amount` and `revenue_amount` populated, the system shall raise a discrepancy rather than choose between them. Acceptance: `settlement_totals_check.region_mapping_conflict` is false for every row. Priority: Must |

## A11.4 Endpoints, and one that is not used

| Purpose | Endpoint |
|---|---|
| The calculator | `GET /finance/202501/orders/{order_id}/statement_transactions` |
| Settlement list and payment status | `GET /finance/202309/statements`, `sort_field=statement_time` |
| Settlement detail | `GET /finance/202309/statements/{id}/statement_transactions`, `sort_field=order_create_time` |
| Awaiting settlement | `GET /finance/202507/orders/unsettled`, `sort_field=order_create_time` |
| VAT registration at onboarding | `GET /finance/202504/tax_information` |
| Orders | `POST /order/202309/orders/search`, `GET /order/202309/orders` |
| Returns | `POST /return_refund/202309/returns/search`, `GET /return_refund/202309/returns/{id}/records` |

`sort_field` is required on all four finance endpoints and its permitted value differs
between the statement list and the statement transactions. `page_size` accepts 1 to 100 and
defaults to 20. `shop_cipher` is marked required in TikTok's documentation and optional in
its OpenAPI specification; the documentation governs, because passing it wrongly for a
cross-border shop returns incorrect data rather than an error. The required scope for the
finance endpoints is `seller.finance.info`.

Data is available from 1 July 2023 onward. Onboarding must not promise a backfill earlier
than that.

**`GET /finance/202309/payments` is not used.** It is the bank reconciliation endpoint, and
bank reconciliation is out of scope under PRD 6.2, *payments, lending, or any regulated
financial activity*.

## A11.5 Three scope rulings

**Bank reconciliation is out.** No open banking provider, no account matching, and
`GET /finance/202309/payments` is not called.

A consequence follows. No TikTok endpoint returns the text a seller sees on a bank
statement. `settlements.settlement_reference` therefore has no automatic source. It remains
as a nullable field that the seller may fill in, and the v0.2 settlement detail screen must
stop presenting it as something MyShopEdge supplies.

| Requirement | Change |
|---|---|
| REC-3 | Restated. The settlement detail screen shall show TikTok's statement identifier and payment identifier. It shall not show a bank statement reference unless the seller has entered one |

**The TikTok invoice stays.** `tiktok_invoices` is retained, and so is the capture of the
invoice number and the credit note number, because they are what make a fee reversal
reconcilable against the fee that was charged. The original v0.1 mapping already listed
*Invoice number, transaction reference*, so this is a correction of where the data is held
rather than an addition to scope.

What changes is the wording on screen. PRD 6.2 excludes *VAT accounting for registered
sellers*, so the settlement detail screen must not tell the seller the invoice is how they
reclaim VAT on TikTok's fees. The card states what the invoice is and offers the document.
It gives no VAT advice.

**HMRC and Making Tax Digital remain out**, as PRD 6.2 already stated. MyShopEdge prepares
figures. It does not submit, and no screen may imply that it does.

## A11.6 Still unresolved

The invoice number appears in none of the four finance endpoints examined:
`statements`, `statements/{id}/statement_transactions`, `orders/{order_id}/statement_transactions`
and `tax_information`. `payment_id` is a payment reference and `statement_id` is a statement
reference; neither is an invoice number.

Until a UK Seller Center account is inspected, it is not known whether the number is
reachable at all, or whether it exists only on a downloadable document. If it is only on a
document, `tiktok_invoices` is populated by parsing a file rather than by an API call, and
the ingestion design for that table changes.

**The shop currently authorised is `7495568017912465932`, region ID, Indonesia.** Indonesia
is in the SEA region, so it returns the inverse of the UK field set on every point in A11.3
and cannot call the payments endpoint at all. No mapping in this document can be validated
against it. A UK shop, live or sandbox, is the prerequisite for the integration spike.

The TikTok Shop Partner ID on record is `7494921940834551457`. A Partner ID identifies the
Partner Center account and does not authorise a shop.
