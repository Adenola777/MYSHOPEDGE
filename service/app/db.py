"""The only way this service reaches the database.

Every query a request makes runs inside ``tenant()``. There is no second accessor, and no
endpoint is given a raw connection, because the one thing that must never be forgotten is
the line that scopes a connection to one seller.

What ``tenant()`` does before yielding, and why each part matters.

    set local role mse_app;
    select set_config('app.account_id', %s, true);

``mse_app`` is the only role the service ever runs as. It cannot update or delete a ledger
entry, it cannot read the migration ledger, and it owns nothing. ``LOCAL`` on both means
they are undone when the transaction ends, so a pooled connection handed to the next
request carries nothing from this one.

The scoping fails closed rather than open. ``app_account_id()`` is defined as
``nullif(current_setting('app.account_id', true), '')::uuid``, so an unset context is null,
and the policy ``id = app_account_id()`` is then true for no row at all. Verified on the
development branch on 22 September 2026: the right account sees 20 orders, a different
account sees 0, and no context set sees 0.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator
from uuid import UUID

from psycopg import Connection
from psycopg_pool import ConnectionPool

_pool: ConnectionPool | None = None


def pool() -> ConnectionPool:
    """The process's connection pool.

    The size is configurable because the right answer depends on where this runs, and that
    was decided in A28. A long-lived server wants a real pool. A serverless invocation is
    its own process and may be frozen between requests, so a pool of ten there means ten
    connections held per concurrent invocation and Postgres runs out long before the
    platform does. On a serverless host set `DB_POOL_MAX` to 1 and point `DATABASE_URL` at
    Neon's pooled endpoint, which is the hostname carrying `-pooler`.

    The defaults suit a long-lived server, because that is what A28 chose.
    """
    global _pool
    if _pool is None:
        url = os.environ.get("DATABASE_URL")
        if not url:
            raise RuntimeError("DATABASE_URL is not set.")
        max_size = int(os.environ.get("DB_POOL_MAX", "10"))
        min_size = min(int(os.environ.get("DB_POOL_MIN", "1")), max_size)
        _pool = ConnectionPool(url, min_size=min_size, max_size=max_size, open=True)
    return _pool


@contextmanager
def tenant(account_id: UUID | str) -> Iterator[Connection]:
    """A transaction scoped to one seller. Everything an endpoint reads comes from here."""
    with pool().connection() as conn:
        with conn.transaction():
            conn.execute("set local role mse_app")
            conn.execute("select set_config('app.account_id', %s, true)", (str(account_id),))
            yield conn


@contextmanager
def unscoped() -> Iterator[Connection]:
    """For the two calls that happen before an account is known, and for nothing else.

    This still runs as mse_app. It is not a way around row level security: a select against
    a table from in here returns nothing, exactly as it should. The only useful thing that
    can be done with it is to call resolve_account or create_account, which are SECURITY
    DEFINER and elevate themselves for one narrow statement.
    """
    with pool().connection() as conn:
        with conn.transaction():
            conn.execute("set local role mse_app")
            yield conn


def resolve_account_id(subject: str) -> UUID | None:
    """Turns a verified JWT subject into an account id, or None."""
    with unscoped() as conn:
        row = conn.execute("select resolve_account(%s)", (subject,)).fetchone()
    return row[0] if row and row[0] else None


def lookup_identity(subject: str) -> tuple[str | None, str | None] | None:
    """Reads the email and name the identity provider synced, or None if no row exists.

    Neon Auth maintains ``neon_auth.users_sync``. It is the only place a managed token's
    email can be found, because those tokens carry no custom claims. ``mse_app`` holds
    SELECT on it and nothing more, granted by migration 0016.

    The distinction between a missing row and a row with a null email matters. A missing
    row is a sync that has not caught up, which clears on its own. A null email is a real
    dead end. The caller treats them differently and must not collapse them.
    """
    with unscoped() as conn:
        row = conn.execute(
            "select email, name from neon_auth.users_sync "
            "where id = %s and deleted_at is null",
            (subject,),
        ).fetchone()
    return (row[0], row[1]) if row else None


def create_account_id(subject: str, email: str, display_name: str | None) -> UUID:
    """Creates the account on a first verified sign in, or returns the existing one.

    Every argument must come from verified JWT claims. Nothing a client sent may reach it.
    """
    with unscoped() as conn:
        row = conn.execute(
            "select create_account(%s, %s, %s)", (subject, email, display_name)
        ).fetchone()
    if row is None or row[0] is None:
        raise RuntimeError("create_account returned no id.")
    return row[0]
