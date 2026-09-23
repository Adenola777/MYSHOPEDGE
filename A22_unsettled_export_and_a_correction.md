# Action 22. The unsettled export, and a correction to A21

23 September 2026, 17:23. The Seller Centre unsettled orders export for
`GBGBLCRKQTEX`, covering the single British order placed at 16:06. Saved at
`testdata/real_payloads/unsettled_orders_gb_2026-09-23.csv`, 69 named columns, one row. It
carries no personal data, so nothing was removed.

This is the first British money breakdown this project has seen, and it corrects A21.

## 22.1 The correction. The £3.99 is forgone revenue, not a deduction

A21.3 said that of the £8.00 order, "£3.99 is already spent" before any TikTok fee. That
framing is wrong, and this export shows why.

| Column | Value |
|---|---|
| Gross sales | 8.00 |
| Fees | -0.72 |
| Shipping | 0.00 |
| **Total estimated settlement amount** | **7.28** |
| Customer-paid shipping fee before discounts | 3.99 |
| Seller shipping fee discount | -3.99 |

The two shipping lines net to zero and the Shipping total is zero. TikTok's settlement is
`8.00 − 0.72 = 7.28`, and the £3.99 never enters it.

So the seller does not pay £3.99 out of the settlement. The customer would have paid it, the
seller waived it, and it is revenue that was never collected rather than money that leaves.

**The product's claim survives, for a better reason.** This order is Fulfilment by seller.
The seller will pay a real carrier to post a 453 gram parcel, and that cost appears in no
TikTok figure anywhere. It is not in the order export, not in the unsettled export, and it
will not be in the settlement. A seller who reconciles against TikTok alone will never see
it.

So the true position on this order is £7.28 arriving, against the cost of the mug and the
cost of actually posting it, neither of which TikTok records. That is a sharper statement
than A21 made and it is supported by the data rather than by my reading of a column name.

**A21.3 is superseded by this section.** `testdata/ingest_order_export.py` posts
`seller_shipping` at minus £3.99 and that is now known to be wrong as a settlement
deduction. The waived shipping is a pricing decision, and the real postage is a seller cost
that has to come from somewhere other than TikTok.

## 22.2 The commission rate is 9.00 per cent, measured

`TikTok Shop commission fee` is `-0.72` against `Gross sales` of `8.00`. That is exactly
9.00 per cent. It is the only fee on this order: every other fee column is zero.

This is the first real UK rate this project has held. It applies to this shop, this
category, Mugs, and this order content source, Product card. It should not be generalised
into a constant, and nothing in the code should hardcode it. It is recorded so that a
calculated figure can be sanity-checked against a known real one.

## 22.3 Settlement timing is Delivered plus 8 days

| Column | Value |
|---|---|
| Estimated Settle time | Delivered + 8 days |
| Unsettled reasons | Waiting for package delivery |

Nobody had asked when settlement happens, and the whole cash basis depends on it. A5 splits
every view into a sales basis and a cash basis, and `records.py` picks `basis_day` or
`settlement_month` from that choice. This is the rule that sets the gap between them for a
UK seller: money lands eight days after delivery, not after dispatch and not after payment.

Two consequences.

An order paid on the 28th of a month and delivered on the 30th settles in the following
month. The sales basis and the cash basis will disagree across every month end, which is the
behaviour `ledger_basis_month_mismatch` exists to surface, and there is now a real number
behind it.

`Unsettled reasons` is a human-readable status string. It belongs on the screen verbatim,
because "Waiting for package delivery" tells a seller more about their own money than any
status code this project could invent.

## 22.4 The British column labels

69 named columns, against the 57 fee and 24 shipping and 17 tax fields A20 measured in the
Indonesian API payload. These are the seller-facing labels rather than the API field names,
and A8 section 3.5 wanted both.

Every fee column on this order except the commission is zero, which is expected for a first
order with no affiliate, no promotion and no advertising. The column names still tell us
what a UK seller can be charged: affiliate commission and its deposit and refund, affiliate
partner commission, Affiliate Shop Ads commission, co-funded promotion, VAT, shipping
service fee, campaign resource fee, Smart Promotion fee, campaign service fee, managed
service plan per order, and GMV Max ad fee.

## 22.5 What this does not settle

The figure is an estimate. TikTok's own unsettled endpoint warns that every amount it
returns is subject to change before settlement. £7.28 is what TikTok expects to pay, not
what it will pay.

The order is still `Waiting for package delivery`. Until it ships, is delivered, and eight
days pass, there is no statement, and the mapping question in A20.7 stays open. Nothing here
shortens that.
