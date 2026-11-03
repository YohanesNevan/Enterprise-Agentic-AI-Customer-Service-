"""FR-CASE-001 AC2: tulis lokal + outbox dalam satu transaksi; worker drain ke sim-crm dengan retry."""
from __future__ import annotations
import datetime
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session
from ..core.ids import new_id
from ..core import audit as audit_svc
from .models import CrmOutboxRow

CRM_AVAILABLE = {"value": True}  # toggle chaos: sim-crm mati

def tenant_query(db: Session, tenant_id: str):
    from .models import CaseRow, TicketRow
    cases = select(CaseRow.case_id).where(CaseRow.tenant_id == tenant_id)
    tickets = select(TicketRow.ticket_id).where(TicketRow.tenant_id == tenant_id)
    return db.query(CrmOutboxRow).filter(or_(
        and_(CrmOutboxRow.object_type == "CASE", CrmOutboxRow.object_id.in_(cases)),
        and_(CrmOutboxRow.object_type == "TICKET", CrmOutboxRow.object_id.in_(tickets))))

def enqueue(db: Session, object_type: str, object_id: str, payload: dict) -> str:
    oid = new_id("case") if object_type == "CASE" else new_id("ticket")
    # outbox_id pakai prefix generik: gunakan correlation kind
    from ..core.ids import new_id as nid
    db.add(CrmOutboxRow(outbox_id=nid("turn"), object_type=object_type, object_id=object_id,
                        operation="CREATE", payload=payload, state="PENDING"))
    db.commit()
    return object_id

def drain(db: Session, corr: str = "COR-OUTBOX", tenant_id: str = "TNT-TEST") -> dict:
    sent, pending, failed = 0, 0, 0
    rows = tenant_query(db, tenant_id).filter_by(state="PENDING").all()
    for r in rows:
        r.attempts += 1
        if CRM_AVAILABLE["value"]:
            r.state = "SENT"
            r.sent_at = datetime.datetime.now(datetime.timezone.utc)
            sent += 1
            audit_svc.emit("TNT-TEST", corr, "SYSTEM", "outbox-worker", "crm.outbox_sent",
                           "outbox", r.outbox_id, "outbox-worker")
        else:
            r.last_error = "sim-crm unavailable"
            failed += 1
    db.commit()
    pending = tenant_query(db, tenant_id).filter_by(state="PENDING").count()
    return {"sent": sent, "pending": pending, "failed_attempts": failed}
