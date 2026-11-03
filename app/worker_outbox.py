"""Outbox drain loop (FR-CASE-001 AC2)."""
import time, urllib.request, json, os, uuid
from jose import jwt
URL = "http://localhost:8000/internal/outbox-drain"
def headers():
    service_id = "outbox-worker"
    keys = json.loads(os.environ.get("SERVICE_TOKEN_KEYS", "{}"))
    key = keys.get(service_id)
    issuer, audience = os.getenv("JWT_ISSUER"), os.getenv("JWT_AUDIENCE")
    if not key or len(key) < 32 or not issuer or not audience:
        raise RuntimeError("configure JWT_ISSUER, JWT_AUDIENCE and SERVICE_TOKEN_KEYS for outbox-worker")
    now = int(time.time())
    token = jwt.encode({"sub": service_id, "service_id": service_id, "iss": issuer, "aud": audience,
                       "iat": now, "exp": now + 60, "jti": uuid.uuid4().hex,
                       "tenant_id": os.getenv("SERVICE_TENANT_ID", "TNT-TEST"), "role": "supervisor",
                       "token_use": "service", "scope": ["sla.read"]}, key, algorithm="HS256")
    return {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
if __name__ == "__main__":
    while True:
        try:
            req = urllib.request.Request(URL, data=b"{}", headers=headers(), method="POST")
            print(json.loads(urllib.request.urlopen(req, timeout=10).read()))
        except Exception as e:
            print("drain failed:", e)
        time.sleep(15)
