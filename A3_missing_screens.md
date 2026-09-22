# Action 3: The missing screens and flows

Closes audit question 3. Seventeen screens are specified below, S16 to S32. S16 was defined in Action 2 and is repeated here only in the screen map. Every screen follows the design language in section 1.1 and the content rules in section 8 of the Wireframes and Workflows document.

---

## 3.1 Revised screen map

Added to section 2 of the Wireframes and Workflows document.

| ID | Screen | Area | Purpose | Wireframe |
|---|---|---|---|---|
| S16 | Product transactions | Products | Every order line behind a product figure | Fig 12 |
| S17 | Sign up | Account | Create the account before any TikTok connection | Fig 9 |
| S18 | Verify email | Account | Confirm the address and unblock the connection | Fig 9 |
| S19 | Sign in | Account | Return to the account, reset a password, complete a second factor | Fig 10 |
| S20 | Manual cost entry | Onboarding | Type costs for products without a file | Fig 11 |
| S21 | Add or edit a product cost | Products | Change one SKU's cost, packing and postage | Fig 11 |
| S22 | Records behind a figure | Money | The records that add up to any figure | Fig 12 |
| S23 | Export | Money | Choose period and format, watch progress, download | Fig 13 |
| S24 | Other-channel sales | Money | Enter a monthly total from outside TikTok | Fig 13 |
| S25 | Stock adjustment | Stock | Change a count with a reason | Fig 14 |
| S26 | Stock movement history | Stock | Every movement for one SKU | Fig 14 |
| S27 | Alert settings | Settings | Change the thresholds that raise notices | Fig 15 |
| S28 | Connection problem | Onboarding | Reconnect, consent denied, region not supported | Fig 10 |
| S29 | Disconnect | Settings | Confirm, then live in the disconnected state | Fig 15 |
| S30 | Delete my account | Settings | Export prompt, confirmation, progress, completion | Fig 16 |
| S31 | Download my data | Settings | Request the file and collect it | Fig 16 |
| S32 | Glossary | Reference | One definition for every term the product uses | Fig 17 |

---

## 3.2 Account screens

### S17 Sign up

**Purpose.** Create the account. This is step 1 of the end-to-end workflow and the screen ACC-1 depends on.

**Reached from.** The marketing site, and the "Create an account" link on S19.

**Content.** The logo and the tagline sit above the form. The form holds email, password and an optional shop name. A single line states what happens next: "We send you a link. You connect TikTok Shop after that." Password rules are shown before the seller types rather than after a rejection.

**Controls.** Email field, password field with a show control, "Create account" as the primary action, a link to sign in, and links to the privacy notice and terms. The privacy notice link is required by section 11 of the Data Protection Document.

**Rules.** No TikTok connection is offered until the address is verified, which is what ACC-1 requires. The password field accepts a pasted value from a password manager. The form does not ask for a business name, a VAT number or an address, because the tax profile at S5 is optional and later.

**States.** Address already registered shows "That address already has an account" with a sign-in link and no statement of whether the account exists, which avoids account enumeration. A weak password is refused with the rule that failed named in full.

**Trace.** ACC-1, Data Protection section 11.

### S18 Verify email

**Purpose.** Confirm the address, then release the TikTok connection.

**Reached from.** S17, and the verification link in the email.

**Content.** "Check your inbox" with the address shown, a resend control with a countdown, and a line saying the link lasts 24 hours. On return from the link the screen confirms verification and moves the seller to S1.

**States.** Expired link offers a fresh one. Already verified moves straight on rather than showing an error. Resend is rate limited and says so in words rather than failing silently.

**Trace.** ACC-1.

### S19 Sign in

**Purpose.** Return to the account. The screen also carries password reset and the optional second factor, because ACC-2 treats them as one journey.

**Content.** Email and password, "Stay signed in", the primary action, and a "Forgotten your password" link. Where the identity provider hosts these pages rather than MyShopEdge, section 5 of the API Integration document names the provider and this screen documents the hosted equivalent. The decision is recorded in the open decisions list rather than left unstated, which is what the audit asked for.

**Password reset.** Request screen taking the address, a confirmation that says a link was sent whether or not the address exists, then a new-password screen. All sessions end when the password changes, as section 5 of the API Integration document requires.

**Second factor.** Optional. A six-digit code field, a "Use a recovery code" link, and a statement of where the code comes from. Turning the second factor on lives in Settings, not here.

**States.** Wrong password names no specific cause. Repeated failures slow the form and say so. A locked account offers reset rather than support contact.

**Trace.** ACC-2.

---

## 3.3 Cost screens

### S20 Manual cost entry

**Purpose.** Type costs where the seller has no file. S3 offers "I will type them in" and this is the screen that offer leads to.

**Reached from.** S3, and from Settings at any later time.

**Content.** A list of the seller's SKUs, each row showing the SKU code, the product name, the units sold in the last 30 days, and three fields: product cost, packing cost, postage cost. Rows are ordered by units sold, so the products that matter most are typed first. A running coverage line at the top reads "12 of 40 products, 61% of gross sales" and updates as the seller types.

**Controls.** Save as the primary action, "Do this later" as a secondary action, and a filter that narrows the list to products without a cost.

**Rules.** Costs are validated as CST-4 requires: numeric, not negative, in pounds. A zero cost is accepted only after an explicit confirmation on that row. Packing and postage are optional, which is what CST-5 says. Nothing is applied until the seller saves, and saving applies only the rows that hold a valid value.

**States.** Empty shop shows the first sync notice rather than an empty table. A saved row shows a quiet confirmation and the coverage line moves.

**Trace.** CST-1, CST-4, CST-5, CST-6.

### S21 Add or edit a product cost

**Purpose.** Change one SKU. The buttons on S9 and S10 lead here.

**Content.** The product name and image, the SKU code, the current cost with the date it was set, and the three fields. A short line states the effect: "Changing this cost changes Contribution from today. Figures already shown for past months do not move."

**Rules.** A cost change is recorded with its date, so a month already reported keeps the cost that applied then. The change appears in the change log required by LED-7. Where the product holds several SKUs, each SKU carries its own cost and the screen says so.

**States.** No cost yet shows "Not provided" and the prompt from CST-7. A cost that makes Contribution negative saves and shows the negative figure in full, as CST-8 requires.

**Trace.** CST-1, CST-4, CST-5, CST-8, LED-7.

---

## 3.4 Money screens

### S22 Records behind a figure

**Purpose.** Show the records that add up to any figure. This is the screen DSH-8 requires and the one the audit found closest to the grid.

**Reached from.** Any figure on any screen. The figure is tappable and carries a quiet affordance.

**Content.** A header naming the figure, its period, its basis and its confidence chip. Below that, one row per record: date, what it was, the TikTok reference, and the amount. A totals row equals the figure. Where every record belongs to one product, a link offers the fuller S16 grid.

**Rules.** The totals row equals the figure to the penny, which is the acceptance rule in DSH-8. Records carry the TikTok identifier so the seller can find the same record inside TikTok. Records that a discrepancy affects carry a marker and the TikTok value in use, as DSC-2 and DSC-5 require.

**States.** A figure built from no records shows why, rather than an empty list. A figure that is estimated rather than confirmed says which records are still expected.

**Trace.** DSH-8, DSC-5.

### S23 Export

**Purpose.** Produce the Excel or CSV file. S11 and S15 currently hold buttons with no screen behind them.

**Reached from.** "Month summary and export" on S11, "Export for accountant" on S15, and the export control on S16.

**Content, step 1.** Choose what to export: ledger, month summary, or the accountant pack. Choose the period: this month, last month, tax year to date, or a custom range using the start and end dates the exports table already stores. Choose the basis: sales or cash. Choose the format: Excel or CSV. A preview line states what the file will contain and confirms that totals will equal the screen.

**Content, step 2.** Progress. The file builds in the background, so the screen says the seller can leave and will be told when it is ready.

**Content, step 3.** Download. The file, its size, the time it was built, and a plain statement that the link expires after seven days and the file can be rebuilt at no cost after that.

**Rules.** Totals in the file equal the totals on screen, which is the acceptance rule in MON-2. Net Sales is relabelled Net Proceeds, or footnoted where the seller's own layout uses the old label. The header of every file carries the logo, the shop name, the period, the basis and the as-at time.

**States.** A build that fails offers a retry and says what failed. An expired file shows the expiry plainly and offers a rebuild rather than an error.

**Trace.** MON-2, LED-6.

### S24 Other-channel sales

**Purpose.** Enter a monthly sales total from outside TikTok. S6 refers to this and MON-3 requires it.

**Content.** One row per month for the current tax year, each holding a single amount. A line above the list states the rule in the seller's terms: "These totals feed the VAT line and the tax estimate only. They never appear in your TikTok figures."

**Rules.** Entered totals reach the VAT monitor and the set-aside estimate and nothing else, which is the acceptance rule in MON-3. Each entry is dated and can be changed, and a change is recorded. The figures carry the Estimated chip, because they are the seller's own numbers rather than TikTok's.

**Trace.** MON-3, TAX-2, TAX-3.

---

## 3.5 Stock screens

### S25 Stock adjustment

**Purpose.** Change a count by hand with a reason, which STK-4 requires.

**Reached from.** A SKU row on S7, and from S26.

**Content.** The SKU, the current On the shelf figure, TikTok's own figure and the current adjustment, a new count field, and a reason chosen from a short list: stock count, damage found, sample sent, returned to supplier, other. A free-text note is required when the reason is other.

**Rules.** An adjustment without a reason is rejected, which is the acceptance rule in STK-4. The screen states the effect before saving: "On the shelf becomes 34. TikTok still shows 31. We keep the difference as your adjustment." This is where the double-count rule in Action 4 surfaces to the seller.

**States.** A SKU with no TikTok figure yet shows the first sync notice rather than a zero.

**Trace.** STK-4, STK-7.

### S26 Stock movement history

**Purpose.** Every movement for one SKU, which STK-4 requires and the movements endpoint already serves.

**Content.** One row per movement: date, movement type, units in or out, the resulting count, the order or return reference, and the reason where one was given. Movement types are the ones in section 3.1 of the Backend Orchestration document, named in plain English rather than by their internal codes.

**Rules.** Every row links to its order or return. The opening balance is stated, so the rows add up to the current count on screen and the seller can check the arithmetic.

**Trace.** STK-4, STK-1.

### S27 Alert settings

**Purpose.** Change the thresholds. S15 shows "Low stock alert: 14 days" with nothing behind it.

**Content.** Low stock threshold in days, with 14 as the default. Return unchecked threshold in days, with 7 as the default. A toggle for email on critical notices, which NTF-2 allows the seller to turn off. Each control states what it does in one line.

**Rules.** A change takes effect on the next evaluation and does not re-raise notices already resolved, which holds the "appears once" rule in STK-3. Critical connection notices are listed as the messages the seller cannot turn off, so the toggle's limits are stated rather than discovered.

**Trace.** STK-3, NTF-1, NTF-2.

---

## 3.6 Connection and closure screens

### S28 Connection problem

**Purpose.** Three connection failures that CON-2 and CON-4 describe in words with no design behind them.

**Reconnect.** The connection has lapsed or been revoked. The screen states what still works, which is every figure already held, and what has stopped, which is new data. A single primary action reconnects. No data is lost, and the screen says so.

**Consent denied.** The seller declined on TikTok's page. The screen explains what was being asked for, repeats that access is read-only, and offers a second attempt. It does not imply the seller made a mistake.

**Region not supported.** The shop sits outside the supported region. The screen names the supported regions, states that the account remains and costs nothing, and offers to tell the seller when the region is added.

**Rules.** Each variant states the position of the seller's data plainly. None of them lose the account. The stale banner from section 6 of the Wireframes document continues to show on the other screens while any of these states is live.

**Trace.** CON-2, CON-4.

### S29 Disconnect

**Purpose.** Confirm the disconnection, then live in the disconnected state. Section 6 of the Data Protection Document promises 90 days of kept data and no screen shows it.

**Confirmation.** What stops, which is new data. What stays, which is every figure already built. How long it stays, which is 90 days. What happens at the end of 90 days, which is deletion. Three actions are offered before the seller confirms: download the data, delete the account instead, or cancel.

**Disconnected state.** A persistent banner on every screen states the disconnection date and the deletion date as a real date rather than a countdown. Figures remain readable. Exports remain available, because the seller is most likely to need them at exactly this moment. A single action reconnects, and reconnection restores syncing without a fresh sign-up.

**Rules.** The 90-day period comes from section 6 of the Data Protection Document and is shown as a date. Deletion at the end of it is automatic and the seller is told before it happens.

**Trace.** CON-3, Data Protection section 6.

### S30 Delete my account

**Purpose.** Close the account. ACC-4 requires it, deletion may take up to 30 days, and no screen exists.

**Step 1, export prompt.** "Take your data first." The screen offers the download and does not treat skipping it as the easy path.

**Step 2, confirmation.** What is deleted, which is every figure, cost, ledger entry and export. What is kept and why, which is the small set of records law requires, named with their retention period from section 6 of the Data Protection Document. The seller types the word delete to confirm, and confirms with the account password.

**Step 3, in progress.** Deletion begins at once and completes within 30 days. The screen states the date by which it completes. The account is signed out and cannot be used further. A single cancellation window is offered, and its length is stated.

**Step 4, completed.** An email confirms deletion with the date it completed. This is the record the seller keeps.

**Rules.** The TikTok connection is revoked as part of deletion rather than left for the seller. The 30-day figure and the retained records come from the Data Protection Document and are not restated differently here.

**Trace.** ACC-4, Data Protection sections 6 and 7.

### S31 Download my data

**Purpose.** Portability, which ACC-4 requires in CSV and JSON.

**Content.** What the file holds, listed by kind: account, shops, orders, ledger, costs, stock, returns, exports, notifications. The format choice, CSV or JSON. A statement that the file contains no buyer names or addresses, because section 3 of the Data Protection Document says the product never collects them.

**Progress and collection.** The same background build and signed link as S23, with the same seven-day expiry stated in the same words. The screen reuses the export flow rather than defining a second one.

**Trace.** ACC-4, Data Protection section 7.

---

## 3.7 Reference

### S32 Glossary

**Purpose.** One definition for every term. The PRD lists this in the Clarity scope and no screen carries it.

**Content.** Terms in alphabetical order, each with a one-sentence definition in the product's own voice, and where relevant the formula behind it. The initial set covers: Awaiting Settlement, Coming back, Confirmed, Contribution, Cost coverage, Days left, Deduction Rate, Estimated, Gone this month, Gross Sales, Incomplete, Left after TikTok, Net Proceeds, On the shelf, Paid Out, Platform Deductions, Return Loss, Return Rate, Sold not posted, Tax set-aside, VAT line, Written off, You keep.

**Reached from.** Any term on any screen, and from Settings. A term shown on a card links to its own entry rather than to the top of the list.

**Rules.** The glossary is the single source for these labels, which is what section 8 of the Wireframes document means by the terminology standard. A term defined here is never given a second name elsewhere in the product. Tax terms carry "A guide, not advice" and the correct-as-at date, as TAX-7 requires.

**Trace.** PRD section 6.1 Clarity, TAX-7, Wireframes section 8.

---

## 3.8 Additions to section 6, States and edge cases

| State | What the seller sees |
|---|---|
| Not verified | The TikTok connection is offered but not active, with one line saying verification releases it and a resend control. |
| Disconnected | A banner on every screen with the disconnection date and the deletion date, figures still readable, exports still available, one action to reconnect. |
| Deletion in progress | The account is signed out, and the completion date is stated in the confirmation email. |
| Export building | The screen states that the seller can leave, and the notification centre carries the file when it is ready. |
| Export expired | The expiry is stated plainly and a rebuild is offered, at no cost. |
| Region not supported | The supported regions are named, the account remains, and no charge is made. |

---

## 3.9 Resolving the sample data contradiction

The audit found the wireframe sample data contradicting the rules it illustrates. S15 shows product costs on 14 of 20 products, which is a coverage of 70%, yet S12 shows a set-aside estimate and S6 shows "Kept this month". TAX-3 hides the estimate unless coverage is complete, and the API example returns `kept: null` when costs are incomplete.

The fix applied at v0.2 is a single consistent sample shop, used in every figure.

| Figure element | v0.1 | v0.2 |
|---|---|---|
| Cost coverage on S15 | 14 of 20 products | 20 of 20 products, 100% of gross sales |
| Hero label on S6 | Kept this month | You keep, which the complete coverage now earns |
| Set-aside on S12 | Shown | Shown, which complete coverage now permits |

A second sample shop is added to the QA document rather than to the wireframes, holding coverage of 62%, so the "Left after TikTok" label and the hidden set-aside are still testable. Briefing a developer or a pilot tester from the wireframes now shows one coherent shop rather than two contradictory ones.

---

## 3.10 Open UX decisions, updated

The tablet layout is resolved rather than left open. Section 7 of the Wireframes document already states the rule: larger screens use a centred column with a side detail panel and the tabs move to a left rail. Tablets follow the larger-screen rule at 768 px and above. The open decision is removed from section 9 and the rule is stated in section 7.

The remaining open decisions stand: whether Returns earns its own tab after the pilot, whether a guided tour is offered, and how many insights Today can carry.
