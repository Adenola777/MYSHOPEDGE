# Action 2: Product transactions grid and deduction attribution

Closes audit question 1. Text below is written to be merged into the named documents at v0.2.

---

## 2.1 SRD additions, section 3.4 Ledger and calculation

| ID | Requirement | Acceptance | Trace | Priority |
|---|---|---|---|---|
| LED-9 | Attribute every sale, platform deduction, refund, return cost and write-off to an order line and its SKU, either directly from the TikTok reference or by the allocation rule in LED-10, and mark which of the two was used. | Every ledger entry other than a payout carries an order line, a SKU and an attribution of direct or allocated | Section 8 | Must |
| LED-10 | Allocate an order-level deduction across the order's lines in proportion to line attributable value, assigning remaining pence by largest remainder so the allocated amounts sum exactly to the order-level amount. | Golden dataset G11 reproduces the line amounts to the penny, and the allocated amounts sum to the order-level amount with no residual | Section 8 | Must |
| LED-11 | Show a product transactions grid holding one row per order line for a chosen product and period, with a totals row that equals the product figure it was opened from. | The totals row equals the figure on S10 for the same product, period and basis | Section 22 (BK-6) | Must |
| LED-12 | Reverse and repost every affected line entry when TikTok restates an order-level deduction, leaving the original entries in place. | A restated shipping deduction produces one reversal and one new entry per line, and the grid total moves by the difference only | Section 22 (BK-5) | Must |

### Definitions added to SRD section 6, Data requirements

**Line attributable value.** For an order line, unit price in pence multiplied by quantity, less any seller discount recorded on that line. The figure is taken from `order_lines` and never recalculated from the order total.

**Direct attribution.** TikTok supplies a line or SKU reference on the finance record. The entry is posted against that line.

**Allocated attribution.** TikTok supplies the amount at order level only. The entry is split into one entry per line under LED-10.

**Cost of goods retained.** Product cost multiplied by the units the buyer kept, which is units sold less units returned in any condition. A returned unit's cost is carried by Return Loss instead, so no cost is counted twice.

**Contribution, per line.** Net Proceeds for the line less cost of goods retained for the line. Contribution is calculated only where a valid product cost exists, as CST-6 requires.

**Return Loss, per line.** The sum of return cost entries and write-off entries for the line, shown as a positive amount of money lost.

**You keep, per line.** Contribution less Return Loss. This is the figure that reconciles to the shop total on S6.

---

## 2.2 Deduction attribution rule

The rule applies to any `platform_deduction`, `refund` or `return_cost` entry that TikTok reports at order level with no line reference.

Let the order hold lines 1 to n. Let `v_i` be the line attributable value of line i in pence, and let `V` be the sum of `v_i`. Let `D` be the order-level amount in pence, always a whole number of pence and always negative for a deduction.

1. Compute the exact share for each line as `s_i = |D| × v_i ÷ V`.
2. Take the floor of each `s_i` to give the provisional pence `p_i`.
3. Compute the residual `R = |D| − sum of p_i`. R is a whole number between 0 and n−1.
4. Sort the lines by the fractional part of `s_i`, descending. Break ties by `tiktok_line_id` ascending, so the result is stable across reruns.
5. Add one penny to each of the first R lines in that order.
6. Restore the sign of D on every allocated amount.

Three edge cases are defined rather than left to the implementation.

| Case | Rule |
|---|---|
| V is zero because every line is fully discounted | Allocate by units instead of value, using the same largest remainder method. |
| V is zero and total units are zero | Allocate the whole amount to the line with the lowest `tiktok_line_id`, and raise an internal alert for investigation. |
| The order holds one line | Allocate the whole amount to that line and record the attribution as direct. |

The rule is deterministic. Running it twice on the same inputs produces the same pence on the same lines, which is what makes the append-only ledger safe to rebuild.

### Restatement

If TikTok restates an order-level deduction, the system posts one `adjustment` entry per line reversing each earlier allocated entry, then posts the new allocation in full. The original entries are never edited, which holds LED-1 and gives LED-7 its change log.

---

## 2.3 Schema changes

Applied to `MyShopEdge_MVP_schema.sql`, table `ledger_entries`.

```sql
alter table ledger_entries
  add column order_line_id uuid references order_lines(id),
  add column sku_id uuid references skus(id),
  add column attribution text not null default 'none'
    check (attribution in ('direct','allocated','none'));

-- A payout is the only entry type that carries no line.
alter table ledger_entries
  add constraint ledger_attribution_chk check (
    (entry_type = 'payout' and order_line_id is null and attribution = 'none')
    or (entry_type <> 'payout' and order_line_id is not null
        and attribution in ('direct','allocated'))
  );

create index ledger_sku_basis_idx
  on ledger_entries (shop_id, sku_id, basis_month);
create index ledger_line_idx
  on ledger_entries (shop_id, order_line_id);
```

### Idempotency index defect found and fixed

The existing unique index is:

```sql
create unique index ledger_idempotency_idx on ledger_entries
  (shop_id, source, source_ref, entry_type, coalesce(category, ''))
  where source_ref is not null;
```

One order-level deduction now produces one entry per line, and every one of those entries carries the same TikTok `source_ref`. The index as written rejects the second line. It must include the line:

```sql
drop index ledger_idempotency_idx;
create unique index ledger_idempotency_idx on ledger_entries
  (shop_id, source, source_ref, entry_type, coalesce(category, ''),
   coalesce(order_line_id, '00000000-0000-0000-0000-000000000000'::uuid))
  where source_ref is not null;
```

This preserves the original protection, which is that the same TikTok record cannot post twice, while allowing one record to post once per line.

### Backfill

Entries written before this change carry `attribution = 'none'` and no line. The migration runs in three steps.

1. For every non-payout entry whose order holds exactly one line, set `order_line_id` and `sku_id` from that line and set `attribution` to `direct`.
2. For every remaining non-payout entry, run the LED-10 allocation over the order's lines, insert the allocated entries, and mark the original entry as superseded by an `adjustment` that reverses it. The append-only rule is honoured because nothing is edited.
3. Only after step 2 reports zero remaining rows does the check constraint `ledger_attribution_chk` become enforceable. The migration adds it as `not valid` first, then validates it.

---

## 2.4 API addition

Added to the endpoint catalogue in section 4.3 of the API Integration document.

| Method | Path | Purpose | SRD |
|---|---|---|---|
| GET | `/v1/shops/{id}/products/{productId}/transactions` | One row per order line for a product, with totals | LED-11 |

**Query parameters.** `period` taking `today`, `month`, `tax_year` or `custom`; `from` and `to` as local dates when `period` is `custom`; `basis` taking `sales` or `cash`; `sku_id` to narrow a multi-SKU product to one variant; `limit` and `cursor` for paging as section 4.1 requires.

**Response.**

```json
{
  "as_of": "2026-04-06T09:12:04Z",
  "product": { "id": "...", "name": "Ceramic mug, 350ml" },
  "period": { "basis": "sales", "from": "2026-03-01", "to": "2026-03-31" },
  "cost_coverage": 1.0,
  "confidence": "confirmed",
  "rows": [
    {
      "order_line_id": "...",
      "occurred_on": "2026-03-04",
      "tiktok_order_id": "ORD-10001",
      "tiktok_line_id": "L1",
      "sku": "P006",
      "units": 3,
      "gross": { "amount_minor": 3750, "currency": "GBP" },
      "commission": { "amount_minor": -188, "currency": "GBP" },
      "creator_commission": { "amount_minor": -375, "currency": "GBP" },
      "shipping": { "amount_minor": -182, "currency": "GBP" },
      "vouchers": { "amount_minor": -305, "currency": "GBP" },
      "other": { "amount_minor": 0, "currency": "GBP" },
      "refunds": { "amount_minor": 0, "currency": "GBP" },
      "net_proceeds": { "amount_minor": 2700, "currency": "GBP" },
      "product_cost": { "amount_minor": -1260, "currency": "GBP" },
      "contribution": { "amount_minor": 1440, "currency": "GBP" },
      "return_loss": { "amount_minor": 0, "currency": "GBP" },
      "you_keep": { "amount_minor": 1440, "currency": "GBP" },
      "attribution": { "commission": "allocated", "creator_commission": "direct",
                       "shipping": "allocated", "vouchers": "allocated" },
      "flags": []
    }
  ],
  "totals": {
    "units": 3,
    "gross": { "amount_minor": 3750, "currency": "GBP" },
    "net_proceeds": { "amount_minor": 2700, "currency": "GBP" },
    "contribution": { "amount_minor": 1440, "currency": "GBP" },
    "return_loss": { "amount_minor": 0, "currency": "GBP" },
    "you_keep": { "amount_minor": 1440, "currency": "GBP" }
  },
  "next_cursor": null
}
```

**Contract.** The `totals` object covers the whole period, not the current page. It equals the figure the seller opened the grid from. Where a product has no cost, `product_cost`, `contribution` and `you_keep` return null and `cost_coverage` falls below 1, which lets the client apply CST-7. Every row carries `attribution` so the seller can be told which deductions were split rather than reported per line. A row carrying an open discrepancy returns it in `flags`, which satisfies DSC-5 at row level.

---

## 2.5 Golden dataset G11

Added to section 3.1 of the Functionality QA document. G11 proves the split rule, the penny reconciliation and the loss case in one order.

**Order ORD-10001, placed 4 March 2026, two lines.**

| Line | SKU | Units | Unit price | Line attributable value |
|---|---|---|---|---|
| L1 | P006 | 3 | £12.50 | £37.50 (3750p) |
| L2 | P007 | 1 | £24.00 | £24.00 (2400p) |

Order gross is £61.50 (6150p).

**Deductions reported by TikTok.**

| Deduction | Level | Amount |
|---|---|---|
| Commission | Order | −£3.08 (−308p) |
| Creator commission | Line L1 | −£3.75 (−375p) |
| Shipping | Order | −£2.99 (−299p) |
| Voucher | Order | −£5.00 (−500p) |

**Allocation under LED-10.**

| Deduction | Exact L1 share | Exact L2 share | Floor | Residual | Allocated L1 | Allocated L2 |
|---|---|---|---|---|---|---|
| Commission 308p | 187.80 | 120.20 | 187 + 120 = 307 | 1 to L1 | −188p | −120p |
| Shipping 299p | 182.32 | 116.68 | 182 + 116 = 298 | 1 to L2 | −182p | −117p |
| Voucher 500p | 304.88 | 195.12 | 304 + 195 = 499 | 1 to L1 | −305p | −195p |

**Return.** The buyer returns line L2 and TikTok completes the refund on 8 April 2026. Return postage of £2.85 is recorded. The seller checks the item on 9 April and marks it Unsellable. Product costs are £4.20 for P006 and £9.00 for P007.

**Expected ledger.**

| Entry | Line | Type | Amount | Basis month |
|---|---|---|---|---|
| Sale | L1 | sale | +3750p | March 2026 |
| Sale | L2 | sale | +2400p | March 2026 |
| Commission | L1 | platform_deduction | −188p | March 2026 |
| Commission | L2 | platform_deduction | −120p | March 2026 |
| Creator commission | L1 | platform_deduction | −375p | March 2026 |
| Shipping | L1 | platform_deduction | −182p | March 2026 |
| Shipping | L2 | platform_deduction | −117p | March 2026 |
| Voucher | L1 | platform_deduction | −305p | March 2026 |
| Voucher | L2 | platform_deduction | −195p | March 2026 |
| Refund | L2 | refund | −2400p | April 2026 |
| Return postage | L2 | return_cost | −285p | April 2026 |
| Write-off | L2 | write_off | −900p | April 2026 |

**Expected figures.**

| Measure | L1 | L2 | Order |
|---|---|---|---|
| Net Proceeds | £27.00 | −£4.32 | £22.68 |
| Cost of goods retained | £12.60 | £0.00 | £12.60 |
| Contribution | £14.40 | −£4.32 | £10.08 |
| Return Loss | £0.00 | £11.85 | £11.85 |
| You keep | £14.40 | −£16.17 | −£1.77 |

**Reconciliation checks the test must assert.**

1. Order Net Proceeds equals the order-level arithmetic: 6150 − 308 − 375 − 299 − 500 − 2400 = 2268p. The line figures sum to the same 2268p.
2. Every allocation sums to its order-level amount with no residual pence: 188 + 120 = 308, 182 + 117 = 299, 305 + 195 = 500.
3. L2 carries no cost of goods retained, because the buyer kept nothing, and its £9.00 cost appears once as a write-off inside Return Loss.
4. The March grid for P006 shows Net Proceeds of £27.00, and that figure equals the product figure on S10 for March on the sales basis.
5. You keep for the order is negative, which exercises CST-8.

---

## 2.6 QA test cases

Added to section 5.4 of the Functionality QA document.

| ID | Test | Expected result | Trace |
|---|---|---|---|
| TC-LED-09 | Open the transactions grid from a product figure on S10 and compare the totals row with that figure. | The totals row equals the product figure to the penny for the same period and basis. | LED-11 |
| TC-LED-10 | Load G11 and read the allocated commission, shipping and voucher amounts per line. | The amounts match the G11 table exactly, and each pair sums to the order-level amount. | LED-10 |
| TC-LED-11 | Rebuild the ledger from raw events twice and compare the allocated pence. | Identical amounts land on identical lines on both runs. | LED-10 |
| TC-LED-12 | Post an order-level deduction for an order whose lines are fully discounted to zero value. | The amount is allocated by units, and the allocated amounts sum to the order-level amount. | LED-10 |
| TC-LED-13 | Restate the shipping deduction on ORD-10001 from £2.99 to £3.49. | Two reversal entries and two new entries are posted, no earlier row is edited, and the grid total falls by exactly £0.50. | LED-12 |
| TC-LED-14 | Post the same TikTok finance record twice for a two-line order. | Four entries exist in total, not eight, and the idempotency index rejects the repeat. | LED-9 |
| TC-LED-15 | Open the grid for a product with no product cost. | The product cost, contribution and you keep columns read "Not provided", and no profit figure appears. | CST-7, LED-11 |
| TC-LED-16 | Open the grid for P007 for April 2026. | The refund, return postage and write-off rows appear, and You keep reads −£16.17. | LED-11, RET-4 |
| TC-LED-17 | View the grid at 360 px width. | The order ID column stays fixed while the remaining columns scroll sideways, and no figure is truncated. | NFR accessibility |
| TC-LED-18 | Run the backfill migration against a dataset holding multi-line orders with unattributed entries. | Every non-payout entry ends with a line and a SKU, the check constraint validates, and shop totals are unchanged. | LED-9 |

---

## 2.7 Wireframe S16, Product transactions

Added to the screen map and to section 4 of the Wireframes and Workflows document. The figure is rendered in Action 3.

**ID and area.** S16, Products.

**Purpose.** Show every order line behind a product figure, with the deductions that were taken from each one.

**Reached from.** The product figure on S10, any deduction segment on the one-unit breakdown, and the records-behind-a-figure screen where the figure belongs to a single product.

**Header.** Product name, period chip, basis chip, cost coverage chip, and the confidence chip from DSH-9. The header states the figure the grid was opened from, so the seller can see the totals row matching it.

**Columns, in order.** Date, order ID, line, SKU, units, gross, commission, creator, shipping, vouchers, other, refunds, net proceeds, product cost, contribution, return loss, you keep.

**Totals row.** Pinned to the bottom of the grid. It covers the whole period rather than the visible page, and it carries the note "This total equals the figure you opened".

**Allocation marker.** A deduction that was split under LED-10 carries a small dot. Tapping the dot shows "TikTok reported this for the whole order. We split it across the lines by their value." The wording avoids the word allocated, which is consistent with section 8 of the Wireframes document.

**Phone layout.** The order ID column is fixed to the left edge. The remaining columns scroll sideways. Column headers stay visible while the rows scroll vertically.

**Empty state.** "No sales of this product in this period." The period chip stays active so the seller can widen the period without leaving the screen.

**Partial state.** Where cost coverage is below 1, the product cost, contribution and you keep columns show "Not provided" on the rows that lack a cost, and the totals row shows the coverage statement required by CST-6.

**Stale state.** Where the last sync is older than the freshness target, the header carries the as-at time and the standard stale notice.

**Export.** The grid offers an export of the visible period, which reuses the export flow in screen 7 of the missing screens list rather than defining a second one.
