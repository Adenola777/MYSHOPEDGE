# Action 13. The stack, and the client contract

Decided 22 September 2026. The five rules in 13.2 are non-negotiable for the life of this
build. Everything else in this document is a choice that may be revisited.

## 13.1 The stack

| Layer | Choice |
|---|---|
| Language | TypeScript, everywhere a client or a server runs |
| Web application | Next.js App Router, React, deployed on Vercel |
| API | REST over HTTPS, described by `api/openapi.yaml`, OpenAPI 3.1 |
| Database | Neon PostgreSQL 16, `aws-eu-west-2` |
| Identity | Neon Auth on Stack Auth |
| Object storage | Vercel Blob, `lhr1`, private |
| Payments | Stripe |
| Native applications, when they come | React Native with Expo, consuming the same API |

Python remains in the repository for the payload generator and the ingester. Those are test
tooling and they never run in production. No production path is written in Python.

## 13.2 The five rules

These exist so that a native application is an addition rather than a rewrite. A product
that puts its arithmetic in the web layer has to rebuild that arithmetic for every new
client, and the two copies then disagree. This product cannot afford figures that disagree.

**1. There is one API contract, and it is `api/openapi.yaml`.** Every client reads from it.
TypeScript types are generated from it and are never written by hand. A change to a response
shape happens in the specification first and in the code second.

**2. No client computes money.** Every figure a seller sees arrives from the API already
calculated, with its period, its basis and its confidence attached. A client formats and
displays. It does not add, allocate, convert or round.

**3. Money is an integer of minor units with its currency beside it, in every language and
at every layer.** No floating point number ever holds an amount. A figure of £20.84 is
`{ "amount_minor": 2084, "currency": "GBP" }` in the API, `2084` in TypeScript, and
`amount_minor bigint` in PostgreSQL.

**4. The web application has no privileged path.** It reaches the database through the same
API as any other client, under the same authentication and the same row level security. No
server component queries PostgreSQL directly for a figure that an endpoint already returns.

**5. Secrets live only on the server.** The Stripe secret key, the TikTok `app_secret`, the
database connection string and the Stack Auth server key are read from environment variables
inside server code. None of them appears in a client bundle, a repository file, or a
`NEXT_PUBLIC_` variable.

## 13.3 What this buys

A native application later needs new screens and nothing else. It authenticates the same
way, calls the same endpoints, receives the same integers and renders them. The calculator
in section 8.5 of the terminology standard is a response shape, `MoneyView`, so a phone
renders the same lines in the same order as the browser without a second implementation.

## 13.4 What it costs

Server components in Next.js can query a database directly and it is often faster to write
that way. Rule 4 forbids it. The cost is real and it is accepted, because the alternative is
two implementations of the same figure.
