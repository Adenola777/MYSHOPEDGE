"""Turning a request into an account.

Neon Auth provisions Stack Auth, which issues the tokens. This service never sees a
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
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from uuid import UUID

import jwt
from fastapi import Request

from .db import create_account_id, resolve_account_id
from .problems import Problem


@dataclass(frozen=True)
class Account:
    id: UUID
    email: str
    name: str | None
    subject: str


@lru_cache(maxsize=1)
def _jwks_client() -> jwt.PyJWKClient:
    url = os.environ.get("STACK_JWKS_URL")
    if not url:
        project = os.environ.get("STACK_PROJECT_ID")
        if not project:
            raise Problem(503, "auth_unconfigured", "Authentication is not configured.")
        url = f"https://api.stack-auth.com/api/v1/projects/{project}/.well-known/jwks.json"
    # The client caches the keys and refetches when it meets a key id it does not hold,
    # which is what makes provider key rotation a non-event.
    return jwt.PyJWKClient(url, cache_keys=True, lifespan=600)


def verify(token: str) -> dict:
    """Verifies the token and returns its claims. Raises rather than returning None."""
    try:
        signing_key = _jwks_client().get_signing_key_from_jwt(token)
    except Exception as exc:
        raise Problem(401, "token_unverifiable", "Sign in again.") from exc

    audience = os.environ.get("STACK_PROJECT_ID")
    issuer = os.environ.get("STACK_ISSUER")

    try:
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256", "RS256"],
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

    account_id = resolve_account_id(subject)

    if account_id is None:
        # A seller can hold a valid token and have no account row, because the provider and
        # this database are separate systems. Ruled 22 September 2026: create the account on
        # the first verified sign in, because the alternative leaves that seller
        # authenticated with no way in.
        email = claims.get("email")
        if not email:
            raise Problem(
                403,
                "email_required",
                "Your account has no verified email address, so we cannot set up your shop.",
            )
        try:
            account_id = create_account_id(subject, email, claims.get("name"))
        except Exception as exc:
            if "email_already_linked_to_another_identity" in str(exc):
                raise Problem(
                    409,
                    "email_already_linked",
                    "That email address already belongs to an account created with a "
                    "different sign-in method. Use the original method, then link this one.",
                ) from exc
            raise

    return Account(
        id=account_id,
        email=claims.get("email", ""),
        name=claims.get("name"),
        subject=subject,
    )
