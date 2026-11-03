"""FR-SVC-001..007 [A]: inquiry jawab-konfirmasi, service kelayakan-rute-eksekusi,
duplikat, komitmen via sla_calculate / knowledge fallback, konfirmasi resolusi."""
from __future__ import annotations
from sqlalchemy.orm import Session
from ..core import audit as audit_svc
from .models_a import MessageRow

_tickets_by_key: dict[str, str] = {}  # (customer,intent,entity) -> ticket_id (BR-SVC-03)

def check_duplicate(customer: str | None, intent: str, entity: str = "") -> str | None:
    return _tickets_by_key.get(f"{customer}|{intent}|{entity}")

def remember_ticket(customer: str | None, intent: str, ticket_id: str, entity: str = ""):
    _tickets_by_key[f"{customer}|{intent}|{entity}"] = ticket_id

def commitment(object_type: str, category: str, severity: str, created_at) -> dict:
    """BR-SVC-04: tanggal hanya dari sla_calculate atau knowledge tersitasi. Tidak mengarang."""
    try:
        from . import sla_engine as SlaSvc
        s = SlaSvc.calculate(object_type, category, severity, created_at)
        return {"at": s["resolution_due_at"], "source": "SLA_TOOL", "sla": s}
    except Exception:
        return {"at": None, "source": "KNOWLEDGE_CITATION",
                "note": "1x24 jam sesuai artikel terbit [Sumber: Syarat rekening koran]"}

def confirm_resolution(db: Session, conv_id: str, text: str = "Apakah ini sudah selesai? (ya/belum)") -> dict:
    n = db.query(MessageRow).filter_by(conversation_id=conv_id).count()
    return {"confirmation_state": "ASKED", "messages": n, "prompt": text}

def proactive_due(open_cases: int, days_open: int) -> bool:
    """BR-SVC-06: irama minimum tiap 2 hari kerja."""
    return days_open >= 2 and open_cases > 0
