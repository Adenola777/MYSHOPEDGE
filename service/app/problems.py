"""RFC 9457 problem details.

The API contract states that the `code` field is the contract and that `title` and `detail`
are for humans and may change wording. Every error the service returns goes through here so
that promise holds.
"""

from __future__ import annotations

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

BASE = "https://api.myshopedge.com/problems"


class Problem(HTTPException):
    def __init__(self, status: int, code: str, detail: str) -> None:
        super().__init__(status_code=status, detail=detail)
        self.code = code


def problem_response(status: int, code: str, detail: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        media_type="application/problem+json",
        content={
            "type": f"{BASE}/{code}",
            "title": code,
            "status": status,
            "detail": detail,
            "code": code,
        },
    )


async def problem_handler(_request: Request, exc: Exception) -> JSONResponse:
    if isinstance(exc, Problem):
        return problem_response(exc.status_code, exc.code, str(exc.detail))
    if isinstance(exc, HTTPException):
        return problem_response(exc.status_code, "http_error", str(exc.detail))
    # An unhandled exception must not leak a stack trace or a connection string to a
    # seller. It is logged by the server and reported as one line here.
    return problem_response(500, "internal_error", "Something went wrong at our end.")
