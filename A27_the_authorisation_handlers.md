# Action 27. The two connection handlers, and the one fact that stops them finishing

> **Superseded in part by A28, the same evening.** Section 27.4 below concludes that
> TikTok's signing algorithm could not be obtained. That conclusion was wrong. The
> documentation is public and needs no sign in; `WebFetch` returned nothing because the
> pages are a JavaScript application, and a tool returning nothing is evidence about the
> tool rather than about the thing being fetched. A28.2 carries the algorithm. This
> document is left standing because the reasoning in it is still how an unknown should be
> handled, and because how the mistake was made is worth keeping.

23 September 2026. Adenola asked for the TikTok connection endpoints to be built. Most of
the work was possible and one part was not, and the part that was not is worth more of this
document than the part that was.

## 27.1 What was built

`service/app/connections.py`, wired into `main.py`. The contract now has ten of its
fifty-three paths served, up from eight.

`POST /connections/tiktok/authorize` issues the link. It validates `return_to`, generates a
state, stores the state's digest inside the seller's own scope, and returns the URL.

`GET /connections/tiktok/callback` receives the seller back. It spends the state, exchanges
the code, asserts the seller type, and then stops. Why it stops is 27.4.

Every constant came from A23, which was read off TikTok's own page. Nothing was recalled.

## 27.2 The state had nowhere to live, so migration 0021 gave it one

The contract has said since it was written that the state "is single use, expires in ten
minutes and is bound to this account", and that "the callback rejects any state it did not
issue". A23.5 records TikTok recommending the same thing. No table could hold one, so
neither handler could be written as specified.

`tiktok_auth_state` now exists on staging and development. Three decisions in it are worth
stating.

**The state is stored as its SHA-256 and never in the clear.** The raw value travels in a
URL, through TikTok, through the seller's browser history and almost certainly into a log.
A readable copy of the table would be a set of working keys. The service hashes on the way
in and on the way out, which costs one call and makes a copy of the table worthless.

**`mse_app` holds INSERT and nothing else.** This was discovered rather than designed. The
first attempt to verify the tenancy failed with `permission denied for table
tiktok_auth_state` on a SELECT, which is the grant being narrower than the test expected.
It is right: `consume_tiktok_auth_state` is the only read path, so there is no query anybody
can write that returns a live state.

**Consumption is SECURITY DEFINER, on the pattern of `resolve_account` in 0017.** The
callback carries `security: []` in the contract. It arrives by browser redirect with no
bearer token, so it has no account context, and finding the account is the entire point of
the call. The function takes a digest and returns an account id or nothing. The caller
cannot construct a digest without already holding the state.

## 27.3 The tenancy was proved rather than assumed

Run on the development branch as `mse_app`, which is what A25 said to do and what the view
leak in 0019 taught:

| Attempt | Result |
|---|---|
| Consume a state issued to this account | Returns the account and its `return_to` |
| Consume the same state again | No row |
| Consume a state never issued | No row |
| Consume a state that expired a minute ago | No row |
| Insert a row claiming another account's id | `new row violates row-level security policy` |

The last one is the one that matters. Unknown, spent and expired are deliberately
indistinguishable in the result, because telling them apart tells somebody guessing which
guesses were close.

## 27.4 `GetAuthorizedShops` is signed, and the signing algorithm is not a fact here

The callback needs `GET /authorization/202309/shops` to learn the shop id and the cipher.
That call is signed. This project does not hold TikTok's signing algorithm.

What was checked, in order:

- A23.6 says in its own words that signing "is a separate matter and is not covered by this
  page". The gap was recorded when A23 was written and nobody closed it.
- A grep of every document, every Python file and `api/openapi.yaml` for `hmac`, `sha256`
  and `signature` returns nothing.
- TikTok's docv2 pages are a JavaScript application. A fetch returns the navigation chrome
  and no content.
- The bundled `tts-openapi-guide` and `tts-developer-onboarding-guide` skills both refer to
  signing in their descriptions and neither specifies it. The bundled OpenAPI snapshot gives
  paths and schemas, not the signature.

Third-party SDKs on PyPI implement it. They were not read and were not used. A third party's
code is not the vendor's statement, and rule 7 does not accept it. A signature copied from
somebody else's package is an assumption wearing a citation.

So `_authorized_shops` raises `503 tiktok_signing_unimplemented` and the docstring says all
of the above. One function, one named failure, nothing half written to the database.

**Why not guess and see.** Because that is A25 exactly. The authentication module asserted a
documented algorithm, met a different one, had tests written from the same assumption, and
showed nine green cases while refusing every real token. A signature is worse, because a
wrong one that happens to be accepted on some calls and not others is very hard to see.

**Nothing partial is written.** `shops.tiktok_shop_id` is NOT NULL and the token response
does not carry a shop id. It carries `seller_name`, `seller_base_region`, `open_id`,
`user_type` and `granted_scopes`, and none of those identify a shop. A row written from the
token alone would be a shop that can never be reconciled to anything.

The fastest way to close this is to make any call through Partner Center's own API Testing
Tool and read the signature off the request it builds. That tool signs on the caller's
behalf, which is exactly why the three successful calls in A19 needed no algorithm here.

## 27.5 The seller type assertion earns its place

A23.3 records that `user_type` must be `0` for a seller, that `1` is a creator, `3` a
partner, and `4` and `5` Global Selling. The handler asserts it and refuses anything else.

This is not defensive decoration. A23.1 records that every authorisation attempt on 23
September went through `partner.tiktokshop.com` and returned an Indonesian sandbox shop three
times. A seller who reaches the wrong link gets a token that will not read their finances,
and without this assertion the failure would appear much later, as wrong figures rather than
as a refusal.

`services.tiktokshop.com` is the seller link and the handler builds it. A smoke case asserts
the partner host does not appear in what it builds.

## 27.6 What the smoke test now covers

Six cases were added and all eleven pass.

| Case | What it stops |
|---|---|
| Authorize refuses when TikTok is not configured | A link built from an empty service id |
| Authorize refuses `//evil.example`, `https://...` and a backslash | The open redirect the contract warns is an account takeover. A protocol-relative URL passes a naive "starts with a slash" check |
| Authorize issues a seller link and stores only the digest | The partner host, a short state, and the raw state reaching the table |
| Callback refuses a state it did not issue | Connecting a shop the seller never approved |
| Callback refuses a creator account | The wrong authorisation link failing silently |
| Callback stops at the signing gap | A half connection being written |

The third case asserts that the stored value differs from the issued value and equals its
SHA-256. The fourth asserts the problem detail does not echo the input back, because a
problem response is shown to a seller and gets screenshotted.

## 27.7 Still open

The access token lives seven days (A23.4) and nothing schedules a refresh, so a connection
made today stops working next Wednesday. `REFRESH_URL` is a constant in the module and no
code calls it, because a scheduled job needs a host and the service has none. It is in the
blocked table in `CLAUDE.md`.

A23.4 says `shops.refresh_token_enc`. The column is on `tiktok_connections`, not on `shops`.
Small, and left uncorrected in A23 so that this document carries the correction rather than
a ruling being edited quietly.
