# Action 16. The six price sheet rows, settled

Decided 22 September 2026. These six rows sat on the commercial price sheet with nothing
behind them. Four are now out of the MVP, one is built at a larger figure than planned, and
one becomes real work.

## 16.1 The rulings

| Row | Ruling |
|---|---|
| Expense tracking | Out |
| Multiple stores and channels | Out |
| Historical data, tiered at 3, 12 and 24 months | Twenty-four months, not tiered |
| Profit and loss reporting | Out of the MVP |
| Order limits as an enforced quota | Build it |
| Advanced analytics | Out of the MVP |

The four that are out are no longer pending decisions, so they move from `PENDING_SCOPE`
to `OUT_OF_MVP` in `service/app/plans.py`. The old name is kept as an alias so nothing that
imports it breaks.

## 16.2 History is twenty-four months on every plan

`history_months` is 24 on Starter, Growth and Pro. It is not tiered, which is consistent
with the instruction that Starter is not to be crippled.

Four things follow, and the last one is not within our gift.

**The first sync doubles.** S2 already warns that the sync is slow because TikTok limits
how fast we can read. Twice the months means roughly twice the calls and twice the wait.
The screen says "Loading twelve months" and has to be changed.

**MON-5 now applies to twenty-four months.** Every loaded month must open and reconcile.
That doubles the surface the reconciliation has to be correct across, and it doubles what
the acceptance run has to prove.

**The test data covers twelve months.** A12 generated a year. It has to be extended before
the twenty-four month claim can be tested at all.

**TikTok may not offer twenty-four months.** A11 records no history limit because none was
established. Whether the finance endpoints expose two years of statements, or cap at one,
is unverified and cannot be verified without an authorised shop. If TikTok caps below
twenty-four months then this ruling cannot be delivered however firmly it is made, and the
plan copy would have to say what is actually available. This is the same blocker as
everything else waiting on the shop authorisation.

Until that is known, twenty-four months is the intent and the code carries it, and it is
not advertised on a screen a seller can read.

## 16.3 The order limit becomes a control

Counting orders in a billing period is straightforward work. The part that is not settled
is what happens when a seller passes the limit, and until that is settled the quota cannot
be built, because a counter with no consequence attached is not enforcement.

There are two honest answers and they are very different products.

**Soft.** The count is shown, the seller is warned as they approach the limit, and they are
offered the larger plan. Nothing stops. Their figures keep updating and keep reconciling.

**Hard.** The sync stops at the limit, or the figures stop updating, until the seller moves
up a plan.

The recommendation is soft, for the reason already written into A14 section 14.4 about a
failed payment. A bookkeeping product that stops showing a seller their own records is
holding their accounts hostage, and doing it over a volume threshold is worse than doing it
over an unpaid invoice, because the seller has done nothing wrong. They have sold more.

Soft enforcement also earns its money. A seller who can see they are at 480 orders of 500
has a reason to upgrade that does not involve being locked out.

This is not ruled yet. Nothing is built until it is.

## 16.4 What this changes

| Where | Change |
|---|---|
| `service/app/plans.py` | `history_months` 12 becomes 24 on all three plans. `PENDING_SCOPE` becomes `OUT_OF_MVP` with four rows. `IN_SCOPE_NOT_BUILT` carries the quota |
| S2 First sync | "Loading twelve months" becomes twenty-four. Not yet applied, the Figma quota is spent |
| A12 test data | The generator covers twelve months and has to be extended |
| Acceptance run | MON-5 has to pass across twenty-four months rather than twelve |
| The quota | Not buildable until 16.3 is ruled |
