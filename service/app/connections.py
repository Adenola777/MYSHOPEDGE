"""Connecting a TikTok shop.

Two endpoints. `POST /connections/tiktok/authorize` issues the link that sends a seller to
TikTok, and `GET /connections/tiktok/callback` receives them on the way back.

Every constant here comes from A23, which was read from TikTok's own authorisation page on
23 September 2026 and records nothing inferred. The three that are easy to get wrong:

  * The seller link is `services.tiktokshop.com`, not `partner.tiktokshop.com`. A23.1. Every
    authorisation attempt on 23 September used the partner host and every one of them came
    back with a sandbox shop in Indonesia. MyShopEdge is seller facing.
  * The token exchange is `auth.tiktok-shops.com`, which is not the host every other call
    goes to. A23.3.
  * `grant_type` is `authorized_code`. Not `authorization_code`. A23.3 records TikTok's own
    warning about this, and anybody who knows OAuth will correct it once and break it.

WHAT IS NOT FINISHED, AND WHY
=============================

The callback cannot complete. `GetAuthorizedShops` is a signed call and this project does
not hold TikTok's signing algorithm as a fact. A23.6 says so explicitly, a search of the
whole pack for `hmac`, `sha256` and `signature` returns nothing, and TikTok's documentation
pages do not render for a fetch. `_authorized_shops` is the single place that gap lives and
it raises rather than guessing.

Guessing it would be the A25 failure again: an assumption, a test written from the same
assumption, and green results that mean nothing. A signature is either right or the request
is refused, so a wrong one costs an afternoon; a wrong one that happens to be accepted for
some calls and not others costs much more.

Everything that does not depend on signing is finished and works: the state, the link, the
code exchange, the seller type assertion, and the token storage.
"""

from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

import httpx
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from .auth import Account, require_account
from .db import tenant, unscoped
from .problems import Problem

router = APIRouter(tags=["Connection"])

# A23.1. The seller authorises their own shop, so this is the seller link.
AUTHORIZE_BASE = "https://services.tiktokshop.com/open/authorize"

# A23.3 and A23.4. Both on the same host for every market.
TOKEN_URL = "https://auth.tiktok-shops.com/api/v2/token/get"
REFRESH_URL = "https://auth.tiktok-shops.com/api/v2/token/refresh"

# The contract states ten minutes. TikTok allows the auth code thirty (A23.4), so the state
# is the shorter of the two and is therefore what expires first. That is the right way
# round: our own window should close before the vendor's.
STATE_TTL = timedelta(minutes=10)

# A23.3. 1 is a creator, 3 a partner, 4 and 5 Global Selling. Anything but 0 means the
# seller came through the wrong authorisation link, which is the mistake in A23.1, and the
# resulting token will not read a GB shop's finances.
SELLER_USER_TYPE = 0

HTTP_TIMEOUT = 20.0


def _config(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        # Named rather than generic, because the three are obtained from different places
        # in Partner Center and A23.2 records that service_id and app_key are routinely
        # confused for each other.
        raise Problem(
            503, "tiktok_unconfigured",
            "Connecting a TikTok shop is not configured on this deployment.",
        )
    return value


def _digest(state: str) -> str:
    """The state is stored as its SHA-256 and never in the clear. See migration 0021."""
    return hashlib.sha256(state.encode("utf-8")).hexdigest()


def _safe_return_to(value: str | None) -> str | None:
    """An absolute path on this application, or nothing.

    The contract says this must be an allow-listed MyShopEdge path and that an open
    redirect here would be an account takeover. It is checked on the way in, when there is
    somebody to tell, rather than on the way out.

    One leading slash and no second one. `//evil.example` is a protocol-relative URL that
    most clients follow to another host, and it passes a naive "starts with /" check, which
    is exactly how this mistake is usually made. A backslash is refused because some clients
    normalise it to a slash.
    """
    if value is None or value == "":
        return None
    if not value.startswith("/") or value.startswith("//") or "\\" in value:
        raise Problem(
            400, "return_to_not_allowed",
            "return_to must be a path on MyShopEdge beginning with a single slash.",
        )
    return value


class AuthorizeRequest(BaseModel):
    return_to: str | None = None


class AuthorizeOut(BaseModel):
    authorization_url: str
    state: str
    expires_at: datetime


@router.post("/connections/tiktok/authorize", status_code=201, response_model=AuthorizeOut)
def authorize_tiktok(
    account: Annotated[Account, Depends(require_account)],
    body: AuthorizeRequest | None = None,
) -> AuthorizeOut:
    """Issue the link that sends this seller to TikTok. Traces CON-1."""
    service_id = _config("TIKTOK_SERVICE_ID")
    return_to = _safe_return_to(body.return_to if body else None)

    # 32 bytes from the system CSPRNG. The value must be unguessable, because anyone who can
    # guess a live state can complete a connection the seller did not start.
    state = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + STATE_TTL

    # Written inside the seller's own scope, so row level security binds it to them. The
    # policy's WITH CHECK refuses a row claiming another account, proven on the development
    # branch on 23 September.
    with tenant(account.id) as conn:
        conn.execute(
            "insert into tiktok_auth_state "
            "(state_sha256, account_id, return_to, expires_at) values (%s, %s, %s, %s)",
            (_digest(state), str(account.id), return_to, expires_at),
        )

    return AuthorizeOut(
        authorization_url=f"{AUTHORIZE_BASE}?service_id={service_id}&state={state}",
        state=state,
        expires_at=expires_at,
    )


def _exchange_code(code: str) -> dict[str, Any]:
    """Turn an auth code into tokens. A23.3.

    Unsigned. This call takes the app secret directly as a query parameter, which is TikTok's
    design rather than ours, and it is the reason this request must never be made from a
    browser and must never be logged with its parameters.
    """
    params = {
        "app_key": _config("TIKTOK_APP_KEY"),
        "app_secret": _config("TIKTOK_APP_SECRET"),
        "auth_code": code,
        "grant_type": "authorized_code",
    }
    try:
        response = httpx.get(TOKEN_URL, params=params, timeout=HTTP_TIMEOUT)
    except httpx.HTTPError:
        raise Problem(
            502, "tiktok_unreachable",
            "TikTok did not answer. Start the connection again.",
        )

    # The detail must never carry the code, the state or anything from params, because a
    # problem response is shown to the seller and is very likely to end up in a screenshot.
    if response.status_code != 200:
        raise Problem(400, "code_exchange_failed", "TikTok refused the authorisation.")

    body = response.json()
    if body.get("code") != 0:
        raise Problem(400, "code_exchange_failed", "TikTok refused the authorisation.")

    data = body.get("data") or {}
    if not data.get("access_token"):
        raise Problem(400, "code_exchange_failed", "TikTok refused the authorisation.")
    return data


def _authorized_shops(access_token: str) -> list[dict[str, Any]]:
    """GET /authorization/202309/shops.

    NOT IMPLEMENTED, and deliberately not attempted.

    This call is signed and the signing algorithm is not a fact this project holds. A23.6
    states that request signing was not covered by the page A23 was written from. A search
    of every document, every Python file and the API contract for `hmac`, `sha256` and
    `signature` returns nothing. TikTok's docv2 pages are a JavaScript application and do
    not render for a fetch. The bundled `tts-openapi-guide` and `tts-developer-onboarding-guide`
    skills both refer to signing without specifying it.

    Three ways to obtain it, in the order they are likely to work:

      1. Make any call through Partner Center's own API Testing Tool and read the signature
         it produces off the generated request. The tool signs on the caller's behalf, which
         is why the three successful calls in A19 needed no algorithm here.
      2. Read the signature page in Partner Center's documentation while signed in.
      3. TikTok's developer support.

    Until one of those happens this raises. It does not guess, and it does not borrow an
    implementation from a third-party SDK, because a third party's code is not the vendor's
    statement and rule 7 does not accept it.
    """
    raise Problem(
        503, "tiktok_signing_unimplemented",
        "The shop lookup is not available yet. Your authorisation was not stored.",
    )


class ConnectionResultOut(BaseModel):
    shop: dict[str, Any] | None = None
    accepted: bool
    rejection_reason: str | None = None
    return_to: str | None = None


@router.get("/connections/tiktok/callback", response_model=ConnectionResultOut)
def tiktok_callback(
    code: Annotated[str, Query()],
    state: Annotated[str, Query()],
) -> ConnectionResultOut:
    """Receive the seller back from TikTok. Traces CON-1.

    This endpoint carries `security: []` in the contract. It arrives by browser redirect
    with no bearer token, so the state is the only thing that says whose connection this is.
    """
    # One statement reads and spends it. An unknown state, a spent state and an expired
    # state are indistinguishable here, which is deliberate: telling them apart tells
    # somebody guessing which guesses were close.
    with unscoped() as conn:
        row = conn.execute(
            "select account_id, return_to from consume_tiktok_auth_state(%s)",
            (_digest(state),),
        ).fetchone()

    if row is None:
        raise Problem(
            400, "state_invalid",
            "That connection link is no longer valid. Start the connection again.",
        )

    account_id, return_to = row[0], row[1]

    data = _exchange_code(code)

    # A23.3. Asserted rather than ignored, because anything but 0 means the seller went
    # through the wrong authorisation link and the token will not read a shop's finances.
    if data.get("user_type") != SELLER_USER_TYPE:
        raise Problem(
            400, "not_a_seller_account",
            "That TikTok account is not a Shop seller account.",
        )

    # Everything past this point needs the signed shop lookup, because shops.tiktok_shop_id
    # is NOT NULL and the token response does not carry a shop id. The token response gives
    # seller_name, seller_base_region, open_id and granted_scopes, and none of those identify
    # the shop. So there is nothing to write until _authorized_shops works, and writing a
    # partial row would leave a shop that can never be reconciled.
    _authorized_shops(data["access_token"])

    raise AssertionError("unreachable until _authorized_shops is implemented")
