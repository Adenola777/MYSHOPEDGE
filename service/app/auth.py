"""Turning a request into an account.

Neon Auth provisions **Stack Auth** on this project, which issues the tokens. That is the
`auth_provider` value in the project's own Neon Auth configuration, not an inference from a
documentation page. This service never sees a password, never issues a token, and never
stores one. The only thing about a seller's
identity that reaches our database is ``accounts.auth_subject``.

The chain, and the rule that holds it together.

    1. The request carries a bearer JWT.
    2. This module verifies the signature against the provider's published keys, and checks
       issuer, audience and expiry.
    3. The ``sub`` claim of the verified token is the only identity input accepted.
    4. resolve_account turns that subject into an account id.
    5. Every query then runs inside db.tenant(account_id).

The rule is step 3. An account id is never read from a header, a body, a query string or a
cookie, because anything a client can set is something a client can forge. The subject is
taken from the token after verification and from nowhere else.

**The algorithm, and how it was got wrong twice in one day.**

This module first verified ES256 and RS256. On 23 September I narrowed it to EdDSA,
believing Neon Auth provisions Better Auth, and rewrote the tests to sign EdDSA. Every case
passed. Every real token would have been refused, because the provider signs ES256.

The provider's own JWKS, fetched the same evening from the `jwks_url` in this project's
Neon Auth configuration and recorded at `tests/fixtures/provider_jwks_2026-09-23.json`::

    {"kty":"EC","crv":"P-256","alg":"ES256","kid":"LhlLhcwrLjOE", ...}

Both mistakes had the same shape. A vendor page was read, the code was changed to match it,
and the test was changed to match the code. A test that generates its own key can only
confirm that the code agrees with the test. The configuration was one call away on both
occasions.

The test now asserts `ALGORITHMS` against that recorded JWKS, so changing this value
without refetching the provider's keys fails in either direction.

**The email.** This module read ``claims["email"]`` and refused the seller without it, on
the strength of Neon's overview page saying managed tokens carry "no custom claims". The
JWT plugin page contradicts that and lists the payload: ``iat``, ``name``, ``email``,
``emailVerified``, ``image``, ``createdAt``, ``updatedAt``, ``role``, ``banned``,
``banReason``, ``banExpires``, ``id``, ``sub``, ``exp``, ``iss`` and ``aud``. The email is
there.

Two pages of the same vendor's documentation disagree, so this module trusts neither and
takes the claim when it is present and ``neon_auth.users_sync`` when it is not. That is
correct whichever page is right, and it survives the provider changing its mind.

``emailVerified`` matters more than ``email``. An unverified address is a claim by whoever
signed up, not a fact, and a financial product must not attach a seller's payout history to
an address nobody has proved they control. Where the claim is present and false, the seller
is refused until they verify.

**Issuer and audience are configured, not derived.** They used to default to the origin of
the Neon Auth URL, which came from the same page that named the wrong provider. What Stack
Auth puts in ``iss`` and ``aud`` has never been observed here, because no real token has
ever reached this service. Guessing would mean refusing every valid token, or accepting one
issued for somebody else. So ``NEON_AUTH_AUDIENCE`` and ``NEON_AUTH_ISSUER`` must both be
set, read off a real token once, and the service refuses to verify until they are.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import urlsplit
from uuid import UUID

import jwt
from fastapi import Request

from .db import create_account_id, lookup_identity, resolve_account_id
from .problems import Problem

# ES256 and nothing else. Listing more algorithms than the provider uses is not tolerance,
# it is an invitation: every additional algorithm is another verification path an attacker
# can aim a token at.
#
# This value has now been wrong twice, in both directions, on the same day. It is ES256
# because the provider's own JWKS says so, fetched 23 September 2026 from the URL in this
# project's Neon Auth configuration and recorded verbatim at
# tests/fixtures/provider_jwks_2026-09-23.json:
#
#     {"kty":"EC","crv":"P-256","alg":"ES256","kid":"LhlLhcwrLjOE", ...}
#
# Do not change this line on the strength of a documentation page. A test asserts it
# against that fixture, so a change here without a refetch fails.
ALGORITHMS = ["ES256"]


@dataclass(frozen=True)
class Account:
    id: UUID
    email: str
    name: str | None
    subject: str


def _origin_of(url: str) -> str:
    """The scheme and host, with no path.

    Issuer and audience are both the ORIGIN of the Neon Auth URL, while the JWKS lives
    under its full path. Deriving one from the other by string concatenation would produce
    an issuer with `/neondb/auth` on the end, and every token would then be refused for the
    wrong issuer. The difference is one line and a day of confusion.
    """
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}"


def _base_url() -> str | None:
    """The Neon Auth base URL, however the environment happens to supply it.

    The Neon-managed Vercel integration injects NEON_AUTH_BASE_URL. VITE_NEON_AUTH_URL is
    the same value under the name the browser build uses. Both are read so the service
    works under the integration without anybody hand-setting a variable.
    """
    return os.environ.get("NEON_AUTH_BASE_URL") or os.environ.get("VITE_NEON_AUTH_URL")


@lru_cache(maxsize=1)
def _jwks_client() -> jwt.PyJWKClient:
    """The JWKS URL is configured, never derived.

    It used to be built by appending `/.well-known/jwks.json` to the Neon Auth base URL.
    That is wrong for this project. The real URL is on a different host entirely:

        https://api.stack-auth.com/api/v1/projects/<project id>/.well-known/jwks.json

    which `get_neon_auth_config` reports and which no amount of string concatenation from
    a Neon hostname would ever produce. Deriving it meant every token was checked against
    a URL that does not exist, and the failure would have looked like a network problem
    rather than a configuration mistake.
    """
    url = os.environ.get("NEON_AUTH_JWKS_URL")
    if not url:
        raise Problem(
            503, "auth_unconfigured",
            "Authentication is not configured. Set NEON_AUTH_JWKS_URL to the jwks_url "
            "from the project's Neon Auth configuration.",
        )
    # The client caches the keys and refetches when it meets a key id it does not hold,
    # which is what makes provider key rotation a non-event.
    return jwt.PyJWKClient(url, cache_keys=True, lifespan=600)


def verify(token: str) -> dict:
    """Verifies the token and returns its claims. Raises rather than returning None."""
    try:
        signing_key = _jwks_client().get_signing_key_from_jwt(token)
    except Exception as exc:
        raise Problem(401, "token_unverifiable", "Sign in again.") from exc

    # Issuer and audience are configured and never guessed.
    #
    # These used to default to the origin of the Neon Auth URL, on the strength of a
    # documentation page describing a different provider from the one this project
    # actually uses. What Stack Auth puts in `iss` and `aud` has never been observed here,
    # because no real token has ever reached this service. Guessing would mean either
    # refusing every valid token or, worse, accepting one issued for somebody else.
    #
    # So the service refuses to verify until both are supplied. Read them off a real token
    # once, with jwt.decode(token, options={"verify_signature": False}), and set them.
    audience = os.environ.get("NEON_AUTH_AUDIENCE")
    issuer = os.environ.get("NEON_AUTH_ISSUER")
    if not audience or not issuer:
        raise Problem(
            503, "auth_unconfigured",
            "Authentication is not configured. Set NEON_AUTH_AUDIENCE and "
            "NEON_AUTH_ISSUER from a real token's aud and iss claims.",
        )

    try:
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=ALGORITHMS,
            audience=audience,
            issuer=issuer,
            # Every one of these is checked. require forces the claim to be present at all,
            # because a missing exp is otherwise treated as a token that never expires.
            options={
                "require": ["exp", "sub"],
                "verify_signature": True,
                "verify_exp": True,
                "verify_aud": audience is not None,
                "verify_iss": issuer is not None,
            },
        )
    except jwt.ExpiredSignatureError as exc:
        # Managed tokens last fifteen minutes, so this is an ordinary path rather than an
        # edge case. A seller sitting through the first sync will meet it. S37 covers it.
        raise Problem(401, "token_expired", "Your session has expired. Sign in again.") from exc
    except jwt.InvalidTokenError as exc:
        raise Problem(401, "token_invalid", "Sign in again.") from exc


def require_account(request: Request) -> Account:
    """The dependency every authenticated endpoint takes."""
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise Problem(401, "unauthenticated", "Sign in to continue.")

    claims = verify(token)
    subject = claims["sub"]

    # Present and false is a refusal. Absent is not, because the claim's presence depends on
    # which of the provider's two documentation pages is currently right, and an absent
    # claim is checked against users_sync further down instead.
    if claims.get("emailVerified") is False:
        raise Problem(
            403,
            "email_unverified",
            "Verify your email address with your sign-in provider, then come back.",
        )

    account_id = resolve_account_id(subject)
    if account_id is not None:
        email = claims.get("email") or ""
        name = claims.get("name")
        if not email:
            identity = lookup_identity(subject)
            if identity:
                email, name = identity[0] or "", identity[1] or name
        return Account(id=account_id, email=email, name=name, subject=subject)

    # A seller can hold a valid token and have no account row, because the provider and this
    # database are separate systems. Ruled 22 September 2026: create the account on the
    # first verified sign in, because the alternative leaves that seller authenticated with
    # no way in.
    email = claims.get("email")
    name = claims.get("name")

    if not email:
        identity = lookup_identity(subject)
        if identity is None:
            # The provider has issued a token for a user it has not yet synced into the
            # database. This is a race rather than a rejection, and it clears on its own,
            # so the seller is asked to try again rather than told they cannot be set up.
            raise Problem(
                503,
                "identity_syncing",
                "We are still setting up your account. Try again in a moment.",
            )
        email, synced_name = identity
        name = name or synced_name

    if not email:
        # The row exists and carries no email address. That is a real dead end rather than
        # a timing problem, and it is the only case that should refuse the seller outright.
        raise Problem(
            403,
            "email_required",
            "Your account has no verified email address, so we cannot set up your shop.",
        )

    try:
        account_id = create_account_id(subject, email, name)
    except Exception as exc:
        if "email_already_linked_to_another_identity" in str(exc):
            raise Problem(
                409,
                "email_already_linked",
                "That email address already belongs to an account created with a "
                "different sign-in method. Use the original method, then link this one.",
            ) from exc
        raise

    return Account(id=account_id, email=email, name=name, subject=subject)
