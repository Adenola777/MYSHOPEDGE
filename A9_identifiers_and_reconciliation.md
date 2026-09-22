# Action 9: TikTok identifiers and reconciliation

Two questions. Where does the TikTok order number go, and why is the invoice number not captured. The first has a good answer. The second is a defect with a retention problem behind it.

---

## 9.1 Where the order number goes today

| Held in | Column | Note |
|---|---|---|
| Orders | `orders.tiktok_order_id` | Unique per shop. This is the order number. |
| Order lines | `order_lines.tiktok_line_id` | Unique within the order |
| Returns | `returns.tiktok_return_id` | Unique per shop |
| Settlements | `settlements.tiktok_statement_id`, `tiktok_payment_id`, `payout_reference` | |
| Ledger | `ledger_entries.source_ref` | TikTok's transaction or event ID on the entry |

It reaches the seller on S16 as the fixed left column, on S22 against every record, in the S8 return header, in the S14 discrepancy header, and in every export. MON-2 requires the export to carry "all TikTok identifiers", and DSH-8 requires drill-down records to show their TikTok references.

That part was already right.

---

## 9.2 The invoice number was not captured at all

The pack mentions the invoice number twice, both in the API Integration document.

> Section 3.5, field mapping: "Invoice number, transaction reference | retained in raw payload and export | Confirm field names"
>
> Section 3.5, fields to confirm in the spike: "Whether invoice numbers are available and where."

Three problems follow.

**It is in no table.** Searching the schema for "invoice" returns nothing. A field that lives only in a raw payload cannot be queried, exported by name, or reconciled against.

**It is destroyed after 90 days.** Section 4.6 purges `raw_events` 90 days after processing. So the one place the invoice number was held is emptied three months later.

**That breaks VAT.** A UK seller reclaiming input VAT on TikTok's fees needs TikTok's invoices, and HMRC expects VAT records to be kept for six years. A product whose purpose is to make a seller's numbers defensible cannot discard the documents that defend them.

---

## 9.3 What is now captured

### The invoice itself

A new table holds the invoice rather than only its number, because at an HMRC enquiry the seller needs the document.

| Column | Purpose |
|---|---|
| `tiktok_invoice_number` | Unique per shop |
| `invoice_type` | TikTok's own label, for example Platform Service Fee, kept verbatim |
| `issued_on`, `period_start`, `period_end` | The VAT period the invoice belongs to |
| `net_minor`, `vat_minor`, `gross_minor`, `vat_rate_bp` | The figures, in pence |
| `supplier_vat_number`, `buyer_vat_number` | TikTok's and the seller's, as shown on the invoice |
| `document_url`, `document_fetched_at` | TikTok's link expires, so the fetch time records when a copy was taken |
| `settlement_id` | Which payout it was billed against |

The table carries `check (gross_minor = net_minor + vat_minor)`, so the arithmetic on every invoice is self-verifying. This was tested: an invoice whose gross did not equal net plus VAT was refused by the database.

### The identifiers on everything else

```sql
ledger_entries  + tiktok_invoice_number, + invoice_id
settlements     + tiktok_invoice_number, + settlement_reference
returns         + tiktok_credit_note_number, + tiktok_refund_reference
```

`settlement_reference` is the reference the seller sees **on their bank statement**. Without it a payout can be reconciled against TikTok but not against the bank, which is the reconciliation that actually matters at month end.

`tiktok_credit_note_number` is how a reversed fee is matched back to the fee that was charged. Without it the reversal is a credit with nothing to tie it to.

The invoice number is held as text as well as a foreign key, because a fee often arrives before its invoice does. The text lets the fee be reconciled the moment the invoice lands, without a re-sync.

### Retention

Invoice rows are **excluded from the 90-day purge** and retained for six years from the end of the VAT period. They are deleted only with the account under ACC-4, and the deletion flow tells the seller to take their invoices first.

---

## 9.4 The two reconciliations

### Payment reconciliation

```sql
create view settlement_reconciliation as ...
```

One row per payout, carrying the statement ID, the payment ID, the bank reference, the number of orders settled, the net proceeds on those orders, the invoiced gross, and **`unexplained_minor`**.

`unexplained_minor` is the payout amount less the net proceeds of the orders behind it. **It must be zero.** Anything else is a payout that does not agree with its orders, and raises a discrepancy.

S33 Settlement detail puts this in front of the seller: the payout, its orders, every fee itemised, the refunds, the net proceeds, the amount paid, and Unexplained at the bottom reading £0.00. The invoice billed against the payout sits under it with its net, VAT and gross, and a control to download the document.

### Returns reconciliation

```sql
create view return_reconciliation as ...
```

One row per return, putting four things side by side that were previously only checkable by hand: the refund TikTok reported, the refund posted to the ledger, the fees reversed on the credit note, and the count of stock movements.

The rule is stated rather than implied. **A refund-only return must show zero stock movements. A return with goods, once checked, must show exactly one.** Any other combination is a defect. That is the same rule RET-9 states from the stock side, now checkable from the money side.

S34 Return detail shows it: the order number, the return ID, the credit note number, the refund difference at £0.00, the fees reversed, the return costs, and the stock movement count.

---

## 9.5 Requirements added to the SRD

| ID | Requirement | Acceptance | Priority |
|---|---|---|---|
| REC-1 | Capture the TikTok order number, statement ID, payment ID and bank settlement reference, and reconcile every payout against the orders behind it. | `unexplained_minor` is zero for every settled payout, and a deliberately misstated payout raises a discrepancy | Must |
| REC-2 | Capture the TikTok return ID, credit note number and refund reference, and reconcile every return across refund, reversed fees and stock. | A refund-only return shows zero stock movements; a checked return with goods shows exactly one | Must |
| REC-3 | Capture every TikTok invoice with its number, type, date, period, net, VAT and gross, and hold the document, not only the link. | Every fee in the ledger can be traced to the invoice it was billed on | Must |
| REC-4 | Retain invoice records for six years from the end of the VAT period, outside the 90-day raw event purge. | An invoice from 18 months ago is still readable and downloadable | Must |
| REC-5 | Show both the order number and the invoice number wherever a fee is shown at line level, and carry both into every export. | The transactions grid and the ledger export both carry both identifiers | Must |

### Test cases

| ID | Test | Expected result |
|---|---|---|
| TC-REC-01 | Load a settled payout and read `unexplained_minor`. | £0.00. |
| TC-REC-02 | Misstate a payout by £5 and run the nightly check. | A discrepancy is raised naming the payout and the £5. |
| TC-REC-03 | Post a refund-only return and read the reconciliation view. | Refund posted, fees reversed, zero stock movements. |
| TC-REC-04 | Post a return with goods, check it resellable, read the view. | Exactly one stock movement. |
| TC-REC-05 | Store an invoice whose gross does not equal net plus VAT. | The database refuses it. |
| TC-REC-06 | Run the 90-day raw event purge, then read an invoice from 100 days ago. | The invoice is intact. |
| TC-REC-07 | Export the ledger and check the columns. | Order number and invoice number are both present on every fee row. |
| TC-REC-08 | Open the transactions grid for a product. | The order number is fixed to the left and the invoice number sits beside it. |

---

## 9.6 Still to confirm in the spike

The API Integration document already asks "Whether invoice numbers are available and where", and that question is not answered by public documentation. What this action does is make the pack ready for either answer.

**If TikTok exposes invoice numbers through the API**, the fields are there to receive them and the reconciliation views work on day one.

**If TikTok exposes them only in the Seller Centre**, the same fields take a seller-entered or uploaded value, and `source` on the ledger entry records that the invoice came from the seller rather than from TikTok. The reconciliation still works, and the seller is told which invoices are missing rather than discovering the gap at their VAT return.

Either way the spike now has a specific question to answer and a place to put the answer, instead of a note saying the number is kept in a payload that gets purged.

---

## 9.7 Summary of what Action 9 changes

| Document | Change |
|---|---|
| Schema SQL | Migration 0009. `tiktok_invoices` table, invoice and reference columns on the ledger, settlements and returns, two reconciliation views, row-level security and grants. Run and tested against PostgreSQL 16. |
| SRD | REC-1 to REC-5 added. |
| API Integration | Section 3.5 field mapping updated, with both spike outcomes specified. |
| Backend Orchestration and Schema | The two reconciliation views added to section 4.5. Invoice retention added to section 4.6, explicitly outside the 90-day purge. |
| Data Protection | Section 6 gains the six-year invoice retention and its lawful basis, which is a legal obligation rather than consent. ACC-4 deletion notes the invoice prompt. |
| Wireframes and Workflows | S33 Settlement detail and S34 Return detail added, as figure 18. S16 gains the invoice column. S22 carries both identifiers. |
| Functionality QA | TC-REC-01 to TC-REC-08. |

Requirements move from 93 to 98. Test cases move from 135 to 143. Screens move from 32 to 34, figures from 17 to 18, tables from 31 to 32.
