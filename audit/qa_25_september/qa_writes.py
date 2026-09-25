"""QA of authentication, tenancy and the four writes, against the local copy of development."""
import json, time, uuid, urllib.request, urllib.error, psycopg, jwt
BASE="http://127.0.0.1:8801/v1"; SH="8a773a13-73b5-a382-7dd0-fda02e950369"; ACC="56e487ea-e0fa-3691-7857-724855e716fc"
KEY=open("key.pem").read()
def mint(sub, **kw):
    now=int(time.time()); c={"sub":sub,"iss":"qa-issuer","aud":"qa-aud","iat":now,"exp":now+3600}; c.update(kw)
    return jwt.encode(c, KEY, algorithm="ES256", headers={"kid":"qa1"})
A=mint("stack|synthetic-uk-shop"); B=mint("stack|qa-other", email="other@qa.test", name="Other Seller")
db=psycopg.connect("postgresql://postgres@/myshopedge?host=/tmp&port=5439", autocommit=True)
def q(sql,*a):
    c=db.execute(sql,a)
    return c.fetchall() if c.description else []
def call(method, path, tok=A, body=None, headers=None):
    h={"Content-Type":"application/json"}; h.update(headers or {})
    if tok: h["Authorization"]=f"Bearer {tok}"
    r=urllib.request.Request(BASE+path, method=method, headers=h, data=json.dumps(body).encode() if body is not None else None)
    try:
        with urllib.request.urlopen(r) as f: return f.status, json.loads(f.read() or b"{}")
    except urllib.error.HTTPError as e: return e.code, json.loads(e.read() or b"{}")
res=[]
def check(name, got, want):
    ok=got==want; res.append((ok,name,got,want)); print(("PASS" if ok else "FAIL"), name, "" if ok else f"got {got!r} want {want!r}")

# Outside services without their secrets, and the TikTok callback with a forged state
check("billing: subscription refuses cleanly without Stripe", call("POST","/billing/subscription",body={"plan":"starter"})[1].get("code"), "billing_unconfigured")
check("stripe webhook: unsigned is 400", call("POST","/webhooks/stripe",tok=None,body={"type":"x"})[0], 400)
check("tiktok callback: forged state is 400 state_invalid", call("GET","/connections/tiktok/callback?code=x&state=forged",tok=None)[1].get("code"), "state_invalid")
check("tiktok authorize: needs sign in", call("POST","/connections/tiktok/authorize",tok=None,body={"return_to":"/shops"})[0], 401)
check("tiktok authorize: foreign return_to refused", call("POST","/connections/tiktok/authorize",body={"return_to":"https://evil.example"})[0] in (400,422), True)
# Authentication
check("auth: no token is 401", call("GET","/me",tok=None)[0], 401)
check("auth: tampered signature is 401", call("GET","/me",tok=A[:-4]+("AAAA" if not A.endswith("AAAA") else "BBBB"))[0], 401)
check("auth: wrong audience is 401", call("GET","/me",tok=mint("stack|synthetic-uk-shop",aud="someone-else"))[0], 401)
check("auth: wrong issuer is 401", call("GET","/me",tok=mint("stack|synthetic-uk-shop",iss="https://evil.example"))[0], 401)
check("auth: expired is 401 token_expired", call("GET","/me",tok=mint("stack|synthetic-uk-shop",exp=int(time.time())-60))[1].get("code"), "token_expired")
none_tok=jwt.encode({"sub":"stack|synthetic-uk-shop","iss":"qa-issuer","aud":"qa-aud","exp":int(time.time())+600}, None, algorithm="none")
check("auth: alg none is 401", call("GET","/me",tok=none_tok)[0], 401)
check("auth: emailVerified false is 403", call("GET","/me",tok=mint("stack|synthetic-uk-shop",emailVerified=False))[0], 403)

# A second seller, created on first sign in
s,me=call("GET","/me",tok=B)
check("tenant B: account created on first sign in", (s, me.get("email"), me.get("shop_count")), (200,"other@qa.test",0))
check("tenant B: sees no shops", call("GET","/shops",tok=B)[1].get("shops"), [])
sku=q("select id::text from skus where shop_id=%s order by id limit 1",SH)[0][0]
disc=q("select id::text from discrepancies where status='open' limit 1")[0][0]
sett=q("select id::text from settlements limit 1")[0][0]
prod=q("select id::text from products limit 1")[0][0]
reads=["/today","/money","/products",f"/products/{prod}","/records","/returns","/returns/metrics","/settlements",
       f"/settlements/{sett}","/stock",f"/stock/{sku}/movements","/sync","/needs-you","/discrepancies","/costs/coverage"]
ghost=str(uuid.uuid4())
for p in reads:
    sb,bb=call("GET",f"/shops/{SH}{p}",tok=B); sg,bg=call("GET",f"/shops/{ghost}{p}",tok=B)
    check(f"tenant B: {p} on A's shop is refused like a missing shop", (sb, bb.get("code")), (sg, bg.get("code")))
    check(f"tenant B: {p} refusal is 403 forbidden_shop", (sb, bb.get("code")), (403,"forbidden_shop"))
before=q("select count(*) from product_costs")[0][0]
check("tenant B: cannot set A's cost", call("PUT",f"/shops/{SH}/skus/{sku}/cost",tok=B,body={"cost":{"amount_minor":1,"currency":"GBP"}})[0], 403)
check("tenant B: cannot adjust A's stock", call("POST",f"/shops/{SH}/stock/{sku}/adjustments",tok=B,body={"quantity":-1,"reason":"x"},headers={"Idempotency-Key":str(uuid.uuid4())})[0], 403)
check("tenant B: cannot resolve A's discrepancy", call("POST",f"/shops/{SH}/discrepancies/{disc}/resolve",tok=B,body={"resolution":"explained","note":"x"},headers={"Idempotency-Key":str(uuid.uuid4())})[0], 403)
check("tenant B: nothing written", q("select count(*) from product_costs")[0][0], before)

# A notification for A, inserted as the fixture the seed lacks
nid=str(uuid.uuid4())
q("delete from notifications where type='test'")
q("insert into notifications (id, account_id, shop_id, type, severity, title, body) values (%s,%s,%s,'test','warning','QA notification','Inserted by the QA run')", nid, ACC, SH)
s,nl=call("GET","/notifications?status=unread")
check("notifications: A sees its notification", (s, [n["id"] for n in nl.get("notifications",[])], nl.get("unread_count")), (200,[nid],1))
check("notifications: B does not see it", call("GET","/notifications",tok=B)[1].get("notifications"), [])
check("notifications: B cannot mark it", call("PATCH",f"/notifications/{nid}",tok=B,body={"status":"read"})[0], 404)
s,n=call("PATCH",f"/notifications/{nid}",body={"status":"read"})
check("notifications: A marks it read", (s, n.get("status")), (200,"read"))
check("notifications: status stored", q("select status from notifications where id=%s",nid)[0][0], "read")
check("notifications: unread count falls to 0", call("GET","/notifications?status=unread")[1].get("unread_count"), 0)

# Cost
s,c=call("PUT",f"/shops/{SH}/skus/{sku}/cost",body={"cost":{"amount_minor":777,"currency":"GBP"},"effective_from":"2026-09-25"})
check("cost: A sets a cost", s in (200,201), True)
check("cost: stored", q("select cost_minor from product_costs where sku_id=%s order by effective_from desc, created_at desc limit 1",sku)[0][0], 777)
check("cost: negative refused", call("PUT",f"/shops/{SH}/skus/{sku}/cost",body={"cost":{"amount_minor":-5,"currency":"GBP"}})[0] in (400,422), True)
check("cost: wrong currency refused", call("PUT",f"/shops/{SH}/skus/{sku}/cost",body={"cost":{"amount_minor":5,"currency":"USD"}})[0] in (400,409,422), True)

# Stock adjustment, replayed with the same key
key=str(uuid.uuid4()); n0=q("select count(*) from stock_movements where sku_id=%s",sku)[0][0]
s1,a1=call("POST",f"/shops/{SH}/stock/{sku}/adjustments",body={"quantity":-2,"reason":"QA: two damaged"},headers={"Idempotency-Key":key})
s2,a2=call("POST",f"/shops/{SH}/stock/{sku}/adjustments",body={"quantity":-2,"reason":"QA: two damaged"},headers={"Idempotency-Key":key})
check("adjustment: created", s1, 201)
check("adjustment: replay returns the first answer", (s2, a2), (s1, a1))
check("adjustment: one movement written", q("select count(*) from stock_movements where sku_id=%s",sku)[0][0], n0+1)
s3,_=call("POST",f"/shops/{SH}/stock/{sku}/adjustments",body={"quantity":-3,"reason":"different"},headers={"Idempotency-Key":key})
check("adjustment: same key, different body is refused", s3 in (409,422), True)
check("adjustment: without a key is accepted, as the contract makes the key optional", call("POST",f"/shops/{SH}/stock/{sku}/adjustments",body={"quantity":-1,"reason":"QA: no key"})[0], 201)
st=[i for i in call("GET",f"/shops/{SH}/stock?limit=100")[1]["items"] if i["sku_id"]==sku][0]
check("adjustment: stock screen shows both adjustments", st["adjusted_delta"], -3)

# Resolve
k=str(uuid.uuid4())
s,r=call("POST",f"/shops/{SH}/discrepancies/{disc}/resolve",body={"resolution":"explained","note":"QA: TikTok penalty explained"},headers={"Idempotency-Key":k})
check("resolve: accepted", (s, r.get("discrepancy",{}).get("status")), (200,"resolved"))
check("resolve: stored", q("select status, resolution from discrepancies where id=%s",disc)[0], ("resolved","explained"))
check("resolve: replay is the same", call("POST",f"/shops/{SH}/discrepancies/{disc}/resolve",body={"resolution":"explained","note":"QA: TikTok penalty explained"},headers={"Idempotency-Key":k}), (s,r))
check("resolve: Needs you no longer lists it", any(i["type"]=="open_discrepancies" for i in call("GET",f"/shops/{SH}/needs-you")[1]["items"]), False)
print(f"\n{sum(r[0] for r in res)} passed, {sum(not r[0] for r in res)} failed")
json.dump([dict(ok=o,name=n,got=g,want=w) for o,n,g,w in res], open("writes.json","w"), indent=1, default=str)
