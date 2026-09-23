# Action 19. The first live TikTok calls, and what they settled

23 September 2026. Until today every claim this project made about the TikTok API rested on
a document or on a generated fixture. Three calls were made against a real authorised shop
through the Partner Center API Testing Tool. This records what they proved, what they did
not prove, and one thing they proved that nobody had asked about.

## 19.1 The connection works

Three endpoints answered `code: 0`.

| Call | Result |
|---|---|
| `GET /finance/202309/payments` | `{"payments": []}` |
| `GET /finance/202309/statements`, `statement_time_ge` two years back | `{"statements": []}` |
| `GET /authorization/202309/shops` | One shop returned |

The app key, the access token, the authorisation and the request shape all work. That had
never been demonstrated before today. Every earlier claim about this API came from reading.

## 19.2 The authorised shop is not a UK shop

`GET /authorization/202309/shops` returned one shop:

| Field | Value |
|---|---|
| name | `TestCase idl2l rjEUT 60285` |
| region | `ID` |
| seller_type | `LOCAL` |
| id | `7495568017912465932` |

The name is a generated test-case string and `idl2l` reads as Indonesia local to local. The
cipher is deliberately not recorded here, for the same reason no secret is written into this
repository.

This is the finding of the day, and it has two consequences.

**It explains both empty arrays.** A shop with no trading history has no payments and no
statements. Neither empty result is evidence about anything else.

**It means the sandbox proves shapes and not money.** MyShopEdge is a UK product. Prices are
GBP, `basis_day` is Europe/London by A11.1, the VAT threshold tracking is HMRC's, and A15.6
set the plan prices exclusive of UK VAT. An Indonesian shop settles in IDR and carries
Indonesian fee and tax structures. TikTok's own notice of 22 September makes the same point
from the other direction: the growth package fee fields apply to US, JP, EU and UK, and the
tax fields to US only. Fields vary by region.

So a test that passes against this shop says the request and response shapes are right. It
says nothing about whether the arithmetic is right for a British seller.

## 19.3 A16.2 is still unverified, and this route cannot verify it

A16.2 promises twenty four months of history on every plan. The statements call used
`statement_time_ge = 1727049600`, which is midnight UTC on 23 September 2024, exactly two
years back, with the upper bound left empty so it defaults to now.

It returned nothing. That is not evidence that TikTok retains less than twenty four months,
because a shop created recently has no history to return regardless of the retention limit.

`RUNBOOK_tiktok_connection.md` states that connecting a shop settles this question. That is
wrong for a shop with no trading history, and the runbook is corrected accordingly. The
question can only be answered by a shop that has been trading for more than two years.

## 19.4 Facts about the API that the pack did not have

Read from the OpenAPI specification that ships with the `tts-openapi-guide` skill, not
inferred.

**`sort_field` is required on every finance endpoint.** It is optional on order search and
on returns search. A finance call without it fails.

| Endpoint | `sort_field` accepts |
|---|---|
| `/finance/202309/statements` | `statement_time` only |
| `/finance/202501/statements/{id}/statement_transactions` | `order_create_time` only |
| `/finance/202309/payments` | `create_time` only |
| `/finance/202507/orders/unsettled` | `order_create_time` only |
| `/order/202309/orders/search` | `create_time` or `update_time` |
| `/return_refund/202309/returns/search` | `create_time` or `update_time` |

**`sort_field` is typed as a plain string in all 29 paths that take it. Not one declares an
enum.** So a misspelling is not rejected. TikTok's own wording on the affiliate endpoint is
explicit about what happens instead: "If sort_field is empty or invalid, PRODUCT_ID will be
set as default." A typo returns correctly formed data in an order nobody asked for, with a
200 and no error. On a paginated finance call that is a silent correctness fault.

**The default `sort_order` is not consistent across the API.** Finance defaults to ASC on
all four endpoints. Order search defaults to DESC. Returns search defaults to ASC.
Fulfillment package search defaults to DESC. Code that omits the parameter will page orders
newest first and statements oldest first in the same run.

The consequence for the client we have not written yet: set both parameters explicitly on
every call, and have the signed request helper refuse a `sort_field` that is not on the
allowed list for that path, because TikTok will not refuse it.

**Statements are generated daily at 00:00 UTC.** Stated in the `statement_time_ge`
description. Our `basis_day` is Europe/London, so through British Summer Time the statement
boundary falls at 01:00 local. The test data covers July and August 2026 only, so nothing
has ever exercised that boundary, and A12 should carry a case that does.

**An empty time filter has undefined behaviour.** The specification defines a default only
for the case where one bound is given and the other is empty. With both empty it says
nothing. So a call with no time filter returns an unstated window, and every call this
project makes should set the lower bound explicitly.

## 19.5 A defect in the ingest, found while checking the new fee fields

TikTok's notice of 22 September adds eight properties under `fee_tax_breakdown`, four fees
and four taxes. Checking whether `testdata/ingest.py` tolerates them found that the two
loops do not behave the same way.

The fee loop at line 189 iterates every key, and anything absent from `FEE_MAP` becomes
`unmapped_fee`, keeps TikTok's field name, and is recorded in an `UNMAPPED` set.

The tax loop at line 194 reads `if TAX_MAP.get(field) and pence(amt)`, and `TAX_MAP` holds
one entry, `{"local_vat_amount": None}`. Every field not in that map fails the condition and
is discarded without being recorded anywhere.

Today that loses no money, because the four new tax fields return `"0"` in the UK where the
tax is netted into the fee. The exposure is if TikTok ever populates them for UK sellers.
Money would leave the ledger silently with nothing to find it by.

The fix is to make the tax loop record unknown fields exactly as the fee loop does. It is
not a judgement call and it changes no figure today. It is not yet applied.

## 19.6 What is open after today

| Question | State |
|---|---|
| Whether TikTok exposes twenty four months of statements | Open. Needs a shop trading for over two years. The sandbox cannot answer it |
| What a settlement export calls its columns | Open. A8 section 3.5. May be answerable from a shop with settlements, in the shop's own region |
| Whether the invoice number is reachable | Open |
| Whether a GB sandbox shop can be created | **Settled 23 September. It can.** See 19.7 for what that does and does not give us |
| Where the four growth package fees belong | Open. A product judgement. Left alone they land in `unmapped_fee`, so the arithmetic is right and only the label differs |
| Whether to fix the tax loop | **Deferred 23 September by decision.** Not forgotten and not disputed. It changes no figure today because the four new tax fields return `"0"` in the UK. It becomes urgent the day TikTok populates them |

## 19.7 A GB sandbox shop can be created, and what that is worth

Confirmed 23 September 2026. This removes the region problem in 19.2. A GB sandbox shop
settles in GBP and carries the UK fee structure, so tests against it exercise the same
arithmetic a British seller will meet rather than an Indonesian one.

`testdata/sandbox_probe.sh` already defaults to `REGION=GB`, so it runs against such a shop
as written.

**What a GB sandbox shop gives.** Orders, order status transitions, returns through the
reverse flow, and webhook delivery, all in GBP with UK fee fields. That covers the order and
return half of A11 properly, replacing fixtures that only prove the code agrees with the
assumptions that generated them.

**What it does not give, and this should not be discovered later by someone trusting a green
test.** Nothing in the sandbox catalogue creates a settlement. The 42 sandbox endpoints
cover the order lifecycle and stop there. So a GB sandbox shop will produce orders and
returns and no statements, which means:

- the settlement ingestion stays proved against generated fixtures only
- A8 section 3.5, the literal column labels on a settlement export, stays open
- A16.2, twenty four months of history, stays open and is unanswerable here for the reason
  in 19.3

Two of the three questions this project has been carrying since the terminology standard
was written are finance questions, and the sandbox reaches neither.

**One thing worth testing there that nobody has asked for.** Statements are generated daily
at 00:00 UTC and `basis_day` is Europe/London. A GB sandbox shop is the only place the
British Summer Time boundary can be exercised before a real seller meets it, and the test
data covering July and August 2026 has never touched it.
