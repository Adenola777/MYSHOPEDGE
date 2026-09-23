# Action 24. Two app paths, and the project needs both

23 September 2026. Read from TikTok's developer onboarding guide after Adenola said he can
only authorise through a developer account. He is right, and the reason reframes the
integration work rather than adding a detail to it.

## 24.1 The two paths

| Path | For | Requirement | Authorisation | Review |
|---|---|---|---|---|
| **ISV** | Apps serving many sellers | Developer account plus company or entity qualification | Multiple sellers, **after approval** | **App review required before production launch** |
| **Seller Developer** | A merchant building a custom tool for their own shop | An active operating seller account | **Bound to that seller's own shop. Not installable by other sellers** | No marketplace-style review |

## 24.2 Why every authorisation today returned a sandbox shop

The app approved on 23 September is an ISV app. The ISV checklist reads: configure sandbox,
build and test in sandbox, submit for review, launch after approval, then guide sellers
through authorisation.

Production seller authorisation is therefore gated on review. `GBGBLCRKQTEX` cannot be
authorised to that app yet, and `GetAuthorizedShops` returning the same Indonesian sandbox
shop three times is the system behaving correctly rather than a misconfiguration.

A23.1 blamed the authorisation domain, and the domain does matter. This is the larger
reason underneath it. Both are true and this one is not fixable by changing a URL.

## 24.3 What follows for the project

**MyShopEdge is an ISV product.** It exists to serve many UK TikTok Shop sellers. The ISV
app is the right long-term path and its review is a launch gate, not a problem for today.

**A Seller Developer custom app is how the build gets real British data now.** It is created
from the seller or developer entry point on the seller account, it binds to that seller's own
shop, and it needs no marketplace review. A merchant building a tool for their own shop is
precisely the case it exists for, and it is precisely what is happening while the product is
under construction.

So two apps with two jobs:

| App | Job |
|---|---|
| Seller Developer custom app on `GBGBLCRKQTEX` | Real GB orders, unsettled transactions and settlements as they arrive. Unblocks A20.7, the fifty-field mapping, and the whole ingestion |
| The existing ISV app | Stays in sandbox. Goes to review when the product is ready to serve sellers who are not Adenola |

Nothing about the code differs between them. The same token exchange, the same refresh, the
same signing and the same handlers serve both, because the difference is which shops may
authorise the app rather than how they do it.

## 24.4 Two review risks that touch code not yet written

The guide lists common reasons ISV apps fail review. Two of them are about code this project
has not built, so they are cheaper to get right first than to correct under review:

- **App secret exposed in frontend code.** A13 already puts the secret server-side, and the
  Next.js front end holds no secrets, but the rule should be stated rather than assumed.
- **Weak redirect URL validation or callback handling.** This is exactly the `state`
  parameter in A23.5. A callback that accepts any `code` it is handed, without checking a
  state it issued, is both a security fault and a documented review failure.

The others listed are incomplete or buggy app flows, requesting unnecessary scopes, and a
poor seller authorisation experience. The scopes point is worth noting now: the onboarding
guide warns that enabling unnecessary scopes lengthens review and lowers the authorisation
rate. `tiktok_connections.scopes` currently records
`{seller.finance.info,seller.order.info}` for the seeded shop, and whether that is the
minimal set the product actually needs has never been checked against the screens.
