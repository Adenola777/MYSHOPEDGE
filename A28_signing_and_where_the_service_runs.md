# Action 28. The signature, and the hosting decision

23 September 2026, late. Adenola asked for the three items on the open list to be completed.
Two are done and the third is decided and prepared.

## 28.1 Production was four migrations behind, and half of a fifth

The ledger on production recorded through `0016` and nothing after it. All five views
already carried `security_invoker = true`, so `0019`'s security fix had been applied by hand
with no ledger row, which is the exact failure `0015` exists to prevent.

It had also been applied incompletely. `0019` creates `order_quota` as well as fixing the
views, and `order_quota` was absent. So was `subscriptions`, from `0018`. **Nobody could
have subscribed on production**, and the order quota in A16 had nothing to count against.

A snapshot was taken first, `snap-frosty-frog-zar8dzos`. Then `0017`, `0018`, `0019`, `0020`
and `0021` were applied in order, each with its ledger row.

Verified by fingerprint rather than by eye. A single query hashing every column, every view
with its `security_invoker` setting, and every function with its `SECURITY DEFINER` flag
returns the same value on production and on staging:

```
1278d46738b166978d1fe1735bbb01a5   526 objects
```

Production now records 22 migrations, holds 6 views, and has both `subscriptions` and
`order_quota`.

## 28.2 The signing algorithm was public all along

A27 recorded signing as unobtainable. That was wrong, and the reason it was wrong is worth
keeping.

`WebFetch` returned only navigation chrome from `partner.tiktokshop.com`, and the conclusion
drawn was that the pages needed a sign in. They do not. They are a JavaScript application,
and a fetch that does not run JavaScript sees nothing whichever page it asks for. Opening
the same site in a browser shows the full developer guide, signed out, including a page
called **Sign your API request**.

The lesson is narrower than "use a browser". It is that *a tool returning nothing is not
evidence about the thing being fetched.* It is evidence about the tool. A27 turned one
tool's limitation into a fact about TikTok, wrote it into three documents and a blocked
table, and stopped work on the strength of it.

### The algorithm, from TikTok's page

HMAC-SHA256, keyed with the app secret, hex encoded.

1. Take every query parameter except `sign` and `access_token`.
2. Sort the keys alphabetically.
3. Concatenate them as `{key}{value}`, with no separator.
4. Put the request path on the front.
5. Append the raw body, unless `Content-Type` is `multipart/form-data`.
6. Wrap the result: `secret + input + secret`.
7. HMAC-SHA256 with the secret as the key, hex encode.

The app secret appears three times: twice as padding and once as the key. It looks redundant
and it is not optional.

### The common parameters, from the same guide

| Where | Name | Note |
|---|---|---|
| Query | `app_key` | From the app detail page |
| Query | `timestamp` | Ten digits, **seconds**. Valid from five minutes ago to thirty seconds ahead |
| Query | `sign` | The above |
| Header | `x-tts-access-token` | For 202309 and later. Not in the query string and **not signed** |
| Header | `content-type` | `application/json` |

`36009004 Invalid timestamp` is the error for a timestamp outside that window. This project
met that code by hand earlier in the day and did not know why. A millisecond timestamp
produces it, which is the natural mistake from any language whose clock returns
milliseconds.

### What the shop lookup actually returns

`GET /authorization/202309/shops` takes no query parameters of its own. TikTok's own OpenAPI
confirms 202309 is the only version of it. Each shop carries `id`, `code`, `name`, `region`,
`seller_type` and `cipher`.

Every one of those maps onto a column. `code` and `seller_type` are the two that migration
0020 added earlier the same evening, when the only evidence for them was that the contract
served them and the table could not hold them. They are exactly what TikTok sends.

## 28.3 The callback is finished

It exchanges the code, asserts `user_type` is 0, calls the signed shop lookup, and writes the
shop and its tokens in one transaction. A shop without its connection cannot be read from and
a connection without its shop has nothing to hang on, so neither is allowed to exist alone.

**Tokens are encrypted before the transaction opens**, with AES-256-GCM and a fresh nonce on
the front of each ciphertext. The key is read from `TIKTOK_TOKEN_KEY`, thirty-two bytes
base64 encoded, and a missing or wrong-length key refuses the connection rather than falling
back to anything weaker. `key_version` is written as 1, meaning "the key in that variable".
Rotation still needs somewhere to hold two keys at once, so the register remains open and
0021's comment still says so.

**An unsupported shop is stored and listed, not refused.** A shop outside `GB`, or a
`CROSS_BORDER` seller, comes back with `accepted: false` and a `rejection_reason`, exactly as
the contract specifies. Refusing outright would throw away the authorisation the seller just
granted, and the auth code is single use, so they would have to start again.

**A shop already connected elsewhere returns 409.** The insert conflicts on
`UNIQUE (platform, tiktok_shop_id)`, and because the conflict clause updates rather than
doing nothing, a null result means row level security hid another account's row. The guard
recorded in A26.4 is now load bearing rather than theoretical.

Fourteen smoke cases pass. Four are new: the signature's documented properties, the token
round trip with its refusal on a missing key, a GB shop connecting with nothing readable
reaching the database, and an unsupported shop being listed rather than rejected.

**`_sign` is unverified against a live call.** It is written from the vendor's stated steps
and no request has been made with it. A signature is either accepted or refused, so the
first real call is the test. The code says so at the top of the module, and this is not the
same class of unknown as before: the algorithm is now written down from its source rather
than absent.

## 28.4 Where the Python service runs

**Decided: a long-lived container in London, not serverless.** Three facts decide it.

`db.py` holds a `psycopg_pool.ConnectionPool`. A pool belongs to a process that outlives a
request. A serverless invocation is its own process and may be frozen between requests, so a
pool of ten there means ten connections held per concurrent invocation, and Postgres runs
out long before the platform does. Neon's pooled endpoint mitigates it and does not remove
the mismatch.

The access token lives seven days (A23.4) and nothing refreshes it. A refresh needs something
that runs on a schedule and holds the encryption key. That is a background worker, and it
wants the same process and the same configuration as the service.

The database is in `aws-eu-west-2` and the front end's functions are in `lhr1`. Both are
London, and the service should be too, because every request it serves makes several
database round trips.

The pool is now configurable, so the decision is reversible without a rewrite. `DB_POOL_MAX`
set to 1 with a `-pooler` connection string makes it serverless-safe if the choice changes.

**Not provisioned.** Deploying needs two things that are not mine to supply: the 51 local
commits pushed to GitHub, and the environment variables, which carry `DATABASE_URL`, the
Stripe secret key, `TIKTOK_APP_SECRET` and `TIKTOK_TOKEN_KEY`. Those are secrets and they go
in through Adenola's own hands.

The full set the service needs:

| Variable | What it is |
|---|---|
| `DATABASE_URL` | Neon, as `mse_app` |
| `NEON_AUTH_JWKS_URL`, `NEON_AUTH_ISSUER`, `NEON_AUTH_AUDIENCE` | Stack Auth. Issuer and audience must be read off one real token, per A25.2 |
| `STRIPE_SECRET_KEY` | Live account |
| `STRIPE_PRICE_STARTER`, `_GROWTH`, `_PRO` | The three in `CLAUDE.md` |
| `TIKTOK_APP_KEY`, `TIKTOK_APP_SECRET`, `TIKTOK_SERVICE_ID` | A23.2. `service_id` is not `app_key` |
| `TIKTOK_TOKEN_KEY` | 32 random bytes, base64. Generate once and never regenerate, or every stored token becomes unreadable |
| `DB_POOL_MAX` | Only if this ends up serverless after all |

## 28.5 Still open

The shop authorisation itself, which needs TikTok's app review. Nothing above can be tested
end to end against the GB shop until that clears.

A14's second-factor ruling still rests on Better Auth's plugin list, which is the wrong
provider.
