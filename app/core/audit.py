"""TRD §16.7 + FR-SEC-004 amplop audit. ADR-09: tulis dalam transaksi yang sama (di sini: append-only in-memory + siap Postgres)."""
from __future__ import annotations
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
import hashlib, json
from .ids import new_id

AUDIT_FIELDS = ["audit_id","occurred_at","tenant_id","correlation_id","conversation_id","session_id",
    "actor_type","actor_id","on_behalf_of","action","object_type","object_id","reason",
    "before","after","policy_decision_id","approval_id","tool_call_id","source_component",
    "result","error_code","schema_version"]

_store: list[dict] = []
_last_hash: dict[str, str] = {}

def emit(tenant_id: str, correlation_id: str, actor_type: str, actor_id: str,
         action: str, object_type: str, object_id: str, source_component: str,
         reason: str | None = None, before: dict | None = None, after: dict | None = None,
         conversation_id: str | None = None, session_id: str | None = None,
         on_behalf_of: str | None = None, policy_decision_id: str | None = None,
         approval_id: str | None = None, tool_call_id: str | None = None,
         result: str = "OK", error_code: str | None = None) -> dict:
    occurred = datetime.now(timezone.utc).isoformat()
    audit_id = new_id("audit")
    prev = _last_hash.get(tenant_id, "GENESIS")
    canonical = json.dumps({"a": audit_id, "act": action, "obj": object_id, "t": occurred, "prev": prev}, sort_keys=True)
    record_hash = hashlib.sha256((canonical + prev).encode()).hexdigest()
    _last_hash[tenant_id] = record_hash
    rec = {"audit_id": audit_id, "occurred_at": occurred, "tenant_id": tenant_id,
        "correlation_id": correlation_id, "conversation_id": conversation_id, "session_id": session_id,
        "actor_type": actor_type, "actor_id": actor_id, "on_behalf_of": on_behalf_of,
        "action": action, "object_type": object_type, "object_id": object_id, "reason": reason,
        "before": before, "after": after, "policy_decision_id": policy_decision_id,
        "approval_id": approval_id, "tool_call_id": tool_call_id,
        "source_component": source_component, "result": result, "error_code": error_code,
        "schema_version": "1.0", "previous_hash": prev, "record_hash": record_hash}
    _store.append(rec)
    return rec

def trail(correlation_id: str, tenant_id: str | None = None) -> list[dict]:
    """US-SEC-01: rekonstruksi perjalanan per correlation_id berurutan."""
    return sorted([r for r in _store if r["correlation_id"] == correlation_id
                   and (tenant_id is None or r["tenant_id"] == tenant_id)],
                  key=lambda r: (r["occurred_at"], r["audit_id"]))

def verify_chain(tenant_id: str) -> tuple[bool, str | None]:
    prev = "GENESIS"
    for r in [x for x in _store if x["tenant_id"] == tenant_id]:
        if r["previous_hash"] != prev:
            return False, r["audit_id"]
        prev = r["record_hash"]
    return True, None
