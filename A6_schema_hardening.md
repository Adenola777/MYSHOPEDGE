# Action 6: Schema hardening

Closes the two schema findings in the audit, folds in the schema changes from Actions 2, 4 and 5, and verifies the result against a running PostgreSQL 16 rather than asserting that it works.

Everything below was executed. The consolidated file loads into an empty database, and a seventeen-test harness runs against it. Both files ship in `schema/`.

---

## 6.1 What was wrong

| Finding | Where it came from |
|---|---|
| The append-only ledger is not enforced anywhere in the SQL | Audit. LED-1 and TC-LED-04 rely on a restricted database role that no file defines. |
| Row-level security is enabled but not forced, and a table owner bypasses it | Audit. ACC-3 depends on the policies holding. |
| No roles, no grants, no revokes exist at all | Found while writing this action. The pack names a restricted role and never creates one. |
| The idempotency index rejects split deductions | Action 2. One order-level deduction posts once per line under the same TikTok reference. |
| `daily_metrics` holds no basis, so a daily cash-basis figure cannot be cached | Action 5. |
| `reference_rules` is writable by the application | Found while verifying. It is shared tax reference data under TAX-6, not tenant data. |
| Roles are cluster-wide, so the role migration is not idempotent | Found while loading the file into a second database. |

The last three were found only because the schema was run rather than read.

---

## 6.2 Append-only, enforced twice

LED-1 says no ledger row can be updated or deleted by the application. v0.1 stated the rule and enforced nothing at all.

**Layer one is privilege.** `update`, `delete` and `truncate` are revoked from `mse_app` on `ledger_entries`, and also on `change_log` and `audit_log`, which are logs and were equally unprotected. The application cannot ask.

**Layer two is a trigger.** `enforce_append_only` raises on update and delete, and a statement-level trigger raises on truncate. The trigger holds against every role, including the owner and the migrator, so a mistake during maintenance is caught as well as a mistake in the application.

Maintenance that genuinely must rewrite history sets `app.allow_ledger_maintenance` to `on`, local to the transaction. The Action 2 backfill is the one place that uses it. The escape hatch is deliberately useless to the application, and that was tested: `mse_app` setting the flag still gets `permission denied`, because the privilege layer refuses before the trigger is ever reached.

Retention still works. Section 4.6 purges `raw_events` and expired exports, neither of which is append-only, and account deletion under ACC-4 removes the whole account rather than individual rows.

---

## 6.3 Roles

The pack referred to a restricted role and defined none. Four roles now exist, and the application uses exactly one.

| Role | Purpose |
|---|---|
| `mse_owner` | Owns every object. Cannot log in. |
| `mse_app` | The only role the application connects as. Subject to forced row-level security. Never owns an object and is never granted `BYPASSRLS`. |
| `mse_analytics` | Read-only, for analysis. Subject to row-level security. |
| `mse_migrator` | Runs migrations. Granted `mse_owner` and `BYPASSRLS` so a backfill can reach every shop. Never used by the application or by a person's session. |

Roles are cluster-wide rather than per database, so migration 0001 is written to be idempotent and is run once per cluster. That was found by loading the consolidated file into a second database and watching it fail.

The account identity must be set with `set_config('app.account_id', $1, true)`, where `true` makes the setting local to the transaction. A session-level setting would let a pooled connection carry one seller's identity into another seller's request. The rule is recorded as a comment on `app_account_id()` so it sits next to the function that depends on it.

---

## 6.4 Forced row-level security

`ENABLE ROW LEVEL SECURITY` is bypassed by the table owner. Every shop-scoped table is now `FORCE`, which is thirty tables of the thirty-one.

The thirty-first is `reference_rules`, and that is correct. It holds the shared tax thresholds, allowances, rates and dates that TAX-6 requires, with their correct-as-at dates, and every seller reads the same rows. It carries no policy by design. What it did carry was write access for the application, which it should not: a rule change is a deployment made by the migrator, not something a seller's session can reach. `insert`, `update`, `delete` and `truncate` are now revoked.

The v0.1 policies are declared `for all` with a `using` clause and no `with check`. PostgreSQL applies `using` as `with check` in that case, so writing into another seller's shop was already refused. The `with check` is written out explicitly on the five highest-value tables anyway, so that a later edit to one clause cannot silently open the other.

A session with no `app.account_id` set reads nothing, because `app_account_id()` returns null and every policy compares against it. Failing closed is the intended behaviour and is tested.

---

## 6.5 The migration set

Seven files, run in order. Each one is independently runnable and each states which requirement it serves.

| File | What it does |
|---|---|
| `0001_roles_and_grants.sql` | Four roles, grants, default privileges, the `reference_rules` revoke, the transaction-local identity rule |
| `0002_append_only.sql` | Revokes and triggers on `ledger_entries`, `change_log` and `audit_log` |
| `0003_force_row_level_security.sql` | `FORCE` on thirty tables, explicit `with check` on five |
| `0004_ledger_line_attribution.sql` | Action 2. Line and SKU columns, the attribution constraint, the corrected idempotency index, backfill step one |
| `0005_stock_absorption.sql` | Action 4. `adjustment_absorbed` movement type, the absorption tolerance |
| `0006_ledger_day_week_keys.sql` | Action 5. `basis_day` and `basis_week` in Europe/London, and the mismatch view |
| `0007_daily_metrics_and_exports.sql` | Action 5. Cache basis and Return Loss columns, export basis and kind, `export_schedules`, `feed_tokens` |

`MyShopEdge_MVP_schema_v0.2.sql` is the base schema followed by all seven, and is what a new environment loads.

### Two things the live run corrected

**The stock movement column is `movement_type`, not `kind`**, and its accepted values are `sale_reserved`, `posted`, `cancelled`, `return_resellable`, `write_off` and `manual_adjustment`. The Action 4 text used plausible but wrong names. It is corrected, and `adjustment_absorbed` is added to the real list.

**STK-4 was already enforced.** A second check constraint, `stock_movements_check`, already refuses a `manual_adjustment` with a null reason. The audit listed manual adjustment with a reason as an undesigned screen, which it was, but the database rule behind it was present all along. The test harness asserts it rather than adding it.

### One thing worth knowing about the generated columns

`basis_day` and `basis_week` are stored generated columns computed with `occurred_at at time zone 'Europe/London'`. PostgreSQL requires a generation expression to be immutable, and `timezone(text, timestamptz)` is marked immutable, so the columns are accepted. The practical consequence is that a stored value is computed once at insert and is not recomputed if the timezone database is later updated. For Europe/London this is safe: historical rules are fixed, and the dates of the clock changes are set in law rather than by convention. If that ever ceased to be true, the `ledger_basis_month_mismatch` view is the pattern for detecting it.

---

## 6.6 Verification

`verify_v0.2.sql` and `verify_v0.2_as_app.sql` run seventeen tests. Every one passed against PostgreSQL 16.13. A test that prints an error where its comment says it must is passing.

| # | What it proves | Result |
|---|---|---|
| 1 | One order-level deduction posts once per line under the same TikTok reference | Two rows |
| 2 | The same record cannot post twice for the same line | Unique violation |
| 3 | `update` on the ledger is refused | Append-only error |
| 4 | `delete` on the ledger is refused | Append-only error |
| 5 | `truncate` on the ledger is refused | Append-only error |
| 6 | Only a payout may carry no order line | Check violation, constraint validates |
| 7 | Day and week keys are derived in Europe/London | All six G13 rows match |
| 8 | A month derived in UTC is reported, not moved silently | One row, June stored, July correct |
| 9 | `adjustment_absorbed` is accepted as a movement | One row |
| 10 | A manual adjustment with no reason is refused | Check violation |
| 11 | A session with no account set sees nothing | 0 rows |
| 12 | A seller sees their own rows | 9 rows, 1 shop |
| 13 | Another seller sees none of them | 0 rows |
| 14 | Another seller cannot write into this shop | RLS violation |
| 15 | The application has no update privilege on the ledger | Permission denied |
| 16 | The maintenance flag does not help the application | Permission denied |
| 17 | Reference rules are readable and not writable | true, false |

Test 7 output, which is the one worth reading in full:

```
 source_ref |     london_time     | basis_day  | basis_week
------------+---------------------+------------+------------
 G13-A      | 2026-06-11 00:30:00 | 2026-06-11 | 2026-06-08
 G13-B      | 2026-07-01 00:30:00 | 2026-07-01 | 2026-06-29
 G13-C      | 2026-12-10 23:30:00 | 2026-12-10 | 2026-12-07
 G13-D      | 2026-03-29 02:30:00 | 2026-03-29 | 2026-03-23
 G13-E      | 2026-10-25 01:30:00 | 2026-10-25 | 2026-10-19
 G13-F      | 2026-10-25 01:30:00 | 2026-10-25 | 2026-10-19
```

A and B are the cases that matter. Both are 23:30 UTC, and both land on the following day in London because British Summer Time is in force. B crosses a month end, which is where a UTC-derived key would put a July sale on a June VAT return. E and F carry the same local clock time and are an hour apart in real time, because 25 October 2026 holds the repeated hour. Both belong to the 25th, both appear once.

### Final state

```
tables 31 | forced RLS 30 | policies 30 | triggers 7
```

---

## 6.7 Test cases added to the QA document

Section 5.1 of the Functionality QA document gains the harness as a named suite, so it runs in the pipeline rather than by hand.

| ID | Test | Trace |
|---|---|---|
| TC-SEC-01 | `update`, `delete` and `truncate` on `ledger_entries` are refused as `mse_app` | LED-1 |
| TC-SEC-02 | The same three are refused by the trigger even as the owner | LED-1 |
| TC-SEC-03 | The maintenance flag set by `mse_app` does not permit an update | LED-1 |
| TC-SEC-04 | A session with no `app.account_id` reads nothing from any table | ACC-3 |
| TC-SEC-05 | One seller cannot read another seller's rows | ACC-3 |
| TC-SEC-06 | One seller cannot write into another seller's shop | ACC-3 |
| TC-SEC-07 | `app.account_id` is set transaction-local, and a new transaction on a pooled connection starts with none | ACC-3 |
| TC-SEC-08 | `mse_app` can read and cannot write `reference_rules` | TAX-6 |
| TC-SEC-09 | The consolidated schema loads into an empty database with no error | Release sign-off |
| TC-SEC-10 | The role migration runs twice against two databases in one cluster without failing | Release sign-off |

Ten cases, taking the total to 129.

---

## 6.8 Summary of what Action 6 changes

| Document | Change |
|---|---|
| Schema SQL | Reissued as `MyShopEdge_MVP_schema_v0.2.sql`, plus seven numbered migrations and two verification files. |
| Backend Orchestration and Schema | Section 4.1 gains the role model, the append-only enforcement and the forced row-level security. Section 5, Migration and change control, gains the numbered migration set and the rule that migrations run as `mse_migrator`. |
| TRD | Section 5.5, Multi-tenancy and access control, and section 5.6, Security architecture, state the four roles and the two enforcement layers rather than describing intent. |
| SRD | LED-1 and ACC-3 acceptance columns now name the enforcement rather than a role defined elsewhere. |
| Functionality QA | Ten TC-SEC cases and the harness as a named suite. |
| Cloud Hosting | Section 6, Network and security, names the four database roles and states that the application's credentials are for `mse_app` only. |
