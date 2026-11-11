"""FR-WS-002 antrean + perutean. prioritas = w1*severity + w2*sla_risk + w3*wait + w4*vuln (TRD §4.13)."""
from __future__ import annotations
import datetime
from sqlalchemy.orm import Session
from ..core.ids import new_id
from ..core import audit as audit_svc
from ..core.errors import AppError
from .models import HandoffRow, SlaRecordRow, CaseRow, TicketRow

W = {"severity": 10, "sla_risk": 8, "wait_per_min": 1, "vuln": 25}
SEV_W = {"LOW": 1, "MEDIUM": 2, "HIGH": 4, "CRITICAL": 8}

def _sla_risk(db: Session, conversation_id: str) -> int:
    case_ids = [r.case_id for r in db.query(CaseRow.case_id).filter_by(origin_conversation_id=conversation_id).all()]
    ticket_ids = [r.ticket_id for r in db.query(TicketRow.ticket_id).filter_by(conversation_id=conversation_id).all()]
    object_ids = case_ids + ticket_ids
    if not object_ids:
        return 0
    records = db.query(SlaRecordRow).filter(SlaRecordRow.object_id.in_(object_ids)).all()
    if any(r.state == "BREACHED" for r in records): return 10
    if any(r.state == "AT_RISK" for r in records): return 5
    return 0

def score(severity: str, sla_risk: int, wait_min: float, vuln: bool) -> int:
    return (W["severity"] * SEV_W.get(severity, 2) + W["sla_risk"] * sla_risk
            + int(min(wait_min, 120) * W["wait_per_min"]) + (W["vuln"] if vuln else 0))

def enqueue(db: Session, conversation_id: str, reason_code: str, ctx: dict, corr: str,
            severity: str = "MEDIUM", skill_tags: list[str] | None = None,
            language: str = "id", vulnerability_flag: bool = False,
            package_complete: bool = True, queue_id: str = "Q-GENERAL") -> dict:
    hid = new_id("handoff")
    now = datetime.datetime.now(datetime.timezone.utc)
    s = score(severity, _sla_risk(db, conversation_id), 0, vulnerability_flag)
    db.add(HandoffRow(handoff_id=hid, tenant_id=ctx["tenant_id"], conversation_id=conversation_id, reason_code=reason_code,
                      priority_score=s, queue_id=queue_id, skill_tags=skill_tags or [],
                      language=language, severity=severity,
                      vulnerability_flag=vulnerability_flag, state="QUEUED",
                      package_complete=package_complete, queued_at=now))
    db.commit()
    audit_svc.emit("TNT-TEST", corr, ctx["actor_type"], ctx["actor_id"], "handoff.queued",
                   "handoff", hid, "queue-svc", conversation_id=conversation_id, reason=reason_code)
    return {"handoff_id": hid, "queue_id": queue_id, "estimated_wait_s": 240,
            "package_complete": package_complete, "priority_score": s, "state": "QUEUED"}

def list_queue(db: Session, tenant_id: str, queue_id: str | None = None, agent_skills: list[str] | None = None) -> list[dict]:
    q = db.query(HandoffRow).filter_by(state="QUEUED", tenant_id=tenant_id)
    if queue_id: q = q.filter_by(queue_id=queue_id)
    rows = q.all()
    # filter skill: cocok bila irisan tak kosong atau agen tanpa filter
    if agent_skills:
        rows = [r for r in rows if not r.skill_tags or set(r.skill_tags) & set(agent_skills)]
    # urut prioritas lalu waktu tunggu (FR-WS-002 AC1: Critical dulu)
    now = datetime.datetime.now(datetime.timezone.utc)
    out = []
    from .models_a import ConversationRow, MessageRow
    for r in rows:
        qa = r.queued_at.replace(tzinfo=datetime.timezone.utc) if r.queued_at.tzinfo is None else r.queued_at
        wait_s = int((now - qa).total_seconds())
        live_score = score(r.severity, _sla_risk(db, r.conversation_id), wait_s / 60, r.vulnerability_flag)
        
        c_row = db.query(ConversationRow).filter_by(conversation_id=r.conversation_id).first()
        last_msg = (
            db.query(MessageRow)
            .filter_by(conversation_id=r.conversation_id, direction="INBOUND")
            .order_by(MessageRow.sequence_no.desc())
            .first()
        )
        summary_snippet = ""
        if last_msg and last_msg.content:
            summary_snippet = (last_msg.content[:80] + "...") if len(last_msg.content) > 80 else last_msg.content
        intent_code = c_row.intent_current if c_row and c_row.intent_current else r.reason_code

        out.append({"handoff_id": r.handoff_id, "conversation_id": r.conversation_id,
                    "customer_id": c_row.customer_id if c_row else None,
                    "intent_code": intent_code,
                    "summary_snippet": summary_snippet,
                    "reason_code": r.reason_code, "priority_score": live_score,
                    "severity": r.severity, "queue_id": r.queue_id, "skill_tags": r.skill_tags,
                    "language": r.language, "wait_s": wait_s,
                    "estimated_wait_s": max(60, 300 - wait_s), "package_complete": r.package_complete})
    out.sort(key=lambda item: (-item["priority_score"], item["wait_s"]))
    return out

def accept(db: Session, handoff_id: str, agent_id: str, ctx: dict, corr: str) -> dict:
    r = db.query(HandoffRow).filter_by(handoff_id=handoff_id, tenant_id=ctx["tenant_id"]).first()
    if not r: raise AppError("E_NOT_FOUND", "handoff not found", customer_message_id="HANDOFF.NOT_FOUND")
    if r.state != "QUEUED": raise AppError("E_CONFLICT", f"already {r.state}", customer_message_id="HANDOFF.STATE")
    from .models_a import ConversationRow
    from .conversation import VALID_TRANSITIONS
    conversation = db.query(ConversationRow).filter_by(
        conversation_id=r.conversation_id, tenant_id=ctx["tenant_id"]).first()
    if not conversation:
        raise AppError("E_NOT_FOUND", "conversation not found", customer_message_id="CONV.NOT_FOUND")
    before_status = conversation.status
    if before_status != "ACTIVE_HUMAN":
        if "ACTIVE_HUMAN" not in VALID_TRANSITIONS.get(before_status, set()):
            raise AppError("E_CONFLICT", f"cannot accept handoff while conversation is {before_status}",
                           customer_message_id="CONV.STATE")
        conversation.status = "ACTIVE_HUMAN"
        conversation.status_reason = "handoff_accepted"
    now = datetime.datetime.now(datetime.timezone.utc)
    conversation.last_activity_at = now
    r.state = "ACCEPTED"; r.accepted_by = agent_id; r.offered_to = agent_id
    db.commit()
    audit_svc.emit(ctx["tenant_id"], corr, ctx["actor_type"], agent_id, "handoff.accepted",
                   "handoff", handoff_id, "queue-svc", conversation_id=r.conversation_id)
    if before_status != "ACTIVE_HUMAN":
        audit_svc.emit(ctx["tenant_id"], corr, ctx["actor_type"], agent_id, "conversation.status_changed",
                       "conversation", conversation.conversation_id, "queue-svc",
                       reason="handoff_accepted", before={"status": before_status},
                       after={"status": "ACTIVE_HUMAN"}, conversation_id=conversation.conversation_id)
    return {"handoff_id": handoff_id, "state": "ACCEPTED", "accepted_by": agent_id,
            "conversation_id": r.conversation_id, "conversation_status": conversation.status}

def transfer(db: Session, handoff_id: str, to_queue: str, reason: str, note: str, ctx: dict, corr: str) -> dict:
    """BR-WS-04: pengalihan antarmanusia wajib catatan."""
    if not (note or "").strip():
        raise AppError("E_VALIDATION", "transfer note required (BR-WS-04)",
                       customer_message_id="TRANSFER.NOTE_REQUIRED",
                       details=[{"field": "note", "rule": "REQUIRED"}])
    r = db.query(HandoffRow).filter_by(handoff_id=handoff_id, tenant_id=ctx["tenant_id"]).first()
    if not r: raise AppError("E_NOT_FOUND", "handoff not found", customer_message_id="HANDOFF.NOT_FOUND")
    r.queue_id = to_queue; r.transfer_note = note; r.state = "QUEUED"
    # skor ulang agar antrean tujuan memprioritaskan dengan benar
    r.priority_score = score(r.severity, 0, 0, r.vulnerability_flag)
    db.commit()
    audit_svc.emit(ctx["tenant_id"], corr, ctx["actor_type"], ctx["actor_id"], "conversation.transferred",
                   "handoff", handoff_id, "queue-svc", reason=reason)
    return {"handoff_id": handoff_id, "queue_id": to_queue, "state": "QUEUED"}
