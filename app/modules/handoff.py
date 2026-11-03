"""FR-WS-001 + TRD §16.4 kontrak paket handoff. BR-HO-01/06: tak lengkap = cacat, tetap jalan."""
from __future__ import annotations
from ..core.ids import new_id
from ..core import audit as audit_svc

REQUIRED = ["schema_version","handoff_id","conversation_id","correlation_id","reason_code",
    "reason_narrative","customer_summary","assurance_state","intent_history",
    "conversation_transcript_ref","recent_turns","ai_action_log","knowledge_used",
    "commitments_made","open_items","linked_objects","sla_state","guardrail_events"]

def build_package(conversation_id: str, correlation_id: str, reason_code: str, ctx: dict,
                  partial: dict | None = None) -> dict:
    handoff_id = new_id("handoff")
    payload = {"schema_version": "1.0.0", "handoff_id": handoff_id,
        "conversation_id": conversation_id, "correlation_id": correlation_id,
        "reason_code": reason_code, "reason_narrative": (partial or {}).get("reason_narrative", "Need human help"),
        "customer_summary": (partial or {}).get("customer_summary", {"customer_id": None, "name": "***", "contacts_masked": {}, "flags": {}}),
        "assurance_state": (partial or {}).get("assurance_state", [{"channel": "WEB_CHAT", "assurance_level": "AL1", "al_method": [], "al_expires_at": None, "lock_state": "NONE"}]),
        "intent_history": (partial or {}).get("intent_history", [{"intent_code": "OTHER_UNCLASSIFIED", "confidence": 0.3, "decision": "HANDOFF", "classified_at": None, "taxonomy_version": "1.0.0"}]),
        "conversation_transcript_ref": conversation_id,
        "recent_turns": (partial or {}).get("recent_turns", [{"role": "customer", "text": "***"}]),
        "ai_action_log": (partial or {}).get("ai_action_log", []),
        "knowledge_used": (partial or {}).get("knowledge_used", []),
        "commitments_made": (partial or {}).get("commitments_made", []),
        "open_items": (partial or {}).get("open_items", []),
        "linked_objects": (partial or {}).get("linked_objects", {"ticket_ids": [], "case_ids": [], "evidence_request_ids": [], "approval_ids": []}),
        "sla_state": (partial or {}).get("sla_state"),
        "guardrail_events": (partial or {}).get("guardrail_events", [])}
    missing = [k for k in REQUIRED if payload.get(k) in (None, [], "") and k not in ("sla_state",)]
    # validasi commitments source (kontrak §16.4 aturan 1)
    for cm in payload["commitments_made"]:
        if cm.get("source") not in ("SLA_TOOL", "KNOWLEDGE_CITATION"):
            missing.append("commitments_made[].source")
            break
    complete = len(missing) == 0
    audit_svc.emit("TNT-TEST", correlation_id, ctx["actor_type"], ctx["actor_id"],
                   "handoff.package_built", "handoff", handoff_id, "handoff-svc",
                   conversation_id=conversation_id, reason=reason_code,
                   after={"package_complete": complete, "missing": missing})
    if not complete:
        audit_svc.emit("TNT-TEST", correlation_id, "SYSTEM", "qa-monitor", "handoff.package_incomplete",
                       "handoff", handoff_id, "handoff-svc", reason=f"missing={missing}")
    return {"handoff_id": handoff_id, "queue_id": "Q-GENERAL", "estimated_wait_s": 240,
            "package_complete": complete, "missing_fields": missing, "state": "QUEUED", "package": payload}
