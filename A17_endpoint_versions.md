# Action 17. Endpoint versions, checked against the specification

Decided 23 September 2026, using the TikTok Shop OpenAPI bundle carried in this session.
Two questions were put to it. One had a wrong answer sitting in A11 since yesterday.

## 17.1 The settlement detail endpoint was pinned to the wrong version

A11 section 6 lists `GET /finance/202309/statements/{id}/statement_transactions` for
settlement detail, while using `202501` for the order-level equivalent on the same page. A
`202501` version of the statement-level endpoint exists, and the difference between the two
is not cosmetic.

| | 202309 | 202501 |
|---|---|---|
| Fields in the response | 69 | 131 |
| Array key | `statement_transactions` | `transactions` |

Eighty-one fields appear only in `202501`. Five of them are the ones this product was built
on:

- `reserve_id`
- `reserve_amount`
- `reserve_status`
- `total_reserve_amount`
- `payable_amount`

Migration 0014 added the `reserve` entry type, the `reserve_withheld` and `reserve_released`
categories, `settlements.payable_amount_minor` and `settlements.total_reserve_amount_minor`,
and rewrote `settlement_reconciliation` to exclude reserves from net proceeds. Every one of
those models a field that `202309` does not return.

Had the integration been written to the document rather than to the fixtures, it would have
called `202309`, found no reserve fields, and recorded no reserves at all. The
reconciliation would then have reported a correct statement as wrong by the reserved
amount, which is exactly the fault found and fixed on 22 September when a reserve fixture
was first seeded.

**The ruling.** Settlement detail is `GET /finance/202501/statements/{statement_id}/statement_transactions`.
A11 section 6 is corrected. The payload generator and the ingest already used the `202501`
shape, including the `transactions` array key, so no code changes.

Other renames between the two versions, recorded so nobody reintroduces the old names:
`gross_sales_amount` becomes `subtotal_before_discount_amount`, `fee_amount` becomes `fee`,
`customer_shipping_fee_amount` becomes `customer_shipping_fee`,
`affiliate_commission_before_pit` becomes `affiliate_commission_amount_before_pit`,
`isr_income_tax_amount` becomes `isr_amount`, and `iva_vat_amount` becomes `iva_amount`.

## 17.2 The other versions are correct

| Purpose | Endpoint | Highest available |
|---|---|---|
| The calculator | `/finance/202501/orders/{order_id}/statement_transactions` | Yes |
| Settlement list | `/finance/202309/statements` | Yes, no newer version exists |
| Awaiting settlement | `/finance/202507/orders/unsettled` | Yes |
| VAT registration | `/finance/202504/tax_information` | Yes |
| Payments | `/finance/202309/payments` | Deliberately unused, A11 section 7 |

## 17.3 The history window is not stated, so it has to be measured

A16.2 rules twenty-four months of history on every plan, and recorded that whether TikTok
exposes two years was unverified.

The specification does not settle it either way. `/finance/202309/statements` takes
`statement_time_ge` and `statement_time_lt` as an open range with no documented maximum
window, no documented retention floor, and no error described for asking too far back. The
same is true of `/finance/202309/payments` and `/finance/202309/withdrawals`. Nothing in the
finance or order specifications names a limit in days, months or years.

So twenty-four months is neither promised nor forbidden. It is an empirical question, and
it became answerable on 23 September when the shop was approved. The test is one call:
request statements with `statement_time_ge` set two years back and see where the oldest
record falls. Until that call has been made, A16.2 stands as an intent and no screen
advertises it.

## 17.4 What this check could not do

The bundled specification is a local snapshot, not proof of what is current. The proper
procedure is to check Partner Center docv2 for versions newer than the bundle carries.
`partner.tiktokshop.com` is refused by this environment's network policy, along with every
other TikTok host, so that check was not possible.

This means 17.1 and 17.2 are correct against the bundle and may be behind the live
catalogue. Both should be re-checked once the allowed domains are opened.
