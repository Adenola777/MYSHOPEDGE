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

SIGNING
=======

Read from TikTok's own "Sign your API request" and "Common parameters" pages on the evening
of 23 September 2026, through a browser, because those pages are a JavaScript application
and do not render for a plain fetch. That is the only reason the pack went a day without
them. They are public and need no sign in.

A27 records the steps and `_sign` implements them. The one that catches people is the
wrapping: the string is `secret + input + secret` and then that is HMACed with the secret as
the key, so the secret appears three times.

**Unverified against a live call.** The algorithm is implemented from the vendor's stated
steps and no request has yet been made with it. A signature is either accepted or refused,
so the first real call is the test. Until then treat `_sign` as written but not proven.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

import httpx
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
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

# Every other call goes here. Not the auth host above, and not the partner host.
API_BASE = "https://open-api.tiktokglobalshop.com"

# The only version of GetAuthorizedShops in TikTok's own OpenAPI. Confirmed against the
# bundled snapshot, which lists 202309 for shops, 202403 for DeauthorizeShop, and nothing
# else under /authorization for either.
SHOPS_PATH = "/authorization/202309/shops"

# What the MVP can read correctly. A shop outside these returns a different finance field
# set on every call, so it is connected, listed, and produces no figures. The contract
# provides exactly this outcome in ConnectionResult.
SUPPORTED_REGION = "GB"
SUPPORTED_SELLER_TYPE = "LOCAL"

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


def _sign(path: str, query: dict[str, str], body: bytes, secret: str) -> str:
    """TikTok's request signature. HMAC-SHA256, hex encoded.

    From TikTok's "Sign your API request" page, read 23 September 2026. The steps, in the
    order the page gives them:

      1. Take every query parameter except `sign` and `access_token`.
      2. Sort the keys alphabetically.
      3. Concatenate them as `{key}{value}`, with no separator of any kind.
      4. Put the request path on the front.
      5. Append the raw request body, unless Content-Type is multipart/form-data.
      6. Wrap the result: `secret + input + secret`.
      7. HMAC-SHA256 it, keyed with the same secret, and hex encode.

    Step 6 with step 7 is the part worth pausing on. The app secret is used twice as
    padding and again as the HMAC key, so it appears three times. It looks redundant and it
    is not optional: a signature built without the wrapping is a different string and is
    refused.

    `access_token` is excluded because for version 202309 and later it travels in the
    `x-tts-access-token` header and is not signed at all. The exclusion is kept for the
    legacy endpoints that still put it in the query string.
    """
    ordered = "".join(f"{k}{query[k]}" for k in sorted(query) if k not in ("sign", "access_token"))
    payload = f"{secret}{path}{ordered}".encode("utf-8") + body + secret.encode("utf-8")
    return hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def _signed_get(path: str, access_token: str, query: dict[str, str] | None = None) -> dict[str, Any]:
    """A signed GET against the open API host.

    `timestamp` is ten digits, in seconds. TikTok accepts it from five minutes ago to thirty
    seconds ahead and answers `36009004 Invalid timestamp` outside that, which is the error
    this project already met once by hand. A millisecond timestamp is refused, and it is the
    obvious mistake for anyone reaching for a language whose clock returns milliseconds.
    """
    app_key = _config("TIKTOK_APP_KEY")
    secret = _config("TIKTOK_APP_SECRET")

    params = dict(query or {})
    params["app_key"] = app_key
    params["timestamp"] = str(int(time.time()))
    params["sign"] = _sign(path, params, b"", secret)

    try:
        response = httpx.get(
            f"{API_BASE}{path}",
            params=params,
            headers={"x-tts-access-token": access_token, "content-type": "application/json"},
            timeout=HTTP_TIMEOUT,
        )
    except httpx.HTTPError:
        raise Problem(502, "tiktok_unreachable", "TikTok did not answer. Try again shortly.")

    body = response.json() if response.content else {}
    if response.status_code != 200 or body.get("code") != 0:
        # TikTok's own message is carried through, because at this point the seller has
        # already authorised and a bare "something went wrong" makes the failure
        # undiagnosable. It carries no secret: the token is in a header and the signature is
        # not echoed.
        raise Problem(
            502, "tiktok_call_failed",
            f"TikTok refused the request: {body.get('message') or response.status_code}",
        )
    return body.get("data") or {}


def _authorized_shops(access_token: str) -> list[dict[str, Any]]:
    """GET /authorization/202309/shops.

    Takes no query parameters of its own. Each shop carries `id`, `code`, `name`, `region`,
    `seller_type` and `cipher`, which is every column `shops` needs plus the cipher that
    `tiktok_connections` holds. The two columns migration 0020 added this evening, `code`
    and `seller_type`, are both in this response and neither had anywhere to go before it.
    """
    return _signed_get(SHOPS_PATH, access_token).get("shops") or []


def _encrypt(value: str) -> bytes:
    """AES-256-GCM, with the nonce on the front of the ciphertext.

    The key comes from `TIKTOK_TOKEN_KEY`, base64 of 32 bytes, and the service refuses to
    store a token without one rather than falling back to anything weaker.

    `key_version` is written as 1. That number means "the key in TIKTOK_TOKEN_KEY", and
    nothing yet maps a number to a key, because rotation needs somewhere to keep two keys at
    once and the service has no host. What is decided here is only the algorithm and where
    the key is read from. The register is still open, and migration 0021's comment on
    `key_version` says so.
    """
    raw = os.environ.get("TIKTOK_TOKEN_KEY")
    if not raw:
        raise Problem(
            503, "token_encryption_unconfigured",
            "Connecting a shop is not available on this deployment.",
        )
    key = base64.b64decode(raw)
    if len(key) != 32:
        raise Problem(
            503, "token_encryption_unconfigured",
            "Connecting a shop is not available on this deployment.",
        )
    nonce = secrets.token_bytes(12)
    return nonce + AESGCM(key).encrypt(nonce, value.encode("utf-8"), None)


KEY_VERSION = 1


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

    shops = _authorized_shops(data["access_token"])
    if not shops:
        raise Problem(
            400, "no_authorised_shop",
            "That TikTok account has no shop authorised for MyShopEdge.",
        )

    # The first shop. TikTok's own description of LOCAL is a seller with exactly one shop,
    # so for every seller the MVP supports this list has one entry. A CROSS_BORDER seller
    # can have several and is refused below whichever one is taken, so the choice cannot
    # change an outcome. A12.7 rules one shop per account.
    shop = shops[0]

    region = shop.get("region")
    seller_type = shop.get("seller_type")

    rejection_reason = None
    if region != SUPPORTED_REGION:
        rejection_reason = "region_unsupported"
    elif seller_type != SUPPORTED_SELLER_TYPE:
        rejection_reason = "seller_type_unsupported"
    accepted = rejection_reason is None

    now = datetime.now(timezone.utc)
    access_expires = now + timedelta(seconds=int(data.get("access_token_expire_in") or 0))
    refresh_expires = now + timedelta(seconds=int(data.get("refresh_token_expire_in") or 0))

    # Encrypted before the transaction opens, so a missing key fails before anything is
    # written rather than halfway through.
    enc_access = _encrypt(data["access_token"])
    enc_refresh = _encrypt(data.get("refresh_token") or "")
    enc_cipher = _encrypt(shop["cipher"]) if shop.get("cipher") else None

    # The shop row and its tokens are written together. A shop without its connection is a
    # shop that cannot be read from, and a connection without its shop has nothing to hang
    # on, so neither may exist alone.
    with tenant(account_id) as conn:
        row = conn.execute(
            "insert into shops (account_id, platform, tiktok_shop_id, tiktok_shop_code, "
            "  shop_name, region, seller_type, currency, connection_status) "
            "values (%s, 'tiktok_shop', %s, %s, %s, %s, %s, 'GBP', 'pending') "
            "on conflict (platform, tiktok_shop_id) do update set "
            "  tiktok_shop_code = excluded.tiktok_shop_code, shop_name = excluded.shop_name, "
            "  region = excluded.region, seller_type = excluded.seller_type, "
            "  connection_status = 'pending' "
            "returning id",
            (str(account_id), shop["id"], shop.get("code"), shop.get("name"),
             region, seller_type),
        ).fetchone()

        if row is None:
            # The conflict clause updates rather than doing nothing, so a null here means
            # the row belongs to another account and row level security hid it. That is the
            # UNIQUE (platform, tiktok_shop_id) guard doing its job.
            raise Problem(
                409, "shop_already_connected",
                "That shop is already connected to another MyShopEdge account.",
            )
        shop_id = row[0]

        conn.execute(
            "insert into tiktok_connections (shop_id, access_token_enc, refresh_token_enc, "
            "  shop_cipher_enc, access_expires_at, refresh_expires_at, scopes, key_version, "
            "  authorised_at) values (%s, %s, %s, %s, %s, %s, %s, %s, now()) "
            "on conflict (shop_id) do update set "
            "  access_token_enc = excluded.access_token_enc, "
            "  refresh_token_enc = excluded.refresh_token_enc, "
            "  shop_cipher_enc = excluded.shop_cipher_enc, "
            "  access_expires_at = excluded.access_expires_at, "
            "  refresh_expires_at = excluded.refresh_expires_at, "
            "  scopes = excluded.scopes, key_version = excluded.key_version, "
            "  authorised_at = now(), revoked_at = null",
            (str(shop_id), enc_access, enc_refresh, enc_cipher, access_expires,
             refresh_expires, data.get("granted_scopes") or [], KEY_VERSION),
        )

        conn.execute("select sweep_tiktok_auth_state()")

    return ConnectionResultOut(
        shop={
            "id": str(shop_id),
            "platform": "tiktok_shop",
            "tiktok_shop_id": shop["id"],
            "tiktok_shop_code": shop.get("code"),
            "shop_name": shop.get("name"),
            "region": region,
            "seller_type": seller_type,
            "currency": "GBP",
            "connection_status": "pending",
        },
        accepted=accepted,
        rejection_reason=rejection_reason,
        return_to=return_to,
    )
