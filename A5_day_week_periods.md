# Action 5: Daily and weekly views, and keeping Excel current

Closes audit question 5b and the Excel currency question left open under question 1.

Monthly is fully specified in v0.1. Daily stops at a period named Today with no way to reach another day. Weekly exists only for expected payouts and 7-day averages. The ledger stores `basis_month` and `settlement_month`, both month-sized, and the rule that a refund counts in the month it completes is also stated only by month. Day and week need the same treatment, and they need a timezone rule that v0.1 states for the API but not for the ledger.

---

## 5.1 The day key

### Why it needs defining

Section 4.1 of the API Integration document says months and days are local dates in Europe/London. Section 3 of the Backend Orchestration document says `basis_month` is the order month and never says in which zone. `occurred_at` is a `timestamptz` held in UTC. A sale at 23:30 UTC on 30 June 2026 is 00:30 on 1 July in London, because British Summer Time is in force. Deriving the month in UTC puts that sale in June and deriving it in London puts it in July. One of those is wrong on the seller's VAT return, and nothing in the pack says which.

### The rule

Every date key on a ledger entry is derived from `occurred_at` converted to Europe/London, then truncated. This applies to the day, the week and the month, so the three agree with one another by construction.

```sql
alter table ledger_entries
  add column basis_day date
    generated always as (((occurred_at at time zone 'Europe/London')::date)) stored,
  add column basis_week date
    generated always as (
      date_trunc('week', (occurred_at at time zone 'Europe/London'))::date
    ) stored;

create index ledger_basis_day_idx  on ledger_entries (shop_id, basis_day);
create index ledger_basis_week_idx on ledger_entries (shop_id, basis_week);
```

`basis_month` is restated in the same terms rather than left implicit, and the migration checks that no existing row changes month under the corrected derivation. Any row that does change is reported rather than moved silently, because a month that has already been exported to an accountant must not shift without the seller being told.

`settlement_day` and `settlement_week` are derived the same way from the settlement timestamp, for the cash basis.

### Two days a year are not 24 hours long

In 2026 British Summer Time begins on 29 March and ends on 25 October. The 29th of March holds 23 hours and the 25th of October holds 25 hours. Both are still one day. Because the key is a truncated local date rather than an offset from a fixed instant, both days take every entry that falls inside them and neither loses nor duplicates an hour.

The 25th of October also holds a repeated hour between 01:00 and 02:00 local. Two entries an hour apart in real time can carry the same local clock time. They are distinct rows, they both belong to the 25th, and ordering within the day uses `occurred_at` rather than the local clock time, so the display order stays truthful.

---

## 5.2 The week

### The rule

A week runs Monday to Sunday and is identified by the date of its Monday. Weeks follow ISO 8601, so the week belongs to the year holding its Thursday. This matters once a year: the week of 28 December 2026 to 3 January 2027 is week 53 of 2026, not week 1 of 2027.

Monday is chosen over Sunday because it is the British convention and because HMRC's own weekly periods start on a Monday. The choice is recorded rather than assumed.

### Weeks are derived, never stored as a table

`daily_metrics` already holds one row a day. A week is the sum of its seven daily rows and a month is the sum of its days. No weekly table is added, so there is no second cache to fall out of step with the first. The trade is a slightly heavier read for a guarantee that day, week and month always agree.

### Weeks cross months, and that is allowed

A week may hold days from two months. The week of 29 June to 5 July 2026 holds two days of June and five of July. Weekly figures are therefore never reconciled against monthly figures directly, and no screen adds a weekly figure to a monthly one. Where a week spans a month end, the week view states it: "This week covers 29 June to 5 July."

### Refunds across boundaries

RET-2 says a refund counts in the month it completes and the original month is not restated. The same rule extends downward without change. A refund counts in the day it completes and in the week that day falls in. The original day and week are not restated either. One sentence in the SRD now covers all three periods rather than only the month.

---

## 5.3 Periods offered

MON-1 is replaced.

| ID | Requirement | Acceptance | Trace | Priority |
|---|---|---|---|---|
| MON-1 | Offer Today, This week, This month, Tax year to date and a custom date range, with a toggle between sales basis and cash basis on every one of them. | Each period returns figures that reconcile to the ledger for that period on both bases | Section 21 (VIS-5) | Must |
| MON-5 | Let the seller move to any earlier day or week, not only the current one, back to the start of the loaded history. | A day twelve months ago opens and its figures reconcile to the ledger | Section 21 (VIS-5) | Must |
| MON-6 | State on every period view which dates it covers, in full, including where a week crosses a month end. | The stated dates match the figures returned | Section 25 (CL-5) | Must |
| MON-7 | Offer a period picker on every export, covering the same periods as the screens and a custom range. | An export of a custom range reproduces the on-screen totals for that range | Section 22 (BK-4) | Must |

The custom range is capped at 366 days, which covers a full tax year and one leap day, and the cap is stated on the picker rather than enforced by a failure.

### What each period means, exactly

| Period | Definition |
|---|---|
| Today | The current local date in Europe/London, from 00:00 to the as-at time. Partial by nature, and labelled so. |
| This week | The Monday of the current local week to the as-at time. Partial, and labelled so. |
| This month | The first of the current local month to the as-at time. Partial, and labelled so. |
| Tax year to date | 6 April to the as-at time, using the tax year in the seller's profile where one is set, and the UK personal tax year where it is not. |
| Custom | Two local dates, inclusive at both ends, up to 366 days apart. |

Partial periods carry the Estimated chip only where figures are genuinely still moving. A completed day carries Confirmed once the nightly reconciliation has run against it, which is the same rule that already applies to months.

---

## 5.4 The Net Proceeds identity, extended

LED-4 requires Net Proceeds to equal Paid Out plus Awaiting Settlement for any order month, and the nightly check runs per order month only.

The identity holds for any grouping of orders, because Awaiting Settlement is derived per order from `order_settlements` rather than per month. Extending the check costs nothing but catches a whole class of error the monthly check cannot see: a settlement attributed to the wrong day inside the right month passes the monthly check and fails the daily one.

| ID | Requirement | Acceptance | Trace | Priority |
|---|---|---|---|---|
| LED-13 | Assert nightly that Net Proceeds equals Paid Out plus Awaiting Settlement for every order day and every order week, as well as every order month, and raise a discrepancy where it does not. | The check runs at all three levels and a deliberately misdated settlement is caught at day level | Section 22 (BK-2) | Must |

The job runs day level first, then week, then month, and stops reporting at the finest level that fails, so one misdated settlement raises one discrepancy rather than three.

---

## 5.5 Schema changes to daily_metrics

Two defects surface once day and week become real periods.

**There is no basis.** `daily_metrics` holds one row per shop, SKU and date, with no column saying whether the row is a sales-basis or a cash-basis figure. A daily cash-basis view cannot be served from it at all. The unique index has to change with it.

**Return costs and write-offs are missing.** Action 4 puts Return Loss into You keep. Neither entry type has a column here, so You keep cannot be computed for a day without going back to the ledger.

```sql
alter table daily_metrics
  add column basis text not null default 'sales'
    check (basis in ('sales','cash')),
  add column return_cost_minor bigint not null default 0,
  add column write_off_minor  bigint not null default 0,
  add column you_keep_minor   bigint;

drop index daily_metrics_key_idx;
create unique index daily_metrics_key_idx on daily_metrics (
  shop_id,
  coalesce(sku_id, '00000000-0000-0000-0000-000000000000'::uuid),
  metric_date,
  basis
);
```

`you_keep_minor` is nullable, and stays null where cost coverage for the day is incomplete. That mirrors the API, which already returns `kept: null` with a reason rather than a zero.

`metric_date` is derived in Europe/London under section 5.1, so the cache and the ledger agree on which day a figure belongs to.

---

## 5.6 API changes

Existing endpoints gain the period parameters rather than growing siblings.

| Endpoint | Change |
|---|---|
| `GET /v1/shops/{id}/money` | `period` accepts `today`, `week`, `month`, `tax_year`, `custom`; `from` and `to` for custom; `date` or `week_start` to open an earlier one |
| `GET /v1/shops/{id}/today` | Unchanged in shape. It remains the named screen endpoint for the current day. |
| `GET /v1/shops/{id}/money/where-it-went` | Same period parameters |
| `GET /v1/shops/{id}/velocity` | Same period parameters |
| `GET /v1/shops/{id}/products` | Same period parameters |
| `GET /v1/shops/{id}/products/{productId}/transactions` | Already carries them, from Action 2 |
| `POST /v1/shops/{id}/exports` | Accepts `period`, `from`, `to` and `basis` |

One endpoint is added, mirroring the month summary that LED-6 already requires.

| Method | Path | Purpose | SRD |
|---|---|---|---|
| GET | `/v1/shops/{id}/summary/week/{weekStart}` | Week summary, in the same shape as the month summary | LED-6, MON-5 |
| GET | `/v1/shops/{id}/summary/day/{date}` | Day summary, same shape | LED-6, MON-5 |

Every period response carries `period.from`, `period.to` and `period.label`, so MON-6 is satisfied by the API rather than by each client inventing its own wording. Where a week crosses a month end, `period.label` reads "29 June to 5 July".

The `exports` table already holds `period_start` and `period_end`. It gains `basis` and a fourth kind.

```sql
alter table exports
  add column basis text not null default 'sales'
    check (basis in ('sales','cash'));
alter table exports
  drop constraint exports_kind_check;
alter table exports
  add constraint exports_kind_check
    check (kind in ('month_summary','ledger','accountant','transactions'));
```

---

## 5.7 Keeping Excel current

### What the audit found

The account ledger in PostgreSQL updates itself on every webhook, every 15-minute poll and every nightly reconciliation. Excel does not. An export builds a file on request and that file expires after seven days. Nothing pushes a change into a workbook the seller already holds. The PRD's spreadsheet seller wants to stop re-typing TikTok data, and today that want is met by re-downloading rather than by a sheet that stays current.

### What is specified for the MVP

Two things, neither of which writes into the seller's own file.

**A scheduled export.** The seller chooses a day and a format, and the file is built and made available on that day without being asked for. Monthly on a chosen date, or weekly on a chosen weekday. The seller is told in the app and, if they have not opted out, by email. This is the smallest change that removes the re-typing, and it reuses the export pipeline already specified.

| ID | Requirement | Acceptance | Trace | Priority |
|---|---|---|---|---|
| MON-8 | Let the seller schedule an export monthly or weekly, deliver it without being asked, and tell them it is ready. | A scheduled export appears on the chosen day with totals equal to the screen for that period | Section 22 (BK-4) | Should |

```sql
create table export_schedules (
  id uuid primary key default gen_random_uuid(),
  shop_id uuid not null references shops(id),
  kind text not null check (kind in ('month_summary','ledger','accountant','transactions')),
  format text not null check (format in ('xlsx','csv')),
  basis text not null default 'sales' check (basis in ('sales','cash')),
  cadence text not null check (cadence in ('weekly','monthly')),
  day_of_week smallint check (day_of_week between 1 and 7),
  day_of_month smallint check (day_of_month between 1 and 28),
  active boolean not null default true,
  last_run_at timestamptz,
  created_at timestamptz not null default now(),
  check ((cadence = 'weekly'  and day_of_week  is not null and day_of_month is null)
      or (cadence = 'monthly' and day_of_month is not null and day_of_week  is null))
);
```

The day of month is capped at 28 so a monthly schedule never skips February.

**A refresh feed.** A private, revocable link that Excel's own Refresh command can read, so the seller's workbook pulls the current figures rather than being written into. The link is a URL with a token, it serves one period on one basis, and it is listed in Settings with the date it was created, the date it was last used and a control to revoke it.

| ID | Requirement | Acceptance | Trace | Priority |
|---|---|---|---|---|
| MON-9 | Offer a private, revocable feed link that a spreadsheet can refresh from, listed in Settings with its last use, revocable in one action, and expiring on its own after 90 days of no use. | Refreshing the workbook returns current figures. Revoking the link makes the next refresh fail. | Section 22 (BK-4) | Could |

### The security position, stated rather than assumed

A feed link is a bearer credential. Anyone holding the URL holds the data, and a URL travels in ways a password does not: it sits in the workbook, in the file the seller emails to their accountant, and in the browser history of anyone who opens it. That is a real change to the product's security posture and it needs the following before MON-9 ships.

1. The token is scoped to one shop, one export kind, one basis and read access only. It can never reach another shop or write anything.
2. The token is high entropy, stored only as a hash, and shown to the seller once.
3. Every use is logged with the time and the requesting address, and the last use is shown in Settings, so an unexpected use is visible.
4. The link expires after 90 days without use and is revocable in one action, which revokes it immediately rather than at the next cache expiry.
5. Rate limits apply per token, tighter than the per-account limits in section 4.1.
6. The privacy notice and the record of processing in section 3 of the Data Protection Document are updated, because the seller is choosing to make financial data reachable by anyone holding a URL. The choice is theirs to make, and it is stated plainly at the moment they make it rather than in the terms.
7. A data protection impact assessment entry is added to the register in section 10 of the Data Protection Document, since this is the only route by which the product's data leaves an authenticated session.

Point 6 is why MON-9 is Could rather than Must. The scheduled export in MON-8 removes most of the re-typing with none of this exposure. The feed is worth building, and it is worth building after the pilot rather than before it.

**A connector to Google Sheets or OneDrive is out of scope for the MVP**, and the reason is recorded rather than left as silence. Both require an OAuth relationship with a third party, ongoing token custody, and a write scope into the seller's own files. That is a larger security and support commitment than the MVP can carry, and the audit's own reading agrees. It stays on the Release 2 list in section 6.2 of the PRD.

---

## 5.8 Golden dataset G13

Added to section 3.1 of the Functionality QA document. G13 proves the day key, the week key and the clock changes in one dataset.

**Inputs.** Six sales, each of £10.00 with no deductions, on a single product with a cost of £4.00.

| Sale | `occurred_at` in UTC | London local time | Expected day | Expected week starting | Expected month |
|---|---|---|---|---|---|
| A | 2026-06-10 23:30 | 2026-06-11 00:30 BST | 11 June 2026 | 8 June 2026 | June 2026 |
| B | 2026-06-30 23:30 | 2026-07-01 00:30 BST | 1 July 2026 | 29 June 2026 | July 2026 |
| C | 2026-12-10 23:30 | 2026-12-10 23:30 GMT | 10 December 2026 | 7 December 2026 | December 2026 |
| D | 2026-03-29 01:30 | 2026-03-29 02:30 BST | 29 March 2026 | 23 March 2026 | March 2026 |
| E | 2026-10-25 00:30 | 2026-10-25 01:30 BST, the first pass of the repeated hour | 25 October 2026 | 19 October 2026 | October 2026 |
| F | 2026-10-25 01:30 | 2026-10-25 01:30 GMT, the second pass of the repeated hour | 25 October 2026 | 19 October 2026 | October 2026 |

**Expected results.**

1. Sale A falls on 11 June, not 10 June. Deriving the day in UTC would place it on the 10th.
2. Sale B falls in July, not June. This is the case that would put a sale in the wrong month on a VAT return.
3. Sale C falls on 10 December, because Greenwich Mean Time is in force and no conversion moves it.
4. The 29th of March 2026 holds 23 hours and still takes sale D. The 25th of October 2026 holds 25 hours and takes both E and F.
7. Sales E and F carry the same local clock time of 01:30 and are an hour apart in real time. Both belong to the 25th of October, both appear once, and E is listed before F because ordering within a day uses `occurred_at` rather than the local clock.
5. The week of 29 June to 5 July holds sale B and two days of June. Its label reads "29 June to 5 July", and its total is never added to a June or July monthly total.
6. The week containing 31 December 2026 is week 53 of 2026, because its Thursday falls in 2026.

---

## 5.9 Test cases

Added to sections 5.4 and 5.10 of the Functionality QA document.

| ID | Test | Expected result | Trace |
|---|---|---|---|
| TC-MON-05 | Load G13 and read the day, week and month keys for all five sales. | Every key matches the G13 table. | MON-1 |
| TC-MON-06 | Open a day twelve months back and reconcile it against the ledger. | The figures agree to the penny. | MON-5 |
| TC-MON-07 | Open the week of 29 June 2026. | The label reads "29 June to 5 July" and the total holds both months' days. | MON-6 |
| TC-MON-08 | Toggle basis on the day, week, month and custom views. | Every period returns both bases and each reconciles to the ledger. | MON-1, LED-4 |
| TC-MON-09 | Export a custom range of 1 to 17 March and compare with the screen. | The file totals equal the screen totals. | MON-7 |
| TC-MON-10 | Request a custom range of 400 days. | The picker states the 366-day cap before the request is made. | MON-7 |
| TC-MON-11 | Set a monthly scheduled export for the 28th and wait for it. | The file appears on the 28th, with totals equal to the screen, and the seller is told. | MON-8 |
| TC-MON-12 | Refresh a workbook against a feed link, then revoke the link and refresh again. | The first refresh returns current figures. The second fails. Settings shows the last use. | MON-9 |
| TC-MON-13 | Leave a feed link unused for 91 days. | The link has expired and Settings says so. | MON-9 |
| TC-LED-19 | Misdate a settlement to the wrong day inside the right month, then run the nightly check. | The day-level check raises one discrepancy. The month-level check would have passed. | LED-13 |
| TC-LED-20 | Complete a refund on 3 October for an order placed on 28 September. | October's day, week and month all show the refund. September's are unchanged at all three levels. | RET-2, LED-13 |
| TC-LED-21 | Run the migration that restates `basis_month` in Europe/London. | Any row whose month changes is reported rather than moved silently. | MON-1 |

---

## 5.10 Summary of what Action 5 changes

| Document | Change |
|---|---|
| SRD | MON-1 replaced. MON-5 to MON-9 and LED-13 added. The refund period rule restated to cover day, week and month in one sentence. |
| API Integration | Period parameters on seven endpoints, two summary endpoints added, `period.label` added to every period response. |
| Backend Orchestration and Schema | Day and week keys defined in Europe/London. The nightly identity check extended to day and week. `export_schedules` added. |
| Schema SQL | `basis_day` and `basis_week` on `ledger_entries`. `basis`, `return_cost_minor`, `write_off_minor` and `you_keep_minor` on `daily_metrics`, with the unique index changed. `basis` and a fourth kind on `exports`. `export_schedules` created. |
| Functionality QA | Golden dataset G13. Twelve test cases. |
| Wireframes and Workflows | Period chips gain This week and a custom range. S23 gains the period picker, already drawn in Action 3. Settings gains scheduled exports and the feed link with its last use and revoke control. |
| PRD | Google Sheets and OneDrive connectors recorded on the Release 2 list with the reason. |
| Data Protection | Feed links added to the record of processing, the privacy notice and the impact assessment register. |
