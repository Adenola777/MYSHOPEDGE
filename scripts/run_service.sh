#!/usr/bin/env bash
# Local QA harness only. Starts the real service against the local database.
set -euo pipefail
cd /app/service
set -a
source /app/service/.env
set +a
exec uvicorn app.main:app --host 127.0.0.1 --port 8801
