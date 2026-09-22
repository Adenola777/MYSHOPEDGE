# Action 8: The terminology standard

Every label in MyShopEdge is either the name TikTok uses for the thing, or the correct accounting term for it. There is no third category. No invented shorthand, no nickname, and no TikTok fee merged with another.

This replaces the terminology standard referred to in section 8 of the Wireframes and Workflows document and governs every screen, the glossary, the SRD definitions, the API field names, the ledger categories and the export headers.

---

## 8.1 Why this changed

v0.1 used friendly labels that were neither TikTok's nor accounting's: "Their cut", "You keep", "Left after TikTok", "Contribution", "Return Loss", "On the shelf". Three problems followed.

**Fees were merged.** "TikTok and creator cut" put the platform commission and the affiliate commission in one bar. Those are two different fees, charged on different bases, and a seller can change one without touching the other. Merging them removes the single most actionable number on the screen.

**"Contribution" is not a beginner accounting term.** The figure it named is Net proceeds less cost of goods sold, which is Gross profit. Contribution margin exists in management accounting and means something related but not identical, so using it here was both unfamiliar and imprecise.

**"You keep" implied net profit.** It excludes the seller's rent, software, their own time and their tax. A seller reading "You keep £2,767" and planning around it would be wrong by the whole of their overheads.

The product exists to render TikTok's data faithfully and to make it legible in ordinary accounting terms. A label that is neither serves neither purpose.

---

## 8.2 The rule

| Where a figure comes from | What it is called |
|---|---|
| TikTok charges it, reports it, or names it | The name TikTok uses |
| It is an accounting concept | The correct accounting term |
| Neither | It does not appear as a label |

A plain-English sentence may explain a term. It may not replace it.

---

## 8.3 TikTok fees, each on its own line

No fee is ever merged with another, on any screen, in any export, or in any total that is not explicitly labelled as a subtotal.

| Label | What it is | Status |
|---|---|---|
| Platform commission | TikTok's fee for selling on the platform, 9% of net sales in the UK | Confirmed, TikTok Seller University |
| Affiliate commission | What the seller pays a creator for a sale that creator drove | Confirmed, TikTok's own term |
| Transaction fee | Payment processing charged by TikTok | To confirm in the spike |
| Smart Promotions fee | TikTok's promotional programme, on by default | Confirmed by name, rate to confirm |
| Shipping fee | Shipping charged by TikTok rather than paid by the seller | To confirm in the spike |
| Return handling fee | Charged per unit returned | Confirmed by name, rate to confirm |
| FBT operations fee | Fulfilled by TikTok, per-item handling | Confirmed by name |
| FBT shipping fee | Fulfilled by TikTok, shipping portion | Confirmed by name |
| FBT storage fee | Fulfilled by TikTok, storage | Confirmed by name |

**Subtotal.** Where a total of these is genuinely needed it is called **Total TikTok fees**, it appears directly under the lines that make it up, and it is never shown without them.

**"Their cut" is withdrawn.** It named no real thing and hid four fees.

### The unmapped fee rule

TikTok adds and renames fees. A fee arriving with a type the system does not recognise is posted as `unmapped_fee`, carried at its full amount into Total TikTok fees so no money goes missing, **and raises a discrepancy under DSC-1** naming the TikTok fee type verbatim.

It is never absorbed into an "other" bucket and never silently merged. A seller seeing an unnamed fee is a bug to fix, not a category to keep.

---

## 8.4 The full mapping

| v0.1 label | v0.2 label | Source |
|---|---|---|
| What customers paid | **Gross sales (GMV)** | accounting, with TikTok's term in brackets on first use |
| Your vouchers | **Seller discounts** | TikTok |
| — | **Net sales** | accounting. Gross sales less seller discounts |
| Their cut | **Total TikTok fees**, over the itemised lines | plain subtotal |
| TikTok and creator cut | **Platform commission** and **Affiliate commission**, separately | TikTok |
| Left after TikTok | **Net proceeds** | already correct in the pack |
| What the stock cost you | **Cost of goods sold** | accounting |
| Postage and packing | **Shipping and packaging you pay** | distinguishes it from TikTok's shipping fee |
| **Contribution** | **Gross profit** | accounting |
| **You keep** | **Gross profit after returns** | accounting |
| Return Loss | **Return costs**, split into **Return shipping you paid** and **Stock written off** | accounting |
| Deduction Rate | **TikTok fees as a share of gross sales** | plain and exact |
| Paid out | **Settled to your bank** | TikTok settles |
| Awaiting settlement | **Awaiting settlement** | TikTok |
| Shop Money | **Settlement** | TikTok |
| On the shelf | **Stock on hand** | stock control |
| Sold, not posted | **Sold, not yet dispatched** | plain |
| Coming back | **Returns in transit** | stock control |
| Gone this month | **Units sold** | plain |
| Written off | **Stock written off** | accounting |
| Days left | **Days of cover** | stock control |
| The VAT line | **VAT registration threshold** | HMRC's term |

### Two labels that carried a promise they could not keep

**"You keep" is withdrawn entirely**, including as a subtitle. Gross profit after returns is what the figure is, and every screen showing it also shows the sentence "before your own running costs and your tax". A seller who wants true net profit needs to add their overheads, which this product does not collect.

**"Left after TikTok" is withdrawn** in favour of Net proceeds, which the pack already defined correctly and then declined to use on screen.

---

## 8.5 The calculator view

Money is presented as a running calculation, because that is the essence of the product. Every line is named, every subtotal states what it is made of, and the arithmetic can be followed from the top to the bottom without leaving the screen.

The order is fixed and is the same on every period, every product and every export.

```
  Gross sales (GMV)
− Seller discounts
= Net sales

  TikTok fees
  − Platform commission
  − Affiliate commission
  − Transaction fee
  − Smart Promotions fee
  − Shipping fee
  − Return handling fee
  − FBT fees, each on its own line where used
  = Total TikTok fees

= Net proceeds before refunds
− Refunds to customers
= Net proceeds

  Your costs
  − Cost of goods sold
  − Shipping and packaging you pay
  = Total your costs

= Gross profit

  Return costs
  − Return shipping you paid
  − Stock written off
  = Total return costs

= Gross profit after returns
```

A fee that is zero for the period is omitted rather than shown as £0.00, except on the one-unit view where a zero is informative. A fee that exists is never omitted, whatever its size.

### Worked example, August 2026, the sample shop

| Line | Amount |
|---|---|
| Gross sales (GMV) | £8,325.20 |
| Seller discounts | −£701.12 |
| **Net sales** | **£7,624.08** |
| Platform commission, 9% of net sales | −£686.17 |
| Affiliate commission | −£742.46 |
| Transaction fee, 2% of net sales | −£152.48 |
| Smart Promotions fee | −£177.12 |
| Return handling fee, 7 units at £1.80 | −£12.60 |
| **Total TikTok fees** | **−£1,770.83** |
| **Net proceeds before refunds** | **£5,853.25** |
| Refunds to customers | −£68.00 |
| **Net proceeds** | **£5,785.25** |
| Cost of goods sold | −£1,892.60 |
| Shipping and packaging you pay | −£1,073.79 |
| **Gross profit** | **£2,818.86** |
| Return shipping you paid | −£34.20 |
| Stock written off | −£18.00 |
| **Gross profit after returns** | **£2,766.66** |

---

## 8.6 What this fixed in the sample data

Two inconsistencies that predate this work came out in the wash.

**G1 and G5 disagreed about the same product.** G1 gave Vitamin C Serum a contribution of £12.64 on a £24.99 unit, which is 50.6%. G5 said the same product kept 44p in the pound. The two were irreconcilable because G1 omitted the shipping the seller pays and G5 included it. Under the standard, gross profit includes every direct cost, so the unit is £24.99 less £4.15 of TikTok fees, less £8.20 of goods, less £1.60 of shipping, which is £11.04, or 44.2p in the pound. **G1 and G5 now agree**, and G1's net proceeds of £20.84 and fee share of 16.6% are unchanged.

**The product ranking did not add up to the month.** v0.1's five ranked products totalled £2,639 against a month figure of £2,887, with no statement of where the difference went. S9 now shows the top five at £2,610.02, the other fifteen products at £156.64, and the total at £2,766.66, which is the figure on Money. The ranking reconciles to the month, and the screen says so.

---

## 8.7 Schema change

The ledger's category list is replaced. The v0.1 list was `commission`, `affiliate_commission`, `shipping`, `promotion`, `other`, which merged four distinct fees into `other` and named the platform commission ambiguously.

```sql
alter table ledger_entries drop constraint if exists ledger_entries_category_check;
alter table ledger_entries add constraint ledger_entries_category_check check (
  category is null or category in (
    -- money in
    'gross_sales', 'seller_discount', 'refund',
    -- TikTok fees, each named as TikTok names it
    'platform_commission', 'affiliate_commission', 'transaction_fee',
    'smart_promotions_fee', 'shipping_fee', 'return_handling_fee',
    'fbt_operations_fee', 'fbt_shipping_fee', 'fbt_storage_fee',
    -- a TikTok fee type the system does not recognise. Carried at full value and
    -- raised as a discrepancy. Never a silent bucket.
    'unmapped_fee',
    -- seller costs and returns
    'cost_of_goods_sold', 'seller_shipping', 'return_shipping', 'stock_written_off',
    -- settlement
    'settlement'
  )
);

alter table ledger_entries
  add column tiktok_fee_type text;
comment on column ledger_entries.tiktok_fee_type is
  'The fee type string exactly as TikTok supplied it, kept verbatim so a category '
  'mapping can be checked and an unmapped_fee can be investigated without a re-sync.';
```

Keeping TikTok's own string alongside the mapped category means the mapping can be audited after the fact, which matters because the exact settlement labels are still to be confirmed against a live export.

---

## 8.8 Requirements added to the SRD

| ID | Requirement | Acceptance | Priority |
|---|---|---|---|
| CLR-1 | Use only labels from the terminology standard, each of which is either the name TikTok uses or the correct accounting term. | No screen, export or message contains a label outside the standard | Must |
| CLR-2 | Show every TikTok fee on its own line, and never merge two fees under one label. | A month with seven fee types shows seven lines | Must |
| CLR-3 | Show money as a running calculation in which every subtotal is preceded by the lines that make it up. | Each subtotal equals the sum of the lines above it, to the penny | Must |
| CLR-4 | Post a TikTok fee whose type is unrecognised as `unmapped_fee` at its full value, keep TikTok's own fee-type string, and raise a discrepancy. | An unknown fee reduces net proceeds correctly and appears in the notification centre naming TikTok's own string | Must |
| CLR-5 | State on every screen showing gross profit after returns that the figure is before the seller's running costs and tax. | The statement appears wherever the figure appears | Must |

### Test cases

| ID | Test | Expected result |
|---|---|---|
| TC-CLR-01 | Load the August sample and add each line of the calculator. | Every subtotal equals the lines above it, and the final figure is £2,766.66. |
| TC-CLR-02 | Post an order carrying platform commission and affiliate commission. | Two separate lines. No screen shows them combined. |
| TC-CLR-03 | Post a fee with a type the mapping does not hold. | It posts as `unmapped_fee` at full value, net proceeds falls by that amount, and a discrepancy is raised naming TikTok's string. |
| TC-CLR-04 | Read the unit economics for Vitamin C Serum. | Net proceeds £20.84, gross profit £11.04, margin 44.2%, fee share 16.6%, agreeing with G1 and G5. |
| TC-CLR-05 | Sum the product ranking and compare with the month figure. | The ranked products plus the remainder equal the month total exactly. |
| TC-CLR-06 | Search every screen, export header and notification for withdrawn labels. | No occurrence of "Their cut", "You keep", "Left after TikTok", "Contribution", "Return Loss". |

---

## 8.9 What is confirmed, and what is not

The platform commission and the affiliate commission are named by TikTok in its own seller documentation. The FBT fees, the return handling fee and Smart Promotions are named in current seller guidance. **The literal column labels on a TikTok settlement export are not published**, and section 3.5 of the API Integration document already lists field mapping as an open item for the integration spike.

Every label in this standard is therefore marked confirmed or to be confirmed. A developer must not build a column mapping against a label marked "to confirm" without checking it against a real settlement file first. Keeping `tiktok_fee_type` verbatim is what makes that check possible after the fact.

Sources: TikTok Seller University, Platform Commission Fee, `seller-uk.tiktok.com`. TikTok Shop UK fee guidance, Z Media, 2026. TikTok Shop fees for UK sellers, Social Commerce Accountants.

---

## 8.9a The product view

S9 is a horizontal table rather than a vertical list of bars. One row per product, one
column per fee, the product name fixed to the left and the rest scrolling sideways, the
same shape as the order grid on S16. The columns add up across to gross profit, and the
products add up down to the figure on Money, with the remaining fifteen products stated
rather than left as a silent difference.

The stacked bar survives only on S10, where a single product's pound is being broken
down and the picture earns its place. Colour there follows the standard in section 7.10
of Action 7: navy for gross profit, blue tints for TikTok fees, plum tints for your
costs, and no orange anywhere in the data.

---

## 8.10 Summary of what Action 8 changes

| Document | Change |
|---|---|
| Wireframes and Workflows | Section 8 replaced by this standard. Every figure re-rendered. S11 and S10 become calculator views. S32 rewritten. |
| SRD | CLR-1 to CLR-5 added. Every definition in section 6 renamed. The labels in DSH-1, DSH-5, LED-8, MON-1, RET-4 and RET-7 follow. |
| API Integration | Field names follow the standard. Section 3.5 gains the confirmed and to-confirm marking. |
| Backend Orchestration and Schema | Ledger categories replaced. The unmapped fee rule added to section 3. |
| Schema SQL | Migration 0008. Category list replaced, `tiktok_fee_type` added. |
| Functionality QA | TC-CLR-01 to TC-CLR-06. G1 and G5 restated so they agree. |
| PRD | The Clarity scope names the standard as the single source. |

Requirements move from 88 to 93. Test cases move from 129 to 135.
