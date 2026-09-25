import sys, time, jwt
sub = sys.argv[1]; extra = dict(a.split("=",1) for a in sys.argv[2:])
now = int(time.time())
print(jwt.encode({"sub":sub,"iss":"qa-issuer","aud":"qa-aud","iat":now,"exp":now+6*3600,**extra}, open("key.pem").read(), algorithm="ES256", headers={"kid":"qa1"}))
