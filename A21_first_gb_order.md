# Action 21. The first real British order, and a rule it breaks

23 September 2026, 16:06. A real order was placed on `GBGBLCRKQTEX`, the British shop, and
its Seller Centre export is the first genuine GB commercial data this project has held.

The export is saved at `testdata/real_payloads/order_export_gb_2026-09-23.csv` with nineteen
of its sixty-two columns removed. SYN-7 says buyer and recipient data is dropped before
anything is written, and that rule binds whoever is writing, not only the ingest. Recipient,
phone, address, buyer username, tracking and package identifiers are all gone.

## 21.1 The order

| Field | Value |
|---|---|
| Order ID | `576955651451099542` |
| SKU ID | `1729934206123809441` |
| Product | My Special Mug, Default, 1 unit |
| Created | 23/09/2026 16:06:19 |
| Paid | 23/09/2026 16:06:25 |
| Status | To ship, Awaiting Packing |
| Fulfilment | By seller |
| Weight | 0.453 kg |
| Category | Mugs |
| Channel | Product cards |

Paid and not shipped, so it is unsettled. That makes it the input to the first GB finance
payload this project will ever see, which A20.7 records as the thing the fee mapping waits
for.

## 21.2 The thirteen money columns, verbatim

TikTok's own labels, which is what A8 section 3.5 wanted for the export side.

| Column | Value |
|---|---|
| SKU Unit Original Price | GBP 8.00 |
| SKU Subtotal Before Discount | GBP 8.00 |
| SKU Platform Discount | GBP 0.00 |
| SKU Seller Discount | GBP 0.00 |
| SKU Subtotal After Discount | GBP 8.00 |
| Original Shipping Fee | GBP 3.99 |
| Shipping Fee Seller Discount | GBP 3.99 |
| Shipping Fee Platform Discount | GBP 0.00 |
| Shipping Fee After Discount | GBP 0.00 |
| Taxes | GBP 0.00 |
| Product Tax Amount | GBP 0.00 |
| Shipping Tax Amount | GBP 0.00 |
| Order Amount | GBP 8.00 |

## 21.3 The seller funded the shipping, and Order Amount does not say so

The buyer paid £8.00. Shipping listed at £3.99 and the buyer paid none of it, because
`Shipping Fee Seller Discount` is the full £3.99 and `Shipping Fee Platform Discount` is
zero. The seller absorbed it.

`Order Amount` is £8.00. It does not carry the £3.99.

So on this order the seller's position before TikTok has taken a single fee is £8.00 of
revenue against £3.99 of shipping they paid for, which is a third of the order's value, plus
the cost of the mug, which is not in this export at all. A seller reading Order Amount as
their takings is wrong by nearly half before anything else is deducted.

This is the first time this project has seen that gap in real data rather than asserted it
in a specification. It is the product's entire reason to exist, sitting in row one of the
first real order.

## 21.4 A11.2 has to be amended, and this order is why

A11.2 rules that `supplementary_component` explains its parents and is never summed. The
arithmetic reason for that rule is sound and it stands.

The problem is where TikTok puts the seller and platform split. In the real settlement
payload:

- `shipping_cost_breakdown.shipping_fee_discount_amount` sits at the top level and is what
  `SHIP_MAP` maps.
- `shipping_cost_breakdown.supplementary_component.seller_shipping_fee_discount_amount` and
  `platform_shipping_fee_discount_amount` sit inside the object A11.2 tells us to leave
  alone.

The total discount is therefore reachable and the question of who paid it is not. On this
order the seller funded all £3.99. Had TikTok funded it instead, every figure our ledger
records would be identical and the seller's true cost would be zero.

**A11.2 is amended.** `supplementary_component` must never be summed into a total, because
double counting it would corrupt every reconciliation. It must be read for attribution,
because the seller and platform split of a discount exists nowhere else, and only the
seller-funded part is a seller cost.

The rule was written to prevent double counting and it does that. It was not written to
forbid reading, and read as a blanket prohibition it would lose the single most important
number on this order.

## 21.5 No VAT on this order

`Taxes`, `Product Tax Amount` and `Shipping Tax Amount` are all GBP 0.00, and both tax rate
columns are `0`. Consistent with a seller below the registration threshold, which is what
the VAT threshold tracking in the Starter plan feature list is for. Nothing to change, but it
means this order will not exercise any VAT path, and the first VAT-bearing order should be
treated as a separate test case.

## 21.6 What this unblocks

The order id `576955651451099542` is the input to two calls that would produce the first GB
fee and tax payload:

- `GET /finance/202501/orders/{order_id}/statement_transactions`, which needs only the order
  id and the shop cipher.
- `GET /finance/202507/orders/unsettled`, with `search_time_ge` at `1735689600`. Its own
  description warns that every amount it returns is an estimate that changes at settlement,
  so it is good for field names and not for figures.

Either would let `testdata/check_maps_against_real.py` run against British data instead of
Indonesian, which is the condition A20.7 set on the fifty-field mapping decision.

A settled GB statement still requires this order to ship, deliver, and pass the return
window. That is real time and nothing can shorten it.

---

## 21.7 Section 21.3 is corrected by A22

Written 23 September at 17:30, after the unsettled orders export arrived.

21.3 said £3.99 of the £8.00 was "already spent". The unsettled export shows TikTok's
estimated settlement is `8.00 − 0.72 = 7.28`, with the shipping lines netting to zero. The
£3.99 is forgone revenue the customer would have paid, not money leaving the settlement.

The real uncaptured cost on this order is the postage the seller pays a carrier to send a
453 gram parcel, which appears in no TikTok figure at all. A22.1 has the detail.
