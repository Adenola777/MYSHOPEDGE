# MyShopEdge v0.3, work in progress

Prepared 21 September 2026, revised 22 September 2026 at 22:00. This package closes the
gaps found in the specification audit of the v0.1 drafts dated 20 September 2026, and
carries every platform, integration and commercial decision taken since.

## What this repository holds

| Folder | Contents |
|---|---|
| `A2` to `A18` | The rulings, one document per action |
| `schema/` | The consolidated v0.2 schema and migrations 0001 to 0018 |
| `api/` | `openapi.yaml`, 58 operations across 53 paths, 59 schemas |
| `service/` | The Python service. FastAPI, psycopg 3, PyJWT |
| `web/` | The Next.js front end, JavaScript with JSDoc |
| `testdata/` | The payload generator, the ingest, and the seeded rows |
| `design/` | The Figma change set that is written and not yet applied |

## Progress by action

| Action | Subject | Status |
|---|---|---|
| 2 | Per-product deductions grid and the Excel ledger | Specified |
| 3 | Every screen from onboarding to account closure | Specified and drawn |
| 4 | Returns, stock and the account | Specified |
| 5 | Daily, weekly and monthly views | Specified |
| 6 | Schema hardening | Specified and applied |
| 7 | Logo integration | Complete. 15 vector files derived from the master |
| 8 | Terminology standard | Specified and applied |
| 9 | Identifiers and reconciliation | Specified and applied |
| 10 | Platform, region and identity | Decided and provisioned |
| 11 | Statement ingestion and scope rulings | Specified |
| 12 | Test data requirements | Built. 119 ledger entries. The ingest did not parse between 142c3dd and 23 September, see A20.8 |
| 13 | Stack and client contract | Decided. Python and JavaScript, no TypeScript |
| 14 | The onboarding screen set | Specified. Corrected 23 September for the real provider |
| 15 | Four screen rulings, the copy pass, VAT | Specified and applied |
| 16 | The six price sheet rows | Specified. Migration 0018 applied to staging and development |
| 17 | Endpoint versions checked against the specification | Settlement detail corrected to finance 202501 |
| 18 | The eight screens the rulings moved | Specified |
| 19 | The first live TikTok calls | Connection proved. The authorised shop is a sandbox shop in region ID, not GB |
| 20 | The real settlement payload, measured | A8 section 3.5 closed. 57 fee fields, 24 shipping, 17 tax. Our maps cover 7, 5 and 1 |

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
5. **Sign-in pages are hosted by the identity provider.** Settled by Action 10, corrected
   23 September 2026. The provider is Better Auth 1.4.18, delivered as Neon Auth's Managed
   Better Auth, and not Stack Auth as A14 originally stated. A14 is now rewritten. Tokens
   are signed EdDSA over Ed25519, expire in fifteen minutes, and carry `email`,
   `emailVerified`, `name` and `role` among their claims. Issuer and audience are both the
   origin of the Neon Auth URL. **There is no second factor and none can be added**, which
   A14 section 14.7 sets out.
6. **The database is Neon, in London.** Action 10. Plain PostgreSQL 16 with the four
   hand-rolled roles and FORCE row level security applying verbatim.
7. **Bank reconciliation is out of scope.** Action 11, against PRD 6.2. The consequence is
   that `settlements.settlement_reference` has no automatic source.
8. **The TikTok invoice stays**, as an identifier for reconciliation. The VAT reclaim
   wording comes off the screen, because PRD 6.2 excludes VAT accounting for registered
   sellers.
9. **Where TikTok and a seller's own document disagree, TikTok is taken as correct.**
10. **Cost files are Excel and CSV only.** A15.1. Word and PDF carry no columns, so reading
    a cost from one means guessing, and a wrong cost is worse than a missing one.
11. **The three prices are exclusive of VAT.** A15.6. Starter, Growth and Pro are £9.99,
    £24.99 and £49.99 plus VAT. Stripe prices are immutable once created, so
    `tax_behavior: "exclusive"` had to be right first time. It was. The three prices were
    created in the live account on 23 September 2026 and each one reads back as GBP,
    recurring monthly, and exclusive.
12. **History is twenty-four months on every plan**, not tiered. A16.2. Whether TikTok
    exposes two years of statements is unverified. It was tested on 23 September and the
    test answered nothing, because the shop had no trading history. Only a shop that has
    been trading for over two years can answer it, so connecting any shop is not enough.
13. **The order limit is enforced softly.** A16.3. The count is shown at eighty per cent
    and at a hundred, the larger plan is offered, and nothing stops. No month closes, no
    export is withheld, no figure stops updating.

## Open items, by owner

| Item | Owner | Blocks |
|---|---|---|
| TikTok app developer approval | **Granted 23 September 09:00** | Four categories, all UK: Finance and Accounting, ERP, Order Management, Product Information Management |
| App credentials and a shop authorisation | Adenola | Every claim the ingestion makes. Needs `TIKTOK_APP_KEY` and `TIKTOK_APP_SECRET` set as environment variables, which a session reads only at start |
| Whether TikTok exposes twenty-four months of statements | **Still open after 23 September.** The call was made and returned nothing, against a shop with no trading history, so it answered nothing. Needs a shop trading over two years. See A19.3 | Whether A16.2 can be delivered |
| Whether the TikTok invoice number is reachable from Seller Center | Adenola | Reconciliation identifier |
| The literal column labels on a settlement export | **Closed 23 September.** Measured from a real payload. See A20 | A8 section 3.5 |
| Which Neon project the product runs on | **Settled 23 September** | `super-mouse-64697125`, the direct Neon account. See below |
| Applying migrations 0017 and 0018 | Adenola | Nothing blocks it now the project is settled |
| Repository access for `Adenola777/My-ShopEdge` | Adenola | Every commit so far, none pushed |
| Backup retention, capped at six hours on the current Neon plan | Commercial | Nothing yet |
| Immutable storage for the invoice documents | Deferred, see A10.8 | Nothing yet |
| A Vercel blob store named `myshopedge-seller-files`, provenance unknown | Identify or remove | Nothing yet |
| Whether Vercel `lhr1` guarantees data at rest in London | Confirm before launch | Data protection alignment |
| Where Better Auth processes identity data | Confirm before launch | Data protection alignment |
| Whether single factor authentication is acceptable at launch | Commercial and risk | Nothing technical. A14 section 14.7 |
| Where the Python service is hosted | Decision | `NEXT_PUBLIC_API_BASE_URL` on Vercel, and where `DATABASE_URL` lives |

## The Vercel, GitHub and Neon wiring

Traced 23 September 2026, because two Neon projects were in play and only one held the work.

| Piece | Value |
|---|---|
| GitHub | `Adenola777/My-ShopEdge`. Vercel is wired to this one, not to `MyShopEdge-` |
| Vercel team | `coterie448-8267's projects`, `team_H7VQC0OWq6IaOif0bUtyZlgg` |
| Vercel project | `my-shop-edge`, `prj_r4jxHJm7Pw4dJxYmN9RyRV7grwvg`. Framework nextjs, root `web`, functions in `lhr1` |
| Database | `super-mouse-64697125`, London, in the Neon account under adenola.adegbesan@gmail.com |

**The trap to avoid.** A Neon project provisioned through the Vercel Marketplace lives in a
Neon organisation that Vercel creates and manages, tied to the Vercel login rather than to
the Neon account you sign into at neon.com. That is what `holy-glitter-85206770` is, and it
is why an API key from the direct account cannot see it. It held no schema of ours, and
`DATABASE_URL` on the Vercel project pointed at it.

The product runs on the direct account's project, because that is where twenty migrations,
three branches, the seeded seller and the verified row level security live.

**The convenience is kept, by using the other integration.** Ruled 23 September 2026. Neon
offers three ways to connect to Vercel, not two. The Vercel-managed one provisions a new
database under Vercel. The **Neon-managed** one, installed from the Neon console and listed
in the Vercel Marketplace under Connectable Accounts, connects a project that already
exists and still injects the variables automatically and still creates a database branch
per preview deployment. Its branch cleanup follows git branches rather than deployments,
which is the better of the two.

So `DATABASE_URL`, `DATABASE_URL_UNPOOLED`, the legacy `PG*` variables and
`NEON_AUTH_BASE_URL` are all set automatically, on a project holding the work. **The two
integrations cannot coexist on one Vercel project**, so the Vercel-managed one is removed
first.

**None of this is urgent, and it was treated as though it were.** Checked 23 September:
the Next.js front end never touches the database. It calls the API over HTTP through
`NEXT_PUBLIC_API_BASE_URL` and contains no Postgres client, no Neon package and no
reference to `DATABASE_URL`. The database belongs to the Python service, which is not
hosted on Vercel and has no host decided yet.

So the stale `DATABASE_URL` entries left on the Vercel project by the marketplace
integration are inert. Nothing reads them. They can stay until the integration is sorted
out at leisure. The one variable the Vercel project will need is
`NEXT_PUBLIC_API_BASE_URL`, and that waits on the service having somewhere to run.

**Where the Python service runs is an open item nobody has raised.** Vercel is hosting the
front end. FastAPI, psycopg and a connection pool are a different shape of deployment, and
choosing its home also decides where `DATABASE_URL` lives.

`NEON_AUTH_BASE_URL` is the variable the service already falls back to. With it present,
the JWKS URL, the issuer and the audience are all derived and nothing has to be set by
hand. The issuer and audience are the origin of that URL with no path, which is why the
service derives them with `urlsplit` rather than by appending to the base.

## Counts

| Measure | v0.1 | v0.3 |
|---|---|---|
| Functional requirements | 73 | 87 |
| Of which Must | 64 | 78 |
| Test cases | 84 | 107 |
| Golden datasets | 10 | 12 |
| Screens ruled | 15 | 39 |
| Screens drawn in Figma | 0 | 18 |
| Schema migrations | 0 | 19 |
| API operations specified | 0 | 58 |

## Build status

The specification is nearly complete. The application is not.

| Layer | State |
|---|---|
| Brand, terminology, screen specification, data model, API contract | Done |
| Schema applied | Through 0019 on staging and development, 20 recorded each. Production holds through 0016 plus the 0019 security fix |
| Backend | 4 of 58 routes. Billing and health |
| Authentication | Fixed 23 September. EdDSA verified, email from `users_sync`, nine tests passing |
| Billing | Screens built. The three products and prices were created in the live Stripe account on 23 September. See CLAUDE.md for the identifiers |
| TikTok integration | Not built. Checked 23 September: nothing in the repository calls a TikTok host. The ingest reads local JSON files. `/connections/tiktok/authorize` and `/connections/tiktok/callback` are specified and unimplemented |
| Front end | 2 pages of 39 screens |
| Deployment | Vercel chosen. Nothing deployed |
| Tests | 1 file, 9 cases, rewritten against Ed25519 with a regression case |

## Scope check

Every screen added in Action 3, S16 to S32, was tested against PRD section 6.1 and maps to
an epic that is in the MVP. Nothing added in Actions 2 to 16 falls inside PRD 6.2, with
three exceptions ruled on above: bank reconciliation, which has been withdrawn, the VAT
reclaim wording, which has been removed while the invoice identifier is kept, and four
price sheet rows ruled out of the MVP in A16.
