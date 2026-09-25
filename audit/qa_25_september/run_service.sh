cd /home/user/My-ShopEdge/service
export DATABASE_URL="postgresql://qa_local@/myshopedge?host=/tmp&port=5439"
export NEON_AUTH_JWKS_URL=http://127.0.0.1:8766/jwks.json NEON_AUTH_ISSUER=qa-issuer NEON_AUTH_AUDIENCE=qa-aud
export ALLOWED_ORIGINS=http://localhost:3977
exec /tmp/claude-0/-home-user-My-ShopEdge/4022bda9-b4f8-509d-a2b4-4172db8dfff3/scratchpad/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8801
