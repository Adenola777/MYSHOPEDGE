"""Puts real tokens through verify() against a locally served JWKS.

This is the test that matters most in the service. A flaw here is not a wrong figure on a
screen, it is one seller reading another seller's payouts. It runs without a database and
without the identity provider, by generating a key, serving a JWKS on localhost, and
signing tokens with it.

    python3 tests/test_auth_verification.py

Rewritten twice on 23 September 2026, and the second rewrite is the interesting one.

The first version signed ES256 and the service checked ES256. Believing the provider
signed EdDSA, I changed both, and every case still passed, because a test that generates
its own key proves only that the code agrees with the test.

The provider signs ES256. Fetched from the jwks_url in this project's own Neon Auth
configuration and recorded at fixtures/provider_jwks_2026-09-23.json. Both times the
mistake was reading a vendor page instead of making one call.

So this file no longer decides the algorithm for itself. It reads the recorded JWKS and
asserts that what the service accepts is what the provider actually publishes. Changing
ALGORITHMS without refetching that fixture now fails, in either direction.
"""

import json, os, sys, threading, time, http.server, socketserver
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import jwt
from cryptography.hazmat.primitives.asymmetric import ed25519, ec

# The algorithm is read from what the provider publishes, not chosen here. If the recorded
# fixture ever carries more than one, this raises rather than silently picking the first.
HERE = os.path.dirname(os.path.abspath(__file__))
RECORDED = json.load(open(os.path.join(HERE, "fixtures", "provider_jwks_2026-09-23.json")))
PROVIDER_ALGS = sorted({k["alg"] for k in RECORDED["keys"]})
assert PROVIDER_ALGS == ["ES256"], f"Recorded JWKS carries {PROVIDER_ALGS}; update this test."

key = ec.generate_private_key(ec.SECP256R1())
jwk = json.loads(jwt.algorithms.ECAlgorithm.to_jwk(key.public_key()))
jwk.update({"kid": "test-key-1", "use": "sig", "alg": "ES256"})
JWKS = json.dumps({"keys": [jwk]}).encode()

class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.send_header("content-type","application/json")
        self.send_header("content-length", str(len(JWKS))); self.end_headers()
        self.wfile.write(JWKS)
    def log_message(self, *a): pass

srv = socketserver.TCPServer(("127.0.0.1", 0), H)
port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()

os.environ["NEON_AUTH_JWKS_URL"] = f"http://127.0.0.1:{port}/jwks.json"
os.environ["NEON_AUTH_AUDIENCE"] = "myshopedge"
os.environ["NEON_AUTH_ISSUER"] = "https://ep-test.neonauth.eu-west-2.aws.neon.tech/neondb/auth"

from app.auth import verify, ALGORITHMS
from app.problems import Problem

AUD = os.environ["NEON_AUTH_AUDIENCE"]
ISS = os.environ["NEON_AUTH_ISSUER"]

def token(**over):
    now = int(time.time())
    claims = {"sub": "user_synthetic_uk_shop", "aud": AUD, "iss": ISS,
              "iat": now, "exp": now + 300}
    claims.update(over)
    return jwt.encode(claims, key, algorithm="ES256", headers={"kid": "test-key-1"})

failures = []

def case(name, fn, expect_code=None):
    try:
        out = fn()
        ok = expect_code is None
        print(f"  {'PASS' if ok else 'FAIL'}  {name}"
              + ("" if ok else f": expected {expect_code}, got success"))
        if not ok: failures.append(name)
        return out
    except Problem as e:
        ok = e.code == expect_code
        print(f"  {'PASS' if ok else 'FAIL'}  {name}: {e.code}")
        if not ok: failures.append(name)
        return None

print("verify()")

c = case("a valid ES256 token resolves its subject", lambda: verify(token()))
assert c and c["sub"] == "user_synthetic_uk_shop"

# The provider's JWT plugin page lists email and emailVerified in the payload, while its
# overview page says there are no custom claims. Nothing downstream may depend on either
# being right, so the bare fixture carries neither and users_sync is the fallback.
assert "email" not in c, "the bare fixture stands for the no-claims case"

case("an expired token is refused", lambda: verify(token(exp=int(time.time())-10)),
     "token_expired")
case("a token with no exp is refused",
     lambda: verify(jwt.encode({"sub":"x","aud":AUD,"iss":ISS}, key,
                               algorithm="ES256", headers={"kid":"test-key-1"})),
     "token_invalid")
case("a token for another audience is refused", lambda: verify(token(aud="another-project")),
     "token_invalid")
case("a token from another issuer is refused", lambda: verify(token(iss="https://evil.test")),
     "token_invalid")

other = ec.generate_private_key(ec.SECP256R1())
forged = jwt.encode({"sub":"user_attacker","aud":AUD,"iss":ISS,
                     "exp":int(time.time())+300},
                    other, algorithm="ES256", headers={"kid":"test-key-1"})
case("a token signed by another key is refused", lambda: verify(forged), "token_invalid")

unsigned = jwt.encode({"sub":"user_attacker","exp":int(time.time())+300},
                      key=None, algorithm="none")
case("an unsigned token is refused", lambda: verify(unsigned), "token_unverifiable")

# The regression. An EdDSA token must be refused whatever else changes, because accepting
# a second algorithm gives an attacker a second door to try. If somebody widens ALGORITHMS
# to make an unrelated problem go away, this fails and says why.
ed_key = ed25519.Ed25519PrivateKey.generate()
ed_token = jwt.encode({"sub":"user_attacker","aud":AUD,"iss":ISS,
                       "exp":int(time.time())+300},
                      ed_key, algorithm="EdDSA", headers={"kid":"test-key-1"})
case("an EdDSA token is refused, whatever else changes", lambda: verify(ed_token),
     "token_invalid")

# The check that would have caught both mistakes. What the service accepts must be what the
# provider publishes, and the provider's answer is the recorded fixture rather than anyone's
# recollection of a documentation page.
assert ALGORITHMS == PROVIDER_ALGS, (
    f"The service accepts {ALGORITHMS} but the provider publishes {PROVIDER_ALGS}. "
    f"Refetch fixtures/provider_jwks_2026-09-23.json before changing either."
)

# emailVerified false must be refused. An unverified address is a claim by whoever signed
# up, not a fact, and this product attaches payout history to it.
from app.auth import require_account
class Req:
    def __init__(self, tok): self.headers = {"authorization": "Bearer " + tok}
case("an unverified email address is refused",
     lambda: require_account(Req(token(email="x@y.test", emailVerified=False))),
     "email_unverified")

srv.shutdown()
print(f"\n{'all cases passed' if not failures else 'FAILURES: ' + ', '.join(failures)}")
sys.exit(1 if failures else 0)
