"""Every route the service serves must exist in the contract.

Rule 1 of A13 says the contract in api/openapi.yaml is the single source of truth and the
service implements it. On 22 September I broke that rule four hours after writing it, by
calling a route that was not in the contract. A rule nobody checks is a preference.

This runs without a database, without credentials and without the network. It imports the
application, generates the schema FastAPI derives from the actual handlers, and compares it
against the contract. It does not check that every documented route is implemented, because
most are not yet and that is expected. It checks the other direction, which is the one that
matters: nothing is served that was never agreed.

    python3 tests/test_contract_conformance.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import yaml

from app.main import app

HERE = os.path.dirname(os.path.abspath(__file__))
CONTRACT = os.path.normpath(os.path.join(HERE, "..", "..", "api", "openapi.yaml"))
PREFIX = "/v1"

# Not part of the contract and not meant to be. The health check is infrastructure, and the
# documentation routes are FastAPI's own.
EXEMPT = {"/health", "/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect"}

contract = yaml.safe_load(open(CONTRACT))["paths"]
served = app.openapi()["paths"]

failures = []

for path, operations in sorted(served.items()):
    bare = path[len(PREFIX):] if path.startswith(PREFIX) else path
    if bare in EXEMPT or path in EXEMPT:
        continue
    if bare not in contract:
        failures.append(f"served but not in the contract: {bare}")
        continue
    for method in operations:
        if method not in contract[bare]:
            failures.append(f"served but not in the contract: {method.upper()} {bare}")

implemented = sum(
    1
    for p in served
    if (p[len(PREFIX):] if p.startswith(PREFIX) else p) in contract
)

print("contract conformance")
print(f"  contract paths:    {len(contract)}")
print(f"  served paths:      {len(served)}")
print(f"  of those in the contract: {implemented}")
print(f"  remaining to build:       {len(contract) - implemented}")

for f in failures:
    print(f"  FAIL  {f}")

print(f"\n{'every served route is in the contract' if not failures else 'CONTRACT BREACH'}")
sys.exit(1 if failures else 0)
