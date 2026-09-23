# Action 25. The assumption audit, and the one it found in my own work

23 September 2026, evening. Adenola asked for rule 7 to be reinforced and for everything
built so far to be audited so that no assumption sits in it. The audit found four things.
The first would have stopped every seller signing in, and I had introduced it that
afternoon.

## 25.1 The provider is Stack Auth and it signs ES256

One call to the project's own Neon Auth configuration:

```
"auth_provider": "stack",
"jwks_url": "https://api.stack-auth.com/api/v1/projects/f1762e29-.../.well-known/jwks.json"
```

Fetching that URL returns two keys, both ES256 over P-256. Recorded verbatim at
`service/tests/fixtures/provider_jwks_2026-09-23.json`.

`auth.py` read `ALGORITHMS = ["EdDSA"]`. Every real token would have been refused.

**The sequence matters more than the fault.** The module originally verified ES256 and
RS256. On the afternoon of 23 September I read Neon's documentation about Managed Better
Auth, concluded the provider signs EdDSA over Ed25519, rewrote the module, rewrote the test
to generate an Ed25519 key, and watched nine cases pass. I then wrote that episode into
`CLAUDE.md` as fault number two, describing exactly this failure mode:

> Authentication verified the wrong signing algorithm for a day, and its tests passed
> because the fixtures were generated from the same assumption.

And I had just done it again, in the opposite direction, on the same file, on the same day.
Rule 7 was written three hours after the change that broke it. The configuration was one
tool call away throughout.

A14 was "corrected" from Stack Auth to Better Auth on the same reasoning. The original
statement was right. A14, the README and `CLAUDE.md` are all corrected.

## 25.2 Three further defects in the same module

**The JWKS URL was derived, and derivation cannot reach the truth.** `_jwks_client()` built
it by appending `/.well-known/jwks.json` to the Neon Auth base URL. The real URL is on
`api.stack-auth.com` with a Stack Auth project id in the path. No amount of concatenation
from a Neon hostname produces it. It is now configured and the service refuses to start
verifying without it.

**Issuer and audience were guessed.** They defaulted to the origin of the Neon Auth URL,
from the same page that named the wrong provider. What Stack Auth puts in `iss` and `aud`
has never been observed here, because no real token has ever reached this service. Guessing
means either refusing every valid token or, worse, accepting one issued for somebody else.
Both must now be set explicitly, read off a real token once.

**The 403 on an unverified email is unverified.** The live configuration has
`verify_email_on_sign_up: false` and `email_password.enabled: false`, with GitHub and
Google as shared OAuth providers. Whether Stack Auth emits an `emailVerified` claim at all
is unknown. The code refuses a seller when the claim is present and false, which is safe
whether or not the claim exists, so it stays. It is recorded here as untested rather than
left to look deliberate.

## 25.3 No handler had ever been invoked

Eight routes served and not one had been called. `test_contract_conformance.py` imports the
application and reads the schema FastAPI derives from the handlers, which exercises their
declarations and never their bodies. `test_auth_verification.py` calls `verify()` directly.

Every "Verified against the seeded seller on the development branch" line in `records.py`,
`settlements.py` and `products.py` refers to SQL I ran by hand. The handler around that SQL
had never executed.

That is how 25.1 survived. The parts that were checked were checked carefully, and the
parts nobody called were assumed to work.

`service/tests/test_handlers_smoke.py` now calls every route with canned rows, and asserts
the behaviour each one promises: settlements keeps the reserve's sign, records distinguishes
the total from the page sum, and a product with no cost returns a null `kept` with a reason
rather than a figure that reads as profit.

It is explicit about its limits. The SQL never runs, so a wrong query returning plausible
rows passes here and fails in production. It sits alongside the checks against the real
database rather than replacing them.

## 25.4 A stale count

`records.py` claimed 118 ledger entries. The database holds 119. The other three claims in
that sentence were right: seventeen type and category combinations, and
`platform_adjustment`, `unmapped_fee` and `reserve_withheld` each present.

Small, and worth recording because it is the same species as A20.8. A figure written once
and never recounted becomes a claim rather than a measurement.

## 25.5 What now guards against a repeat

| Guard | Catches |
|---|---|
| `test_auth_verification.py` asserts `ALGORITHMS` against the recorded JWKS | Somebody changing the algorithm on the strength of a document |
| `check_provider_jwks.py` refetches and compares | The provider rotating to a different algorithm, which is otherwise a silent outage |
| `test_handlers_smoke.py` calls every route | A handler that cannot execute, or that stops keeping a promise |
| `check_maps_against_real.py` measures the maps against a real payload | Coverage drifting from what TikTok actually sends |
| `schema/checks/ret7_product_reconciliation.sql` | The product table ceasing to reconcile to the shop figure |
| `check_contract_against_schema.py` compares the contract's properties to the columns | A field the contract serves that no table can hold. Added 23 September after `Shop` was found to declare two such fields. See A26 |

Four of those five did not exist this morning.

## 25.6 The rule, restated

Rule 7 in `CLAUDE.md` says facts only, and lists five things it means in practice. The
audit suggests one addition, which is now in that rule:

**A vendor's documentation is not a fact about this project.** It describes what the vendor
generally does. What this project actually runs is in its own configuration, and reading
that costs one call. Twice today a documentation page was taken as evidence about this
installation, and both times the installation said something different.
