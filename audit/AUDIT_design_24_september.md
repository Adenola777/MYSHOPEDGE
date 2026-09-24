# Design audit of the built screens, 24 September 2026

Asked for by the owner on 24 September after seeing the live site: the screens do not follow
the wireframes, the logo is not deployed, and the result reads as improvised rather than
designed. **The owner is right on all three counts.** This audit records where and why, and
proposes the order of repair. Nothing has been changed yet.

## How the audit was done

Every built shop screen was rendered from a local build at phone width, 390 by 844, fed
with the responses the service's own handlers return in `test_handlers_smoke.py`. The
figures are therefore real handler output, not invented. Each was set beside its wireframe
sheet from `design/wireframes/`. The side by side images are in this folder:

`S6_Today.png`, `S7_Stock.png`, `S9_Products.png`, `S10_Product_detail.png`,
`S11_Money.png`, `S14_Discrepancy.png`.

## Which document governs what

| Source | Governs |
|---|---|
| MSE-WFW-001, `project-source/MyShopEdge_Wireframes_and_Workflows.docx`, section 1.1 | Type, layout, navigation, voice, card grammar |
| The wireframe sheets 02 to 09 | The structure of S1 to S15 |
| A7 | Logo, colour. **Section 7.10 replaces the 1.1 colour rule** |
| A8, A15, A18, A29 | Later rulings on labels and content, which win over the wireframes |
| The master skill | UX principles only (sections 39 to 45 and 63). It holds no visual rules, and A29.11 ranks it below the rulings |

The wireframes are low fidelity by their own statement ("structure, content and behaviour,
not final visual design"). The target is therefore their structure and the written design
language, drawn with A7's colours, not a pixel copy of the sheets.

## Differences that are correct, because a later ruling made them

These are not faults and should stay.

- "You keep" became **Gross profit after returns**, and "Left after TikTok" became **Net
  proceeds** (A8). Every screen showing gross profit carries "before your own running costs
  and your tax".
- The VAT line is gone from Today, and there is no Tax tab, because VAT is out of scope
  (A29.8, ruled 24 September).
- Money shows net proceeds, reserve withheld and payout as three figures (A18.3).
- Expected payouts and Month summary and export are absent because they are blocked
  (CLAUDE.md, blocked table), not forgotten.

## Faults across every screen

These come from one place, the application shell and the stylesheet, so fixing them once
fixes every screen.

| # | Finding | Rule broken | Evidence |
|---|---|---|---|
| G1 | **The logo is not used anywhere.** The top bar draws its own small line icon and sets "MyShopEdge" in a font. The 13 brand files in `brand/` are not in the web build, and `web/public` does not exist | A7.6 "never rebuilt by setting the wordmark in a font"; A7.7 top bar uses `mse-mark-small.svg` with the two tone wordmark | `web/src/app/layout.jsx` |
| G2 | **The tagline is set as separate text, "Know Your Numbers.", with a full stop** | A7.6 "appears only as part of a supplied lockup, never set separately… carries no full stop" | `layout.jsx` |
| G3 | **No favicon, app icon or web manifest.** The browser tab shows a blank icon | A7.7 "Web app icons, favicon, splash" | no `public/`, no `icons` in metadata |
| G4 | **The palette is not A7's.** Text and headings are a warm brown grey (`#1b1714`, `#6b615a`); the interface orange is `#f2700f` and `#cf5a04` | A7.5 interface orange `#C4400C`; A7.10 navy `#111820` and `#10263D` for text and headline figures | `globals.css` `:root` |
| G5 | **The hero figure is orange on an orange panel** | A7.10 "Orange… never carries data meaning"; headline figures are navy | Today, Product detail, Money |
| G6 | **Every deduction is printed in red** | A7.10 red is reserved for "Not paid, overdue", "so that red on this product always means money that has not arrived" | Today, Money, Product detail |
| G7 | **Stock chips use the payment status colours** (red Out of stock, amber Low) | A7.10 the three status colours are for payment only | Stock, Product detail, Today |
| G8 | **The fonts are the system font, and figures are monospace** | 1.1 "Archivo for figures, Plus Jakarta Sans for text, self-hosted" | `globals.css` `--font`, `--font-num` |
| G9 | **Navigation is a row of pills at the top, and on a phone "Money" is cut off** | 1.1 "five bottom tabs"; section 7 "Larger screens… the tabs move to a left rail" | every shop screen |
| G10 | **The top bar has no "Updated" stamp and no notification bell** | 1.1 "notification bell and Updated stamp in the top bar" | every screen. Both are already served: `freshness.last_synced_at` and the notification `unread_count` |
| G11 | **Cards do not follow the card grammar.** Some have no title; many open with a paragraph of explanation instead of one line | 1.1 "Each card has a title and one line on why it matters"; master skill 39 and 63 | Stock, Products, Today |
| G12 | **Internal codes reach the seller.** `adjustment_amount`, `PLATFORM_PENALTY`, "-5.00" unformatted, and `LOGISTICS_REIMBURSEMENT` as a Money line | A18.5 "a seller reading `reserve_withheld`… has hit a hole in the product"; A8 labels | Discrepancies, Money |

## Faults screen by screen

| Screen | What the wireframe has that the build lacks | Front end only, or needs the contract |
|---|---|---|
| **S6 Today** (`S6_Today.png`) | Shop name under the title; one line under the hero ("From £X of sales across N orders"); Sold and Kept this month as two small cards side by side, not two full width cards; Shop Money as one short card of three rows, where the build shows six rows and a paragraph | Layout is front end. **The hero line needs a contract field**: TodayView carries no day's sales or order count |
| **S7 Stock** (`S7_Stock.png`) | Three cards: Units in hand (on the shelf, sold not posted, coming back, written off), What runs out first, Coming back. The build has filter pills and one flat list under a paragraph | **Needs the contract.** `getStock` serves item rows only, not the four unit totals, and summing them in the browser would break A29.1 |
| **S9 Products** (`S9_Products.png`) | The measure switch (Money kept, Units, Returns); a pence in the pound bar on every row with a legend; uncosted products below the ranked ones with "Add cost" | The switch is front end, because `listProducts` already takes `measure`. **The bars need the contract**: the per product split is a financial rule and belongs in Python |
| **S10 Product detail** (`S10_Product_detail.png`) | One segmented bar with a legend; a Returns card; an "Edit product cost" button. The build adds an allocation notice and repeats Gross sales in two cards | The bar needs the same contract field as S9. The Returns card needs a product return rate, which the contract does not carry. "Worth a look" is not served, which the file already records |
| **S11 Money** (`S11_Money.png`) | A period switch (Today, This month, Tax year) above the basis switch; one compact card. The build repeats the hero at the bottom, and its "Held and paid out" subtotal of -£463.88 has no meaning a seller can use | The switch and layout are front end. The subtotal should go |
| **S14 Discrepancy** (`S14_Discrepancy.png`) | A title naming the problem, the order reference, three labelled rows, an Effect card, three full width actions | Front end. The raw codes in G12 must go |
| **S1 Connect** | Close to the wireframe. It inherits G1 to G11 | Front end |
| **S17 Start** | A7.7 specifies `mse-logo-horizontal.svg` on this screen; it shows the rebuilt wordmark. The privacy and terms links are missing because neither page exists | Front end, plus two pages to write |
| **S13 Notifications** | Not built, although `listNotifications` is served. The bell in G10 has nowhere to go without it | Front end |
| S21, S22, S25, S26, S33, S34 | Not wireframed. They inherit G1 to G12 and should be redrawn with the same shell and card grammar | Front end |

## Proposed repair, in order

**Phase 1. The shell and the design system.** One PR, front end only.
Self-hosted Archivo and Plus Jakarta Sans; A7's palette as tokens; the logo lockups, favicon,
icons and manifest from `brand/`; a top bar with the brand mark, the Updated stamp and the
bell; five bottom tabs on a phone and a left rail on wide screens, with Tax left out until it
exists; one card component that enforces a title and one line; money in Archivo with
tabular figures, deductions in navy with a minus sign, not red. This fixes G1 to G11 on every
screen at once.

**Phase 2. The screens, one at a time, to the wireframe.** S6, S7, S9, S10, S11, S14, then
S1, S17 and S13. Each PR carries its side by side image, so each screen is signed off by eye
before it merges.

**Phase 3. The contract additions the wireframes need.** Stock unit totals, the Today hero
line, and the per product pence in the pound split. A29.2 requires the contract to change
before the code, so each is its own ruling, then its own PR.

**How every screen will be checked from now on.** Before a PR is opened, the screen is
rendered at phone and desktop width with real handler data and placed beside its
wireframe, and the image goes in the PR. A screen without that image is not ready.

## Why this happened

The screens were built to the contract and the rulings, and checked for correct figures and
states, but never compared with the wireframe sheets or A7 while they were built. The design
language in MSE-WFW-001 was not read until this audit. That is the gap the check above
closes.
