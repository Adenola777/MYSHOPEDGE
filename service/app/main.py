"""The MyShopEdge API.

One contract, api/openapi.yaml, and this service implements it. Rule 1 of A13.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from . import billing, connections, products, records, settlements
from .problems import problem_handler

app = FastAPI(
    title="MyShopEdge API",
    version="0.3.0",
    description="Bookkeeping and finance for UK TikTok Shop sellers.",
    docs_url="/v1/docs",
    openapi_url="/v1/openapi.json",
)

app.add_exception_handler(HTTPException, problem_handler)
app.add_exception_handler(Exception, problem_handler)

app.include_router(billing.router, prefix="/v1")
app.include_router(connections.router, prefix="/v1")
app.include_router(products.router, prefix="/v1")
app.include_router(records.router, prefix="/v1")
app.include_router(settlements.router, prefix="/v1")


@app.get("/health", include_in_schema=False)
def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})
