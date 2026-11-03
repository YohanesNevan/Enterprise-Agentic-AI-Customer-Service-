"""TRD §4.15 tick Beat 60s: peristiwa dihitung dari timestamp tersimpan, bukan dari tick.
Sehingga tick terlewat menunda notifikasi tapi tak mengubah kapan pelanggaran terjadi (SM-10)."""
from __future__ import annotations
import datetime
from sqlalchemy.orm import Session
from ..core.ids import new_id
from ..core import audit as audit_svc
from .models import SlaRecordRow, SlaEventRow, EscalationRow

def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)

def _has(db: Session, sla_id: str, typ: str) -> bool:
    return db.query(SlaEventRow).filter_by(sla_id=sla_id, type=typ).first() is not None

def tick(db: Session, now: datetime.datetime | None = None, corr: str = "COR-TICK") -> dict:
    now = now or _now()
    fired = {"at_risk": 0, "breached": 0, "escalated": []}
    for rec in db.query(SlaRecordRow).filter(SlaRecordRow.state.in_(["RUNNING", "AT_RISK"])).all():
        # pastikan naive vs aware konsisten
        fr_due = rec.first_response_due_at
        reso_due = rec.resolution_due_at
        if fr_due.tzinfo is None: fr_due = fr_due.replace(tzinfo=datetime.timezone.utc)
        if reso_due.tzinfo is None: reso_due = reso_due.replace(tzinfo=datetime.timezone.utc)
        total = (reso_due - rec.started_at.replace(tzinfo=datetime.timezone.utc) if rec.started_at.tzinfo is None else reso_due - rec.started_at).total_seconds()
        elapsed = (now - (rec.started_at.replace(tzinfo=datetime.timezone.utc) if rec.started_at.tzinfo is None else rec.started_at)).total_seconds()
        pct = (elapsed / total) if total > 0 else 1.0
        # AT_RISK pada 80%
        if pct >= 0.8 and not _has(db, rec.sla_id, "AT_RISK"):
            db.add(SlaEventRow(sla_event_id=new_id("sla"), sla_id=rec.sla_id, type="AT_RISK",
                               occurred_at=now, computed_from=rec.resolution_due_at.isoformat(), reason_code="PCT_80"))
            rec.state = "AT_RISK"
            fired["at_risk"] += 1
            audit_svc.emit(rec.tenant_id, corr, "SYSTEM", "sla-engine", "sla.at_risk",
                           "sla", rec.sla_id, "sla-engine")
        # BREACHED pada 100% + eskalasi satu tingkat otomatis
        if now >= reso_due and not _has(db, rec.sla_id, "BREACHED"):
            db.add(SlaEventRow(sla_event_id=new_id("sla"), sla_id=rec.sla_id, type="BREACHED",
                               occurred_at=now, computed_from=rec.resolution_due_at.isoformat(), reason_code="OVERDUE"))
            rec.state = "BREACHED"
            fired["breached"] += 1
            eid = new_id("escalation")
            db.add(EscalationRow(escalation_id=eid, object_type=rec.object_type, object_id=rec.object_id,
                                 level="L1", trigger_type="SLA_BREACH", target_role="SUPERVISOR"))
            fired["escalated"].append(eid)
            audit_svc.emit(rec.tenant_id, corr, "SYSTEM", "sla-engine", "sla.breached",
                           "sla", rec.sla_id, "sla-engine", reason="OVERDUE")
    db.commit()
    return fired
