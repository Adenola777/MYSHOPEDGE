# Action 14. The onboarding screen set, settled

Decided 22 September 2026. This action closes two things. It settles who owns the account
screens, which A3 and A13 disagreed about. It completes the onboarding phase, which was
short by five screens and one state.

## 14.1 The ruling on the account screens

**Stack Auth hosts sign up, sign in, email verification and password reset.** A3 sections
3.2 specified those as MyShopEdge screens, with password fields, password rules, weak
password refusal, reset, session termination on password change and a six digit second
factor. None of that is ours to build. This action replaces that specification.

The consequence worth stating plainly is that MyShopEdge never holds a password. There is
no hash to leak, no reset flow to get wrong, no lockout policy to tune, and no credential
in any log. The cost is that the look of three pages is limited to what the provider's
theming allows, and that is a smaller cost than the one it removes.

What remains ours on those three screens is the entry point, the return, and the failures
that belong to us rather than to the provider.

## 14.2 The onboarding order

Payment sits after the TikTok connection, ruled 22 September, because a seller who cannot
connect a shop has nothing to pay for.

```
S17 Start          →  S18 Return           →  S1  Connect TikTok Shop
   →  S2  First sync   →  S33 Plan and card  →  S3  Product costs choice
   →  S4  Upload mapping  or  S20 Manual cost entry
   →  S5  Tax profile  →  S6  Today
```

Five screens sit off that line and are reached from it when something happens.

## 14.3 The account screens, rewritten

### S17 Start

**Purpose.** Send the seller to the provider to create an account or sign in.

**Content.** The logo, the tagline, one sentence saying what happens next, and two actions.
"Create an account" and "Sign in" both hand off to Stack Auth. Links to the privacy notice
and the terms sit below, which section 11 of the Data Protection Document requires and
which cannot live on a page we do not control.

**Rules.** No password field appears here, because we never receive one. Nothing on this
screen collects anything. It exists so that the first thing a seller sees carries our name
and our words rather than the provider's.

**Trace.** ACC-1, ACC-2, Data Protection section 11.

### S18 Return

**Purpose.** Receive the seller back from the provider, resolve them to an account, and
send them onward.

**Content.** A brief waiting state. Most sellers never read it, because the resolution takes
one round trip.

**Rules.** The account is created here on a first verified sign in, by `create_account` in
migration 0017. Every value comes from verified JWT claims. A seller arriving with a token
whose claims carry no verified email address cannot be set up, and is told so rather than
being given a half-made account.

**States.** New account created, existing account resolved, no verified email, and the
identity conflict that S36 covers.

**Trace.** ACC-1, ACC-2.

### S19 Sign in

**Purpose.** Return to the account.

**Content.** Hosted by the provider. This section documents the hosted page rather than
specifying one of ours, so that the pack states where the seller actually goes.

**What we brand.** The provider's theming carries the logo, the brand colours from A7 and
the product name. What it does not carry is our copy, and that limit is accepted.

**Second factor.** Whether the provider offers one is still unconfirmed and has been open
since the morning of 22 September. It is the one item in this action that is not settled.

**Trace.** ACC-2.

## 14.4 The five screens that were missing

### S34 Payment confirmed

**Purpose.** Receive the seller back from their bank after a 3D Secure challenge.

**Why it exists.** S33 confirms the card without leaving the page where the bank allows it.
Where the bank insists on a redirect, the seller leaves the site entirely and comes back to
`return_url`. Until this action that URL pointed at a route that did not exist, so a seller
whose bank forced a redirect would have landed on a 404 with their card already verified
and no way to know it had worked.

**Content.** Confirmation that the trial has started, the plan, the date of the first
payment, and one action onward to the product.

**States.** Confirmed. Not confirmed, where the bank refused, with the card step offered
again. Arrived without a pending setup, where the seller reloaded the page later, which
shows the current subscription state rather than an error.

**Trace.** S33, and the Stripe SetupIntent return.

### S35 Continue setting up

**Purpose.** Receive a seller who left during onboarding and came back.

**Why it exists.** S2 states that a seller can leave during the twelve month sync and
return. Nothing said what they see when they do, and the sync is the longest wait in the
product.

**Content.** What is already done, what is left, and one action that resumes at the right
step. The sync state is shown honestly: still running, finished, or failed on a particular
domain.

**Rules.** The screen never restarts a completed step. A seller who has connected their shop
is not asked to connect it again.

**Trace.** SYN-1, CST-1.

### S36 That email is already in use

**Purpose.** Explain an identity conflict in words a seller can act on.

**Why it exists.** A seller can create an account with a password and later sign in with a
social provider using the same address, or the reverse. `create_account` raises rather than
creating a second account, and the API returns 409. Without this screen that becomes an
error code.

**Content.** A statement that the address already belongs to an account created a different
way, and what to do about it, which is to sign in the original way. It names the method
where the provider tells us, and says nothing at all where it does not, because guessing
would be worse than silence.

**Trace.** Migration 0017, the `email_already_linked` problem code.

### S37 Signed out

**Purpose.** One screen for the two ways a session ends.

**Content.** Two states with different copy and the same shape.

**Signed out deliberately.** "You are signed out." A sign in action. Nothing alarming.

**Session expired.** "Your session has expired." The same action. This is what a seller
sees when a token expires mid onboarding, which the sync makes likely because the sync is
long.

**Rules.** Neither state discards onboarding progress. A seller who signs back in resumes at
S35 rather than starting again.

**Trace.** ACC-2, and the `token_expired` problem code.

### S38 Payment did not go through

**Purpose.** Tell a seller the first payment after the trial failed, and what happens next.

**Why it exists.** `invoice.payment_failed` moves an account towards suspended, and
`accounts.status` has carried a `suspended` value since the v0.2 schema with no route into
it and no screen for it.

**Content.** What failed, when the next attempt happens, how long the data is kept, and one
action to change the card. The tone is not a warning. A declined card is usually a bank
being cautious rather than a seller in trouble.

**Rules.** The seller keeps read access to their figures while the account is past due. A
bookkeeping product that locks a seller out of their own records over a failed card is
holding their accounts hostage, and this product does not do that.

**Trace.** `invoice.payment_failed`, `accounts.status`.

## 14.5 Two corrections to the screen map

**S33 joins the map.** The map in A3 runs S1 to S32 and predates the plan and card screen.
S33 sits in the Onboarding area, between S2 and S3.

**Sign out is a control, not a screen.** It lives in the top bar and in Settings, and it
leads to S37. It was missing from the map entirely, which is how the product reached
thirty-three screens with no way to leave.

## 14.6 The revised count

| | Before | After |
|---|---|---|
| Screens in the map | 32 | 38 |
| Onboarding screens | 9 | 11, plus 5 reached from them |
| Screens we build that hold a password | 3 | 0 |

## 14.7 What is still open

The second factor. Whether Neon Auth on Stack Auth offers one has been an open item since
the morning of 22 September and this action does not close it. For a product holding a
seller's financial history it is worth knowing before launch rather than after.
