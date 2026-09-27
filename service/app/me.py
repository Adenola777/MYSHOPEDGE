"""Who is signed in, and which shops they have. `getMe` and `listShops`.

Every shop screen carries a shop id in its address, and until these two existed nothing
gave a signed-in seller that id. Both read only the caller's own rows, through `tenant()`,
so neither takes an id from the request.

WHAT IS LEFT OUT, AND WHY

`Account.tax_profile_completed` is optional in the contract and is not served. No document
says what makes a tax profile complete, since every column in `tax_profiles` except the
flag is nullable. A guess would drive a prompt the seller acts on.

`Shop.authorization_expires_at` is served as null. CLAUDE.md records that nobody has checked
whether it is the same instant as `tiktok_connections.refresh_expires_at`, and one real
authorisation settles it. Serving the refresh expiry under that name would be the guess.

A shop whose `connection_status` is `deleted` is not listed, which matches `require_shop`.
The contract's enum has no `deleted`, because a deleted shop is gone as far as the seller
is concerned.

Checked on the development branch, 24 September 2026, with the SQL below: one account,
one shop.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, Response
from pydantic import BaseModel

from .auth import Account, require_account
from .dates import now_utc
from .db import tenant
from .idempotency import record, replay, request_hash
from .problems import Problem

router = APIRouter(tags=["Account"])


class AccountOut(BaseModel):
    id: UUID
    email: str
    display_name: str | None = None
    locale: str
    timezone: str
    status: Literal["active", "suspended", "deleted"]
    created_at: datetime
    shop_count: int


class Shop(BaseModel):
    id: UUID
    platform: Literal["tiktok_shop"]
    tiktok_shop_id: str
    tiktok_shop_code: str | None = None
    shop_name: str | None = None
    region: str
    seller_type: Literal["LOCAL", "CROSS_BORDER"] | None = None
    currency: str
    connection_status: Literal["pending", "connected", "needs_reconnect", "disconnected"]
    first_synced_at: datetime | None = None
    last_synced_at: datetime | None = None
    authorization_expires_at: datetime | None = None


class ShopList(BaseModel):
    shops: list[Shop]


ACCOUNT_SQL = """
select a.id, a.email::text as email, a.display_name, a.locale, a.timezone, a.status,
       a.created_at,
       (select count(*) from shops s
         where s.account_id = a.id and s.connection_status <> 'deleted') as shop_count
  from accounts a
 where a.id = %s
"""

SHOPS_SQL = """
select id, platform, tiktok_shop_id, tiktok_shop_code, shop_name, region, seller_type,
       trim(currency) as currency, connection_status, first_synced_at, last_synced_at
  from shops
 where connection_status <> 'deleted'
 order by created_at, id
"""


def etag_of(model: BaseModel) -> str:
    digest = hashlib.sha256(
        json.dumps(model.model_dump(mode="json"), sort_keys=True).encode()
    ).hexdigest()
    return f'"{digest[:32]}"'


def _with_etag(model: BaseModel, response: Response, if_none_match: str | None):
    etag = etag_of(model)
    if if_none_match is not None and if_none_match == etag:
        return Response(status_code=304, headers={"ETag": etag})
    response.headers["ETag"] = etag
    return model


@router.get("/me", response_model=AccountOut)
def get_me(
    response: Response,
    account: Annotated[Account, Depends(require_account)],
    if_none_match: Annotated[str | None, Header()] = None,
):
    with tenant(account.id) as conn:
        cur = conn.execute(ACCOUNT_SQL, (str(account.id),))
        cols = [d.name for d in cur.description]
        row = cur.fetchone()
    if row is None:
        # The token verified and resolved to this id, so a missing row means the account
        # was removed between the two. Treated as signed out rather than as a server fault.
        raise Problem(401, "account_not_found", "Please sign in again.")
    return _with_etag(AccountOut(**dict(zip(cols, row, strict=True))), response, if_none_match)


@router.get("/shops", response_model=ShopList, tags=["Shops"])
def list_shops(
    response: Response,
    account: Annotated[Account, Depends(require_account)],
    if_none_match: Annotated[str | None, Header()] = None,
):
    with tenant(account.id) as conn:
        cur = conn.execute(SHOPS_SQL)
        cols = [d.name for d in cur.description]
        rows = [dict(zip(cols, r, strict=True)) for r in cur.fetchall()]
    return _with_etag(ShopList(shops=[Shop(**r) for r in rows]), response, if_none_match)


# --- deleteMe, ACC-4 -----------------------------------------------------------------------
#
# Deletion is a soft delete: the account is stamped closed rather than erased, because the
# ledger is append-only (A29) and a seller's settled figures are records, not preferences.
# `accounts.status` becomes `deleted` and `deleted_at` is stamped, every shop is
# disconnected, and each stored TikTok token is marked revoked so it can no longer be used.
# The response states plainly what was done and what is kept, so a seller who believed
# deletion erased everything is corrected in the acknowledgement itself.


class DeleteMeIn(BaseModel):
    confirm_email: str
    reason: str | None = None


class DeletionAcknowledgement(BaseModel):
    account_id: UUID
    scheduled_at: datetime
    includes: list[str]
    invoices_retained_until: str | None = None
    cancel_by: datetime | None = None


@router.delete("/me", status_code=202, response_model=DeletionAcknowledgement,
               summary="Delete the account and its data")
def delete_me(
    body: DeleteMeIn,
    account: Annotated[Account, Depends(require_account)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    if body.confirm_email.strip().lower() != (account.email or "").strip().lower():
        raise Problem(422, "confirm_email_mismatch",
                      "The email you typed does not match the account email.")
    if body.reason is not None and len(body.reason) > 500:
        raise Problem(422, "validation_failed", "That reason is too long.")

    op = "deleteMe"
    digest = request_hash(str(account.id), body.confirm_email.strip().lower())
    now = now_utc()
    with tenant(account.id) as conn:
        again = replay(conn, account.id, op, idempotency_key, digest)
        if again:
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=again[0], content=again[1])

        # Soft delete. A row already closed stays closed, so a repeat is harmless even
        # without a key.
        conn.execute(
            "update accounts set status = 'deleted', "
            "deleted_at = coalesce(deleted_at, now()) where id = %s",
            (str(account.id),),
        )
        # Every shop is disconnected and every token marked revoked, so nothing can read a
        # closed account's shop. The rows remain for the record.
        conn.execute(
            "update shops set connection_status = 'disconnected' "
            "where account_id = %s and connection_status <> 'deleted'",
            (str(account.id),),
        )
        conn.execute(
            "update tiktok_connections set revoked_at = coalesce(revoked_at, now()) "
            "where shop_id in (select id from shops where account_id = %s)",
            (str(account.id),),
        )
        ack = DeletionAcknowledgement(
            account_id=account.id,
            scheduled_at=now,
            includes=[
                "Your account and sign-in",
                "Every shop connection and its stored TikTok tokens",
                "Your orders, returns, settlements and ledger",
                "Your product costs and cost uploads",
                "Your saved figures entered by hand",
            ],
            invoices_retained_until=None,
            cancel_by=None,
        )
        record(conn, account.id, op, idempotency_key, digest, 202, ack.model_dump(mode="json"))
    return ack


# --- requestAccountExport, ACC-4 -----------------------------------------------------------
#
# A full download of the account's data. The archive is written by a background worker that
# is not built yet (BUILD_PLAN Wave 2), so this persists a queued job and answers 202. The
# poll and download path arrive with the worker. The export is stored against the account's
# shop, because `exports` is shop-scoped and the MVP allows one shop per account.


class ExportJob(BaseModel):
    id: UUID
    status: Literal["queued", "ready", "failed", "expired"]
    requested_at: datetime
    ready_at: datetime | None = None
    expires_at: datetime | None = None
    download_url: str | None = None
    size_bytes: int | None = None


@router.post("/me/export", status_code=202, response_model=ExportJob,
             summary="Request a download of the account's data")
def request_account_export(
    account: Annotated[Account, Depends(require_account)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    """Queue a full account-data export.

    The archive is written by a background worker to object storage, and neither the worker
    nor an account-scoped export store exists yet (BUILD_PLAN Wave 2). The `exports` table is
    for shop report exports only (its `kind` and `format` checks forbid an account archive),
    so nothing is written there. This accepts the request and answers 202 with a queued job.
    The job id is held against the Idempotency-Key so a repeat returns the same id, which is
    the promise the contract makes. `download_url` stays absent until the worker exists.
    """
    op = "requestAccountExport"
    digest = request_hash(str(account.id))
    with tenant(account.id) as conn:
        again = replay(conn, account.id, op, idempotency_key, digest)
        if again:
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=again[0], content=again[1])

        job = ExportJob(id=uuid4(), status="queued", requested_at=now_utc())
        record(conn, account.id, op, idempotency_key, digest, 202, job.model_dump(mode="json"))
    return job
