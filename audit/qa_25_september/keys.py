import json, jwt
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
k = ec.generate_private_key(ec.SECP256R1())
open("key.pem","wb").write(k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
jwk = json.loads(jwt.algorithms.ECAlgorithm.to_jwk(k.public_key())); jwk.update(kid="qa1", alg="ES256", use="sig")
json.dump({"keys":[jwk]}, open("jwks.json","w"))
