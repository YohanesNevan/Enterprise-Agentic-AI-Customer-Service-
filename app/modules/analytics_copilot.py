"""FR-ANA-001..008 + FR-CP copilot saran (B). Saran tidak pernah terkirim otomatis (BR-CP-01)."""
from ..core.ids import new_id
from ..core import audit as audit_svc

def operational_dashboard() -> dict:
    from . import cases as C
    from . import escalation as E
    return {"cases_total": len(C.CASES), "tickets_total": len(C.TICKETS),
            "escalations_by_level": {}, "open_cases": [c for c in C.CASES.values() if c["status"] not in ("CLOSED",)],
            "definitions": {"cases_total": "count(case)", "source": "case-svc"}}

def driver_tree() -> dict:
    """Q-12 default: dua tingkat kategori->subkategori."""
    from . import cases as C
    tree: dict = {}
    for c in C.CASES.values():
        l1 = c.get("category", "?"); l2 = c.get("sub_category") or "-"
        tree.setdefault(l1, {}).setdefault(l2, 0)
        tree[l1][l2] += 1
    return tree

def suggest_reply(conversation_id: str, corr: str) -> dict:
    """FR-CP-001: maks 3 saran + sitasi, tidak terkirim otomatis."""
    sid = new_id("turn")
    s = {"suggestion_id": sid, "text": "[SARAN — perlu dikirim manual oleh agen] ...",
         "citations": [], "contains_internal": False, "used": False}
    audit_svc.emit("TNT-TEST", corr, "AI_AGENT", "copilot", "copilot.suggestion_generated",
                   "copilot_suggestion", sid, "copilot-svc", conversation_id=conversation_id)
    return s
