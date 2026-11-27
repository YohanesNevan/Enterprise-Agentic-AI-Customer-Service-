"""FR-SLA-005/006 eskalasi L1-L3. BR-SLA-05: objek bersiklus hidup."""
from __future__ import annotations
import datetime
from sqlalchemy.orm import Session
from ..core.ids import new_id
from ..core import audit as audit_svc
from .models import EscalationRow

ESCALATIONS: dict[str, dict] = {}

def raise_escalation(object_type: str, object_id: str, level: str, trigger: str, ctx: dict, corr: str, db: Session | None = None) -> dict:
    eid = new_id("escalation")
    now_dt = datetime.datetime.now(datetime.timezone.utc)
    target_role_map = {"L1": "SUPERVISOR", "L2": "COMPLAINT_OFFICER", "L3": "MANAGEMENT"}
    target = target_role_map.get(level, "SUPERVISOR")
    e = {"escalation_id": eid, "object_type": object_type, "object_id": object_id,
         "level": level, "trigger_type": trigger, "target_role": target,
         "created_at": now_dt.isoformat(), "acknowledged_by": None}
    ESCALATIONS[eid] = e

    if db is not None:
        try:
            row = EscalationRow(
                escalation_id=eid,
                object_type=object_type,
                object_id=object_id,
                level=level,
                trigger_type=trigger,
                target_role=target,
                created_at=now_dt,
                acknowledged_by=None,
            )
            db.add(row)
            db.commit()
        except Exception:
            db.rollback()

    audit_svc.emit(ctx.get("tenant_id", "TNT-TEST"), corr, ctx.get("actor_type", "SYSTEM"),
                   ctx.get("actor_id", "system"), "escalation.created",
                   "escalation", eid, "escalation-engine", reason=trigger)
    return e


def list_escalations_db(db: Session, target_role: str | None = None, tenant_id: str = "TNT-TEST") -> list[dict]:
    """Retrieve escalations from DB with target_role filtering."""
    query = db.query(EscalationRow)
    if target_role:
        query = query.filter(EscalationRow.target_role.ilike(f"%{target_role}%"))
    rows = query.order_by(EscalationRow.created_at.desc()).all()
    results = []
    for r in rows:
        results.append({
            "escalation_id": r.escalation_id,
            "object_type": r.object_type,
            "object_id": r.object_id,
            "level": r.level,
            "trigger_type": r.trigger_type,
            "target_role": r.target_role,
            "created_at": r.created_at.isoformat() if r.created_at else "",
            "acknowledged_by": r.acknowledged_by,
        })
    # Also include any uncommitted in-memory escalations matching role
    for eid, mem in ESCALATIONS.items():
        if not any(item["escalation_id"] == eid for item in results):
            if not target_role or target_role.upper() in mem.get("target_role", "").upper():
                results.append(mem)
    return results


def acknowledge_escalation_db(db: Session, escalation_id: str, actor_id: str, corr: str = "COR-?", tenant_id: str = "TNT-TEST") -> dict | None:
    """Mark an escalation as acknowledged by a supervisor or complaint officer."""
    row = db.query(EscalationRow).filter_by(escalation_id=escalation_id).first()
    if row:
        row.acknowledged_by = actor_id
        db.commit()
    if escalation_id in ESCALATIONS:
        ESCALATIONS[escalation_id]["acknowledged_by"] = actor_id
    audit_svc.emit(tenant_id, corr, "STAFF", actor_id, "escalation.acknowledged",
                   "escalation", escalation_id, "escalation-engine")
    return {
        "escalation_id": escalation_id,
        "acknowledged_by": actor_id,
        "status": "ACKNOWLEDGED",
    }

