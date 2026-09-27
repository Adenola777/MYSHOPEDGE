"""Reference rules, shared and read-only. `listRules`, tracing TAX-6.

`reference_rules` is the one table without row-level security, because its rows are the
same for every seller: the VAT threshold, income tax and National Insurance rules, and the
MTD rules, each with the date it takes effect. This endpoint reads them and never writes.

It runs unscoped rather than through `tenant()`, because the rows belong to no account and
`app.account_id` is irrelevant to them. `mse_app` holds SELECT on the table and nothing
more.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, Query, Response
from pydantic import BaseModel

from .auth import Account, require_account
from .db import unscoped

router = APIRouter(tags=["Tax"])

RuleSet = Literal["vat", "income_tax", "national_insurance", "mtd"]


class ReferenceRule(BaseModel):
    rule_set: RuleSet
    rule_key: str
    value: object
    effective_from: date
    effective_to: date | None = None
    source_url: str | None = None
    reviewed_at: date | None = None


class RulesOut(BaseModel):
    rules: list[ReferenceRule]


@router.get("/rules", response_model=RulesOut, summary="Reference rules with correct-as-at dates")
def list_rules(
    response: Response,
    account: Annotated[Account, Depends(require_account)],
    rule_set: Annotated[RuleSet | None, Query()] = None,
    effective_on: Annotated[date | None, Query()] = None,
    if_none_match: Annotated[str | None, Header()] = None,
):
    on = effective_on or date.today()
    where = ["effective_from <= %s", "(effective_to is null or effective_to >= %s)"]
    args: list[object] = [on, on]
    if rule_set:
        where.append("rule_set = %s")
        args.append(rule_set)
    sql = (
        "select rule_set, rule_key, value, effective_from, effective_to, source_url, "
        "reviewed_at from reference_rules "
        f"where {' and '.join(where)} order by rule_set, rule_key, effective_from desc"
    )
    with unscoped() as conn:
        cur = conn.execute(sql, args)
        cols = [d.name for d in cur.description]
        rows = [dict(zip(cols, r, strict=True)) for r in cur.fetchall()]

    out = RulesOut(rules=[ReferenceRule(**r) for r in rows])
    etag = f'"{hashlib.sha256(json.dumps(out.model_dump(mode="json"), sort_keys=True).encode()).hexdigest()[:32]}"'
    if if_none_match is not None and if_none_match == etag:
        return Response(status_code=304, headers={"ETag": etag})
    response.headers["ETag"] = etag
    return out
