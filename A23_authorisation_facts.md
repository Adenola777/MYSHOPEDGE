# Action 23. The authorisation flow, from TikTok's own page

23 September 2026. Read from TikTok's Authorization overview. Everything here is the
vendor's statement, not an inference.

Until today the pack held none of this. A grep across every document, every Python file and
`api/openapi.yaml` for `auth.tiktok-shops.com`, `services.tiktokshop.com`, `authorized_code`,
`service_id`, `token/get` and `token/refresh` returned nothing. A11 specified what to ingest
and A14 specified our own identity provider. Neither said how a seller's shop actually
becomes connected.

## 23.1 There are two authorisation domains, and we used the wrong one

| Who is authorising | Link, Rest of World |
|---|---|
| **Seller**, their own shop | `https://services.tiktokshop.com/open/authorize?service_id={service_id}` |
| Partner, TAP | `https://partner.tiktokshop.com/open/authorize?service_id={service_id}` |
| Creator | `https://shop.tiktok.com/alliance/creator/auth?app_key={app_key}&state={state}` |

Every authorisation attempt on 23 September went through `partner.tiktokshop.com`, and the
result was a sandbox test shop in Indonesia. `GetAuthorizedShops` returned that shop and only
that shop, three times.

**MyShopEdge is a seller-facing application.** Its users authorise their own shops, so the
`services.tiktokshop.com` link is the one the product needs, and the one the connect screen
must build. This is the most likely reason `GBGBLCRKQTEX` has never appeared in an
authorisation response.

## 23.2 `service_id` is not `app_key`

Both appear on the app detail page in Partner Center under App and Service. `service_id`
identifies the registered online application, which is the OAuth client, and it is what the
authorisation link takes. `app_key` and `app_secret` are what the token exchange takes.

`RUNBOOK_tiktok_connection.md` collected the app key and the app secret and never mentioned
`service_id`. Without it no authorisation link can be constructed, which made step 4 of that
runbook impossible to follow as written.

## 23.3 The token exchange

`GET https://auth.tiktok-shops.com/api/v2/token/get`, the same host for every market. Note
that this is not `open-api.tiktokglobalshop.com`, which is where every other call goes.

| Parameter | Value |
|---|---|
| `app_key` | from the app page |
| `app_secret` | from the app page |
| `auth_code` | from the redirect |
| `grant_type` | `authorized_code` |

**`authorized_code`, not `authorization_code`.** TikTok's page carries an explicit warning
about this: it is not the standard OAuth spelling, and correcting it to the standard makes
the request fail. Anyone who knows OAuth will get this wrong once.

The response carries `access_token`, `access_token_expire_in`, `refresh_token`,
`refresh_token_expire_in`, `open_id`, `seller_name`, `seller_base_region`, `user_type` and
`granted_scopes`.

**`user_type` must be `0` for a seller.** 1 is a creator, 3 is a current partner, 4 and 5 are
Global Selling. The value should be asserted on rather than ignored, because receiving
anything else means the shop authorised through the wrong link, which is precisely the
mistake in 23.1.

## 23.4 Expiry, and what it means for us

| Thing | Life |
|---|---|
| `auth_code` | **30 minutes**, single use |
| `access_token` | **7 days** by default |
| `refresh_token` | as long as the authorisation the seller granted |

The runbook said the auth code "expires within minutes". Thirty minutes is the fact, and the
imprecision was in the direction that makes somebody rush.

Seven days is short enough that refresh is not optional. `shops.refresh_token_enc` exists to
hold the refresh token and nothing anywhere schedules a refresh, so a connection made today
would silently stop working next Wednesday. The refresh call is
`GET https://auth.tiktok-shops.com/api/v2/token/refresh` with `app_key`, `app_secret`,
`refresh_token` and `grant_type=refresh_token`, and the response has the same shape.

## 23.5 The state parameter

TikTok recommends a `state` parameter on the authorisation link for CSRF protection: an
unguessable, server-generated, single-use random string, validated on callback.

`/connections/tiktok/authorize` and `/connections/tiktok/callback` are both in the contract
and neither is implemented. When they are, the authorize handler generates and stores the
state and the callback handler refuses any response whose state does not match. A callback
that accepts any `code` it is handed will connect a shop the seller never approved.

## 23.6 What this unblocks

The authorisation half of the integration can now be written entirely from facts. Nothing in
23.1 to 23.5 is inferred, and the two handlers, the token exchange, the refresh and the state
check all have their inputs, their endpoints and their expiry rules stated.

The request signing for the ordinary API calls is a separate matter and is not covered by
this page.
