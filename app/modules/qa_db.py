"""FR-QA-001..007 DB-backed: sampling ber-seed + skor + gagal-otomatis + temuan."""
from __future__ import annotations
import random
from sqlalchemy.orm import Session
from ..core.ids import new_id
from ..core import audit as audit_svc
from ..core.errors import AppError
from .models import QaSampleRow, QaReviewRow, QaFindingRow, CaseRow

AUTO_FAIL_RULES = ["PII_UNDER_AL", "NO_CITATION", "PROHIBITED_TOOL"]
SCORE_FIELDS = ["identitas", "sitasi", "klasifikasi", "tool", "bukti", "komunikasi", "komitmen", "penutupan"]

def draw_sample_db(db: Session, seed: int = 42, corr: str = "COR-QA", tenant_id: str = "TNT-TEST") -> dict:
    # populasi: case CLOSED/RESOLVED + mandatory: reopened/escalated/high
    all_cases = db.query(CaseRow).filter_by(tenant_id=tenant_id).all()
    closed_ids = [c.case_id for c in all_cases if c.status in ("CLOSED", "RESOLVED", "REOPENED")]
    mandatory = [c.case_id for c in all_cases
                 if (c.reopen_count or 0) > 0 or (c.severity_confirmed in ("HIGH", "CRITICAL"))]
    rnd = random.Random(seed)
    base = set(rnd.sample(closed_ids, max(0, int(len(closed_ids) * 0.1)))) if closed_ids else set()
    selected = sorted(base | set(mandatory))
    run_id = new_id("qa_review")
    db.add(QaSampleRow(sample_run_id=run_id, seed=seed, selected=selected))
    db.commit()
    audit_svc.emit("TNT-TEST", corr, "SYSTEM", "qa-sampler", "qa.sample_drawn",
                   "qa_sample", run_id, "qa-svc", after={"selected": selected, "seed": seed})
    return {"sample_run_id": run_id, "method": "10pct_random+100pct_risk",
            "seed": seed, "selected_ids": selected}

def score_db(db: Session, item_id: str, scores: dict, reviewer: str, corr: str,
             auto_fail: str | None = None) -> dict:
    for k in scores:
        if k not in SCORE_FIELDS:
            raise AppError("E_VALIDATION", f"unknown score field {k}", customer_message_id="QA.FIELD")
    if auto_fail and auto_fail not in AUTO_FAIL_RULES:
        raise AppError("E_VALIDATION", "unknown auto-fail rule", customer_message_id="QA.AUTO_FAIL")
    for k, v in scores.items():
        if not (0 <= int(v) <= 10):
            raise AppError("E_VALIDATION", f"score {k} out of range", customer_message_id="QA.RANGE")
    total = 0 if auto_fail else sum(int(v) for v in scores.values())
    rid = new_id("qa_review")
    db.add(QaReviewRow(review_id=rid, item_id=item_id, reviewer_id=reviewer,
                       scores=scores, total=total, auto_fail=bool(auto_fail),
                       auto_fail_criterion=auto_fail))
    db.commit()
    audit_svc.emit("TNT-TEST", corr, "HUMAN_AGENT", reviewer, "qa.review_completed",
                   "qa_review", rid, "qa-svc", after={"total": total})
    return {"review_id": rid, "item_id": item_id, "total": total,
            "auto_fail": bool(auto_fail), "auto_fail_criterion": auto_fail}

def add_finding_db(db: Session, review_id: str, ftype: str, severity: str,
                   description: str, corr: str, ctx: dict) -> dict:
    if ftype not in ("individual_coaching", "knowledge_gap", "process_defect", "ai_defect", "system_defect"):
        raise AppError("E_VALIDATION", "unknown finding type", customer_message_id="QA.FINDING_TYPE")
    fid = new_id("qa_review")
    db.add(QaFindingRow(finding_id=fid, review_id=review_id, type=ftype,
                        severity=severity, description=description, status="OPEN"))
    db.commit()
    audit_svc.emit("TNT-TEST", corr, ctx["actor_type"], ctx["actor_id"], "qa.finding_raised",
                   "qa_finding", fid, "qa-svc", reason=ftype)
    routed = "knowledge-manager" if ftype == "knowledge_gap" else ("root-cause-register" if ftype in ("process_defect", "system_defect", "ai_defect") else "agent-coach")
    return {"finding_id": fid, "review_id": review_id, "type": ftype, "routed_to": routed, "status": "OPEN"}

def summary_db(db: Session, tenant_id: str = "TNT-TEST") -> dict:
    revs = (db.query(QaReviewRow).join(CaseRow, QaReviewRow.item_id == CaseRow.case_id)
            .filter(CaseRow.tenant_id == tenant_id).all())
    if not revs:
        return {"n": 0, "avg_total": 0, "auto_fail_rate": 0, "definitions": {"avg_total": "mean(qa_review.total)"}}
    avg = sum(r.total for r in revs) / len(revs)
    afr = sum(1 for r in revs if r.auto_fail) / len(revs)
    by_field: dict[str, float] = {}
    for f in SCORE_FIELDS:
        vals = [r.scores.get(f, 0) for r in revs if f in (r.scores or {})]
        by_field[f] = round(sum(vals) / len(vals), 2) if vals else 0
    return {"n": len(revs), "avg_total": round(avg, 2), "auto_fail_rate": round(afr, 3),
            "by_field": by_field, "definitions": {"avg_total": "mean(qa_review.total)", "source": "qa-svc"}}
