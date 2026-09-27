"""Backend tests for WAVE 2: Exports (S23) + Records product filter (S16)."""
import os
import uuid
import pytest
import requests

BASE = "https://3574af37-00da-4199-8fc8-75173ccd4d0b.preview.emergentagent.com/api/v1"
SHOP = "8a773a13-73b5-a382-7dd0-fda02e950369"

with open("/app/scripts/qa/tok_a") as f:
    TOKEN = f.read().strip()

HDR = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
PERIOD = {"period_start": "2026-07-01", "period_end": "2026-08-31"}


def _product_id():
    import subprocess
    out = subprocess.check_output(
        ["psql", "postgresql://mse_migrator@127.0.0.1:5432/myshopedge",
         "-tAc", "select id from products limit 1"]).decode().strip()
    return out


# --- Exports: create ledger CSV ---
class TestCreateExports:
    def test_ledger_csv_ready(self):
        body = {"kind": "ledger", "format": "csv", "basis": "sales", **PERIOD}
        r = requests.post(f"{BASE}/shops/{SHOP}/exports", headers=HDR, json=body)
        assert r.status_code == 202, r.text
        j = r.json()
        assert j["status"] == "ready"
        assert j["download_url"]
        assert j["size_bytes"] > 0
        assert j["row_count"] is not None and j["row_count"] > 0
        assert j["format"] == "csv"

    def test_month_summary_xlsx_ready(self):
        body = {"kind": "month_summary", "format": "xlsx", "basis": "sales", **PERIOD}
        r = requests.post(f"{BASE}/shops/{SHOP}/exports", headers=HDR, json=body)
        assert r.status_code == 202, r.text
        j = r.json()
        assert j["status"] == "ready"
        assert j["row_count"] > 0
        assert j["format"] == "xlsx"
        assert j["size_bytes"] > 0

    def test_period_invalid(self):
        body = {"kind": "ledger", "format": "csv", "basis": "sales",
                "period_start": "2026-08-31", "period_end": "2026-07-01"}
        r = requests.post(f"{BASE}/shops/{SHOP}/exports", headers=HDR, json=body)
        assert r.status_code == 422
        # RFC7807-style problem
        assert "validation_failed" in r.text or r.json().get("type", "").endswith("validation_failed")

    def test_idempotency(self):
        key = "test-wave2-" + uuid.uuid4().hex[:12]
        h = {**HDR, "Idempotency-Key": key}
        body = {"kind": "ledger", "format": "csv", "basis": "sales", **PERIOD}
        r1 = requests.post(f"{BASE}/shops/{SHOP}/exports", headers=h, json=body)
        r2 = requests.post(f"{BASE}/shops/{SHOP}/exports", headers=h, json=body)
        assert r1.status_code == 202 and r2.status_code == 202
        assert r1.json()["id"] == r2.json()["id"]

    def test_auth_required(self):
        body = {"kind": "ledger", "format": "csv", "basis": "sales", **PERIOD}
        r = requests.post(f"{BASE}/shops/{SHOP}/exports", json=body,
                          headers={"Content-Type": "application/json"})
        assert r.status_code == 401

    def test_forbidden_other_tenant_shop(self):
        other = "00000000-0000-0000-0000-000000000001"
        body = {"kind": "ledger", "format": "csv", "basis": "sales", **PERIOD}
        r = requests.post(f"{BASE}/shops/{other}/exports", headers=HDR, json=body)
        assert r.status_code in (403, 404)


# --- Exports: get + download ---
class TestGetAndDownload:
    @pytest.fixture(scope="class")
    def export_csv(self):
        body = {"kind": "ledger", "format": "csv", "basis": "sales", **PERIOD}
        r = requests.post(f"{BASE}/shops/{SHOP}/exports", headers=HDR, json=body)
        assert r.status_code == 202
        return r.json()

    @pytest.fixture(scope="class")
    def export_xlsx(self):
        body = {"kind": "month_summary", "format": "xlsx", "basis": "sales", **PERIOD}
        r = requests.post(f"{BASE}/shops/{SHOP}/exports", headers=HDR, json=body)
        assert r.status_code == 202
        return r.json()

    def test_get_status(self, export_csv):
        eid = export_csv["id"]
        r = requests.get(f"{BASE}/shops/{SHOP}/exports/{eid}", headers=HDR)
        assert r.status_code == 200
        j = r.json()
        assert j["status"] == "ready"
        assert j["download_url"]

    def test_get_unknown(self):
        r = requests.get(f"{BASE}/shops/{SHOP}/exports/{uuid.uuid4()}", headers=HDR)
        assert r.status_code == 404
        assert "export_not_found" in r.text

    def test_download_csv(self, export_csv):
        eid = export_csv["id"]
        r = requests.get(f"{BASE}/shops/{SHOP}/exports/{eid}?download=1", headers=HDR)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("text/csv")
        assert "attachment" in r.headers.get("content-disposition", "")
        assert "filename" in r.headers.get("content-disposition", "")
        assert len(r.content) > 0
        # header row check
        first_line = r.content.decode("utf-8-sig").splitlines()[0]
        assert "Date" in first_line

    def test_download_xlsx(self, export_xlsx):
        eid = export_xlsx["id"]
        r = requests.get(f"{BASE}/shops/{SHOP}/exports/{eid}?download=1", headers=HDR)
        assert r.status_code == 200
        assert "spreadsheetml" in r.headers.get("content-type", "")
        assert "attachment" in r.headers.get("content-disposition", "")
        # xlsx zip starts with PK
        assert r.content[:2] == b"PK"

    def test_download_auth_required(self, export_csv):
        eid = export_csv["id"]
        r = requests.get(f"{BASE}/shops/{SHOP}/exports/{eid}?download=1")
        assert r.status_code == 401


# --- Records product filter ---
class TestRecordsProductFilter:
    def test_records_by_product(self):
        pid = _product_id()
        assert pid
        r = requests.get(f"{BASE}/shops/{SHOP}/records",
                         headers=HDR, params={"product_id": pid})
        assert r.status_code == 200, r.text
        j = r.json()
        assert "entries" in j
        assert "total" in j
        assert "shown_total" in j
