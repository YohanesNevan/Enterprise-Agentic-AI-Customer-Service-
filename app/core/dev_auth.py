"""Configuration guard for the fixed-account local customer login."""
from __future__ import annotations

import os
import time
import uuid
import ipaddress
from jose import jwt


def validate_dev_customer_auth_config(environment: str | None = None, enabled: str | None = None,
                                      staff_enabled: str | None = None) -> None:
    env = (environment if environment is not None else os.getenv("ENVIRONMENT", "")).lower()
    flag = (enabled if enabled is not None else os.getenv("DEV_CUSTOMER_AUTH_ENABLED", "")).lower()
    staff_flag = (staff_enabled if staff_enabled is not None else os.getenv("DEV_STAFF_AUTH_ENABLED", "")).lower()
    if (flag == "true" or staff_flag == "true") and env != "development":
        raise RuntimeError("Development authentication flags are allowed only when ENVIRONMENT=development")


def issue_dev_access_token(actor_id: str, tenant_id: str, role: str) -> tuple[str, int]:
    key = os.getenv("JWT_SIGNING_KEY", "")
    issuer, audience = os.getenv("JWT_ISSUER", ""), os.getenv("JWT_AUDIENCE", "")
    if len(key) < 32 or not issuer or not audience:
        raise ValueError("JWT signing key, issuer, and audience must be configured")
    now = int(time.time())
    claims = {"sub": actor_id, "iss": issuer, "aud": audience, "iat": now,
              "exp": now + 900, "jti": uuid.uuid4().hex, "tenant_id": tenant_id,
              "role": role, "token_use": "access", "assurance_level": "AL0"}
    return jwt.encode(claims, key, algorithm="HS256"), 900


def dev_auth_client_allowed(client_host: str | None) -> bool:
    """Allow loopback plus exact, explicitly configured local proxy addresses.

    Docker Desktop forwards host-loopback requests into the API container from
    its bridge gateway. Trust only that exact server-configured address; never
    use caller-supplied forwarding headers or broad private-network ranges.
    """
    if not client_host:
        return False
    try:
        remote = ipaddress.ip_address(client_host)
    except ValueError:
        return client_host == "testclient"
    if remote.is_loopback:
        return True
    trusted = {item.strip() for item in os.getenv("DEV_AUTH_TRUSTED_CLIENTS", "").split(",") if item.strip()}
    return client_host in trusted
