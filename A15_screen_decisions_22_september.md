# Action 15. Four rulings on the screen set

Decided 22 September 2026, in the evening, after the onboarding frames were drawn and read
back. Three of these rulings remove things. One of them puts something back.

## 15.1 Cost files are Excel and CSV only

Word and PDF were asked for and then withdrawn on the same evening, and the reason for
withdrawing them is the right one.

An Excel or CSV file arrives with rows and columns. A cost sits in a cell, the cell sits in
a column, and the column can be matched to a meaning. That is what S4 does when it says a
column is the seller SKU and another is the cost per unit.

A Word file or a PDF carries no columns. It carries a layout that happens to look like a
table. Reading a cost out of it means guessing where one number ends and the next begins,
and a guess about a cost is not a small error. It moves the cost of goods, which moves the
gross profit, which moves the figure the seller relies on. A wrong cost is worse than no
cost, because no cost is visibly missing and a wrong cost is not.

**The ruling.** The upload accepts `.xlsx`, `.xls` and `.csv`, up to 10 MB. A seller whose
costs live in a Word document or a PDF types them in on S20. The screens say so rather
than leaving the seller to discover it after the upload fails.

This ruling changes the accepted content types on the cost upload endpoint in
`api/openapi.yaml` and the matching validation in the service. Neither is applied yet.

## 15.2 S19 Sign in is cut from the screen set

Stack Auth renders that page. A frame in our pack that documents a page we do not build
serves no seller and invites us to design something we cannot ship. What we control about
it is already written down in A14 section 14.3, and that is where it stays.

## 15.3 S18 Return is cut as a screen

It was a waiting page for one round trip. In practice it is a flash of text that nobody
reads, and it stood between the seller and the product.

The state does not disappear with the screen. The wait becomes a state on S17 Start. The
one real failure it carried, a seller whose token has no verified email address, moves to
S36, which already exists to explain an identity problem in words a seller can act on.

The `/return` route in the web application still exists and still resolves the account. It
renders a state, not a page of its own.

## 15.4 The three cards on S3 are cut

S3 offered three choices as cards and then repeated the same three choices as buttons
underneath them. Six controls for three decisions. The cards are cut and the buttons stay,
because a button is the thing a seller presses.

One line survives the cut. The reassurance that costs can be added later, and that we will
remind the seller where it matters, is kept as a footnote under the buttons. A seller who
skips a step without being told what skipping costs them will assume the worst, and that
assumption is the reason people abandon a setup.

## 15.5 S6 keeps its congratulation

It was proposed for cutting on the grounds that it costs a tap and gives nothing. It is
kept, and it now carries a celebration on the heading.

The argument for keeping it is the one that matters here. A seller who has just connected
a shop, waited through a twelve month sync, chosen a plan, confirmed a card and entered
their costs has done a long piece of work. Landing them on a dense screen of figures with
no acknowledgement treats that work as though it did not happen.

## 15.6 The prices are exclusive of VAT

Ruled 22 September 2026. Starter £9.99, Growth £24.99 and Pro £49.99 are all exclusive of
VAT. A UK registered seller therefore pays £11.99, £29.99 and £59.99 at 20 per cent.

Three things follow and none of them is optional.

**Stripe carries the tax rather than the price.** The three prices are created with
`tax_behavior: "exclusive"`. Setting this wrongly cannot be corrected later, because a
Stripe price is immutable once created. A price created as inclusive has to be replaced
and every subscription moved across.

**S33 shows both numbers.** A plan card that says £9.99 and then charges £11.99 is the
kind of surprise that produces a chargeback. The card carries the price and the words
"plus VAT", and the total including VAT appears before the card is confirmed.

**The seller's own VAT position does not change ours.** Most of these sellers are below
the registration threshold and cannot reclaim it. The price they pay is the price with VAT
on it, and the screen says so rather than assuming a reclaim they cannot make.

## 15.7 The copy pass

Ten strings were removed from the frames because they were written for a reviewer rather
than a seller. They included requirement identifiers, references to this document set, and
explanations of why a screen behaves as it does. A customer screen is not the place to
argue with a specification.

Eleven strings were fragments and are now sentences, which is what the house style asks
for. The repeated "Nothing is lost" construction was cut back to the single screen where
it earns its place, which is the failed connection, because a reassurance repeated on six
screens stops being a reassurance and becomes a tic.
