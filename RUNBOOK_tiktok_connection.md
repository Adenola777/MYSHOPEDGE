# Runbook. Connecting the TikTok Shop, step by step

Rewritten 24 September 2026. The first version was written on 23 September, before any
connection code existed, and asked for the authorisation code to be copied out of an address
bar by hand. That is no longer how it works. The service now runs on Render, sign-in works,
and the site has a Connect button, so the code never passes through a person.

**The rule that shapes this runbook: no secret is ever typed into a chat.** The app secret
and the token key go straight into Render's environment page and nowhere else.

## What is built and what is not

| Piece | State |
|---|---|
| The Connect button, S1, on `/shops` while no shop is connected | Built 24 September |
| `POST /v1/connections/tiktok/authorize`, which issues a ten minute, single use link | Built, never called with real values |
| The return page, `/connections/tiktok/callback` on the site | Built 24 September |
| `GET /v1/connections/tiktok/callback`, which exchanges the code, checks the shop and stores the encrypted tokens | Built, never called against TikTok |
| Reading orders, returns and statements after the connection | **Not built.** No file in the service calls those TikTok endpoints |
| Refreshing the access token before its seven days run out | **Not built** |
| Disconnecting, S29 | **Not built** |

The first real connection is therefore the first test of the signing, the code exchange and
the shop lookup in `service/app/connections.py`.

## Step 1. Get the three values from Partner Center

In Partner Center, open **Manage apps** and select the app. Under **App & Service** the page
shows three values:

| Value | What it is for |
|---|---|
| **Service ID** | Building the authorisation link. It is not a secret |
| **App key** | The token exchange |
| **App secret** | The token exchange. It is a secret |

A23.2 records that the service ID and the app key are routinely confused, so copy each from
its own label.

## Step 2. Set the callback URL on the app

On the same app page, set **Callback URL** or **Redirect URL** to exactly:

```
https://my-shop-edge.vercel.app/connections/tiktok/callback
```

**This replaces the address set earlier on 24 September**, which pointed at the service on
Render. The service answers the callback with JSON, so a seller sent there would see raw
data. The site's page at this path hands the code to the service and shows the result in
words.

## Step 3. Put four values into Render

Open Render, the service **My-ShopEdge-1**, then **Environment**, and add:

| Variable | Value |
|---|---|
| `TIKTOK_SERVICE_ID` | The service ID from step 1 |
| `TIKTOK_APP_KEY` | The app key from step 1 |
| `TIKTOK_APP_SECRET` | The app secret from step 1 |
| `TIKTOK_TOKEN_KEY` | A new random key, made as below |

`TIKTOK_TOKEN_KEY` encrypts the TikTok tokens before they are stored. `_encrypt` in
`connections.py` requires exactly 32 bytes, base64 encoded, and refuses anything else. Make
one in your own terminal:

```
python3 -c "import os, base64; print(base64.b64encode(os.urandom(32)).decode())"
```

Paste the printed line into Render and nowhere else. **If this key is lost or changed, every
stored token becomes unreadable and the shop has to be connected again.** Nothing yet
supports two keys at once, which is why `key_version` is always 1.

Save. Render redeploys the service, which takes about a minute.

## Step 4. Connect

1. Sign in at `https://my-shop-edge.vercel.app/start`.
2. `/shops` shows **Connect your TikTok Shop** while no shop is connected. Press
   **Connect with TikTok Shop**.
3. TikTok's own page opens on `services.tiktokshop.com`, the seller link from A23.1. Sign in
   as the seller that owns the UK shop and approve.
4. TikTok sends you back to the site, which shows the result.

The link from step 2 lasts ten minutes and works once. If you wait longer, start again.

## What the service does with the approval

This is read from `tiktok_callback` in `service/app/connections.py`.

1. It spends the state, which binds the approval to the account that pressed Connect.
2. It exchanges the code at `auth.tiktok-shops.com` with `grant_type=authorized_code`, the
   spelling TikTok's own page warns against correcting (A23.3).
3. It refuses any account whose `user_type` is not 0, the seller type. Anything else means
   the partner link was used, which returned an Indonesian sandbox shop on 23 September.
4. It reads the authorised shops, takes the first, and marks it supported only when its
   region is `GB` and its seller type is `LOCAL`.
5. It encrypts the access token, the refresh token and the shop cipher, and writes the shop
   and its connection in one transaction.

## What each result on the return page means

| The page says | Meaning |
|---|---|
| "is connected." | The shop and its encrypted tokens are stored |
| "is connected, but MyShopEdge cannot read it." | The shop is not a UK local seller shop |
| "That connection link has expired." | Ten minutes passed, or the link was already used. Start again |
| "That TikTok account is not a Shop seller account." | The wrong TikTok account approved, or the partner link was used |
| "No shop was shared with MyShopEdge." | TikTok returned no shop for that account |
| "That shop is already connected to another MyShopEdge account." | The shop belongs to a different sign-in |
| "Connecting a TikTok Shop is not switched on yet." | A value from step 3 is missing on Render |
| "The connection was not completed." | TikTok sent you back without a code, usually because approval was declined |

Anything else shows TikTok's or the service's own words. Send a screenshot of it.

## Questions the connection alone does not answer

These need the statement reading that is not built yet, so they stay open after a
successful connection.

1. **How far back the statements go.** A16.2 promises twenty-four months. A19.3 records that
   an empty result from a new or test shop settles nothing.
2. **What a settlement export calls its columns.** A8 section 3.5.
3. **Whether the invoice number is reachable.**

## Two things to know

**The access token lasts seven days**, and nothing refreshes it yet. A shop connected today
stops being readable a week later until the refresh in A23.4 is built. Connecting again
issues a fresh token.

**The single use code can reach request logs.** TikTok puts it in the address. Render's log
records the service call with its query string, and Vercel's log may record the return
page's address too. The code is spent within the same second and TikTok allows it thirty
minutes at most, so a copy in a log cannot be used again.
