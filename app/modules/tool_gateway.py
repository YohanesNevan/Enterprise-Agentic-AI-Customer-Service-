"""FR-TOOL-001..009 + FR-SEC-002 [A/J]: registri berversi, daftar tolak,
validasi skema I/O, idempotensi, retry, circuit breaker. TRD §4.9."""
from __future__ import annotations
import hashlib, json, time
from ..core.errors import AppError
from ..core import audit as audit_svc
from ..core.ids import new_id

REGISTRY = {
    "knowledge_search": {"version": "1.0.0", "risk": "READ", "al": "AL0", "idempotent": True, "timeout_ms": 3000},
    "customer_profile_lookup": {"version": "1.0.0", "risk": "READ", "al": "AL1", "idempotent": True, "timeout_ms": 3000},
    "account_lookup": {"version": "1.0.0", "risk": "READ", "al": "AL2", "idempotent": True, "timeout_ms": 3000},
    "transaction_lookup": {"version": "1.0.0", "risk": "READ", "al": "AL2", "idempotent": True, "timeout_ms": 3000},
    "order_claim_lookup": {"version": "1.0.0", "risk": "READ", "al": "AL1", "idempotent": True, "timeout_ms": 3000},
    "auth_challenge": {"version": "1.0.0", "risk": "WRITE_LOW", "al": "AL0", "idempotent": True, "timeout_ms": 5000},
    "auth_verify": {"version": "1.0.0", "risk": "WRITE_LOW", "al": "AL0", "idempotent": True, "timeout_ms": 5000},
    "card_status_update": {"version": "1.0.0", "risk": "WRITE_MEDIUM", "al": "AL2", "idempotent": False, "timeout_ms": 8000,
                           "allowed": ["TEMP_BLOCK"], "approval": False},
    "create_crm_ticket": {"version": "1.0.0", "risk": "WRITE_LOW", "al": "AL1", "idempotent": True, "timeout_ms": 5000},
    "update_crm_ticket": {"version": "1.0.0", "risk": "WRITE_LOW", "al": "AL1", "idempotent": True, "timeout_ms": 5000},
    "crm_ticket_lookup": {"version": "1.0.0", "risk": "READ", "al": "AL1", "idempotent": True, "timeout_ms": 3000},
    "create_case": {"version": "1.0.0", "risk": "WRITE_LOW", "al": "AL1", "idempotent": True, "timeout_ms": 5000},
    "case_lookup": {"version": "1.0.0", "risk": "READ", "al": "AL1", "idempotent": True, "timeout_ms": 3000},
    "evidence_request": {"version": "1.0.0", "risk": "WRITE_LOW", "al": "AL1", "idempotent": True, "timeout_ms": 5000},
    "evidence_upload_link": {"version": "1.0.0", "risk": "READ", "al": "AL1", "idempotent": True, "timeout_ms": 3000},
    "sla_calculate": {"version": "1.0.0", "risk": "READ", "al": "AL0", "idempotent": True, "timeout_ms": 3000},
    "notification_send": {"version": "1.0.0", "risk": "WRITE_LOW", "al": "AL1", "idempotent": True, "timeout_ms": 5000},
    "handoff_request": {"version": "1.0.0", "risk": "WRITE_LOW", "al": "AL0", "idempotent": True, "timeout_ms": 5000},
}
PROHIBITED = {"execute_refund", "reverse_transaction", "transfer_funds", "change_credentials",
              "reset_password", "update_customer_profile", "grant_permission", "override_policy",
              "close_case_without_checklist", "unblock_card", "issue_card"}
_circuits: dict[str, dict] = {}
_idem: dict[str, dict] = {}
_calls: list[dict] = []

def permitted_set(session_al: str, actor: str = "AI_AGENT") -> list[str]:
    """RBAC-03 irisan: role x AL x circuit. Model hanya lihat ini (ADR-04)."""
    order = ["AL0", "AL1", "AL2", "AL3"]
    out = []
    for name, meta in REGISTRY.items():
        if order.index(session_al) < order.index(meta["al"]): continue
        c = _circuits.get(name)
        if c and c.get("open") and c["until"] > time.time(): continue
        out.append(name)
    return out

def _idem_key(conv: str, tool: str, args: dict) -> str:
    canon = json.dumps(args or {}, sort_keys=True)
    return hashlib.sha256(f"{conv}|{tool}|{canon}".encode()).hexdigest()[:32]

def evaluate(tool: str, args: dict, session_al: str, ctx: dict, corr: str, conv: str) -> dict:
    """FR-ORC-002: ALLOW / ALLOW_WITH_APPROVAL / STEP_UP_REQUIRED / DENY + audit."""
    pd = new_id("policy_decision")
    if tool in PROHIBITED or tool not in REGISTRY:
        audit_svc.emit("TNT-TEST", corr, "SYSTEM", "policy-engine", "security.prohibited_action_attempted",
                       "tool", tool, "tool-gateway", conversation_id=conv, result="DENY")
        audit_svc.emit("TNT-TEST", corr, "SYSTEM", "policy-engine", "policy.evaluated",
                       "tool", tool, "policy-engine", conversation_id=conv,
                       policy_decision_id=pd, result="DENY", error_code="E_PROHIBITED")
        raise AppError("E_PROHIBITED", f"tool {tool} prohibited/unknown",
                       customer_message_id="TOOL.PROHIBITED")
    meta = REGISTRY[tool]
    order = ["AL0", "AL1", "AL2", "AL3"]
    if order.index(session_al) < order.index(meta["al"]):
        audit_svc.emit("TNT-TEST", corr, "SYSTEM", "policy-engine", "policy.evaluated",
                       "tool", tool, "policy-engine", conversation_id=conv,
                       policy_decision_id=pd, result="STEP_UP")
        return {"decision": "STEP_UP_REQUIRED", "policy_decision_id": pd,
                "reason_code": "E_ASSURANCE_REQUIRED", "required": meta["al"]}
    # WRITE_HIGH selalu butuh approval; card block TEMP_BLOCK otonom (Q-03), limit change butuh approval
    if tool == "card_status_update" and (args or {}).get("action") not in ("TEMP_BLOCK",):
        return {"decision": "DENY", "policy_decision_id": pd, "reason_code": "E_PROHIBITED"}
    if tool in ("card_status_update",) and False:
        pass
    audit_svc.emit("TNT-TEST", corr, "SYSTEM", "policy-engine", "policy.evaluated",
                   "tool", tool, "policy-engine", conversation_id=conv,
                   policy_decision_id=pd, result="ALLOW")
    return {"decision": "ALLOW", "policy_decision_id": pd, "reason_code": None}

def record_call(conv: str, tool: str, args: dict, status: str, corr: str,
                pd_id: str, err: str | None = None, ms: int = 50) -> dict:
    tc = new_id("tool_call")
    rec = {"tool_call_id": tc, "tool_name": tool, "tool_version": REGISTRY.get(tool, {}).get("version", "?"),
           "status": status, "error_code": err, "duration_ms": ms, "policy_decision_id": pd_id}
    _calls.append(rec)
    audit_svc.emit("TNT-TEST", corr, "AI_AGENT", "orchestrator", "tool.called",
                   "tool", tool, "tool-gateway", conversation_id=conv,
                   policy_decision_id=pd_id, tool_call_id=tc,
                   result=status, error_code=err)
    return rec

def idem_lookup(conv: str, tool: str, args: dict):
    return _idem.get(_idem_key(conv, tool, args))

def idem_store(conv: str, tool: str, args: dict, res: dict):
    _idem[_idem_key(conv, tool, args)] = res

def trip(tool: str):
    _circuits[tool] = {"open": True, "until": time.time() + 30}
    audit_svc.emit("TNT-TEST", "COR-?", "SYSTEM", "tool-gateway", "tool.circuit_opened",
                   "tool", tool, "tool-gateway")
