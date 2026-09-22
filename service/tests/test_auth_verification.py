"""Puts real tokens through verify() against a locally served JWKS.

This is the test that matters most in the service. A flaw here is not a wrong figure
on a screen, it is one seller reading another seller's payouts. It runs without a
database and without the identity provider, by generating a key, serving a JWKS on
localhost, and signing tokens with it.

    python3 tests/test_auth_verification.py
"""

import json, os, sys, threading, time, http.server, socketserver
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import jwt
from cryptography.hazmat.primitives.asymmetric import ec

key = ec.generate_private_key(ec.SECP256R1())
pub = key.public_key()
jwk = json.loads(jwt.algorithms.ECAlgorithm.to_jwk(pub))
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

os.environ["STACK_JWKS_URL"] = f"http://127.0.0.1:{port}/jwks.json"
os.environ["STACK_PROJECT_ID"] = "f1762e29-4750-42f6-80e1-c94b040a72e8"
os.environ["STACK_ISSUER"] = "https://api.stack-auth.com"

from app.auth import verify
from app.problems import Problem

def token(**over):
    now = int(time.time())
    claims = {"sub": "stack|synthetic-uk-shop", "email": "owner@synthetic-uk-shop.test",
              "name": "Adenola", "aud": os.environ["STACK_PROJECT_ID"],
              "iss": os.environ["STACK_ISSUER"], "iat": now, "exp": now + 300}
    claims.update(over)
    return jwt.encode(claims, key, algorithm="ES256", headers={"kid": "test-key-1"})

def case(name, fn, expect_code=None):
    try:
        out = fn()
        print(f"  PASS  {name}" if expect_code is None else f"  FAIL  {name}: expected {expect_code}, got success")
        return out
    except Problem as e:
        ok = e.code == expect_code
        print(f"  {'PASS' if ok else 'FAIL'}  {name}: {e.code}")
        return None

print("verify()")
c = case("a valid token resolves its subject", lambda: verify(token()))
assert c and c["sub"] == "stack|synthetic-uk-shop"
case("an expired token is refused", lambda: verify(token(exp=int(time.time())-10)), "token_expired")
case("a token with no exp is refused", lambda: verify(jwt.encode({"sub":"x","aud":os.environ["STACK_PROJECT_ID"],"iss":os.environ["STACK_ISSUER"]}, key, algorithm="ES256", headers={"kid":"test-key-1"})), "token_invalid")
case("a token for another audience is refused", lambda: verify(token(aud="some-other-project")), "token_invalid")
case("a token from another issuer is refused", lambda: verify(token(iss="https://evil.test")), "token_invalid")

other = ec.generate_private_key(ec.SECP256R1())
forged = jwt.encode({"sub":"stack|attacker","aud":os.environ["STACK_PROJECT_ID"],
                     "iss":os.environ["STACK_ISSUER"],"exp":int(time.time())+300},
                    other, algorithm="ES256", headers={"kid":"test-key-1"})
case("a token signed by another key is refused", lambda: verify(forged), "token_invalid")

unsigned = jwt.encode({"sub":"stack|attacker","exp":int(time.time())+300}, key=None, algorithm="none")
case("an unsigned token is refused", lambda: verify(unsigned), "token_unverifiable")
srv.shutdown()
