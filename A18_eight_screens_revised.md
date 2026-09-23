# Action 18. The eight screens the rulings moved

Decided 23 September 2026. A15 settled six screens on the evening of 22 September and left
eight others describing a product that had changed underneath them. These eight are the
ones the reading half of the application displays, so building from the old specification
would have built the wrong thing carefully.

| Screen | What moved under it |
|---|---|
| S9 Products | A row that cannot be matched never creates a product |
| S10 Product detail | The calculator view, and variants with no seller SKU |
| S11 Money | Reserves are withheld money, and a payout is not net proceeds |
| S14 Discrepancy detail | A seventh kind, `unmapped_fee` |
| S22 Records behind a figure | Four new categories and three new filters |
| S23 Export | The accountant feed left the MVP |
| S25 Stock adjustment | A cancellation raises a stock movement |
| S26 Stock movement history | The same movement has to appear in the history |

## 18.1 S9 Products

**What changed.** Ruled 22 September: where TikTok returns no seller SKU for a variant, no
product is created. The old specification had the upload create one.

**What the screen shows.** The product list is what TikTok says exists, and nothing else. A
variant with no seller SKU still appears, because TikTok returned the variant, but it
carries no cost and cannot be given one from a file.

**The state that needs words.** A variant with no seller SKU is not an error and must not
look like one. It reads "No seller SKU. Add a cost on this screen." with the manual entry
beside it. A seller who sees a warning triangle against a product that is selling perfectly
well will think something is broken.

**What the screen must never do.** It must not invent a product to hold an orphaned cost
row. Those rows stay on S4 until the seller fixes them or abandons them.

## 18.2 S10 Product detail

**What changed.** Two things. The calculator view from A2 belongs here, and the blank
seller SKU ruling applies to the cost field.

**The calculator.** For one product, over a chosen period: units sold, gross sales, each
deduction as its own line, the cost of goods, and what is left. It is the per-product
version of the grid A2 specifies, and it answers the question this product exists to answer,
which is whether a particular item makes money.

**Where the figures come from.** `GET /finance/202501/orders/{order_id}/statement_transactions`
at ingestion, allocated across order lines by largest remainder, then read from
`ledger_entries` by `product_id`. The allocation is why a single product's deductions add up
to the order's deductions exactly, with no rounding drift, and the screen should say the
figures are allocated rather than letting a seller assume TikTok reports per product.

**The cost field.** Editable where the variant has a seller SKU. Where it does not, the
field is present and the file route is not offered.

## 18.3 S11 Money

This is the screen the reserve work changed most, and getting it wrong misstates what a
seller is owed.

**Three figures that are not the same.**

| Figure | What it is |
|---|---|
| Net proceeds | Sales less every deduction, from `settlement_reconciliation` |
| Reserve withheld | Money TikTok is holding, `total_reserve_amount_minor` |
| Payout | What actually reaches the bank, `payable_amount_minor` |

**Why it matters.** A seller who reads net proceeds as the amount arriving in their account
will think TikTok has short-paid them by the reserved amount. The screen shows all three,
in that order, with the reserve labelled as held rather than lost. Reserves are released
later and appear as `reserve_released`, so the same money must not be counted twice.

**Settlement status.** `settlement_reconciliation` computes `unexplained_minor` over ledger
entries excluding `payout` and `reserve`. A settlement reconciles or it does not, and where
it does not the difference is shown with a route to S14 rather than a silent rounding.

**Trace.** Migration 0014, A11, A17.1.

## 18.4 S14 Discrepancy detail

**What changed.** A seventh discrepancy kind, `unmapped_fee`, raised by the nightly sweep
when TikTok charges a fee the mapping table does not recognise.

**Why it is different from the other six.** The other six compare two figures. This one has
only TikTok's side: `tiktok_value` carries TikTok's verbatim field name and `seller_value`
is null, because the seller has no competing figure to offer.

**What the screen shows.** The fee's verbatim name as TikTok sent it, the amount, the
settlement it appeared on, and an explanation that MyShopEdge does not recognise this fee
rather than that the seller has done something wrong. The money is counted either way. It
sits in `unmapped_fee` and reduces what the seller keeps, so the figures stay right while
the label stays honest.

**Trace.** Migration 0013, `ledger_unmapped_idx`.

## 18.5 S22 Records behind a figure

**What changed.** Four categories were added and three filters became available.

The categories are `platform_adjustment`, `unmapped_fee`, `reserve_withheld` and
`reserve_released`. All four have to render with a human label, because a seller reading
`reserve_withheld` in a list of otherwise plain English has hit a hole in the product.

The filters are `product_id`, `return_id` and `settlement_id` on `GET /records`, added on
22 September. Together with the period parameters that were already there, this is what lets
every figure on every screen open into the records behind it.

**The rule this screen exists for.** Every figure a seller sees can be opened, and what
opens is the ledger rows that produced it, not a recalculation. If the rows do not add up to
the figure, the figure is wrong, and the seller should be the one who finds that out.

**Trace.** Migration 0014, `api/openapi.yaml`.

## 18.6 S23 Export

**What changed.** The accountant feed is out of the MVP, ruled 22 September. `feed_tokens`
was dropped and `accountant` was removed from both the `exports` and `export_schedules`
kind constraints.

**What remains.** Three kinds: `month_summary`, `ledger` and `transactions`.

**What the screen must not do.** It must not offer the accountant feed, mention it as
coming, or leave a disabled control where it used to be. A greyed-out button is a promise,
and this one is not being made.

**Scheduled exports** stay on Pro, as the price sheet says.

## 18.7 S25 Stock adjustment and 18.8 S26 Stock movement history

**What changed.** Ruled 22 September: a cancellation raises a stock movement. Until then
only returns did.

**Why it was wrong.** A cancelled order never ships. The units were committed and then
released, and a seller counting stock against the product's figures would have found the
product short by every cancelled unit. That is the kind of error that makes a seller stop
trusting the whole product rather than the one screen.

**What S25 shows.** The adjustment form, unchanged, plus an accurate on-hand figure that
now accounts for cancellations.

**What S26 shows.** Movements of five kinds rather than four: sale, return resellable,
return damaged, manual adjustment, and cancellation. The cancellation row says the order was
cancelled and the units returned to stock, with the order reference beside it.

**The trap.** A cancellation after a return, or a return on an order later cancelled, must
not move the same units twice. `RETURN_BY_ORDER` links them and the ingest applies one
movement per unit per event.

## 18.9 What this action does not settle

The figures on all eight screens have only ever been seen against fixtures generated from
TikTok's published specification. A17.3 records that even the history window is unstated.
Nothing here is proved until a real shop is connected, and these screens are where a wrong
assumption would show up first, because they are the screens a seller reads.
