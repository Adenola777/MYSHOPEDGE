# Test credentials and local QA harness

This project does not use the standard Emergent stack. It is FastAPI in `/app/service`,
PostgreSQL, and a Next.js front end in `/app/web`. Sign-in is Stack Auth (ES256 JWTs),
which cannot be reached from this container, so the harness mints its own ES256 tokens.

## Local harness, rebuilt from the repository (data dir is outside /app, so re-run after a pod restart)

1. Build the database (PostgreSQL 15, local):
   - `pg_ctlcluster 15 main start`
   - `su postgres -c "psql -v ON_ERROR_STOP=1 -f /app/scripts/00_superuser.sql"`
   - `su postgres -c "psql -c 'drop database if exists myshopedge'"`
   - `su postgres -c "psql -c 'create database myshopedge owner mse_migrator'"`
   - `su postgres -c "psql -d myshopedge -f /app/scripts/01_dbsetup.sql"`
   - `python3 /app/scripts/local_migrate.py`   (backfills 0001-0009, applies base + 0010-0024, loads seed)
2. Tokens: `cd /app/scripts/qa && python3 keys.py` then serve `python3 -m http.server 8899` in that dir.
   Mint: `cd /app/scripts/qa && python3 mint.py 'stack|synthetic-uk-shop' emailVerified=true email=owner@synthetic-uk-shop.test > tok_a`
3. Service: `bash /app/scripts/run_service.sh &`  (serves on http://127.0.0.1:8801, routes under /v1)

## Local database roles (LOCAL THROWAWAY ONLY, never production)
- Service role: `postgresql://mse_app:apppw_local@127.0.0.1:5432/myshopedge`
- Migrator/admin: `postgresql://mse_migrator:migpw_local@127.0.0.1:5432/myshopedge`

## Seeded seller account
- id: `56e487ea-e0fa-3691-7857-724855e716fc`
- auth_subject: `stack|synthetic-uk-shop`
- email: `owner@synthetic-uk-shop.test`
- One connected shop, 119 ledger entries (July and August 2026).

## Local auth env (in /app/service/.env)
- NEON_AUTH_JWKS_URL=http://127.0.0.1:8899/jwks.json
- NEON_AUTH_ISSUER=qa-issuer
- NEON_AUTH_AUDIENCE=qa-aud
- A ready bearer token lives at `/app/scripts/qa/tok_a` (ES256, ~6h expiry).

## Stripe (platform test sandbox, wired into /app/service/.env)
- STRIPE_SECRET_KEY (sk_test), STRIPE_WEBHOOK_SECRET (whsec_), STRIPE_PUBLISHABLE_KEY (pk_test).
- STRIPE_PRICE_STARTER/GROWTH/PRO created by `python3 service/scripts/setup_stripe.py`.
- Webhook signing for tests: HMAC-SHA256 of `<ts>.<raw_body>` with STRIPE_WEBHOOK_SECRET.
- Test card 4242 4242 4242 4242 (browser card confirmation needs js.stripe.com, which this
  container blocks; verify that step on the deployed app).

## Billing QA
- `/app/service/tests/test_billing_local_harness.py` (pytest, needs the harness running): 9 tests, all pass.
- `/app/scripts/qa/test_billing_webhook.py`: signed-webhook driver, all checks pass.
