"""Refetch the provider's JWKS and compare it to what the service accepts.

The unit test asserts `ALGORITHMS` against a recorded fixture, which catches somebody
changing the code. It cannot catch the provider changing its keys, because the fixture is
frozen. This does, and it is the only check here that needs the network.

    python3 tests/check_provider_jwks.py

The URL is the `jwks_url` from the project's Neon Auth configuration, which is where the
truth lives. It is not derived from a Neon hostname, because the provider is Stack Auth and
its keys are served from `api.stack-auth.com`. Deriving it is the mistake recorded in A25.

Run it before a release and whenever sign-in starts failing for no visible reason. A
provider rotating from ES256 to something else is a silent outage otherwise: every token is
refused, the logs say `token_unverifiable`, and nothing points at the cause.
"""

import json, os, sys, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

FIXTURE = os.path.join(HERE, "fixtures", "provider_jwks_2026-09-23.json")
URL = os.environ.get("NEON_AUTH_JWKS_URL") or (
    "https://api.stack-auth.com/api/v1/projects/"
    "f1762e29-4750-42f6-80e1-c94b040a72e8/.well-known/jwks.json"
)

from app.auth import ALGORITHMS

recorded = json.load(open(FIXTURE))
recorded_algs = sorted({k["alg"] for k in recorded["keys"]})

try:
    with urllib.request.urlopen(URL, timeout=20) as r:
        live = json.loads(r.read())
except Exception as exc:
    print(f"Could not reach the provider: {exc}")
    print("This check needs the network. Nothing is concluded from a failure to fetch.")
    sys.exit(2)

live_algs = sorted({k["alg"] for k in live["keys"]})

print(f"url             {URL}")
print(f"service accepts {ALGORITHMS}")
print(f"recorded        {recorded_algs}  ({len(recorded['keys'])} keys)")
print(f"live            {live_algs}  ({len(live['keys'])} keys)")

problems = []
if live_algs != ALGORITHMS:
    problems.append(
        f"The service accepts {ALGORITHMS} and the provider now publishes {live_algs}. "
        f"Every token is being refused."
    )
if live_algs != recorded_algs:
    problems.append(
        f"The provider changed since the fixture was recorded: {recorded_algs} -> {live_algs}. "
        f"Refetch fixtures/provider_jwks_2026-09-23.json."
    )

live_kids = sorted(k["kid"] for k in live["keys"])
recorded_kids = sorted(k["kid"] for k in recorded["keys"])
if live_kids != recorded_kids:
    # Not a failure. Key rotation is routine and PyJWKClient refetches on an unknown kid.
    print(f"\nnote: key ids have rotated. recorded {recorded_kids}, live {live_kids}. "
          f"That is normal and the client handles it.")

for p in problems:
    print(f"\nFAIL  {p}")
print("\nprovider and service agree" if not problems else "")
sys.exit(1 if problems else 0)
