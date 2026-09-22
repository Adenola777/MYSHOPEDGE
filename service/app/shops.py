"""Shop scope.

Thirty-odd endpoints take a shopId in the path and declare a 403 ForbiddenShop response.
This is where that comes from.

The check is a query rather than a comparison, and it runs inside the seller's own scope.
A shop belonging to another account is not visible to that query at all, so the answer is
the same whether the shop does not exist or belongs to somebody else. That is deliberate.
A 404 for one and a 403 for the other would let anyone with a shop id learn whether it is
real.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Depends, Path

from .auth import Account, require_account
from .db import tenant
from .problems import Problem


def require_shop(
    shopId: Annotated[UUID, Path()],
    account: Annotated[Account, Depends(require_account)],
) -> UUID:
    with tenant(account.id) as conn:
        row = conn.execute(
            "select id from shops where id = %s and connection_status <> 'deleted'",
            (str(shopId),),
        ).fetchone()
    if row is None:
        raise Problem(403, "forbidden_shop", "That shop is not on your account.")
    return shopId
