"""FR-CASE-001..010 + FR-WS Tiket/Kasus (Kelompok B). BR-CASE-01/02/05/09, BR-ORC-04 outbox."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, Field
from ..contracts.vocabularies import (TicketStatus, CaseStatus, CustomerVisibleStatus, Severity)
from ..core.ids import new_id, short_reference
from ..core.errors import AppError
from ..core import audit as audit_svc

TICKETS: dict[str, dict] = {}
CASES: dict[str, dict] = {}
OUTBOX: list[dict] = []  # crm_outbox PENDING->SENT (FR-CASE-001 AC2)
CRM_AVAILABLE = {"value": True}  # toggle untuk chaos test

INTERNAL_TO_CUSTOMER = {
    "LOGGED": "RECEIVED", "CLASSIFIED": "RECEIVED",
    "EVIDENCE_PENDING": "WAITING_FOR_YOU",
    "UNDER_INVESTIGATION": "BEING_INVESTIGATED",
    "RESOLUTION_PROPOSED": "OUTCOME_READY",
    "AWAITING_CUSTOMER_ACCEPTANCE": "OUTCOME_READY",
    "RESOLVED": "OUTCOME_READY", "CLOSED": "CLOSED", "REOPENED": "REOPENED",
}

class CreateTicketIn(BaseModel):
    conversation_id: str
    customer_id: str | None = None
    type: str = "GENERAL"
    sub_type: str | None = None
    priority: str = "NORMAL"
    description: str
    requested_action: str | None = None
    source_channel: str = "WEB_CHAT"
    linked_case_id: str | None = None
    idempotency_key: str | None = None

class CreateCaseIn(BaseModel):
    conversation_id: str
    customer_id: str | None = None
    category: str
    sub_category: str | None = None
    severity_proposed: Severity
    risk_level: list[str] = []
    vulnerability_flag: bool = False
    description: str
    source_channel: str = "WEB_CHAT"
    linked_ticket_ids: list[str] = []
    idempotency_key: str | None = None

def _utcnow(): return datetime.now(timezone.utc)

def create_ticket(body: CreateTicketIn, ctx: dict, corr: str, tenant: str = "TNT-TEST") -> dict:
    from .sla_engine import calculate
    tid = new_id("ticket")
    now = _utcnow()
    sla = calculate("TICKET", "GENERAL", "MEDIUM", now)
    t = {"ticket_id": tid, "customer_reference": short_reference("ticket", tid),
         "status": "OPEN", "owner_queue": "GENERAL", **body.model_dump(),
         "sla": {**sla, "sla_id": new_id("sla")}, "created_at": now.isoformat(), "replayed": False,
         "pending_system_action": False}
    TICKETS[tid] = t
    audit_svc.emit(tenant, corr, ctx["actor_type"], ctx["actor_id"], "ticket.created",
                   "ticket", tid, "ticket-svc", conversation_id=body.conversation_id)
    return {"ticket_id": tid, "customer_reference": t["customer_reference"], "status": "OPEN",
            "owner_queue": "GENERAL", "sla": t["sla"], "created_at": t["created_at"], "replayed": False}

def create_case(body: CreateCaseIn, ctx: dict, corr: str, tenant: str = "TNT-TEST") -> dict:
    """BR-CASE-09: AI usul HIGH/CRITICAL -> severity_confirmed=null sampai manusia konfirmasi."""
    from .sla_engine import calculate
    cid = new_id("case")
    now = _utcnow()
    needs_confirm = body.severity_proposed in (Severity.HIGH, Severity.CRITICAL) and ctx["actor_type"] == "AI_AGENT"
    sla = calculate("CASE", body.category, body.severity_proposed, now)
    status = "LOGGED"
    c = {"case_id": cid, "customer_reference": short_reference("case", cid),
         "status": status, "customer_visible_status": INTERNAL_TO_CUSTOMER[status],
         "severity_proposed": body.severity_proposed.value,
         "severity_confirmed": None if needs_confirm else body.severity_proposed.value,
         "severity_confirmation_required": needs_confirm,
         "owner_queue": "DISPUTES" if "DISPUTE" in body.category else "GENERAL",
         **body.model_dump(exclude={"severity_proposed"}),
         "severity_proposed": body.severity_proposed.value,
         "sla": {**sla, "sla_id": new_id("sla")}, "logged_at": now.isoformat(),
         "reopen_count": 0, "replayed": False,
         "evidence_required": evidence_required_for(body.category, body.sub_category)}
    # outbox: tulis lokal + antre (FR-CASE-001 AC2)
    if not CRM_AVAILABLE["value"]:
        OUTBOX.append({"object_type": "CASE", "object_id": cid, "state": "PENDING", "created_at": now.isoformat()})
        c["crm_pending"] = True
    CASES[cid] = c
    audit_svc.emit(tenant, corr, ctx["actor_type"], ctx["actor_id"], "case.created",
                   "case", cid, "case-svc", conversation_id=body.conversation_id,
                   after={"severity_proposed": c["severity_proposed"]})
    return {"case_id": cid, "customer_reference": c["customer_reference"], "status": status,
            "customer_visible_status": c["customer_visible_status"],
            "severity_confirmed": c["severity_confirmed"],
            "severity_confirmation_required": needs_confirm,
            "owner_queue": c["owner_queue"], "sla": c["sla"],
            "evidence_required": c["evidence_required"],
            "logged_at": c["logged_at"], "replayed": False}

def evidence_required_for(category: str, sub: str | None) -> list[dict]:
    if category == "TRANSACTION_DISPUTE":
        return [
            {"description": "Transaction detail showing date, amount and merchant", "formats": ["png", "jpg", "pdf"], "mandatory": True},
            {"description": "Your written statement that you do not recognise the transaction", "formats": ["txt", "pdf"], "mandatory": True}]
    return []

CLOSURE_REQUIRED = ["outcome_recorded", "customer_notified", "root_cause_set",
                    "evidence_adjudicated", "no_open_child_tickets", "sla_finalised", "qa_eligible_set"]

def close_case(case_id: str, checklist: dict[str, bool], ctx: dict, corr: str) -> dict:
    c = CASES.get(case_id)
    if not c: raise AppError("E_NOT_FOUND", "case not found", customer_message_id="CASE.NOT_FOUND")
    missing = [k for k in CLOSURE_REQUIRED if not checklist.get(k)]
    if missing:  # BR-CASE-05: tolak + sebutkan yang kurang (FR-CASE-007 AC1)
        raise AppError("E_INVALID_TRANSITION", f"closure refused, missing: {missing}",
                       customer_message_id="CASE.CLOSURE_REFUSED",
                       details=[{"field": m, "rule": "REQUIRED"} for m in missing])
    c["status"] = "CLOSED"; c["customer_visible_status"] = "CLOSED"
    audit_svc.emit("TNT-TEST", corr, ctx["actor_type"], ctx["actor_id"], "case.closed",
                   "case", case_id, "case-svc")
    return c

def reopen_case(case_id: str, reason: str, ctx: dict, corr: str) -> dict:
    c = CASES.get(case_id)
    if not c: raise AppError("E_NOT_FOUND", "case not found", customer_message_id="CASE.NOT_FOUND")
    c["reopen_count"] = c.get("reopen_count", 0) + 1
    c["status"] = "REOPENED"
    c["customer_visible_status"] = "REOPENED"
    audit_svc.emit("TNT-TEST", corr, ctx["actor_type"], ctx["actor_id"], "case.reopened",
                   "case", case_id, "case-svc", reason=reason)
    escalated = None
    if c["reopen_count"] >= 3:  # BR-CASE-14
        from .escalation import raise_escalation
        escalated = raise_escalation("CASE", case_id, "L3", "REOPEN_X3", ctx, corr)
    return {"case": c, "escalation": escalated}
