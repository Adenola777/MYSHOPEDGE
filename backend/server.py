"""Pod serving shim for the Emergent preview environment.

This file exists ONLY so the platform's readonly supervisor program `backend`
(`uvicorn server:app` on port 8001, cwd /app/backend) can serve the real service that
lives in /app/service. It is not part of the product and is never deployed.

It does two things:
  1. Loads /app/service/.env into the process before importing the service.
  2. Mounts the real FastAPI service under /api, because the pod ingress routes external
     /api/* to port 8001 while everything else goes to the Next.js app on 3000. The service
     itself keeps its contract paths at /v1, so /api/v1/... reaches /v1/... unchanged.
  3. Serves the local QA JWKS at /_qa/jwks.json for auth verification in the pod.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SERVICE = Path("/app/service")
sys.path.insert(0, str(SERVICE))

# Self-heal: ensure the local Postgres (under /app/.pgdata, which survives pod restarts) is
# running and seeded before the service imports its db pool. Idempotent and fast when the
# database is already up.
try:
    subprocess.run(["bash", "/app/scripts/pod_bootstrap.sh"], check=True, timeout=120)
except Exception as _exc:  # noqa: BLE001
    print(f"[shim] pod_bootstrap warning: {_exc}", file=sys.stderr)

# Load the service .env before importing anything that reads it.
_env = SERVICE / ".env"
if _env.exists():
    for _line in _env.read_text().splitlines():
        _line = _line.strip()
        if not _line or _line.startswith("#") or "=" not in _line:
            continue
        _k, _v = _line.split("=", 1)
        import os as _os

        _os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

from fastapi import FastAPI  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402

from app.main import app as service_app  # noqa: E402

app = FastAPI(title="MyShopEdge pod shim", docs_url=None, redoc_url=None)

_JWKS = json.loads(Path("/app/scripts/qa/jwks.json").read_text())


@app.get("/_qa/jwks.json", include_in_schema=False)
def qa_jwks() -> JSONResponse:
    return JSONResponse(_JWKS)


@app.get("/health", include_in_schema=False)
def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})


app.mount("/api", service_app)
