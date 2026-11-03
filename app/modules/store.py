"""Store DB-backed B: case/ticket + sla_record + outbox dalam satu transaksi.
Menjaga: logged_at asli untuk SLA saat CRM padam (FR-CASE-001 AC2)."""
from __future__ import annotations
import datetime
from sqlalchemy.orm import Session
from ..core.ids import new_id, short_reference
from ..core import audit as audit_svc
from ..contracts.vocabularies import Severity
from .models import CaseRow, TicketRow, SlaRecordRow, CrmOutboxRow
from . import sla_engine as SlaSvc
from . import cases as Legacy  # untuk evidence_required_for + visible mapping

def _now():
    return datetime.datetime.now(datetime.timezone.utc)

def create_case_db(db: Session, body, ctx: dict, corr: str, tenant: str = "TNT-TEST") -> dict:
    cid = new_id("case")
    now = _now()
    needs_confirm = body.severity_proposed in (Severity.HIGH, Severity.CRITICAL) and ctx["actor_type"] == "AI_AGENT"
    sla = SlaSvc.calculate("CASE", body.category, body.severity_proposed, now)
    fr_due = datetime.datetime.fromisoformat(sla["first_response_due_at"])
    reso_due = datetime.datetime.fromisoformat(sla["resolution_due_at"])
    sla_id = new_id("sla")
    status = "LOGGED"
    c = CaseRow(case_id=cid, tenant_id=tenant, customer_id=body.customer_id,
                origin_conversation_id=body.conversation_id,
                customer_reference=short_reference("case", cid),
                category=body.category, sub_category=body.sub_category,
                severity_proposed=body.severity_proposed.value,
                severity_confirmed=None if needs_confirm else body.severity_proposed.value,
                status=status, customer_visible_status=Legacy.INTERNAL_TO_CUSTOMER[status],
                owner_queue="DISPUTES" if "DISPUTE" in body.category else "GENERAL",
                logged_at=now, reopen_count=0, sla_config_version=sla["sla_config_version"])
    db.add(c)
    db.add(SlaRecordRow(sla_id=sla_id, tenant_id=tenant, object_type="CASE", object_id=cid,
                        sla_config_version=sla["sla_config_version"], started_at=now,
                        first_response_due_at=fr_due, resolution_due_at=reso_due, state="RUNNING"))
    # outbox satu transaksi: CRM mati pun kasus tetap tercatat lokal + nomor referensi langsung keluar
    from .outbox import CRM_AVAILABLE
    db.add(CrmOutboxRow(outbox_id=new_id("turn"), object_type="CASE", object_id=cid,
                        operation="CREATE", payload={"case_id": cid}, state="PENDING"))
    db.commit()
    audit_svc.emit(tenant, corr, ctx["actor_type"], ctx["actor_id"], "case.created",
                   "case", cid, "case-svc", conversation_id=body.conversation_id)
    crm_pending = not CRM_AVAILABLE["value"]
    return {"case_id": cid, "customer_reference": c.customer_reference, "status": status,
            "customer_visible_status": c.customer_visible_status,
            "severity_confirmed": c.severity_confirmed,
            "severity_confirmation_required": needs_confirm,
            "owner_queue": c.owner_queue,
            "sla": {**sla, "sla_id": sla_id}, "logged_at": now.isoformat(),
            "crm_pending": crm_pending,
            "evidence_required": Legacy.evidence_required_for(body.category, body.sub_category),
            "replayed": False}

def create_ticket_db(db: Session, body, ctx: dict, corr: str, tenant: str = "TNT-TEST") -> dict:
    tid = new_id("ticket")
    now = _now()
    sla = SlaSvc.calculate("TICKET", "GENERAL", "MEDIUM", now)
    sla_id = new_id("sla")
    t = TicketRow(ticket_id=tid, tenant_id=tenant, customer_id=body.customer_id,
                  conversation_id=body.conversation_id, type=body.type, sub_type=body.sub_type,
                  priority=body.priority, status="OPEN", description=body.description,
                  owner_queue="GENERAL", sla_id=sla_id, created_at=now)
    db.add(t)
    db.add(SlaRecordRow(sla_id=sla_id, tenant_id=tenant, object_type="TICKET", object_id=tid,
                        sla_config_version=sla["sla_config_version"], started_at=now,
                        first_response_due_at=datetime.datetime.fromisoformat(sla["first_response_due_at"]),
                        resolution_due_at=datetime.datetime.fromisoformat(sla["resolution_due_at"]),
                        state="RUNNING"))
    db.add(CrmOutboxRow(outbox_id=new_id("turn"), object_type="TICKET", object_id=tid,
                        operation="CREATE", payload={"ticket_id": tid}, state="PENDING"))
    db.commit()
    audit_svc.emit(tenant, corr, ctx["actor_type"], ctx["actor_id"], "ticket.created",
                   "ticket", tid, "ticket-svc", conversation_id=body.conversation_id)
    return {"ticket_id": tid, "customer_reference": short_reference("ticket", tid), "status": "OPEN",
            "owner_queue": "GENERAL", "sla": {**sla, "sla_id": sla_id},
            "created_at": now.isoformat(), "replayed": False}

def close_case_db(db: Session, case_id: str, checklist: dict, ctx: dict, corr: str) -> dict:
    """BR-CASE-05: daftar periksa penutupan — tiap butir kurang = tolak + sebutkan (FR-CASE-007 AC1)."""
    from ..core.errors import AppError
    c = db.query(CaseRow).filter_by(case_id=case_id, tenant_id=ctx["tenant_id"]).first()
    if c is None:
        raise AppError("E_NOT_FOUND", "case not found", customer_message_id="CASE.NOT_FOUND")
    missing = [k for k in Legacy.CLOSURE_REQUIRED if not checklist.get(k)]
    if missing:
        raise AppError("E_INVALID_TRANSITION", f"closure refused, missing: {missing}",
                       customer_message_id="CASE.CLOSURE_REFUSED",
                       details=[{"field": m, "rule": "REQUIRED"} for m in missing])
    c.status = "CLOSED"; c.customer_visible_status = "CLOSED"
    db.commit()
    audit_svc.emit("TNT-TEST", corr, ctx["actor_type"], ctx["actor_id"], "case.closed",
                   "case", case_id, "case-svc")
    return {"case_id": case_id, "status": "CLOSED"}

def reopen_case_db(db: Session, case_id: str, reason: str, ctx: dict, corr: str) -> dict:
    c = db.query(CaseRow).filter_by(case_id=case_id, tenant_id=ctx["tenant_id"]).first()
    if c is None:
        from ..core.errors import AppError
        raise AppError("E_NOT_FOUND", "case not found", customer_message_id="CASE.NOT_FOUND")
    c.reopen_count = (c.reopen_count or 0) + 1
    c.status = "REOPENED"; c.customer_visible_status = "REOPENED"
    db.commit()
    audit_svc.emit("TNT-TEST", corr, ctx["actor_type"], ctx["actor_id"], "case.reopened",
                   "case", case_id, "case-svc", reason=reason)
    esc = None
    if c.reopen_count >= 3:
        from .escalation import raise_escalation
        esc = raise_escalation("CASE", case_id, "L3", "REOPEN_X3", ctx, corr)
    return {"case": {"case_id": case_id, "status": c.status, "reopen_count": c.reopen_count}, "escalation": esc}
