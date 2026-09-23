"""Check the environment before the service is started or deployed.

    python3 scripts/check_env.py                 # check what is set
    python3 scripts/check_env.py --generate-key  # make a TIKTOK_TOKEN_KEY
    python3 scripts/check_env.py --live          # also reach the database and the JWKS

Release engineering step 5 is "environment variables verified", and until now verifying
them meant reading a list and hoping. This checks them.

**It never prints a secret.** Every value is reported as present, absent, or wrong shape,
with a length and a prefix at most. A check that echoes what it found cannot be run in a
deployment log, and one that cannot be run in a deployment log does not get run.

What it can and cannot tell you. It proves a variable is present and shaped like the thing
it claims to be, which catches the ordinary mistakes: a service_id pasted into
TIKTOK_APP_KEY, a test key in production, a truncated base64 key, a pooled connection
string where a direct one was meant. It cannot prove a credential is valid. `--live` goes
further and actually connects, which is the only way to know.

Exit codes: 0 all required present and well shaped, 1 something required is missing or
malformed, 2 the script was asked for something it could not do.
"""

from __future__ import annotations

import base64
import os
import sys
from urllib.parse import urlparse

RESET, BOLD, DIM = "\033[0m", "\033[1m", "\033[2m"
GREEN, YELLOW, RED = "\033[32m", "\033[33m", "\033[31m"


def tty(s: str, colour: str) -> str:
    return f"{colour}{s}{RESET}" if sys.stdout.isatty() else s


class Check:
    """One variable, and what would make it wrong."""

    def __init__(self, name, required=True, note="", validate=None, secret=True):
        self.name, self.required, self.note = name, required, note
        self.validate, self.secret = validate, secret


def _pg(value: str) -> str | None:
    """Every fault at once, not the first one.

    An earlier version returned on the first problem, so a string that both lacked
    sslmode and connected as mse_owner reported only the sslmode. Fixing that one would
    have revealed the second on the next run, which turns one round of correction into
    several and makes the privilege fault look like it appeared from nowhere.
    """
    u = urlparse(value)
    faults = []
    if u.scheme not in ("postgres", "postgresql"):
        faults.append("not a postgresql:// URL")
    if not u.hostname:
        faults.append("no host")
    if "sslmode=require" not in (u.query or ""):
        faults.append("no sslmode=require, so the connection may not be encrypted")
    if u.username and u.username != "mse_app":
        faults.append(
            f"connects as {u.username}, and the service must connect as mse_app, which "
            f"cannot change the schema or read the migration ledger"
        )
    return "; ".join(faults) or None


def _https(value: str) -> str | None:
    u = urlparse(value)
    if u.scheme != "https":
        return "must be https"
    return None


def _jwks(value: str) -> str | None:
    if bad := _https(value):
        return bad
    if not value.endswith("/.well-known/jwks.json"):
        return "does not end in /.well-known/jwks.json"
    if "neon.tech" in value:
        return (
            "points at a Neon host. The provider is Stack Auth and its keys are on "
            "api.stack-auth.com. See A25.2"
        )
    return None


def _key32(value: str) -> str | None:
    try:
        raw = base64.b64decode(value, validate=True)
    except Exception:
        return "not valid base64"
    if len(raw) != 32:
        return f"decodes to {len(raw)} bytes, needs exactly 32 for AES-256"
    return None


def _prefix(*allowed: str):
    def check(value: str) -> str | None:
        if not value.startswith(allowed):
            return f"does not start with {' or '.join(allowed)}"
        return None
    return check


def _numeric(value: str) -> str | None:
    return None if value.isdigit() else "should be digits only"


CHECKS = [
    Check("DATABASE_URL", validate=_pg,
          note="Neon, as mse_app"),
    Check("DB_POOL_MIN", required=False, secret=False, validate=_numeric),
    Check("DB_POOL_MAX", required=False, secret=False, validate=_numeric,
          note="set to 1 on a serverless host, with a -pooler connection string"),

    Check("NEON_AUTH_JWKS_URL", validate=_jwks, secret=False),
    Check("NEON_AUTH_ISSUER", validate=_https, secret=False,
          note="read off one real token. Never derived. A25.2"),
    Check("NEON_AUTH_AUDIENCE", secret=False,
          note="read off one real token"),
    Check("NEON_AUTH_BASE_URL", required=False, secret=False),

    Check("STRIPE_SECRET_KEY", validate=_prefix("sk_", "rk_")),
    Check("STRIPE_WEBHOOK_SECRET", validate=_prefix("whsec_")),
    Check("STRIPE_PRICE_STARTER", validate=_prefix("price_"), secret=False),
    Check("STRIPE_PRICE_GROWTH", validate=_prefix("price_"), secret=False),
    Check("STRIPE_PRICE_PRO", validate=_prefix("price_"), secret=False),

    Check("TIKTOK_SERVICE_ID", secret=False,
          note="NOT app_key. A23.2"),
    Check("TIKTOK_APP_KEY", secret=False),
    Check("TIKTOK_APP_SECRET"),
    Check("TIKTOK_TOKEN_KEY", validate=_key32,
          note="32 bytes base64. Changing it makes every stored token unreadable"),
]


def describe(name: str, value: str, secret: bool) -> str:
    """Enough to recognise a wrong value, never enough to use one."""
    if secret:
        return f"{DIM}set, {len(value)} chars{RESET}" if sys.stdout.isatty() \
            else f"set, {len(value)} chars"
    if len(value) <= 48:
        return value
    return f"{value[:40]}... ({len(value)} chars)"


def generate_key() -> int:
    key = base64.b64encode(os.urandom(32)).decode()
    print("TIKTOK_TOKEN_KEY=" + key)
    print()
    print("Put that in .env and in the deployment's environment, then never change it.")
    print("Every TikTok token already stored is encrypted with the key it was stored under,")
    print("so replacing this one makes them permanently unreadable and every seller has to")
    print("reconnect their shop.")
    return 0


def live_checks() -> list[str]:
    """The two things shape cannot tell you: does the database answer, and is the JWKS real."""
    problems = []

    url = os.environ.get("DATABASE_URL")
    if url:
        try:
            import psycopg
            with psycopg.connect(url, connect_timeout=15) as conn:
                who = conn.execute("select current_user").fetchone()
                print(f"  live  database answers, connected as {tty(who[0], GREEN)}")
                if who[0] != "mse_app":
                    problems.append(
                        f"DATABASE_URL connects as {who[0]}. The service must be mse_app."
                    )
        except Exception as exc:
            problems.append(f"DATABASE_URL did not connect: {type(exc).__name__}: {exc}")

    jwks = os.environ.get("NEON_AUTH_JWKS_URL")
    if jwks:
        try:
            import json, urllib.request
            with urllib.request.urlopen(jwks, timeout=20) as r:
                keys = json.loads(r.read()).get("keys", [])
            algs = sorted({k.get("alg") for k in keys})
            print(f"  live  JWKS answers, {len(keys)} key(s), algorithms {algs}")
            if algs != ["ES256"]:
                problems.append(
                    f"The provider publishes {algs} and app/auth.py accepts ES256. "
                    f"Run tests/check_provider_jwks.py."
                )
        except Exception as exc:
            problems.append(f"NEON_AUTH_JWKS_URL was not reachable: {exc}")

    return problems


def main() -> int:
    if "--generate-key" in sys.argv:
        return generate_key()

    print(f"{BOLD}MyShopEdge environment{RESET}" if sys.stdout.isatty()
          else "MyShopEdge environment")
    print()

    missing, malformed = [], []

    for c in CHECKS:
        value = os.environ.get(c.name, "")
        if not value:
            if c.required:
                missing.append(c.name)
                mark, detail = tty("MISSING ", RED), tty("required", RED)
            else:
                mark, detail = tty("unset   ", YELLOW), "optional"
        else:
            problem = c.validate(value) if c.validate else None
            if problem:
                malformed.append(f"{c.name}: {problem}")
                mark, detail = tty("WRONG   ", RED), tty(problem, RED)
            else:
                mark, detail = tty("ok      ", GREEN), describe(c.name, value, c.secret)

        print(f"  {mark}{c.name:<32} {detail}")
        if c.note and (not value or (c.validate and value and c.validate(value))):
            print(f"          {DIM}{c.note}{RESET}" if sys.stdout.isatty()
                  else f"          {c.note}")

    live_problems = []
    if "--live" in sys.argv:
        print()
        live_problems = live_checks()

    print()
    if not missing and not malformed and not live_problems:
        print(tty("Every required variable is present and correctly shaped.", GREEN))
        if "--live" not in sys.argv:
            print("Shape is not validity. Run with --live to actually connect.")
        return 0

    for name in missing:
        print(tty(f"MISSING   {name}", RED))
    for m in malformed:
        print(tty(f"WRONG     {m}", RED))
    for p in live_problems:
        print(tty(f"LIVE      {p}", RED))
    print()
    print("service/.env.example explains every one of these and where to get it.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
