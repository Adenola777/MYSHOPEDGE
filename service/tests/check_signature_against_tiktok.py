"""Check our signature against one TikTok produced itself.

`_sign` was written from TikTok's documented steps and has never produced a signature TikTok
accepted. Every call this service will ever make rests on it. This proves it, or says which
step is wrong, without needing an approved app, a live shop, or a single API call.

HOW TO RUN IT

1. Open Partner Center's API Testing Tool and make any call. It does not matter which, and
   it does not matter whether the call succeeds. The tool signs the request for you, which
   is the whole point: its signature is TikTok's own answer for those inputs.

2. Copy the full request URL the tool shows. It carries `app_key`, `timestamp` and `sign`.
   None of those is a secret. `sign` is a digest, and `app_key` is a public identifier.

3. Run this with your app secret in the environment, so the secret stays on your machine and
   never reaches a file, a log or a conversation:

       cd service
       TIKTOK_APP_SECRET=... python3 tests/check_signature_against_tiktok.py 'PASTE_URL_HERE'

   Quote the URL. An unquoted one is cut at the first `&` by the shell and the check then
   compares the wrong thing.

   For a POST, add the exact request body as a second argument.

WHAT A FAILURE TELLS YOU

It does not just say no. It recomputes the signature under each plausible misreading of the
documented steps and reports which one TikTok's own value matches. That turns a failure into
a one-line fix rather than an afternoon.

WHAT THIS CANNOT PROVE

That the timestamp window, the headers or the endpoint are right. It proves one thing, which
is that given identical inputs we produce the digest TikTok produces. That is the part that
cannot be debugged from an error message, because a wrong signature and a wrong app secret
return the same refusal.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import sys
from urllib.parse import parse_qsl, urlparse


def variant(name: str, path: str, query: dict[str, str], body: bytes, secret: str,
            *, wrap: bool = True, include_path: bool = True, sort: bool = True,
            include_token: bool = False, separator: str = "") -> tuple[str, str]:
    """One reading of the algorithm. `wrap=True, include_path=True, sort=True` is ours."""
    keys = [k for k in query if k != "sign" and (include_token or k != "access_token")]
    if sort:
        keys = sorted(keys)
    ordered = separator.join(f"{k}{query[k]}" for k in keys)
    head = f"{path}{ordered}" if include_path else ordered
    payload = (f"{secret}{head}".encode() + body + secret.encode()) if wrap \
        else (head.encode() + body)
    return name, hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


def main() -> int:
    secret = os.environ.get("TIKTOK_APP_SECRET")
    if not secret:
        print("Set TIKTOK_APP_SECRET in the environment. Do not pass it as an argument,",
              file=sys.stderr)
        print("because arguments are visible to other processes and land in shell history.",
              file=sys.stderr)
        return 2

    if len(sys.argv) < 2:
        print(__doc__)
        return 2

    url = sys.argv[1]
    body = sys.argv[2].encode() if len(sys.argv) > 2 else b""

    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    theirs = query.get("sign")
    path = parsed.path

    if not theirs:
        print("That URL carries no `sign` parameter, so there is nothing to compare against.")
        print("Copy the request URL the testing tool built, not the one you typed into it.")
        return 2
    if not path:
        print("That URL has no path. Copy the whole request URL including the host.")
        return 2

    print(f"path        {path}")
    print(f"parameters  {', '.join(sorted(k for k in query if k != 'sign'))}")
    print(f"body        {len(body)} bytes")
    print(f"TikTok      {theirs}")

    ours = variant("ours", path, query, body, secret)[1]
    print(f"ours        {ours}")

    if ours == theirs:
        print("\nMATCH. The implementation is correct for these inputs.")
        print("Record it in A28 as verified against a real signature, with today's date.")
        return 0

    print("\nNO MATCH. Testing which reading of the steps TikTok actually used.\n")

    candidates = [
        variant("no secret wrapping (step 6 skipped)", path, query, body, secret, wrap=False),
        variant("path not included (step 4 skipped)", path, query, body, secret, include_path=False),
        variant("keys left unsorted (step 2 skipped)", path, query, body, secret, sort=False),
        variant("access_token included in the input", path, query, body, secret, include_token=True),
        variant("body not appended (step 5 skipped)", path, query, b"", secret),
        variant("parameters joined with &", path, query, body, secret, separator="&"),
    ]

    # A variant that computes to the same digest as ours is not a different reading for
    # these particular inputs. Two already-sorted keys are sorted either way, and a request
    # with no body cannot show whether the body is appended. Printing those alongside the
    # real candidates invites somebody to change the code on the strength of a coincidence,
    # so they are counted and set aside instead.
    same = [name for name, digest in candidates if digest == ours]
    distinct = [(name, digest) for name, digest in candidates if digest != ours]

    hit = False
    for name, digest in distinct:
        mark = "  <-- THIS ONE" if digest == theirs else ""
        if digest == theirs:
            hit = True
        print(f"  {digest}  {name}{mark}")

    if same:
        print(f"\n  {len(same)} further variant(s) cannot be told apart on these inputs, so they")
        print(f"  prove nothing either way: {'; '.join(same)}.")
        print("  Re-run against a signed POST with a body and several parameters to separate them.")

    if hit:
        print("\nOne variant matches. Change `_sign` in app/connections.py to that reading,")
        print("correct A28.2, and run this again.")
    else:
        print("\nNo variant matches. The most likely causes, in order:")
        print("  1. TIKTOK_APP_SECRET is not the secret that signed this request.")
        print("  2. The URL was truncated. An unquoted URL is cut at the first & by the shell.")
        print("  3. This was a POST and its body was not passed as the second argument.")
        print("  4. The tool encoded a parameter value differently from how it signed it.")
        print("\nRule out 1 and 2 before touching the code. Neither is a defect in _sign.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
