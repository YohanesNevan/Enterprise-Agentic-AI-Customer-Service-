"""FR-SLA-005/006 eskalasi L1-L3. BR-SLA-05: objek bersiklus hidup."""
from ..core.ids import new_id
from ..core import audit as audit_svc
from datetime import datetime, timezone

ESCALATIONS: dict[str, dict] = {}

def raise_escalation(object_type: str, object_id: str, level: str, trigger: str, ctx: dict, corr: str) -> dict:
    eid = new_id("escalation")
    e = {"escalation_id": eid, "object_type": object_type, "object_id": object_id,
         "level": level, "trigger_type": trigger, "target_role": {"L1": "SUPERVISOR", "L2": "COMPLAINT_OFFICER", "L3": "MANAGEMENT"}[level],
         "created_at": datetime.now(timezone.utc).isoformat(), "acknowledged_by": None}
    ESCALATIONS[eid] = e
    audit_svc.emit("TNT-TEST", corr, ctx["actor_type"], ctx["actor_id"], "escalation.created",
                   "escalation", eid, "escalation-engine", reason=trigger)
    return e
