# Action 13. The stack, and the client contract

Decided 22 September 2026, revised the same evening. The five rules in 13.2 are
non-negotiable for the life of this build. Everything else is a choice that may be
revisited.

## 13.1 The stack

| Layer | Choice |
|---|---|
| API and business logic | Python, FastAPI |
| Web application | Next.js App Router, React, written in JavaScript |
| Type checking, web | JSDoc annotations, checked against generated declarations |
| Database | Neon PostgreSQL 16, `aws-eu-west-2` |
| Identity | Neon Auth on Stack Auth |
| Object storage | Vercel Blob, `lhr1`, private |
| Payments | Stripe |
| Hosting, web | Vercel |
| Hosting, API and the TikTok poller | A long-running Python service, not a serverless function |
| Native applications, when they come | React Native with Expo, consuming the same API |

TypeScript is not used. The web application is JavaScript with JSDoc annotations, which
gives editor and build checking without a TypeScript source file anywhere.

One file is a TypeScript declaration file by necessity. `web/src/lib/api-types.d.ts` is
generated from `api/openapi.yaml` and contains type information only, with no runtime code
and no program to compile. JSDoc comments refer to it so that a change to a response shape
is caught before a seller sees it. If that file is unwanted, the alternative is to generate
JSON Schema from the same contract and validate responses at runtime, which costs
performance and finds the fault later.

**Why Python owns the API.** The allocation and fee mapping already exist in Python in
`testdata/ingest.py`, where they are proved by the five A12 assertions. Under this stack
that code becomes the implementation rather than being rewritten in another language and
proved a second time. It also gives the TikTok poller a home. TikTok publishes no financial
webhook, so the money side is poll-only, and loading twelve months of orders is a long
job that a serverless function cannot finish.

## 13.2 The five rules

These exist so that a native application is an addition rather than a rewrite. A product
that puts its arithmetic in the web layer has to rebuild that arithmetic for every new
client, and the two copies then disagree. This product cannot afford figures that disagree.

**1. There is one API contract, and it is `api/openapi.yaml`.** Every client reads from it.
The web declarations are generated from it and are never written by hand. FastAPI validates
its responses against it. A change to a response shape happens in the specification first
and in the code second.

**2. No client computes money.** Every figure a seller sees arrives from the API already
calculated, with its period, its basis and its confidence attached. A client formats and
displays. It does not add, allocate, convert or round. The plan prices on the sign-up
screen are served by `GET /billing/plans` for this reason, not held in the page.

**3. Money is an integer of minor units with its currency beside it, in every language and
at every layer.** No floating point number ever holds an amount. A figure of £20.84 is
`{"amount_minor": 2084, "currency": "GBP"}` in the API, an `int` in Python, a `number` in
JavaScript, and `amount_minor bigint` in PostgreSQL. In Python, any amount that passes
through a decimal calculation uses `decimal.Decimal` and is converted to an integer before
it leaves the function.

**4. The web application has no privileged path.** It reaches the database only through the
API, under the same authentication and the same row level security as any other client. No
Next.js server component queries PostgreSQL.

**5. Secrets live only on the server.** The Stripe secret key, the TikTok `app_secret`, the
database connection string and the Stack Auth server key are read from environment
variables inside the Python service. None appears in a client bundle, a repository file, or
a `NEXT_PUBLIC_` variable.

## 13.3 What this costs

Two deployments instead of one. The web application deploys to Vercel and the API deploys
to a host that can run a process. That is more to operate than a single Next.js app, and it
is accepted because the poller needs it regardless of language.

A second consequence is that the web application cannot call the database for a figure that
is quicker to fetch directly. Rule 4 forbids it. The cost is real and it is accepted,
because the alternative is two implementations of the same figure.
