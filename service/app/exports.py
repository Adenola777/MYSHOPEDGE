"""Exports, S23. `createExport` (MON-2) and `getExport`.

An accountant asks for a spreadsheet, not a screen. These build one from the ledger and put
it in object storage, then serve it back through us. `basis` is required and has no default,
because the same period is a different figure on a sales basis and a cash basis, and a file
that does not say which one it is cannot be used.

The file is produced now, in the request, because the seller's data is small and a worker
that flips a row later is more machinery than this needs. The job is therefore `ready` by the
time the 202 returns, its `download_url` present. The 202 is the contract's, and a job that is
already done is still an accepted job.

The download is served by `getExport` with `?download=1`, because the store issues no
presigned URLs (A10.8) and a spreadsheet of a seller's finances must not sit behind a public
link. `download_url` is the same operation's path, which the browser fetches with the
seller's token and saves.
"""

from __future__ import annotations

import csv
import io
from datetime import date, datetime, timezone
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, Query, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .auth import Account, require_account
from .db import tenant
from .idempotency import record, replay, request_hash
from .money_view import LABELS, calculate
from .problems import Problem
from .shops import require_shop
from .storage import get_object, put_object

router = APIRouter(tags=["Exports"])

Kind = Literal["month_summary", "ledger", "transactions"]
Fmt = Literal["xlsx", "csv"]

CONTENT_TYPE = {
    "csv": "text/csv",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


class ExportIn(BaseModel):
    kind: Kind
    format: Fmt
    basis: Literal["sales", "cash"]
    period_start: date
    period_end: date


class ShopExportJob(BaseModel):
    id: UUID
    status: Literal["queued", "ready", "failed", "expired"]
    requested_at: datetime
    ready_at: datetime | None = None
    expires_at: datetime | None = None
    download_url: str | None = None
    size_bytes: int | None = None
    kind: Kind
    format: Fmt
    basis: str
    period_start: date
    period_end: date
    row_count: int | None = None


def _rows(conn, shop_id: UUID, body: ExportIn) -> tuple[list[str], list[list]]:
    """The header and rows for the chosen kind, over the period on the chosen basis."""
    if body.kind == "month_summary":
        view = calculate(conn, shop_id, body.period_start, body.period_end, body.basis, "month")
        header = ["Section", "Line", "Amount", "Currency"]
        out: list[list] = []
        for section in view.sections:
            for line in section.lines:
                out.append([
                    section.label, line.label,
                    f"{line.amount.amount_minor / 100:.2f}", line.amount.currency,
                ])
            out.append([section.label, section.subtotal_label or "Subtotal",
                        f"{section.subtotal.amount_minor / 100:.2f}", section.subtotal.currency])
        return header, out

    # ledger and transactions both read the ledger; transactions carries the order and
    # settlement references an accountant reconciles against, ledger carries the accounting
    # category. The basis chooses the date column, exactly as the records screen does.
    date_column = "le.basis_day" if body.basis == "sales" else "le.settlement_month"
    cur = conn.execute(
        "select le.basis_day, le.occurred_at, le.entry_type, le.category, le.amount_minor, "
        "le.currency, o.tiktok_order_id, le.tiktok_invoice_number, le.source, le.attribution "
        "from ledger_entries le left join orders o on o.id = le.order_id "
        f"where le.shop_id = %s and {date_column} >= %s and {date_column} <= %s "
        "order by le.occurred_at, le.id",
        (str(shop_id), body.period_start, body.period_end),
    )
    data = cur.fetchall()
    if body.kind == "ledger":
        header = ["Date", "Type", "Category", "Amount", "Currency", "Source"]
        return header, [
            [r[0].isoformat(), r[2], LABELS.get(r[3], r[3] or ""),
             f"{r[4] / 100:.2f}", r[5], r[8]] for r in data
        ]
    header = ["Date", "Type", "Amount", "Currency", "TikTok order", "Invoice", "Attribution"]
    return header, [
        [r[0].isoformat(), r[2], f"{r[4] / 100:.2f}", r[5], r[6] or "", r[7] or "", r[9] or ""]
        for r in data
    ]


def _serialise(header: list[str], rows: list[list], fmt: Fmt, title: str) -> bytes:
    if fmt == "csv":
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(header)
        w.writerows(rows)
        return buf.getvalue().encode("utf-8-sig")
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = title[:31]
    ws.append(header)
    for row in rows:
        ws.append(row)
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


@router.post("/shops/{shopId}/exports", status_code=202, response_model=ShopExportJob,
             summary="Request an export")
def create_export(
    body: ExportIn,
    account: Annotated[Account, Depends(require_account)],
    shop_id: Annotated[UUID, Depends(require_shop)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    if body.period_start > body.period_end:
        raise Problem(422, "validation_failed", "The period starts after it ends.")

    op = "createExport"
    digest = request_hash(str(shop_id), body.kind, body.format, body.basis,
                          body.period_start.isoformat(), body.period_end.isoformat())
    with tenant(account.id) as conn:
        again = replay(conn, account.id, op, idempotency_key, digest)
        if again:
            return JSONResponse(status_code=again[0], content=again[1])

        export_id = uuid4()
        header, rows = _rows(conn, shop_id, body)
        blob = _serialise(header, rows, body.format, body.kind)
        prefix = "myshopedge"
        path = f"{prefix}/exports/{shop_id}/{export_id}.{body.format}"
        put_object(path, blob, CONTENT_TYPE[body.format])

        now = datetime.now(timezone.utc)
        conn.execute(
            "insert into exports (id, shop_id, kind, period_start, period_end, format, status, "
            "storage_key, created_at, basis) "
            "values (%s, %s, %s, %s, %s, %s, 'ready', %s, %s, %s)",
            (str(export_id), str(shop_id), body.kind, body.period_start, body.period_end,
             body.format, path, now, body.basis),
        )
        job = ShopExportJob(
            id=export_id, status="ready", requested_at=now, ready_at=now,
            download_url=f"/shops/{shop_id}/exports/{export_id}?download=1",
            size_bytes=len(blob), kind=body.kind, format=body.format, basis=body.basis,
            period_start=body.period_start, period_end=body.period_end, row_count=len(rows),
        )
        record(conn, account.id, op, idempotency_key, digest, 202, job.model_dump(mode="json"))
    return job


@router.get("/shops/{shopId}/exports/{exportId}", summary="Export status and download")
def get_export(
    account: Annotated[Account, Depends(require_account)],
    shop_id: Annotated[UUID, Depends(require_shop)],
    exportId: UUID,
    download: Annotated[bool, Query()] = False,
):
    with tenant(account.id) as conn:
        row = conn.execute(
            "select id, kind, period_start, period_end, format, status, storage_key, "
            "created_at, expires_at, basis from exports where id = %s and shop_id = %s",
            (str(exportId), str(shop_id)),
        ).fetchone()
    if row is None:
        # The same answer as an export on another account, for the reason in shops.py.
        raise Problem(404, "export_not_found", "That export was not found.")

    (rid, kind, ps, pe, fmt, status, storage_key, created_at, expires_at, basis) = row

    if download:
        if status != "ready" or not storage_key:
            raise Problem(409, "export_not_ready", "That export is not ready to download.")
        data, content_type = get_object(storage_key)
        filename = f"{kind}-{ps.isoformat()}-to-{pe.isoformat()}.{fmt}"
        return Response(
            content=data, media_type=content_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    return ShopExportJob(
        id=rid, status=status, requested_at=created_at,
        ready_at=created_at if status == "ready" else None, expires_at=expires_at,
        download_url=(f"/shops/{shop_id}/exports/{rid}?download=1" if status == "ready" else None),
        kind=kind, format=fmt, basis=basis, period_start=ps, period_end=pe,
    )
