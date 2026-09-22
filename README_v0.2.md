# MyShopEdge v0.3, work in progress

Prepared 21 September 2026, revised 22 September 2026. This package closes the gaps found
in the specification audit of the v0.1 drafts dated 20 September 2026, and carries the
platform and TikTok integration decisions taken since.

## What this package holds

| Folder | Contents |
|---|---|
| `originals/` | The ten v0.1 files, unchanged, for comparison |
| `specifications/` | The new specification text, by action, ready to merge into the documents |
| `schema/` | The consolidated v0.2 schema and migrations 0001 to 0011 |
| `wireframes/figures/` | The wireframe figures, rendered at 2x |

## Progress against the audit

| Audit question | Action | Status |
|---|---|---|
| 1. Per-product deductions grid and the Excel ledger | Action 2 | Specified |
| 2. Returns, stock and the account | Action 4 | Specified |
| 3. Every screen from onboarding to account closure | Action 3 | Specified and drawn. Seventeen screens, nine figures |
| 4. Logo integration | Action 7 | Complete. Fourteen vector files derived from the master |
| 5b. Daily, weekly and monthly views | Action 5 | Specified |
| Schema hardening | Action 6 | Specified and applied |
| Terminology standard | Action 8 | Specified and applied |
| Identifiers and reconciliation | Action 9 | Specified and applied |
| Platform, region and identity | Action 10 | Decided and provisioned |
| Statement ingestion and scope rulings | Action 11 | Specified |
| Rebuild the ten documents | Action 12 | Not started |

## Decisions taken, and open to reversal

1. **Product Specification v2.0 is absent from the pack.** The formulas its sections 8 and
   12 were expected to carry are written into the SRD instead, so the pack stands on its
   own. Action 4 carries Return Loss, Contribution and You keep.
2. **Contribution excludes the cost of returned units.** A returned unit's cost appears
   once, either as stock value recovered or as a write-off inside Return Loss.
3. **The brand orange for text and actions is #C4400C**, which measures 5.14:1 on white.
   The v0.1 orange of #F05423 measures 3.5:1 and fails WCAG 2.2 AA for normal-size text,
   which NFR-10 requires. The original orange is kept for large graphics.
4. **Golden dataset numbering.** G10 was already in use for the workbook discrepancy
   dataset. The new datasets are G11, from Action 2, and G12, from Action 4.
5. **Sign-in pages may be hosted by the identity provider.** Settled by Action 10. Neon
   Auth provides the hosted pages, so MyShopEdge does not build its own.
6. **The database is Neon, in London.** Action 10. Plain PostgreSQL 16 with the four
   hand-rolled roles and FORCE row level security applying verbatim.
7. **Bank reconciliation is out of scope.** Action 11, against PRD 6.2. The consequence is
   that `settlements.settlement_reference` has no automatic source.
8. **The TikTok invoice stays**, as an identifier for reconciliation. The VAT reclaim
   wording comes off the screen, because PRD 6.2 excludes VAT accounting for registered
   sellers.

## Open items, by owner

| Item | Owner |
|---|---|
| A UK shop, live or sandbox, for the integration spike | Adenola |
| Whether the TikTok invoice number is reachable at all, from Seller Center | Adenola |
| Whether Vercel's `lhr1` guarantees data at rest in London | Confirm before launch |
| Immutable storage for the invoice documents, which Vercel Blob does not offer | Deferred, see A10.8 |
| A pre-existing Vercel blob store named `myshopedge-seller-files`, provenance unknown | Identify or remove |
| Backup retention, capped at six hours on the current Neon plan | Commercial |
| Where Stack Auth processes identity data | Confirm before launch |
| Whether Neon Auth offers multi-factor authentication | Confirm |
| Request and response schemas for the 51 REST endpoints | Specification |
| Hosting, since Vercel and AWS London containers are not the same answer | Decision |

## Counts

| Measure | v0.1 | v0.3 |
|---|---|---|
| Functional requirements | 73 | 87 |
| Of which Must | 64 | 78 |
| Test cases | 84 | 107 |
| Golden datasets | 10 | 12 |
| Designed screens | 15 | 32 |
| Wireframe figures | 8 | 18 |
| Schema migrations | 0 | 11 |

## Scope check

Every screen added in Action 3, S16 to S32, was tested against PRD section 6.1 and maps to
an epic that is in the MVP. Nothing added in Actions 2 to 11 falls inside PRD 6.2, with the
two exceptions ruled on above: bank reconciliation, which has been withdrawn, and the VAT
reclaim wording, which has been removed while the invoice identifier is kept.
