"""Object storage, through the Emergent managed store (S3-style, A10.8's owner decision).

A Python service cannot mint Vercel Blob signed uploads, so files go through the backend
rather than a browser-to-store signed PUT. The store has no presigned URLs and no delete
API, so `exports.storage_key` in the database is the source of truth for what exists, and a
download is always served by us, never by a link straight to the store.

The `storage_key` here is a session credential minted once from `EMERGENT_LLM_KEY`, not a
row key. It is cached; a 404 on an object read can mean the credential went stale, so callers
re-init with `force=True` once before giving up.
"""

from __future__ import annotations

import os

import requests

_BASE = (os.environ.get("INTEGRATION_PROXY_URL") or "").strip() or "https://integrations.emergentagent.com"
_URL = _BASE.rstrip("/") + "/objstore/api/v1/storage"
_KEY = os.environ.get("EMERGENT_LLM_KEY")

_session_key: str | None = None


def _init(force: bool = False) -> str:
    global _session_key
    if _session_key and not force:
        return _session_key
    resp = requests.post(f"{_URL}/init", json={"emergent_key": _KEY}, timeout=30)
    resp.raise_for_status()
    _session_key = resp.json()["storage_key"]
    return _session_key


def put_object(path: str, data: bytes, content_type: str) -> dict:
    key = _init()
    resp = requests.put(
        f"{_URL}/objects/{path}",
        headers={"X-Storage-Key": key, "Content-Type": content_type},
        data=data, timeout=120,
    )
    if resp.status_code == 404:
        resp = requests.put(
            f"{_URL}/objects/{path}",
            headers={"X-Storage-Key": _init(force=True), "Content-Type": content_type},
            data=data, timeout=120,
        )
    resp.raise_for_status()
    return resp.json()


def get_object(path: str) -> tuple[bytes, str]:
    key = _init()
    resp = requests.get(f"{_URL}/objects/{path}", headers={"X-Storage-Key": key}, timeout=60)
    if resp.status_code == 404:
        resp = requests.get(
            f"{_URL}/objects/{path}", headers={"X-Storage-Key": _init(force=True)}, timeout=60,
        )
    resp.raise_for_status()
    return resp.content, resp.headers.get("Content-Type", "application/octet-stream")
