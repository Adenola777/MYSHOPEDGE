"""Turning a request into an account.

Neon Auth provisions Better Auth, which issues the tokens. This service never sees a
password, never issues a token, and never stores one. The only thing about a seller's
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

Two corrections made on 23 September 2026, both of which would have stopped every sign in.

**The algorithm.** This module verified ES256 and RS256. Neon Auth signs EdDSA over
Ed25519, which the published JWKS states plainly::

    {"alg":"EdDSA","crv":"Ed25519","kty":"OKP","kid":"54b08b58-..."}

An Ed25519 signature matches neither of the algorithms that were listed, so every real
token would have been refused as unverifiable. The original tests passed because they were
signed with the same wrong assumption, which is a test confirming a belief rather than
checking a fact.

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

Configuration, from the same page. Issuer and audience are both the origin of the Neon Auth
URL, with no path, for example ``https://ep-xxxx.neonauth.c-2.eu-west-2.aws.neon.tech``.
Access tokens last fifteen minutes.
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

# EdDSA and nothing else. Listing more algorithms than the provider uses is not tolerance,
# it is an invitation: every additional algorithm is another verification path an attacker
# can aim a token at.
ALGORITHMS = ["EdDSA"]


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
    url = os.environ.get("NEON_AUTH_JWKS_URL")
    if not url:
        base = _base_url()
        if not base:
            raise Problem(503, "auth_unconfigured", "Authentication is not configured.")
        url = base.rstrip("/") + "/.well-known/jwks.json"
    # The client caches the keys and refetches when it meets a key id it does not hold,
    # which is what makes provider key rotation a non-event.
    return jwt.PyJWKClient(url, cache_keys=True, lifespan=600)


def verify(token: str) -> dict:
    """Verifies the token and returns its claims. Raises rather than returning None."""
    try:
        signing_key = _jwks_client().get_signing_key_from_jwt(token)
    except Exception as exc:
        raise Problem(401, "token_unverifiable", "Sign in again.") from exc

    # Both default to the origin of the Neon Auth URL, which is what the provider puts in
    # iss and aud. Under the Neon-managed Vercel integration that means the only variable
    # anyone has to set is the one the integration sets itself.
    base = _base_url()
    default_origin = _origin_of(base) if base else None
    audience = os.environ.get("NEON_AUTH_AUDIENCE") or default_origin
    issuer = os.environ.get("NEON_AUTH_ISSUER") or default_origin

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
