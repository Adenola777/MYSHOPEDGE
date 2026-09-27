"""Cost uploads, S3/S4. The six operations that turn a seller's spreadsheet into costs.

The parsing and matching live in `cost_files.py`, which is pure and tested. This module is
the plumbing around it: it stores the file, reads variants, records the match, and writes
the costs the seller confirms.

WHERE THE FILE AND THE MATCH LIVE

The chosen store (A10.8, Emergent object storage) issues no presigned upload URLs, so the
browser cannot PUT straight to the store. `createCostUpload` therefore returns an
`upload_url` that points back at this service (`PUT .../file`), and the bytes come through
us. The store also has no per-row table, so a match is written as one JSON object beside the
file (`{id}.rows.json`); `cost_uploads.storage_key` in the database points at the file, and
the row ids the seller confirms in `apply` are the ids in that JSON. No SKU is ever created
by a cost upload (CST-2).

STATUS

The two contract schemas disagree on one word: a matched upload is `confirmed` on
`CostUpload` and `matched` on `CostUploadSummary`. The database holds the summary's word and
each response emits the word its own schema requires.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .auth import Account, require_account
from .cost_files import CSV_TYPE, XLSX_TYPE, FileUnreadable, Variant, match, parse, suggest_mapping
from .dates import business_today, now_utc
from .db import tenant
from .idempotency import record, replay, request_hash
from .money import Money, money
from .problems import Problem
from .shops import require_shop
from .storage import get_object, put_object

router = APIRouter(tags=["Costs"])

PREFIX = "myshopedge"
MAX_BYTES = 10 * 1024 * 1024
EXT = {CSV_TYPE: "csv", XLSX_TYPE: "xlsx"}


class ColumnMapping(BaseModel):
    match_on: Literal["seller_sku", "tiktok_sku_id"]
    key_column: str | None = None
    cost_column: str
    packing_column: str | None = None
    postage_column: str | None = None
    currency: str = "GBP"


class CreateUploadIn(BaseModel):
    filename: str
    content_type: Literal[
        "text/csv",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ]
    size_bytes: int


class CostUpload(BaseModel):
    id: UUID
    filename: str
    status: Literal["uploaded", "mapped", "confirmed", "applied", "failed"]
    created_at: datetime
    confirmed_at: datetime | None = None
    detected_columns: list[str] = []
    suggested_mapping: ColumnMapping | None = None
    column_mapping: ColumnMapping | None = None
    rows_total: int | None = None
    rows_matched: int | None = None
    rows_unmatched: int | None = None
    rows_duplicate: int | None = None
    error: str | None = None


class CreateUploadOut(BaseModel):
    upload: CostUpload
    upload_url: str
    upload_expires_at: datetime


class MatchRow(BaseModel):
    row_id: UUID
    outcome: Literal["matched", "unmatched", "duplicate"]
    matched_on: Literal["seller_sku", "tiktok_sku_id"] | None = None
    sku_id: UUID | None = None
    seller_sku: str | None = None
    unit_cost: Money | None = None
    reason: str | None = None


class CostMatchResult(BaseModel):
    upload_id: UUID
    rows_total: int
    rows_matched: int
    rows_unmatched: int
    rows_duplicate: int
    rows: list[MatchRow]


def _file_key(shop_id: UUID, upload_id: UUID, ext: str) -> str:
    return f"{PREFIX}/cost-uploads/{shop_id}/{upload_id}.{ext}"


def _rows_key(shop_id: UUID, upload_id: UUID) -> str:
    return f"{PREFIX}/cost-uploads/{shop_id}/{upload_id}-rows.json"


def _content_type(storage_key: str) -> str:
    return XLSX_TYPE if storage_key.endswith(".xlsx") else CSV_TYPE


def _to_cost_upload(row: dict, detected: list[str], suggested, error: str | None) -> CostUpload:
    # The database and CostUpload agree on `confirmed` for a matched upload.
    mapping = row.get("column_mapping")
    return CostUpload(
        id=row["id"], filename=row["filename"], status=row["status"],
        created_at=row["created_at"], confirmed_at=row.get("confirmed_at"),
        detected_columns=detected,
        suggested_mapping=ColumnMapping(**suggested) if suggested else None,
        column_mapping=ColumnMapping(**mapping) if mapping else None,
        rows_total=row.get("rows_total"), rows_matched=row.get("rows_matched"),
        rows_unmatched=row.get("rows_unmatched"), rows_duplicate=row.get("rows_duplicate"),
        error=error,
    )


def _parse_stored(storage_key: str):
    """The stored file parsed, or (None, error) when it cannot be read or is not there yet."""
    try:
        data, _ = get_object(storage_key)
    except Exception:  # noqa: BLE001
        return None, "The file has not been uploaded yet."
    try:
        return parse(data, _content_type(storage_key)), None
    except FileUnreadable as exc:
        return None, str(exc)


UPLOAD_COLUMNS = (
    "id, filename, storage_key, status, column_mapping, rows_total, rows_matched, "
    "rows_unmatched, rows_duplicate, confirmed_at, created_at"
)


@router.post("/shops/{shopId}/cost-uploads", status_code=201, response_model=CreateUploadOut,
             summary="Create a cost upload")
def create_cost_upload(
    body: CreateUploadIn,
    account: Annotated[Account, Depends(require_account)],
    shop_id: Annotated[UUID, Depends(require_shop)],
) -> CreateUploadOut:
    if body.size_bytes < 1 or body.size_bytes > MAX_BYTES:
        raise Problem(422, "validation_failed", "The file must be between 1 byte and 10 MB.")
    upload_id = uuid4()
    storage_key = _file_key(shop_id, upload_id, EXT[body.content_type])
    now = now_utc()
    with tenant(account.id) as conn:
        conn.execute(
            "insert into cost_uploads (id, shop_id, filename, storage_key, status, "
            "created_by, created_at) values (%s, %s, %s, %s, 'uploaded', %s, %s)",
            (str(upload_id), str(shop_id), body.filename[:255], storage_key, str(account.id), now),
        )
        row = conn.execute(
            f"select {UPLOAD_COLUMNS} from cost_uploads where id = %s", (str(upload_id),)
        ).fetchone()
    cols = UPLOAD_COLUMNS.replace(" ", "").split(",")
    rowd = dict(zip(cols, row, strict=True))
    return CreateUploadOut(
        upload=_to_cost_upload(rowd, [], None, None),
        upload_url=f"/shops/{shop_id}/cost-uploads/{upload_id}/file",
        upload_expires_at=now + timedelta(minutes=15),
    )


@router.put("/shops/{shopId}/cost-uploads/{uploadId}/file", response_model=CostUpload,
            summary="Upload the file's bytes")
async def upload_cost_file(
    request: Request,
    account: Annotated[Account, Depends(require_account)],
    shop_id: Annotated[UUID, Depends(require_shop)],
    uploadId: UUID,
) -> CostUpload:
    data = await request.body()
    if not data:
        raise Problem(422, "validation_failed", "The file is empty.")
    if len(data) > MAX_BYTES:
        raise Problem(413, "file_too_large", "The file is larger than 10 MB.")

    with tenant(account.id) as conn:
        row = conn.execute(
            f"select {UPLOAD_COLUMNS} from cost_uploads where id = %s and shop_id = %s",
            (str(uploadId), str(shop_id)),
        ).fetchone()
        if row is None:
            raise Problem(404, "cost_upload_not_found", "That upload was not found.")
        cols = UPLOAD_COLUMNS.replace(" ", "").split(",")
        rowd = dict(zip(cols, row, strict=True))
        content_type = _content_type(rowd["storage_key"])
        put_object(rowd["storage_key"], data, content_type)

        parsed, error = None, None
        try:
            parsed = parse(data, content_type)
        except FileUnreadable as exc:
            error = str(exc)
        status = "failed" if error else "uploaded"
        conn.execute("update cost_uploads set status = %s where id = %s",
                     (status, str(uploadId)))
        rowd["status"] = status

    detected = parsed.columns if parsed else []
    suggested = suggest_mapping(parsed.columns) if parsed else None
    return _to_cost_upload(rowd, detected, suggested, error)


@router.get("/shops/{shopId}/cost-uploads/{uploadId}", response_model=CostUpload,
            summary="Upload status and parsed preview")
def get_cost_upload(
    account: Annotated[Account, Depends(require_account)],
    shop_id: Annotated[UUID, Depends(require_shop)],
    uploadId: UUID,
) -> CostUpload:
    with tenant(account.id) as conn:
        row = conn.execute(
            f"select {UPLOAD_COLUMNS} from cost_uploads where id = %s and shop_id = %s",
            (str(uploadId), str(shop_id)),
        ).fetchone()
    if row is None:
        raise Problem(404, "cost_upload_not_found", "That upload was not found.")
    cols = UPLOAD_COLUMNS.replace(" ", "").split(",")
    rowd = dict(zip(cols, row, strict=True))
    parsed, error = _parse_stored(rowd["storage_key"])
    detected = parsed.columns if parsed else []
    suggested = suggest_mapping(parsed.columns) if parsed else None
    return _to_cost_upload(rowd, detected, suggested, error if rowd["status"] == "failed" else None)


class CostUploadSummary(BaseModel):
    id: UUID
    filename: str
    status: Literal["uploaded", "mapped", "matched", "applied", "failed"]
    uploaded_at: datetime
    rows_total: int = 0
    rows_matched: int = 0
    rows_unmatched: int = 0
    rows_duplicate: int = 0


class CostUploadList(BaseModel):
    uploads: list[CostUploadSummary]
    next_cursor: str | None = None


@router.get("/shops/{shopId}/cost-uploads", response_model=CostUploadList,
            summary="List cost uploads")
def list_cost_uploads(
    account: Annotated[Account, Depends(require_account)],
    shop_id: Annotated[UUID, Depends(require_shop)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> CostUploadList:
    with tenant(account.id) as conn:
        rows = conn.execute(
            "select id, filename, status, created_at, rows_total, rows_matched, "
            "rows_unmatched, rows_duplicate from cost_uploads where shop_id = %s "
            "order by created_at desc, id desc limit %s",
            (str(shop_id), limit),
        ).fetchall()
    return CostUploadList(uploads=[
        CostUploadSummary(
            id=r[0], filename=r[1],
            # The summary schema names a matched upload `matched`; the database holds `confirmed`.
            status="matched" if r[2] == "confirmed" else r[2], uploaded_at=r[3],
            rows_total=r[4] or 0, rows_matched=r[5] or 0,
            rows_unmatched=r[6] or 0, rows_duplicate=r[7] or 0,
        )
        for r in rows
    ])


@router.put("/shops/{shopId}/cost-uploads/{uploadId}/mapping", response_model=CostUpload,
            summary="Set the column mapping")
def put_cost_upload_mapping(
    body: ColumnMapping,
    account: Annotated[Account, Depends(require_account)],
    shop_id: Annotated[UUID, Depends(require_shop)],
    uploadId: UUID,
) -> CostUpload:
    with tenant(account.id) as conn:
        row = conn.execute(
            f"select {UPLOAD_COLUMNS} from cost_uploads where id = %s and shop_id = %s",
            (str(uploadId), str(shop_id)),
        ).fetchone()
        if row is None:
            raise Problem(404, "cost_upload_not_found", "That upload was not found.")
        cols = UPLOAD_COLUMNS.replace(" ", "").split(",")
        rowd = dict(zip(cols, row, strict=True))
        parsed, _ = _parse_stored(rowd["storage_key"])
        if parsed is None:
            raise Problem(409, "file_not_ready", "Upload the file before mapping its columns.")
        if body.cost_column not in parsed.columns:
            raise Problem(422, "validation_failed",
                          f'The file has no column headed "{body.cost_column}".')
        conn.execute(
            "update cost_uploads set column_mapping = %s, status = 'mapped' where id = %s",
            (json.dumps(body.model_dump()), str(uploadId)),
        )
        rowd["status"] = "mapped"
        rowd["column_mapping"] = body.model_dump()
    return _to_cost_upload(rowd, parsed.columns, suggest_mapping(parsed.columns), None)


def _variants(conn, shop_id: UUID) -> list[Variant]:
    rows = conn.execute(
        "select id, seller_sku, tiktok_sku_id from skus where shop_id = %s", (str(shop_id),)
    ).fetchall()
    return [Variant(sku_id=r[0], seller_sku=r[1], tiktok_sku_id=r[2]) for r in rows]


def _run_match(conn, shop_id: UUID, rowd: dict) -> tuple[list[dict], dict]:
    parsed, error = _parse_stored(rowd["storage_key"])
    if parsed is None:
        raise Problem(409, "file_not_ready", error or "The file could not be read.")
    mapping = rowd.get("column_mapping")
    if not mapping:
        raise Problem(409, "not_mapped", "Set the column mapping before matching.")
    currency = mapping.get("currency", "GBP")
    outcomes = match(parsed, mapping, _variants(conn, shop_id))
    stored = []
    for o in outcomes:
        stored.append({
            "row_id": str(uuid4()),
            "row_number": o.row_number,
            "outcome": o.outcome,
            "matched_on": o.matched_on,
            "sku_id": str(o.sku_id) if o.sku_id else None,
            "seller_sku": o.seller_sku,
            "unit_cost_minor": o.unit_cost_minor,
            "packing_minor": o.packing_minor,
            "postage_minor": o.postage_minor,
            "reason": o.reason,
            "currency": currency,
        })
    counts = {
        "rows_total": len(stored),
        "rows_matched": sum(1 for r in stored if r["outcome"] == "matched"),
        "rows_unmatched": sum(1 for r in stored if r["outcome"] == "unmatched"),
        "rows_duplicate": sum(1 for r in stored if r["outcome"] == "duplicate"),
    }
    return stored, counts


def _result(upload_id: UUID, stored: list[dict], counts: dict) -> CostMatchResult:
    return CostMatchResult(
        upload_id=upload_id, **counts,
        rows=[
            MatchRow(
                row_id=r["row_id"], outcome=r["outcome"], matched_on=r["matched_on"],
                sku_id=r["sku_id"], seller_sku=r["seller_sku"],
                unit_cost=(money(r["unit_cost_minor"], r["currency"])
                           if r["unit_cost_minor"] is not None else None),
                reason=r["reason"],
            )
            for r in stored
        ],
    )


@router.post("/shops/{shopId}/cost-uploads/{uploadId}/match", response_model=CostMatchResult,
             summary="Match rows to variants")
def match_cost_upload(
    account: Annotated[Account, Depends(require_account)],
    shop_id: Annotated[UUID, Depends(require_shop)],
    uploadId: UUID,
) -> CostMatchResult:
    with tenant(account.id) as conn:
        row = conn.execute(
            f"select {UPLOAD_COLUMNS} from cost_uploads where id = %s and shop_id = %s",
            (str(uploadId), str(shop_id)),
        ).fetchone()
        if row is None:
            raise Problem(404, "cost_upload_not_found", "That upload was not found.")
        cols = UPLOAD_COLUMNS.replace(" ", "").split(",")
        rowd = dict(zip(cols, row, strict=True))
        stored, counts = _run_match(conn, shop_id, rowd)
        put_object(_rows_key(shop_id, uploadId), json.dumps(stored).encode("utf-8"),
                   "application/json")
        conn.execute(
            "update cost_uploads set status = 'confirmed', rows_total = %s, rows_matched = %s, "
            "rows_unmatched = %s, rows_duplicate = %s where id = %s",
            (counts["rows_total"], counts["rows_matched"], counts["rows_unmatched"],
             counts["rows_duplicate"], str(uploadId)),
        )
    return _result(uploadId, stored, counts)


class ApplyIn(BaseModel):
    apply_row_ids: list[UUID]


@router.post("/shops/{shopId}/cost-uploads/{uploadId}/apply", response_model=CostMatchResult,
             summary="Apply the confirmed costs")
def apply_cost_upload(
    body: ApplyIn,
    account: Annotated[Account, Depends(require_account)],
    shop_id: Annotated[UUID, Depends(require_shop)],
    uploadId: UUID,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> Any:
    wanted = {str(x) for x in body.apply_row_ids}
    op = "applyCostUpload"
    digest = request_hash(str(uploadId), *sorted(wanted))
    with tenant(account.id) as conn:
        again = replay(conn, account.id, op, idempotency_key, digest)
        if again:
            return JSONResponse(status_code=again[0], content=again[1])

        row = conn.execute(
            "select id, storage_key, status from cost_uploads where id = %s and shop_id = %s",
            (str(uploadId), str(shop_id)),
        ).fetchone()
        if row is None:
            raise Problem(404, "cost_upload_not_found", "That upload was not found.")
        try:
            stored = json.loads(get_object(_rows_key(shop_id, uploadId))[0])
        except Exception as exc:  # noqa: BLE001
            raise Problem(409, "not_matched", "Match the file before applying its costs.") from exc

        shop_currency = (conn.execute(
            "select trim(currency) from shops where id = %s", (str(shop_id),)
        ).fetchone() or ["GBP"])[0] or "GBP"
        effective_from = business_today()

        applied = []
        for r in stored:
            if r["row_id"] not in wanted or r["outcome"] != "matched":
                continue
            if r["currency"] != shop_currency:
                raise Problem(422, "validation_failed",
                              f"A cost is in {r['currency']} and this shop sells in {shop_currency}.")
            conn.execute(
                "update product_costs set superseded_at = now() "
                "where sku_id = %s and shop_id = %s and superseded_at is null",
                (r["sku_id"], str(shop_id)),
            )
            conn.execute(
                "insert into product_costs (shop_id, sku_id, cost_minor, packing_minor, "
                "postage_minor, currency, source, cost_upload_id, effective_from, created_by) "
                "values (%s, %s, %s, %s, %s, %s, 'upload', %s, %s, %s)",
                (str(shop_id), r["sku_id"], r["unit_cost_minor"], r["packing_minor"],
                 r["postage_minor"], shop_currency, str(uploadId), effective_from, str(account.id)),
            )
            applied.append(r)

        conn.execute(
            "update cost_uploads set status = 'applied', confirmed_at = now() where id = %s",
            (str(uploadId),),
        )
        counts = {
            "rows_total": len(applied),
            "rows_matched": len(applied),
            "rows_unmatched": 0,
            "rows_duplicate": 0,
        }
        result = _result(uploadId, applied, counts)
        record(conn, account.id, op, idempotency_key, digest, 200,
               result.model_dump(mode="json"))
    return result
