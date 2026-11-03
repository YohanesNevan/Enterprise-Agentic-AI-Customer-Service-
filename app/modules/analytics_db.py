"""FR-ANA DB-backed: operasional, resolusi, handoff, SLA, driver-tree 2 tingkat + definisi + CSV."""
from __future__ import annotations
import csv
import io
from sqlalchemy.orm import Session
from .models import CaseRow, TicketRow, HandoffRow, SlaRecordRow, SlaEventRow, QaReviewRow

METRICS = {
    "cases_total": ("count(case_tbl)", "case_tbl"),
    "tickets_total": ("count(ticket)", "ticket"),
    "sla_attainment": ("1 - breached/started", "sla_record+sla_event"),
    "avg_qa_total": ("mean(qa_review.total)", "qa_review"),
    "handoff_complete_rate": ("complete/total", "handoff"),
}

def operational(db: Session, tenant_id: str = "TNT-TEST") -> dict:
    cases = db.query(CaseRow).filter_by(tenant_id=tenant_id).count()
    tickets = db.query(TicketRow).filter_by(tenant_id=tenant_id).count()
    open_cases = db.query(CaseRow).filter(CaseRow.tenant_id == tenant_id, ~CaseRow.status.in_(["CLOSED"])).count()
    breached = db.query(SlaRecordRow).filter_by(state="BREACHED", tenant_id=tenant_id).count()
    started = db.query(SlaRecordRow).filter_by(tenant_id=tenant_id).count() or 1
    return {"cases_total": cases, "tickets_total": tickets, "open_cases": open_cases,
            "sla_breached": breached, "sla_attainment_ratio": round(1 - breached / started, 3),
            "definitions": {"sla_attainment_ratio": METRICS["sla_attainment"][0], "source": "sla_record+sla_event"}}

def resolution(db: Session, tenant_id: str = "TNT-TEST") -> dict:
    cases = db.query(CaseRow).filter_by(tenant_id=tenant_id).all()
    closed = sum(1 for c in cases if c.status == "CLOSED")
    reopened = sum(1 for c in cases if (c.reopen_count or 0) > 0)
    return {"closed": closed, "reopen_count": reopened,
            "reopen_rate": round(reopened / closed, 3) if closed else 0,
            "target_SM13": "<=0.10",
            "definitions": {"reopen_rate": "cases_reopened/closed_cases", "source": "case_tbl"}}

def handoff_stats(db: Session, tenant_id: str = "TNT-TEST") -> dict:
    rows = db.query(HandoffRow).filter_by(tenant_id=tenant_id).all()
    by_reason: dict[str, int] = {}
    for r in rows: by_reason[r.reason_code] = by_reason.get(r.reason_code, 0) + 1
    complete = sum(1 for r in rows if r.package_complete)
    return {"total": len(rows), "by_reason": by_reason,
            "complete_rate": round(complete / len(rows), 3) if rows else 1.0,
            "target_SM07": 1.0,
            "definitions": {"complete_rate": METRICS["handoff_complete_rate"][0]}}

def driver_tree(db: Session, tenant_id: str = "TNT-TEST") -> dict:
    tree: dict[str, dict] = {}
    for c in db.query(CaseRow).filter_by(tenant_id=tenant_id).all():
        tree.setdefault(c.category or "?", {}).setdefault(c.sub_category or "-", 0)
        tree[c.category or "?"][c.sub_category or "-"] += 1
    return tree

def to_csv(rows: list[dict]) -> str:
    if not rows: return ""
    cols = list(rows[0].keys())
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=cols, extrasaction="ignore", lineterminator="\r\n")
    writer.writeheader()
    for row in rows:
        safe = {}
        for key in cols:
            value = row.get(key, "")
            text = "" if value is None else str(value)
            if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")):
                text = "'" + text
            safe[key] = text
        writer.writerow(safe)
    return stream.getvalue()
