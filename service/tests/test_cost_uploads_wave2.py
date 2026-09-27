"""Wave 2 S3/S4 cost-uploads endpoint tests via public preview URL."""
import os
import secrets
import uuid

import pytest
import requests

BASE = "https://3574af37-00da-4199-8fc8-75173ccd4d0b.preview.emergentagent.com/api/v1"
SHOP_ID = "8a773a13-73b5-a382-7dd0-fda02e950369"
FOREIGN_SHOP = "00000000-0000-0000-0000-000000000001"

with open("/app/scripts/qa/tok_a") as f:
    TOKEN = f.read().strip()


@pytest.fixture(scope="session")
def s():
    sess = requests.Session()
    sess.headers.update({"Authorization": f"Bearer {TOKEN}"})
    return sess


CSV_BODY = b"Seller SKU,Unit Cost,Packing\nHAIR-BLUE,4.44,0.20\nHAIR-RED,5.55,0.20\nZZZ-NOPE,1.00,0.10\n"


@pytest.fixture(scope="session")
def uploaded(s):
    # 1. Create
    r = s.post(
        f"{BASE}/shops/{SHOP_ID}/cost-uploads",
        json={"filename": "costs.csv", "content_type": "text/csv", "size_bytes": len(CSV_BODY)},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert "upload" in body and "upload_url" in body and "upload_expires_at" in body
    upload_id = body["upload"]["id"]
    upload_url = body["upload_url"]
    assert body["upload"]["status"] == "uploaded"
    # 2. PUT bytes
    put_url = BASE.replace("/api/v1", "/api/v1") + upload_url if upload_url.startswith("/") else upload_url
    # upload_url is like "/shops/.../file" (without /api/v1 prefix); prepend BASE
    if upload_url.startswith("/shops"):
        put_url = f"{BASE}{upload_url}"
    r2 = requests.put(
        put_url,
        data=CSV_BODY,
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "text/csv"},
    )
    assert r2.status_code == 200, r2.text
    up = r2.json()
    assert "Seller SKU" in up["detected_columns"]
    assert "Unit Cost" in up["detected_columns"]
    assert up["suggested_mapping"] is not None
    assert up["suggested_mapping"]["cost_column"] == "Unit Cost"
    return {"id": upload_id, "upload_url": upload_url}


class TestCostUploads:
    def test_create_and_upload_returns_detected_columns(self, uploaded):
        assert uploaded["id"]

    def test_get_upload(self, s, uploaded):
        r = s.get(f"{BASE}/shops/{SHOP_ID}/cost-uploads/{uploaded['id']}")
        assert r.status_code == 200
        body = r.json()
        assert body["id"] == uploaded["id"]
        assert "Seller SKU" in body["detected_columns"]
        assert body["status"] in ("uploaded", "mapped", "confirmed", "applied")

    def test_mapping_invalid_cost_column_422(self, s, uploaded):
        r = s.put(
            f"{BASE}/shops/{SHOP_ID}/cost-uploads/{uploaded['id']}/mapping",
            json={"match_on": "seller_sku", "key_column": "Seller SKU",
                  "cost_column": "Not A Column", "currency": "GBP"},
        )
        assert r.status_code == 422, r.text

    def test_mapping_confirms(self, s, uploaded):
        r = s.put(
            f"{BASE}/shops/{SHOP_ID}/cost-uploads/{uploaded['id']}/mapping",
            json={"match_on": "seller_sku", "key_column": "Seller SKU",
                  "cost_column": "Unit Cost", "currency": "GBP"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "mapped"
        assert body["column_mapping"]["cost_column"] == "Unit Cost"

    def test_match(self, s, uploaded):
        r = s.post(f"{BASE}/shops/{SHOP_ID}/cost-uploads/{uploaded['id']}/match")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["rows_total"] == 3
        assert body["rows_matched"] == 2
        assert body["rows_unmatched"] == 1
        # Find ZZZ-NOPE row
        zzz = [r for r in body["rows"] if r["seller_sku"] == "ZZZ-NOPE"]
        assert zzz and zzz[0]["outcome"] == "unmatched"
        assert zzz[0]["reason"]
        matched = [r for r in body["rows"] if r["outcome"] == "matched"]
        assert len(matched) == 2
        for m in matched:
            assert m["unit_cost"] is not None
            assert m["row_id"]
        # Save matched row ids for apply
        uploaded["matched_row_ids"] = [m["row_id"] for m in matched]

    def test_apply_and_idempotent(self, s, uploaded):
        idem = "cost-" + secrets.token_hex(8)
        row_ids = uploaded.get("matched_row_ids")
        assert row_ids
        r1 = s.post(
            f"{BASE}/shops/{SHOP_ID}/cost-uploads/{uploaded['id']}/apply",
            json={"apply_row_ids": row_ids},
            headers={"Idempotency-Key": idem},
        )
        assert r1.status_code == 200, r1.text
        body1 = r1.json()
        assert body1["rows_matched"] == len(row_ids)
        # Replay same idempotency key
        r2 = s.post(
            f"{BASE}/shops/{SHOP_ID}/cost-uploads/{uploaded['id']}/apply",
            json={"apply_row_ids": row_ids},
            headers={"Idempotency-Key": idem},
        )
        assert r2.status_code == 200, r2.text
        assert r2.json() == body1

    def test_list_shows_matched_status(self, s, uploaded):
        r = s.get(f"{BASE}/shops/{SHOP_ID}/cost-uploads")
        assert r.status_code == 200
        body = r.json()
        uploads = body.get("uploads", [])
        found = [u for u in uploads if u["id"] == uploaded["id"]]
        assert found, "created upload not in list"
        # Applied after test_apply; before apply status would be matched.
        assert found[0]["status"] in ("matched", "applied")
        assert found[0]["rows_total"] == 3

    def test_no_auth_401(self):
        r = requests.post(
            f"{BASE}/shops/{SHOP_ID}/cost-uploads",
            json={"filename": "x.csv", "content_type": "text/csv", "size_bytes": 10},
        )
        assert r.status_code == 401

    def test_foreign_shop_403(self, s):
        r = s.post(
            f"{BASE}/shops/{FOREIGN_SHOP}/cost-uploads",
            json={"filename": "x.csv", "content_type": "text/csv", "size_bytes": 10},
        )
        assert r.status_code == 403
        body = r.json()
        err = body.get("code") or body.get("type") or body.get("title") or str(body)
        assert "forbidden" in str(err).lower() or "shop" in str(err).lower()
