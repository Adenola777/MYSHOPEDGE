# Action 4: Returns, stock and the account

Closes audit question 2. Three defects are fixed: stock can be counted twice, return costs never reach "You keep", and the refund-only case has no requirement and no test.

---

## 4.1 Stock can be counted twice

### The defect

`stock_positions.on_shelf` is a generated column: `on_shelf = tiktok_stock + adjusted_delta`.

When the seller marks a returned item Resellable, `adjusted_delta` rises by one. That is correct, because TikTok does not move stock on a return. But many sellers also put the unit back inside TikTok Shop by hand. TikTok's next sync then raises `tiktok_stock` by one as well, and `on_shelf` rises by two for a single returned unit. No document defines a reset, so the error is permanent and silent.

### The rule, SRD section 3.6

| ID | Requirement | Acceptance | Trace | Priority |
|---|---|---|---|---|
| STK-8 | Absorb a rise in TikTok's own stock figure into the seller's adjustment, up to the size of the adjustment, whenever the rise cannot be explained by a recorded movement, and tell the seller that the adjustment was reduced. | A resellable return followed by a matching manual rise in TikTok leaves On the shelf one higher in total, not two, and the seller sees a notice naming the SKU | Section 23 (INV-6) | Must |

### How absorption works

The rule runs at every sync, per SKU, before `on_shelf` is read.

1. Compute the unexplained rise: `rise = new_tiktok_stock − previous_tiktok_stock`, less any rise already explained by a movement recorded since the previous sync, such as a cancellation restoring stock or a new purchase the seller recorded.
2. If `rise` is not positive, stop. Falling stock is ordinary selling and is never absorbed.
3. If `adjusted_delta` is not positive, stop. There is nothing to absorb into.
4. Absorb `absorbed = min(rise, adjusted_delta)` and set `adjusted_delta = adjusted_delta − absorbed`.
5. Write a movement row of type `adjustment_absorbed` carrying `absorbed`, the SKU, the two TikTok figures and the resulting `adjusted_delta`, so S26 shows what happened and why.
6. Raise one notice per SKU per day, worded as: "You put 1 unit of Hydrating Cleanser 300ml back into TikTok. We had already added it, so we have taken ours off. On the shelf is still 34."

`on_shelf` does not move at all when absorption runs, which is the point. The two sources of the same unit cancel.

### Why it is capped at the adjustment

Absorbing more than `adjusted_delta` would hide a genuine restock. A seller who receives 50 units from a supplier and enters them in TikTok sees `tiktok_stock` rise by 50. If the adjustment is 3, only 3 are absorbed and 47 flow through to `on_shelf`, which is correct. The cap is what separates a duplicate from a delivery.

### What the seller sees

S25 states the rule before the seller saves an adjustment, in the words already drafted in Action 3: "If you also change this in TikTok, tell us. When TikTok's own figure rises to match, we take the rise out of your adjustment so the unit is not counted twice."

S26 shows the absorption as its own movement row, with units of zero and the reason given, so the history still adds up to the count on screen.

### Schema and orchestration

Added to section 3.1 of the Backend Orchestration document, in the stock projection rules table.

| Event | Effect on stock_positions |
|---|---|
| TikTok stock rises with no movement to explain it, and an adjustment exists | `adjusted_delta` falls by the smaller of the rise and the adjustment; `on_shelf` is unchanged; a movement of type `adjustment_absorbed` is written; the seller is told. |

```sql
-- The column is movement_type, not kind, and the v0.1 value list is the one below.
-- Both were confirmed by running the schema rather than by reading it.
alter table stock_movements drop constraint stock_movements_movement_type_check;
alter table stock_movements add constraint stock_movements_movement_type_check
  check (movement_type = any (array[
    'sale_reserved','posted','cancelled','return_resellable','write_off',
    'manual_adjustment','adjustment_absorbed']));
```

A second check constraint, `stock_movements_check`, already refuses a `manual_adjustment`
with a null reason, so STK-4's rule was enforced in v0.1 even though no screen existed
for it. The test harness asserts it rather than adding it.

A tolerance is also defined rather than left open. Absorption runs only where the unexplained rise is 20 units or fewer. A larger rise is treated as a restock and raises a discrepancy under DSC-1 instead, because absorbing a large figure silently would do more damage than the duplicate it prevents.

### Test cases, QA section 5.6

| ID | Test | Expected result | Trace |
|---|---|---|---|
| TC-STK-08 | Mark a return Resellable, then raise TikTok's stock for that SKU by 1. | On the shelf rises by 1 in total. The adjustment returns to its previous value. One notice is raised naming the SKU. | STK-8 |
| TC-STK-09 | Raise TikTok's stock by 50 for a SKU whose adjustment is 3. | 3 are absorbed and 47 flow through. On the shelf rises by 47. | STK-8 |
| TC-STK-10 | Raise TikTok's stock by 30 for a SKU whose adjustment is 30. | Nothing is absorbed. A discrepancy is raised, because the rise exceeds the 20-unit tolerance. | STK-8, DSC-1 |
| TC-STK-11 | Let TikTok's stock fall while an adjustment is positive. | Nothing is absorbed. The adjustment is unchanged. | STK-8 |
| TC-STK-12 | Cancel an order before dispatch, which restores stock, then sync. | The rise is explained by the cancellation movement and is not absorbed. | STK-6, STK-8 |

---

## 4.2 Return costs and "You keep"

### The defect

Net Proceeds counts sales, deductions and refunds only. Return postage posts as a `return_cost` entry and a write-off posts as a `write_off` entry, and neither is inside Net Proceeds. Product Specification v2.0 section 12 was expected to carry them through Return Loss, and that document is not in the pack. Nothing in the ten documents states whether return costs reach the figure the seller actually reads.

### The formulas, written into the SRD

These replace the citation of Section 12 and make the pack self-contained.

**Return Loss, for a period.**

```
Return Loss = −( sum of return_cost entries + sum of write_off entries )
```

Both entry types are negative in the ledger, so the leading minus makes Return Loss a positive amount of money lost. This reproduces golden dataset G2 exactly: a return with £2.85 of postage and no write-off gives £2.85; the same return marked Unsellable adds the £2.10 product cost and gives £4.95.

**Contribution, for a period.**

```
Contribution = Net Proceeds − Cost of goods retained
Cost of goods retained = product cost × ( units sold − units returned )
```

A returned unit's cost never appears here. If the unit came back resellable, its cost sits in stock. If it came back unsellable, its cost is a write-off inside Return Loss. Counting it in both places was the error waiting to happen.

**You keep, for a period.**

```
You keep = Contribution − Return Loss
```

**The identity that must hold.**

```
Net Proceeds = Paid Out + Awaiting Settlement
```

This is unchanged. Return costs and write-offs are outside Net Proceeds by design, because TikTok does not settle them: return postage the seller paid never passes through a TikTok statement, and a write-off is not money at all. LED-4 therefore still holds exactly as written, and Action 5 extends the same check to days and weeks without touching it.

### Requirements added to SRD section 3.7

| ID | Requirement | Acceptance | Trace | Priority |
|---|---|---|---|---|
| RET-7 | Carry Return Loss into You keep, so that You keep equals Contribution less Return Loss for every period and every product. | Golden dataset G12 reproduces the figures, and the shop total on S6 equals the sum of the product figures on S9 | Section 12 | Must |
| RET-8 | Show Return Loss as its own line wherever You keep is shown, and never fold it silently into Contribution. | Every screen showing You keep also shows the Return Loss that was taken off it | Section 12, Section 24 (FI-3) | Must |

### Where this surfaces

S6 gains a Return Loss line under "You keep". S10 gains a Return Loss row in the one-unit breakdown. S11 gains return postage and write-offs as their own categories in "Where every pound went", labelled so the seller can see they sit outside the TikTok deductions rather than among them. S16, from Action 2, already carries the column.

The label rule in section 1.1 of the Wireframes document is unchanged. Where cost coverage is incomplete the label stays "Left after TikTok" and no You keep figure is shown, so Return Loss is shown as a figure in its own right rather than as a deduction from something that does not exist.

### Golden dataset G12

Added to section 3.1 of the Functionality QA document. G12 takes one month of one product and proves the chain from Net Proceeds to You keep.

**Inputs.** Product P007, product cost £9.00. In March 2026 the seller sells 20 units at £24.00. TikTok deductions total £74.40. Two units are returned: one resellable, one unsellable. Return postage of £2.85 is recorded on each.

**Expected results.**

| Measure | Working | Result |
|---|---|---|
| Gross Sales | 20 × £24.00 | £480.00 |
| Platform Deductions | given | −£74.40 |
| Refunds | 2 × £24.00 | −£48.00 |
| Net Proceeds | 480.00 − 74.40 − 48.00 | £357.60 |
| Units retained | 20 − 2 | 18 |
| Cost of goods retained | 18 × £9.00 | £162.00 |
| Contribution | 357.60 − 162.00 | £195.60 |
| Return postage | 2 × £2.85 | £5.70 |
| Write-off | 1 × £9.00 | £9.00 |
| Return Loss | 5.70 + 9.00 | £14.70 |
| You keep | 195.60 − 14.70 | £180.90 |

**Checks the test must assert.**

1. The resellable unit adds £9.00 of stock value back and contributes nothing to the write-off.
2. The unsellable unit contributes its £9.00 once, inside Return Loss, and never inside cost of goods retained.
3. Return Loss for a single resellable return reproduces G2's £2.85, and for a single unsellable return reproduces G2's £4.95.
4. Net Proceeds still equals Paid Out plus Awaiting Settlement for March, unaffected by the £14.70.

### Test cases, QA section 5.7

| ID | Test | Expected result | Trace |
|---|---|---|---|
| TC-RET-08 | Load G12 and read You keep for March. | £180.90, with Return Loss shown separately as £14.70. | RET-7, RET-8 |
| TC-RET-09 | Compare the shop You keep on S6 with the sum of product You keep figures on S9. | The two agree to the penny. | RET-7 |
| TC-RET-10 | Check the Net Proceeds identity for March in G12. | Net Proceeds equals Paid Out plus Awaiting Settlement. Return Loss does not appear in either side. | LED-4, RET-7 |
| TC-RET-11 | Open a product whose costs are incomplete. | No You keep figure is shown, and Return Loss is still shown as a figure in its own right. | CST-7, RET-8 |

---

## 4.3 The refund-only case

### The defect

A buyer is sometimes refunded without returning anything. The seller ships a damaged item and refunds it, or TikTok refunds a delivery failure. Money goes back and no goods do, so stock must not move.

The schema anticipates this. `return_items.seller_check_status` accepts `not_applicable` alongside `pending`, `resellable` and `unsellable`. Nothing else does. The SRD has no requirement, the QA document has no test case, and no screen tells the seller what the status means. An implementer reading the pack would have to guess.

### Requirement added to SRD section 3.7

| ID | Requirement | Acceptance | Trace | Priority |
|---|---|---|---|---|
| RET-9 | Record a refund with no goods returned as a return item with a check status of not applicable, post the refund, and make no stock movement of any kind. | A refund-only case posts one refund entry, leaves On the shelf and Coming back unchanged, and raises no return check | Section 11, Section 12 | Must |

### How it is detected and handled

TikTok's return record carries whether goods are expected. Where goods are not expected, the return item is created with `seller_check_status = 'not_applicable'` at the moment the refund is recorded, rather than at `pending`.

| Effect | Rule |
|---|---|
| Refund entry | Posted as normal, in the month the refund completes, as RET-2 requires. |
| Coming back | Unchanged. No unit is on its way. |
| On the shelf | Unchanged. |
| Return check | Not raised. The item never appears in the S8 queue. |
| Unchecked-for-7-days alert | Not raised, because STK-3 counts only items awaiting a check. |
| Return postage | Not applicable. None was paid. |
| Write-off | Not posted. The goods are with the buyer, and their cost was already in cost of goods retained. |
| Return Loss | Zero for this case. |
| Return Rate | The refund counts, because RET-6 measures refunds rather than physical returns. The metric definition is unchanged and the case is named in it. |

The last row matters. A refund-only case reduces Net Proceeds and raises the Return Rate without producing any Return Loss. That combination is correct and would otherwise look like a bug to whoever reconciles the figures.

### Where the seller sees it

S7 shows the refund under Gone this month rather than Coming back, with the label "Refunded, nothing coming back". S8 does not list it, because there is nothing to check. S22 shows the refund among the records with the same label, so the seller opening a Net Proceeds figure can see why money left with no return against it.

### Test cases, QA section 5.7

| ID | Test | Expected result | Trace |
|---|---|---|---|
| TC-RET-12 | Post a refund for an order where TikTok reports no goods expected. | One refund entry is posted. On the shelf and Coming back are unchanged. The check status is not applicable. | RET-9 |
| TC-RET-13 | Leave a refund-only case for eight days. | No unchecked-return alert is raised. | RET-9, STK-3 |
| TC-RET-14 | Read Return Rate and Return Loss for a month holding one refund-only case and nothing else. | Return Rate counts the refund. Return Loss is zero. | RET-6, RET-9 |
| TC-RET-15 | Attempt to mark a refund-only item Resellable or Unsellable. | The action is refused, because the item is not awaiting a check. | RET-3, RET-9 |

---

## 4.4 Summary of what Action 4 changes

| Document | Change |
|---|---|
| SRD | STK-8, RET-7, RET-8, RET-9 added. Return Loss, Contribution and You keep formulas written into section 6, replacing the citation of a document that is not in the pack. |
| Backend Orchestration and Schema | Absorption added to the stock projection rules in section 3.1. |
| Schema SQL | `adjustment_absorbed` added to `stock_movements.movement_type`, and an absorption tolerance added to `alert_settings`. Applied in migration 0005. |
| Functionality QA | Golden dataset G12. Test cases TC-STK-08 to TC-STK-12, TC-RET-08 to TC-RET-15. Thirteen new cases. |
| Wireframes and Workflows | Return Loss line added to S6, S10 and S11. Refund-only labelling added to S7 and S22. |

The requirement count moves from 73 to 82. The Must count moves from 64 to 73. Test cases move from 84 to 107, counting the ten added in Action 2.
