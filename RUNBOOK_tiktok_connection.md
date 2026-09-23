# Runbook. Connecting the TikTok Shop, step by step

Written 23 September 2026, the day the app developer approval came through. Follow it once.
It takes about ten minutes, and nine of them are waiting for pages to load.

**The rule that shapes this runbook: no secret is ever typed into a chat.** The app secret
signs every request the integration makes. Anything pasted into a conversation stays in its
transcript. Every secret below travels through the cloud environment's variables box, which
Claude reads at session start and never displays.

## Before you start

You need three browser tabs open and signed in.

| Tab | Where |
|---|---|
| TikTok Shop Partner Center | partner.tiktokshop.com |
| Your seller account | seller-uk.tiktok.com |
| The cloud environment settings | the environment selector, the cloud icon, in the Claude app |

## Step 1. Get the app key and app secret

In Partner Center, open **Manage apps** and select your app. Under **App & Service** the page
shows three values you need, not two:

| Value | What it is for |
|---|---|
| **Service ID** | Building the authorisation link. This is the OAuth client identifier |
| **App key** | The token exchange |
| **App secret** | The token exchange |

Copy all three. Do not paste the secret into the conversation, an email, or a file in the
repository. **Corrected 23 September: this step previously asked for two values and omitted
the Service ID, which made step 4 impossible to follow.** See A23.2.

## Step 2. Set the callback URL on the app

Still on the app page, find **Callback URL** or **Redirect URL** and set it to the address
the seller returns to after approving. Until the application is deployed, use:

```
http://localhost:3000/connections/tiktok/callback
```

That path matches `tiktokCallback` in `api/openapi.yaml`, so the contract and the app agree.
When the application has a real address the value changes to that host and the same path.

## Step 3. Put the two values into the environment

Open the cloud environment you are using, the same dialog where the allowed domains were
set, and add to **Environment variables**:

```
TIKTOK_APP_KEY=<the app key>
TIKTOK_APP_SECRET=<the app secret>
```

The dialog warns that these are visible to anyone using the environment. That is acceptable
while it is only you, and it is far better than a transcript.

## Step 4. Authorise your shop

**Corrected 23 September. The domain matters and the wrong one was used all day.** There are
two authorisation links and they do different things:

```
seller, your own shop    https://services.tiktokshop.com/open/authorize?service_id=<service id>
partner, TAP             https://partner.tiktokshop.com/open/authorize?service_id=<service id>
```

MyShopEdge is a seller-facing product, so **use the `services.tiktokshop.com` link**. Every
attempt on 23 September went through the partner link and every one of them returned a
sandbox test shop in Indonesia rather than the real British shop. See A23.1.

Open that link. It asks you to sign in as the seller and shows the permissions the app is
requesting.

Approve it. TikTok then redirects you to the callback URL from step 2, and the address bar
carries a parameter:

```
http://localhost:3000/connections/tiktok/callback?code=ROW_xxxxxxxxxxxx
```

The page will fail to load, because nothing is running on localhost yet. **That does not
matter.** The value in the address bar is what you need.

Copy that `code` value. It is single use and expires in **thirty minutes**, which is the
figure on TikTok's own page. This runbook previously said "within minutes", which was
imprecise in the direction that makes people rush.

## Step 5. Put the code into the environment, then start a new session

Add a third variable to the same box:

```
TIKTOK_AUTH_CODE=<the code from the address bar>
```

Then start a **new session**. Environment variables are injected when a session begins, not
during one, which is why an existing session cannot see them however long it waits.

Say to the new session: *connect the shop*.

## What happens next, without you

**None of this is built.** Checked 23 September: no file in this repository calls a TikTok
host. The exchange described below is what the code will do once it exists, and A23 holds
the facts needed to write it.

The exchange is `GET https://auth.tiktok-shops.com/api/v2/token/get`, which is a different
host from every other call, with `app_key`, `app_secret`, `auth_code` and
`grant_type=authorized_code`. That spelling is deliberate and TikTok's page warns against
correcting it. The access token lasts seven days, so a refresh has to be scheduled or the
connection stops working a week later. Then
`GET /authorization/202309/shops` with the `x-tts-access-token` header. That returns
the shop's `id`, `name`, `region`, `seller_type` and, most importantly, its **cipher**.

The cipher is the value every later finance call needs. It is written to the `shops` row
with the tokens, and nothing about it appears in the conversation.

Then three questions that have been open for two days get answered by measurement rather
than assumption:

1. **How far back do the statements go.** A16.2 promises twenty-four months on every plan
   and A17.3 established that TikTok's specification states no limit either way. One call
   to `/finance/202309/statements` with `statement_time_ge` set two years back was made on
   23 September and returned nothing.

   **That call settles nothing, and this step is corrected because of it.** The shop it ran
   against had no trading history, so an empty result says nothing about what TikTok
   retains. Only a shop that has been trading for more than two years can answer this. See
   A19.3. Do not read an empty statement list from a new or test shop as an answer.
2. **What a settlement export actually calls its columns.** A8 section 3.5 has carried this
   as open since the terminology standard was written, because the labels are unpublished.
3. **Whether the invoice number is reachable**, which decides whether the reconciliation
   identifier works.

## If something goes wrong

**The authorisation page rejects the callback URL.** It must match what is registered on
the app exactly, including the scheme and any trailing slash.

**The code has expired.** Repeat step 4. They are short lived by design.

**The new session still cannot see the variables.** Check you edited the environment the
session is actually using. This account has had one environment, named Default, and a
session started before the edit will not have them.

**Any call returns 36004 or an authorisation error.** The token is bound to one shop and
one app. Re-authorising from step 4 issues a fresh one.

## What this runbook does not cover

Refreshing the token when it expires, which the service does on its own once the connection
exists, and disconnecting, which is S29 and is not built yet.
