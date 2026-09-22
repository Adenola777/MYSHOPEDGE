"""Resolves the signed-in account from the request.

Neon Auth on Stack Auth issues the session. ``accounts.auth_subject`` holds the provider
subject and the ``account_identity`` view in migration 0011 joins the two.

This module is deliberately unimplemented. The session flow has not been written, and a
placeholder that returned a made-up account would let billing appear to work while charging
the wrong person. Every endpoint is written against this interface, so nothing changes here
when the real resolution lands.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request

from .problems import Problem


@dataclass(frozen=True)
class Account:
    id: str
    email: str
    name: str | None


def require_account(request: Request) -> Account:
    raise Problem(
        501,
        "auth_not_implemented",
        "The authentication session flow has not been written yet.",
    )
