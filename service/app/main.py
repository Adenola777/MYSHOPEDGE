"""The MyShopEdge API.

One contract, api/openapi.yaml, and this service implements it. Rule 1 of A13.
"""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import (
    billing,
    connections,
    costs,
    discrepancies,
    me,
    notifications,
    money_view,
    products,
    records,
    returns,
    settlements,
    stock,
    sync_status,
    tax,
    today_view,
)
from .problems import problem_handler, problem_response

logger = logging.getLogger("myshopedge")

app = FastAPI(
    title="MyShopEdge API",
    version="0.3.0",
    description="Bookkeeping and finance for UK TikTok Shop sellers.",
    docs_url="/v1/docs",
    openapi_url="/v1/openapi.json",
)

# The front end is on Vercel and this service is not, so a write made from the browser is a
# cross-origin request. Which origins may make one is configuration, not code: nothing
# records the final domain names, so no origin is allowed unless ALLOWED_ORIGINS lists it,
# comma separated, for example https://my-shop-edge.vercel.app. Unset, the service sends
# no CORS headers at all, which is the safe default.
@app.middleware("http")
async def _errors_inside_cors(request: Request, call_next):
    """Turns an unhandled exception into the same 500 problem, inside the CORS layer.

    Starlette answers an unhandled exception from its outermost middleware, which sits
    outside CORSMiddleware, so a 500 left without CORS headers and a browser reported it as
    a network failure. Found on 24 September by driving the stock adjustment form in a
    browser. Middleware added first runs innermost, so this must stay above the CORS block.
    """
    try:
        return await call_next(request)
    except Exception:
        logger.exception("unhandled error on %s %s", request.method, request.url.path)
        return problem_response(500, "internal_error", "Something went wrong at our end.")


_origins = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o.strip()]
if _origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "If-None-Match"],
        expose_headers=["ETag"],
        max_age=600,
    )

app.add_exception_handler(HTTPException, problem_handler)
app.add_exception_handler(Exception, problem_handler)

app.include_router(billing.router, prefix="/v1")
app.include_router(connections.router, prefix="/v1")
app.include_router(costs.router, prefix="/v1")
app.include_router(discrepancies.router, prefix="/v1")
app.include_router(me.router, prefix="/v1")
app.include_router(notifications.router, prefix="/v1")
app.include_router(money_view.router, prefix="/v1")
app.include_router(products.router, prefix="/v1")
app.include_router(records.router, prefix="/v1")
app.include_router(returns.router, prefix="/v1")
app.include_router(settlements.router, prefix="/v1")
app.include_router(stock.router, prefix="/v1")
app.include_router(sync_status.router, prefix="/v1")
app.include_router(tax.router, prefix="/v1")
app.include_router(today_view.router, prefix="/v1")


@app.get("/health", include_in_schema=False)
def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})
