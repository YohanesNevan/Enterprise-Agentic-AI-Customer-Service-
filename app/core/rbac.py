"""Server-side bearer authentication and deny-by-default authorization."""
from __future__ import annotations

import json
import os
import time
from typing import Any, TypedDict

from fastapi import Depends, HTTPException, Request
from jose import JWTError, jwt

# FRD §4.2. Role permissions are server policy; claims can narrow, never expand them.
ROLE_PERMS: dict[str, set[str]] = {
    "customer": {"ticket.read", "case.read", "evidence.upload", "feedback.submit", "handoff.initiate", "conversation.read", "conversation.write"},
    "ai_agent": {"ticket.create", "ticket.read", "case.create", "case.read", "evidence.request", "sla.read", "handoff.initiate", "conversation.read", "conversation.write", "knowledge.read", "tool.invoke"},
    "cs_agent": {"conversation.read", "conversation.write", "knowledge.read", "knowledge.document.ingest", "tool.invoke", "ticket.create", "ticket.read", "ticket.update", "case.create", "case.read", "case.update", "evidence.request", "handoff.accept", "handoff.initiate", "sla.read"},
    "supervisor": {"conversation.read", "conversation.write", "knowledge.read", "knowledge.document.ingest", "tool.invoke", "case.read", "case.create", "case.update", "case.close", "sla.read", "sla.override", "escalation.resolve", "handoff.initiate", "handoff.accept", "evidence.request", "tool.invoke_write_sensitive", "audit.read", "analytics.read"},
    "complaint_officer": {"case.read", "case.update", "case.close", "evidence.adjudicate", "sla.read", "knowledge.read", "knowledge.document.ingest"},
    "qa_analyst": {"qa.review", "case.read", "knowledge.read", "knowledge.document.ingest"},
    "knowledge_manager": {"knowledge.read", "knowledge.write", "knowledge.document.ingest"},
    # RBAC-05: administrative privileges do not grant conversation-content access.
    "admin": {"tool.registry_manage", "user.manage", "config.manage", "knowledge.read", "knowledge.document.ingest"},
    "management": {"analytics.read", "knowledge.read", "knowledge.document.ingest"},
}
HUMAN_ROLES = set(ROLE_PERMS) - {"ai_agent"}


class VerifiedPrincipal(TypedDict):
    actor_id: str
    actor_type: str
    identity_type: str
    role: str
    tenant_id: str
    permissions: set[str]
    scope: list[str]
    jti: str
    token_use: str
    assurance_level: str


def _unauthenticated() -> HTTPException:
    return HTTPException(status_code=401, detail={"error_code": "E_UNAUTHENTICATED", "message": "valid bearer credential required"}, headers={"WWW-Authenticate": "Bearer"})


def _forbidden(role: str, permission: str) -> HTTPException:
    return HTTPException(status_code=403, detail={"error_code": "E_UNAUTHORISED", "message": f"role {role} lacks {permission}", "customer_message_id": "AUTH.FORBIDDEN", "retryable": False, "details": []})


def _base_claims(token: str, key: str, audience: str, issuer: str, expected_use: str) -> dict[str, Any]:
    try:
        claims = jwt.decode(token, key, algorithms=["HS256"], audience=audience, issuer=issuer,
                            options={"require_sub": True, "require_iat": True, "require_exp": True, "require_jti": True})
        now = int(time.time())
        iat, exp = int(claims["iat"]), int(claims["exp"])
        if claims.get("token_use") != expected_use or not claims.get("tenant_id") or iat > now + 30 or exp <= now or exp <= iat:
            raise JWTError("invalid claims")
        return claims
    except (JWTError, KeyError, TypeError, ValueError):
        raise _unauthenticated()


async def get_principal(request: Request) -> VerifiedPrincipal:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer ") or not auth[7:].strip():
        raise _unauthenticated()
    raw = auth[7:].strip()
    issuer, audience = os.getenv("JWT_ISSUER", ""), os.getenv("JWT_AUDIENCE", "")
    if not issuer or not audience:
        raise _unauthenticated()

    # Service identity is selected only from trusted server configuration.
    try:
        service_keys = json.loads(os.getenv("SERVICE_TOKEN_KEYS", "{}"))
        service_scopes = json.loads(os.getenv("SERVICE_TOKEN_SCOPES", "{}"))
        service_roles = json.loads(os.getenv("SERVICE_TOKEN_ROLES", "{}"))
    except (ValueError, TypeError):
        service_keys, service_scopes, service_roles = {}, {}, {}
    unverified: dict[str, Any]
    try:
        unverified = jwt.get_unverified_claims(raw)
    except JWTError:
        raise _unauthenticated()
    if unverified.get("token_use") == "service":
        service_id = unverified.get("service_id")
        key = service_keys.get(service_id) if isinstance(service_keys, dict) else None
        if not isinstance(key, str) or len(key) < 32:
            raise _unauthenticated()
        claims = _base_claims(raw, key, audience, issuer, "service")
        role = claims.get("role")
        scopes = claims.get("scope")
        allowed_scopes = service_scopes.get(service_id, []) if isinstance(service_scopes, dict) else []
        allowed_roles = service_roles.get(service_id, []) if isinstance(service_roles, dict) else []
        if claims.get("service_id") != service_id or role not in ROLE_PERMS or role not in allowed_roles or not isinstance(scopes, list) or not isinstance(allowed_scopes, list):
            raise _unauthenticated()
        if not set(scopes).issubset(set(allowed_scopes)):
            raise _unauthenticated()
        if int(claims["exp"]) - int(claims["iat"]) > 300:
            raise _unauthenticated()
        permissions = ROLE_PERMS[role].intersection(str(s) for s in scopes).intersection(allowed_scopes)
        actor_id, actor_type = service_id, "SYSTEM" if role == "supervisor" else "AI_AGENT"
        identity_type = "service"
    else:
        key = os.getenv("JWT_SIGNING_KEY", "")
        if len(key) < 32:
            raise _unauthenticated()
        claims = _base_claims(raw, key, audience, issuer, "access")
        role = claims.get("role")
        if role not in HUMAN_ROLES or int(claims["exp"]) - int(claims["iat"]) > 900:
            raise _unauthenticated()
        permissions = ROLE_PERMS[role]
        actor_id, actor_type, identity_type = claims["sub"], ("CUSTOMER" if role == "customer" else "HUMAN_AGENT"), "human"
    if claims.get("sub") != actor_id:
        raise _unauthenticated()
    return {"actor_id": actor_id, "actor_type": actor_type, "identity_type": identity_type,
            "role": role, "tenant_id": claims["tenant_id"], "permissions": permissions,
            "scope": claims.get("scope", []), "jti": claims["jti"], "token_use": claims["token_use"],
            "assurance_level": claims.get("assurance_level", "AL0")}


def require_perm(permission: str):
    async def checker(ctx: dict[str, Any] = Depends(get_principal)):
        if permission not in ctx["permissions"]:
            raise _forbidden(ctx["role"], permission)
        return ctx
    return checker


def require_human_perm(permission: str):
    """Require a verified human principal as well as the server role permission."""
    async def checker(ctx: dict[str, Any] = Depends(require_perm(permission))):
        if ctx["identity_type"] != "human":
            raise _forbidden(ctx["role"], permission)
        return ctx
    return checker


async def optional_principal(request: Request) -> VerifiedPrincipal | None:
    if not request.headers.get("Authorization"):
        return None
    return await get_principal(request)


def rotate_refresh_token(raw: str) -> dict[str, str]:
    """Consume one signed refresh token and issue a single-use successor pair."""
    issuer, audience, key = os.getenv("JWT_ISSUER", ""), os.getenv("JWT_AUDIENCE", ""), os.getenv("JWT_SIGNING_KEY", "")
    if not issuer or not audience or len(key) < 32:
        raise _unauthenticated()
    claims = _base_claims(raw, key, audience, issuer, "refresh")
    now = int(time.time())
    if int(claims["exp"]) - int(claims["iat"]) > 28800 or claims.get("role") not in HUMAN_ROLES:
        raise _unauthenticated()
    try:
        import redis
        client = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"), socket_connect_timeout=1)
        remaining = max(1, int(claims["exp"]) - now)
        consumed = client.set(f"eaics:refresh:used:{claims['jti']}", "1", ex=remaining, nx=True)
        if not consumed:
            raise _unauthenticated()
    except HTTPException:
        raise
    except Exception:
        # A refresh-store failure is a hard failure; never issue an untracked token.
        raise HTTPException(status_code=503, detail={"error_code": "E_AUTH_STORE_UNAVAILABLE", "message": "credential rotation unavailable"})
    common = {"sub": claims["sub"], "iss": issuer, "aud": audience,
              "tenant_id": claims["tenant_id"], "role": claims["role"]}
    access_claims = {**common, "iat": now, "exp": now + 900, "jti": __import__("uuid").uuid4().hex,
                     "token_use": "access", "assurance_level": claims.get("assurance_level", "AL0")}
    refresh_claims = {**common, "iat": now, "exp": now + 28800, "jti": __import__("uuid").uuid4().hex,
                      "token_use": "refresh", "assurance_level": claims.get("assurance_level", "AL0")}
    return {"access_token": jwt.encode(access_claims, key, algorithm="HS256"),
            "refresh_token": jwt.encode(refresh_claims, key, algorithm="HS256"),
            "token_type": "Bearer", "expires_in": 900}


# RBAC-02: a requester cannot approve their own request.
def assert_not_self_approval(requested_by: str, approver_id: str) -> None:
    from .errors import AppError
    if requested_by == approver_id:
        raise AppError("E_UNAUTHORISED", "self-approval blocked (RBAC-02)", customer_message_id="APPROVAL.SELF_BLOCKED")
