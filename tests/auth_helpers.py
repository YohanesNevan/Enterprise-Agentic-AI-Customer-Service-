"""Signed credentials for API tests; caller-controlled identity headers are not credentials."""
import os
import time
import uuid
from jose import jwt

def auth_headers(role="cs_agent", actor="agent-1", tenant="TNT-TEST", *, token_use=None, lifetime=None, extra=None):
    token_use = token_use or ("service" if role == "ai_agent" else "access")
    if lifetime is None:
        lifetime = 300 if token_use == "service" else 900
    now = int(time.time())
    claims = {"sub": actor, "iss": os.environ["JWT_ISSUER"], "aud": os.environ["JWT_AUDIENCE"],
              "iat": now, "exp": now + lifetime, "jti": str(uuid.uuid4()),
              "tenant_id": tenant, "role": role, "token_use": token_use}
    key = os.environ["JWT_SIGNING_KEY"]
    if token_use == "service":
        claims["service_id"] = actor
        from app.core.rbac import ROLE_PERMS
        claims["scope"] = extra if extra is not None else sorted(ROLE_PERMS[role])
        key = __import__("json").loads(os.environ["SERVICE_TOKEN_KEYS"])[actor]
    if extra and token_use != "service": claims.update(extra)
    return {"Authorization": "Bearer " + jwt.encode(claims, key, algorithm="HS256")}
