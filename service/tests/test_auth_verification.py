"""Puts real tokens through verify() against a locally served JWKS.

This is the test that matters most in the service. A flaw here is not a wrong figure on a
screen, it is one seller reading another seller's payouts. It runs without a database and
without the identity provider, by generating a key, serving a JWKS on localhost, and
signing tokens with it.

    python3 tests/test_auth_verification.py

Rewritten 23 September 2026. The previous version generated ES256 keys and signed its
fixtures with ES256, while the provider signs EdDSA over Ed25519. Every case passed and
every real token would have been refused. A test that shares the code's assumption cannot
catch the code being wrong about it, so the key type here is taken from the provider's own
published JWKS rather than from what the service expects, and the last case below exists
specifically to fail if anyone widens the algorithm list again.
"""

import json, os, sys, threading, time, http.server, socketserver
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import jwt
from cryptography.hazmat.primitives.asymmetric import ed25519, ec

# Ed25519, because that is what https://<project>.neonauth.<region>.aws.neon.tech
# /neondb/auth/.well-known/jwks.json publishes: {"alg":"EdDSA","crv":"Ed25519","kty":"OKP"}
key = ed25519.Ed25519PrivateKey.generate()
jwk = json.loads(jwt.algorithms.OKPAlgorithm.to_jwk(key.public_key()))
jwk.update({"kid": "test-key-1", "use": "sig", "alg": "EdDSA"})
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
    return jwt.encode(claims, key, algorithm="EdDSA", headers={"kid": "test-key-1"})

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

c = case("a valid EdDSA token resolves its subject", lambda: verify(token()))
assert c and c["sub"] == "user_synthetic_uk_shop"

# Managed tokens carry no custom claims. This is not a failure, and nothing downstream may
# assume an email is present. The email comes from neon_auth.users_sync instead.
assert "email" not in c, "the fixture must not carry claims the provider does not issue"

case("an expired token is refused", lambda: verify(token(exp=int(time.time())-10)),
     "token_expired")
case("a token with no exp is refused",
     lambda: verify(jwt.encode({"sub":"x","aud":AUD,"iss":ISS}, key,
                               algorithm="EdDSA", headers={"kid":"test-key-1"})),
     "token_invalid")
case("a token for another audience is refused", lambda: verify(token(aud="another-project")),
     "token_invalid")
case("a token from another issuer is refused", lambda: verify(token(iss="https://evil.test")),
     "token_invalid")

other = ed25519.Ed25519PrivateKey.generate()
forged = jwt.encode({"sub":"user_attacker","aud":AUD,"iss":ISS,
                     "exp":int(time.time())+300},
                    other, algorithm="EdDSA", headers={"kid":"test-key-1"})
case("a token signed by another key is refused", lambda: verify(forged), "token_invalid")

unsigned = jwt.encode({"sub":"user_attacker","exp":int(time.time())+300},
                      key=None, algorithm="none")
case("an unsigned token is refused", lambda: verify(unsigned), "token_unverifiable")

# The regression. An ES256 token must be refused whatever else changes, because accepting
# a second algorithm gives an attacker a second door to try. If somebody widens ALGORITHMS
# to make an unrelated problem go away, this fails and says why.
es_key = ec.generate_private_key(ec.SECP256R1())
es_token = jwt.encode({"sub":"user_attacker","aud":AUD,"iss":ISS,
                       "exp":int(time.time())+300},
                      es_key, algorithm="ES256", headers={"kid":"test-key-1"})
case("an ES256 token is refused, whatever else changes", lambda: verify(es_token),
     "token_invalid")
assert ALGORITHMS == ["EdDSA"], f"ALGORITHMS widened to {ALGORITHMS}"

srv.shutdown()
print(f"\n{'all cases passed' if not failures else 'FAILURES: ' + ', '.join(failures)}")
sys.exit(1 if failures else 0)
