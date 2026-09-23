# Action 26. How a seller signs in, and how their shop is linked

23 September 2026. Adenola decided Google now and TikTok later, and asked how the TikTok
account gets linked. The answer is that it is not linked by a login, and the distinction is
the reason the decision costs nothing later.

## 26.1 Google is already provisioned

One call to the project's OAuth provider list on the production branch:

```
[{"id": "github", "type": "shared"}, {"id": "google", "type": "shared"}]
```

Both are shared providers, which means Neon's own OAuth client rather than one registered
by this project. Nothing has to be added for sign-in to work. A shared client is adequate
for testing and shows Neon's consent screen rather than MyShopEdge's, so registering an own
client before launch is a branding decision and not a functional one.

TikTok is not available. `add_auth_oauth_provider` accepts exactly `google`, `github`,
`microsoft` and `vercel`. Stack Auth, the provider Neon actually provisions, has been
renamed Hexclave. Whether it accepts a custom OAuth or OIDC provider is unread, and it does
not block the decision below.

## 26.2 The seller and the shop are two different things

TikTok has two identity systems and they do not meet.

Login Kit identifies a **consumer** account and returns an `open_id`. Shop authorisation
identifies a **seller** and returns a token bound to a shop. Nothing TikTok publishes links
one to the other, so signing in with TikTok would not tell this application which shop the
person owns. It would only tell it which TikTok user was at the keyboard.

That is why the account is keyed on the shop authorisation. The identity provider is a way
in, and the shop authorisation is the thing that says whose figures these are.

## 26.3 The chain, as the schema holds it

Read from the development branch rather than from memory:

```
accounts.id                              the tenant
shops.account_id -> accounts.id          the shop belongs to the account
shops.tiktok_shop_id, tiktok_shop_code, region, seller_type, connection_status
tiktok_connections.shop_id -> shops.id
  access_token_enc, refresh_token_enc, shop_cipher_enc, scopes, key_version
```

The sequence is: the seller signs in with Google, Stack Auth issues a token, `auth.py`
resolves the subject to an `accounts` row. The seller then calls
`POST /connections/tiktok/authorize`, is sent to TikTok, and returns through
`GET /connections/tiktok/callback` with a code. That handler exchanges the code, calls
`GetAuthorizedShops`, writes the shop against their `account_id`, and writes the tokens and
cipher into `tiktok_connections`. Every finance call then uses the cipher on that row, and
row level security scopes the reads by `app_account_id()`.

Adding TikTok as a sign-in method later adds a row to the provider list and changes none of
this.

## 26.4 One shop belongs to one account, and the database enforces it

```
UNIQUE (platform, tiktok_shop_id)
```

A second account authorising a shop that is already connected hits a constraint rather than
receiving a second ledger over the same orders. The risk was real and the schema had already
answered it, which is worth recording because it was found by querying `pg_constraint` and
not by remembering.

## 26.5 What 0020 fixed on the way

Comparing the contract's `Shop` schema against `information_schema.columns` found that the
table could not hold two fields the contract serves. `tiktok_shop_code` and `seller_type`
are both added by migration 0020, on staging and development. Production does not have it.

Neither carries a check constraint, and the migration explains why at length. The short
version is that `seller_type` has been observed once, as `LOCAL`, and a constraint built on
one observation would turn an unexpected TikTok response into a failure after the code has
been exchanged. The contract already provides `accepted: false` with
`rejection_reason: seller_type_unsupported` for that case.

`authorization_expires_at` is served by the contract and was deliberately not added.
`tiktok_connections.refresh_expires_at` looks like the same instant and nobody has checked.
It is recorded as open in `CLAUDE.md`.

## 26.6 What is still unanswered

The encryption key that produces the `_enc` columns does not exist. `key_version` is a
column that resolves to nothing. It cannot be settled until the Python service has a host,
because the host decides where a key lives and how it rotates. It is now in the blocked
table in `CLAUDE.md` rather than sitting quietly in a schema that looks finished.
