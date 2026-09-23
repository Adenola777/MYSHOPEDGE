#!/usr/bin/env bash
# Probe what the TikTok sandbox gives us, in one run.
#
# Written 23 September 2026. It has never been executed, because the toolkit refuses to
# authenticate without the macOS Keychain or Windows DPAPI and the session that wrote it
# ran on Linux. Treat every step as unverified until it has run once.
#
# It answers one question that the specification currently answers by assumption:
# whether a sandbox shop returns settlement statements. If it does, most of A11 can be
# proved without a real seller. If it does not, the settlement half stays blocked on the
# real shop authorisation in RUNBOOK_tiktok_connection.md and we stop hoping otherwise.
#
# Run it from the repository root on a machine where `tts_open_toolkit auth status`
# reports authenticated:
#
#     bash testdata/sandbox_probe.sh
#
# It creates at most one sandbox order. It deletes nothing, because the toolkit offers no
# cleanup route.

set -uo pipefail

REGION="${REGION:-GB}"
say() { printf '\n=== %s ===\n' "$1"; }

say "1. Authentication"
if ! tts_open_toolkit auth status --json | grep -q '"authenticated": *true'; then
  echo "Not authenticated. Run: tts_open_toolkit auth login"
  exit 1
fi
echo "Authenticated."

say "2. Sandbox shops in ${REGION}"
tts_open_toolkit sandbox shop list --region-code "${REGION}" --json | tee /tmp/mse_shops.json
SHOP_ID="$(python3 -c '
import json,sys
d=json.load(open("/tmp/mse_shops.json"))
def walk(o):
    if isinstance(o,dict):
        for k,v in o.items():
            if k in ("shop_id","id") and isinstance(v,str): yield v
            yield from walk(v)
    elif isinstance(o,list):
        for v in o: yield from walk(v)
print(next(iter(walk(d)),""))
')"

if [ -z "${SHOP_ID}" ]; then
  echo "No sandbox shop exists. Create one in the Partner Center sandbox page, then run again."
  exit 1
fi
echo "Using shop ${SHOP_ID}"

say "3. Products on that shop"
# The toolkit cannot create products. If this list is empty, create one by hand in the
# Partner Center sandbox page and run this script again.
tts_open_toolkit sandbox product list --shop-id "${SHOP_ID}" --json | tee /tmp/mse_products.json

say "4. The question that matters. Does a sandbox shop return statements?"
# This is the ordinary Shop API rather than a sandbox management endpoint, which is why it
# is a direct call. A17 fixed the version: settlement detail must be 202501, because 202309
# returns 69 fields and omits every reserve field. Do not change it back.
#
# TIKTOK_SANDBOX_TOKEN and TIKTOK_SANDBOX_CIPHER come from the environment. Neither is
# written here and neither is printed, for the reason in the runbook.
if [ -z "${TIKTOK_SANDBOX_TOKEN:-}" ] || [ -z "${TIKTOK_SANDBOX_CIPHER:-}" ]; then
  echo "Skipped. Set TIKTOK_SANDBOX_TOKEN and TIKTOK_SANDBOX_CIPHER to run this step."
  echo "Everything above still stands."
  exit 0
fi

BASE="https://open-api.tiktokglobalshop.com"
for path in \
  "/finance/202309/statements" \
  "/finance/202501/statements" \
  "/finance/202309/payments" \
  "/order/202309/orders/search"
do
  code="$(curl -sS -o /tmp/mse_probe.json -w '%{http_code}' \
    -H "x-tts-access-token: ${TIKTOK_SANDBOX_TOKEN}" \
    -H "content-type: application/json" \
    "${BASE}${path}?shop_cipher=${TIKTOK_SANDBOX_CIPHER}&page_size=5" || echo "000")"
  # The HTTP status is not the answer on this API. A 200 carrying code 36004 is a refusal,
  # so the body's own code is printed alongside it.
  body_code="$(python3 -c '
import json
try: print(json.load(open("/tmp/mse_probe.json")).get("code","?"))
except Exception: print("unreadable")
')"
  printf '  %-40s HTTP %s   body code %s\n' "${path}" "${code}" "${body_code}"
done

say "What to do with the result"
cat <<'NOTE'
A statements path answering with body code 0 and a non-empty list means the sandbox carries
finance data. In that case A11 can be proved against it, and the only questions left for a
real shop are how far back statements go and what a settlement export calls its columns,
because both are properties of a real seller's history rather than of the API.

A statements path answering with any other code means the sandbox covers the order
lifecycle only. Record that in A17 and stop treating the sandbox as a route to settlement
coverage.
NOTE
