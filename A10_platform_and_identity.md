# A10. Platform, region and identity

Prepared 22 September 2026. This action records the platform decisions taken after the
v0.2 specification audit, and it replaces the corresponding rows in the TRD technology
decisions table and the Cloud Hosting document.

## A10.1 What changed and why

The TRD stated *Hosting, AWS London region on containers* and *PostgreSQL 15 or later*.
The database is now provisioned, and the decisions below are what is actually running
rather than what was proposed.

| Decision | v0.1 and v0.2 | v0.3 | Reason |
|---|---|---|---|
| Database platform | PostgreSQL, vendor unnamed | Neon, managed PostgreSQL 16.15 | Plain PostgreSQL. The four hand-rolled roles, the privilege revocations and `FORCE ROW LEVEL SECURITY` apply verbatim, with no vendor identity model to reconcile |
| Region | AWS London, stated for hosting | `aws-eu-west-2`, AWS Europe West 2, London | UK seller financial records. The Data Protection document assumes UK processing |
| Identity provider | Managed provider, vendor unnamed | Neon Auth, running on Stack Auth | Satisfies the stated requirement for a managed provider with email login. See the open item in A10.4 |
| Object storage | Assumed alongside the database | Vercel Blob, region `lhr1`, London | Neon object storage is not offered in the London region. See A10.8 |

## A10.2 Environments

The TRD requires development, staging and production. These are Neon branches of one
project, each with its own compute and its own connection string, all in London.

| Branch | Role |
|---|---|
| `production` | The default branch. Database `myshopedge`, owner role `mse_migrator` |
| `staging` | Branched from production at the schema, for release verification |
| `development` | Branched from production at the schema, for day to day work |

A branch is a copy-on-write clone, so a developer can branch production, run a migration
against the copy, compare the schema and discard it. That replaces the practice of testing
migrations against an approximation of production.

## A10.3 Two capabilities the London region does not provide

Choosing London has a cost, and it is recorded here rather than discovered later.

**Object storage is unavailable.** Neon's branchable object storage is not offered in
`aws-eu-west-2`. The schema has two columns that need a file store, `cost_uploads.storage_key`
and `exports.storage_key`. **Resolved by A10.8**, which places the file store on Vercel Blob
in the London region rather than alongside the database.

**Scheduled backups are not enabled on the current plan.** Point-in-time recovery is
capped at six hours of history retention, against a requested thirty days, and automatic
snapshot schedules are refused. Six hours is not adequate for a system holding financial
records that HMRC expects to be retained for six years. This is a commercial matter rather
than a technical one: the retention ceiling rises with the plan. It must be resolved before
a real seller connects, not after.

## A10.4 Identity

Neon Auth is provisioned on the production branch. It maintains a synchronised copy of the
provider's user records in `neon_auth.users_sync`, whose `id` column is the JWT subject
claim. `accounts.auth_subject` has always held that subject, so the schema needed no change.

Migration 0011 adds the `account_identity` view, which joins the two and exposes
`provider_record_missing`. An account with no matching identity record is a defect and
raises a discrepancy under DSC-1.

`app_account_id()` is unchanged. The application verifies the JWT against the provider's
JWKS endpoint and then sets `app.account_id` with
`set_config('app.account_id', $1, true)`. The transaction-local form is required. A
session-level setting would leak identity across a pooled connection, and that is stated
as a defect in the function's own comment.

**Two open items on identity.**

The provider is Stack Auth, which is a third party reached through Neon. Where Stack Auth
processes and stores identity data has not been confirmed. Having deliberately placed the
database in London, the same question must be answered for the identity records before
launch, and the answer belongs in the Data Protection document rather than here.

Multi-factor authentication is listed in the TRD as optional. Whether Neon Auth offers it,
and on which plan, has not been confirmed.

## A10.5 One capability deliberately declined

Neon offers a Data API, which exposes tables over HTTP in the manner of PostgREST. It is
**not enabled**, and it should not be.

MyShopEdge holds other businesses' financial records. Automatically publishing every table
to the internet makes the correctness of a row-level security policy a breach question
rather than a bug question. `FORCE ROW LEVEL SECURITY` is in place on all 31 tenant tables
and would very probably hold, but the failure mode is not worth the convenience. Every read
goes through the MyShopEdge API layer, which is where authentication, validation and the
tenant setting already live.

This is the same reasoning that counted against Supabase when the platform was chosen.

## A10.6 What is running

| Measure | Value |
|---|---|
| Project | MyShopEdge, `super-mouse-64697125` |
| Region | `aws-eu-west-2`, London |
| Engine | PostgreSQL 16.15 |
| Database | `myshopedge` |
| Tables | 32 |
| Tables with FORCE row level security | 31, every table except `reference_rules` |
| Policies | 31 |
| Views | 5 |
| Append-only triggers | 7 |
| Roles | `mse_owner`, `mse_app`, `mse_analytics`, `mse_migrator` |
| Migrations applied | 0001 to 0011 |

Verified after loading: `mse_app` holds SELECT and INSERT on `ledger_entries` and is refused
UPDATE, DELETE and TRUNCATE; `reference_rules` is read-only to the application; neither
`mse_app` nor `mse_analytics` carries BYPASSRLS; and the Europe/London generated columns
resolve the British Summer Time boundary correctly, with 23:30 UTC on 30 June falling on
1 July.

## A10.7 Changes to the document pack

| Document | Change |
|---|---|
| TRD | Technology decisions table: database, region, identity and environments replaced by A10.1 and A10.2. Section 5.5 gains the identity bridge |
| Cloud Hosting | Region and platform restated. Object storage and backup retention raised as open items from A10.3 |
| Backend Orchestration and Schema | Migration list extended to 0011. Section 4.5 gains `settlement_totals_check` and `account_identity` |
| Data Protection | Identity processor location added as an open item. Retention of `tiktok_invoices` restated at six years against the ninety day `raw_events` purge |
| API Integration | Section 3.5 field mapping replaced by the confirmed TikTok field names. Bank reconciliation removed |
| SRD | REC requirements restated without the bank reference. A new requirement covers the statement dating rule |

## A10.8 Object storage

Neon does not offer object storage in the London region, so the file store is separate from
the database. It is **Vercel Blob in `lhr1`**, which is London.

| Property | Value |
|---|---|
| Store | `myshopedge-files-lhr1` |
| Store ID | `store_wEDVzkmhHUy5FToJ` |
| Region | `lhr1`, London |
| Access | `private` |
| Owner | Vercel team `team_H7VQC0OWq6IaOif0bUtyZlgg` |

Access is private, so nothing is readable without a signed URL issued by the MyShopEdge API.
The schema needed no change: `cost_uploads.storage_key` and `exports.storage_key` hold the
object key and the application generates the URL, so the store can be replaced later without
a migration.

### Key convention

| Prefix | Contents | Life |
|---|---|---|
| `uploads/{shop_id}/{upload_id}/{nonce}/{filename}` | Seller cost files | Kept as the evidence behind applied costs |
| `exports/{shop_id}/{export_id}/{nonce}.{ext}` | Generated spreadsheets | Swept when `exports.expires_at` passes |
| `account-exports/{account_id}/{request_id}/{nonce}.zip` | ACC-4 data downloads | Days |
| `invoices/{shop_id}/{invoice_number}.pdf` | **Not yet used.** See below | Six years |

Every key carries a random `nonce` segment. Identifiers alone are predictable, and a
predictable key plus any future misconfiguration is cross-tenant access. Signed URLs are
issued for fifteen minutes, not hours, because a leaked URL is a leaked file for as long as
it lives.

### What this does not cover

**Immutable retention.** Vercel Blob has no equivalent of S3 Object Lock, so nothing prevents
a bug or a compromised credential from deleting a stored document. That matters for one thing
only: the TikTok fee invoices, which are the evidence behind a VAT position and are retained
for six years.

The `invoices/` prefix is therefore **not populated yet**. `tiktok_invoices.document_url` and
`document_fetched_at` stay empty, which costs nothing today because the invoice number itself
is still unresolved (A11.6). When immutable storage is available, that one prefix moves and
nothing else does.

**Lifecycle sweeping is the application's job.** There are no server-side lifecycle rules, so
the nightly job must delete expired exports by reading `exports.expires_at` rather than
relying on the store to do it.

**Deletion under ACC-4 must reach the store.** Deleting an account's rows does not delete its
files. The account deletion job must remove every object under that account's prefixes, and
the deletion record must say so.

### Two things to confirm

`lhr1` is Vercel's edge region name. That it means data at rest in London needs confirming
from Vercel directly before a seller's file lands in it, and the answer belongs in the Data
Protection document alongside the same question about Stack Auth.

Choosing Vercel Blob leans the hosting decision toward Vercel, which conflicts with the TRD
line specifying AWS London containers. That conflict already existed. This does not create
it, but it does make it harder to leave open.

### One finding worth recording

The first attempt to create this store was refused with `store_name_not_unique`: a store named
`myshopedge-seller-files` already exists on the account, and no tool available here lists
stores or reports their settings. Building on a store whose region and access cannot be
verified would quietly undo both the residency and the privacy decision, so a distinctly named
store was created instead. The pre-existing store should be identified and either removed or
documented.
