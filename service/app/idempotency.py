"""Idempotency-Key, as the contract's IdempotencyKey parameter promises it.

"A repeat with the same key returns the first result rather than acting twice. Keys are
retained for 24 hours." The key is stored with the first response inside the same
transaction as the write, so a write and its key are recorded together or not at all.

A repeat whose body differs from the first is refused with 422. Returning the first result
to a different request would tell the caller that the second request succeeded.

Needs migration 0023, which is **not yet applied**. A request without a key never touches
the table, so it works before 0023 is applied.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import UUID

from .problems import Problem

RETAIN = "24 hours"


def request_hash(*parts: Any) -> str:
    return hashlib.sha256(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()


def replay(conn, account_id: UUID, operation: str, key: str | None, digest: str):
    """The stored (status, body) for a repeat, or None when this is the first request."""
    if key is None:
        return None
    if not 8 <= len(key) <= 128:
        raise Problem(422, "validation_failed", "Idempotency-Key must be 8 to 128 characters.")
    conn.execute(
        "delete from idempotency_keys where account_id = %s and operation = %s and key = %s "
        f"and created_at < now() - interval '{RETAIN}'",
        (str(account_id), operation, key),
    )
    row = conn.execute(
        "select request_hash, status_code, response from idempotency_keys "
        "where account_id = %s and operation = %s and key = %s",
        (str(account_id), operation, key),
    ).fetchone()
    if row is None:
        return None
    if row[0] != digest:
        raise Problem(
            422, "idempotency_key_reused",
            "That Idempotency-Key was already used for a different request.",
        )
    return row[1], row[2]


def record(conn, account_id: UUID, operation: str, key: str | None, digest: str,
           status: int, body: dict[str, Any]) -> None:
    if key is None:
        return
    conn.execute(
        "insert into idempotency_keys (account_id, operation, key, request_hash, "
        "status_code, response) values (%s, %s, %s, %s, %s, %s::jsonb)",
        (str(account_id), operation, key, digest, status, json.dumps(body, default=str)),
    )
