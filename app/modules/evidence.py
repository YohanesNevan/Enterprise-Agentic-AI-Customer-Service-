"""FR-EV-001..007. BR-EV-01: tolak deskripsi generik. BR-EV-04: AI hanya metadata."""
from __future__ import annotations
from ..core.errors import AppError
from ..core import audit as audit_svc
from ..core.ids import new_id

GENERIC = {"bukti", "dokumen", "berkas bukti", "evidence", "document"}

def create_request(case_id: str, items: list[dict], reason: str, due_at: str | None,
                   ctx: dict, corr: str) -> dict:
    if not items:
        raise AppError("E_VALIDATION", "evidence items empty", customer_message_id="EVIDENCE.EMPTY",
                       details=[{"field": "items", "rule": "MIN_ITEMS_1"}])
    for i, it in enumerate(items):
        desc = (it.get("description") or "").strip()
        if len(desc) < 20 or desc.lower() in GENERIC:
            raise AppError("E_VALIDATION", "Evidence item description is too generic",
                           customer_message_id="EVIDENCE.TOO_GENERIC",
                           details=[{"field": f"items[{i}].description", "rule": "MIN_SPECIFICITY"}])
    er_id = new_id("evidence_request")
    audit_svc.emit("TNT-TEST", corr, ctx["actor_type"], ctx["actor_id"], "evidence.requested",
                   "evidence_request", er_id, "evidence-svc", conversation_id=None, reason=reason)
    return {"evidence_request_id": er_id, "upload_target_hint": "/v1/evidence/upload", "due_at": due_at}

def metadata_view(evidence_items: list[dict]) -> list[dict]:
    """FR-EV-004: AI hanya terima metadata, tanpa konten/nama file nasabah."""
    return [{"evidence_id": e.get("evidence_id"), "state": e.get("state"),
             "adjudication": e.get("adjudication_state", "PENDING"),
             "provenance_al": e.get("provenance_al")} for e in evidence_items]
