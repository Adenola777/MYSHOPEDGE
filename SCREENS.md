# The screen register

Written 24 September 2026. **This file is the one the repository relies on for screens.**
Where it disagrees with a count written anywhere else, this file is right, because every
line in it was checked against a source rather than carried forward.

Five things were checked, and each is named against the line it produced:

- The ruling documents `A3`, `A14`, `A15` and `A18`, read for the screen tables and headings.
- `MyShopEdge_Wireframes_and_Workflows.docx`, document MSE-WFW-001 v0.1 dated 20 September,
  whose fifteen screens were extracted as images and three of them opened and read.
- `web/src/app`, listed for what is actually built.
- `design/figma_pending_changeset.js`, read for what the Figma file holds.
- The desktop folder `MYSHOPEDGE`, whose `Dashboard 1` to `6` files were compared image by
  image against the wireframe sheets.

## The counts, corrected

| | Count | Note |
|---|---|---|
| Screen ids defined by a ruling | **38** | S1 to S38 |
| Cut by a later ruling | **2** | S18 and S19, both cut by A15 |
| **Live screens** | **36** | This is the number that matters |
| Wireframed | 15 | S1 to S15 only |
| Built in code | 13 | S6, S7, S9, S10, S11, S14, S17, S21, S22, S25, S26, S33, S34. Requests carry the signed in seller's token since 24 September. None has run against a real API yet, because nobody has signed in on the live site |

**`CLAUDE.md` and `README_v0.2.md` both said "39 screens". That number is wrong twice.**
No ruling defines an S39. The only place S39 appears in the whole repository is
`design/figma_pending_changeset.js`, which is a script rather than a ruling. And the figure
of 39 counts S18 and S19, which A15 cut on 22 September. Both files are corrected.

**"18 screens drawn in Figma" cannot be confirmed or denied.** The Figma account is on the
Starter plan and its tool call limit refuses every read of file `Lv1sLPt9MeE27TeKGy4hOT`.
It refused on 22 September and again on 24 September, so it is a paid gate and not a daily
allowance. What is certain is that the file contains frames, because the pending change set
addresses live node ids for S3, S6, S18, S19 and S39, and that none of those changes were
applied. **Whatever is in Figma predates A15.** Treat it as out of date rather than as a
reference.

## Every screen

`Sheet` is the wireframe sheet in `design/wireframes/`. Each sheet carries two screens side
by side, except the last, which carries S15 alone.

| ID | Screen | Area | Ruled by | Sheet | Built |
|---|---|---|---|---|---|
| S1 | Connect TikTok Shop | Onboarding | Wireframes | 02 | |
| S2 | First sync | Onboarding | Wireframes | 02 | |
| S3 | Product costs choice | Onboarding | Wireframes, amended A15.4 | 03 | |
| S4 | Upload mapping | Onboarding | Wireframes | 03 | |
| S5 | Tax profile | Onboarding | Wireframes | 04 | |
| S6 | Today | Core | Wireframes, amended A15.5 | 04 | `shops/[shopId]/today` |
| S7 | Stock | Core | Wireframes | 05 | `shops/[shopId]/stock` |
| S8 | Return check | Core | Wireframes | 05 | |
| S9 | Products | Core | Wireframes, revised A18 | 06 | `shops/[shopId]/products` |
| S10 | Product detail | Core | Wireframes, revised A18 | 06 | `shops/[shopId]/products/[productId]` |
| S11 | Money | Core | Wireframes, revised A18 | 07 | `shops/[shopId]/money` |
| S12 | Tax | Core | Wireframes | 07 | |
| S13 | Notifications | Core | Wireframes | 08 | |
| S14 | Discrepancy detail | Core | Wireframes, revised A18 | 08 | `shops/[shopId]/discrepancies`, as a list |
| S15 | Settings and data | Settings | Wireframes | 09 | |
| S16 | Product transactions | Products | A3 | | |
| S17 | Start | Account | A3 as Sign up, renamed A14 | | `start`, handing off to Stack's pages at `handler/[...stack]`. No privacy or terms link yet, because neither page exists |
| ~~S18~~ | ~~Return~~ | | **Cut by A15.3** | | |
| ~~S19~~ | ~~Sign in~~ | | **Cut by A15.2** | | |
| S20 | Manual cost entry | Onboarding | A3 | | |
| S21 | Add or edit a product cost | Products | A3 | | Inline on each variant of `shops/[shopId]/products/[productId]` |
| S22 | Records behind a figure | Money | A3, revised A18 | | `shops/[shopId]/records` |
| S23 | Export | Money | A3, revised A18 | | |
| S24 | Other-channel sales | Money | A3 | | |
| S25 | Stock adjustment | Stock | A3, revised A18 | | At the top of `shops/[shopId]/stock/[skuId]` |
| S26 | Stock movement history | Stock | A3, revised A18 | | `shops/[shopId]/stock/[skuId]` |
| S27 | Alert settings | Settings | A3 | | |
| S28 | Connection problem | Onboarding | A3 | | |
| S29 | Disconnect | Settings | A3 | | |
| S30 | Delete my account | Settings | A3 | | |
| S31 | Download my data | Settings | A3 | | |
| S32 | Glossary | Reference | A3 | | |
| S33 | Plan and card | Onboarding | A14 | | `(onboarding)/billing` |
| S34 | Payment confirmed | Onboarding | A14 | | `(onboarding)/billing/confirmed` |
| S35 | Continue setting up | Account | A14 | | |
| S36 | That email is already in use | Account | A14 | | |
| S37 | Signed out | Account | A14 | | |
| S38 | Payment did not go through | Onboarding | A14 | | |

## Where the artwork lives, and what it is worth

`design/wireframes/` holds the fifteen screens as eight PNG sheets and six workflow diagrams,
extracted from the Word document and committed here so that the repository no longer depends
on a file sitting in somebody's chat history or on one desktop.

**They are low fidelity.** The document says so in its own words: they "show structure,
content and behaviour, not final visual design". They are a specification of what is on each
screen, not a specification of how it looks. The visual system is `web/src/app/globals.css`.

**Three of them are known to be out of date.** Each is a later ruling the drawing predates:

| Sheet | Screen | What changed |
|---|---|---|
| 02 | S2 | Shows "Orders, last 12 months". History is twenty four months on every plan |
| 03 | S3 | A15.4 cuts the three cards and keeps the buttons |
| 04 | S6 | A15.5 keeps the congratulation and adds a celebration |

**S16 to S38 have no drawing of any kind.** Twenty one live screens, specified in prose and
never drawn. They are built from their rulings.

## Duplicates that are not extra designs

The desktop folder holds `Dashboard 1.png` through `Dashboard 6.gif`, and five `_5x3`
variants. Compared image by image against the extracted sheets, `Dashboard 1` to `6` are
re-exports of sheets 02 to 07, which is S1 through S12. Perceptual distance was 0 for four
of them and under 5 for the two that were recompressed to JPEG and GIF.

They are the same fifteen screens in a different container. Nothing in that folder is a
design the repository does not already have.

## What this means for building

The written specification is the reference and Figma is not, for as long as the plan limit
stands. That is not a loss worth paying to fix. A low-fidelity wireframe that predates three
rulings would be the weaker reference even if it could be read.

So a screen is built from its ruling, checked against its sheet where one exists, and
checked against the sheet's known staleness above where it applies.

## The seven screens built on 24 September, and what each still lacks

Each was built on a served endpoint, rendered at phone width against the real handlers'
responses to canned rows, and checked in a browser. None has yet run against a real API
with a signed in seller, because the service has no host. What each file leaves out is
written at the top of the file, and summarised here.

| Screen | What is missing | Waiting on |
|---|---|---|
| S6 Today | The VAT line, and the congratulation A15.5 keeps | A29.8 puts VAT out of scope. Nothing tells the screen that onboarding has just finished |
| S7 Stock | The units in hand totals, and the order by what runs out first | `getStock` serves no totals and pages by variant |
| S10 Product detail | The insight, the return rate | No insight source, no return rate in the contract |
| S11 Money | The period switch, expected payouts by week, the export | The contract cannot name a period. Expected payouts need TikTok's unsettled orders. The export needs a file store the service can write to |
| S14 Discrepancy detail | A page for one discrepancy | No endpoint for one discrepancy. The three actions were added on 24 September, and "Correct my record" appears only where the service serves `correctable` |
| S22 Records | The discrepancy marker on affected rows | A ledger entry does not say which discrepancy touches it |
| S26 Movements | The resulting count on each row, the opening balance, links to orders and returns | `getStockMovements` serves no balance. No order or return screen exists |

