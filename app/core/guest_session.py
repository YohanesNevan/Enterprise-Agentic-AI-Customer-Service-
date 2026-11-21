"""Signed guest chat sessions for Tier 1 (public information).

A guest conversation is useful without an account, but the conversation must
not become readable by anyone who guesses its identifier. The guest session is
a short-lived signed token bound to one conversation and tenant. It is a
separate token purpose (``guest``) and can never be used as an access token.
"""
from __future__ import annotations

import os
import time
import uuid

from jose import JWTError, jwt

from .errors import AppError

GUEST_TTL_SECONDS = 8 * 60 * 60
GUEST_SUBJECT = "guest_customer"


def guest_tenant_id() -> str:
    """Tenant used for public knowledge retrieval.

    Guest chat never chooses a tenant from the caller. Use the explicitly
    configured public tenant, else the local development tenant, else the
    synthetic test tenant.
    """
    for name in ("PUBLIC_CHAT_TENANT_ID", "DEV_TENANT_ID"):
        value = (os.getenv(name) or "").strip()
        if value:
            return value[:30]
    return "TNT-TEST"


def _signing_key() -> str:
    key = os.getenv("JWT_SIGNING_KEY", "")
    if len(key) < 32:
        raise AppError("E_UNAVAILABLE", "guest chat is not configured",
                       customer_message_id="AUTH.DEV_UNAVAILABLE")
    return key


def issue_guest_session(conversation_id: str, tenant_id: str) -> dict:
    """Mint a rotating guest session token bound to one conversation."""
    issuer = os.getenv("JWT_ISSUER", "")
    audience = os.getenv("JWT_AUDIENCE", "")
    if not issuer or not audience:
        raise AppError("E_UNAVAILABLE", "guest chat is not configured",
                       customer_message_id="AUTH.DEV_UNAVAILABLE")
    now = int(time.time())
    claims = {
        "sub": GUEST_SUBJECT,
        "iss": issuer,
        "aud": audience,
        "iat": now,
        "exp": now + GUEST_TTL_SECONDS,
        "jti": uuid.uuid4().hex,
        "tenant_id": tenant_id,
        "conversation_id": conversation_id,
        "token_use": "guest",
        "assurance_level": "AL0",
    }
    token = jwt.encode(claims, _signing_key(), algorithm="HS256")
    return {"session_token": token, "expires_in": GUEST_TTL_SECONDS,
            "token_type": "GuestSession", "conversation_id": conversation_id}


def verify_guest_session(token: str | None, conversation_id: str, tenant_id: str) -> bool:
    if not token:
        return False
    issuer, audience = os.getenv("JWT_ISSUER", ""), os.getenv("JWT_AUDIENCE", "")
    if not issuer or not audience:
        return False
    try:
        claims = jwt.decode(token, _signing_key(), algorithms=["HS256"],
                            audience=audience, issuer=issuer,
                            options={"require_sub": True, "require_iat": True,
                                     "require_exp": True, "require_jti": True})
    except (JWTError, KeyError, TypeError, ValueError):
        return False
    return (claims.get("token_use") == "guest"
            and claims.get("sub") == GUEST_SUBJECT
            and claims.get("conversation_id") == conversation_id
            and claims.get("tenant_id") == tenant_id)
