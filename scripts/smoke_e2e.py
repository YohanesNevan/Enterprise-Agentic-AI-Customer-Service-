"""Smoke E2E profil LOCAL — 6 aturan FRD/TRD walking-skeleton B (tanpa server, via TestClient).
Jalankan: python scripts/smoke_e2e.py
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fastapi.testclient import TestClient
from app.main import app

c = TestClient(app)
H = {"X-Role": "cs_agent", "X-Actor-Type": "HUMAN_AGENT", "X-Actor-Id": "agent-1"}
H_AI = {"X-Role": "ai_agent", "X-Actor-Type": "AI_AGENT", "X-Actor-Id": "orchestrator"}
H_SUP = {"X-Role": "supervisor", "X-Actor-Type": "HUMAN_AGENT", "X-Actor-Id": "sup-1"}

checks = []


def check(name, fn):
    try:
        fn()
        checks.append((name, True, ""))
        print(f"[PASS] {name}")
    except AssertionError as e:
        checks.append((name, False, str(e)[:300]))
        print(f"[FAIL] {name}: {e}")


def t_ai_high():
    r = c.post("/v1/cases", json={"conversation_id": "CNV-SMOKE", "category": "TRANSACTION_DISPUTE",
                                  "severity_proposed": "HIGH", "description": "tidak kenal transaksi"}, headers=H_AI)
    assert r.status_code == 200, r.text
    assert r.json()["severity_confirmed"] is None  # BR-CASE-09


def t_close_refused():
    cid = c.post("/v1/cases", json={"conversation_id": "CNV-SMOKE", "category": "GENERAL",
                                    "severity_proposed": "LOW", "description": "x"}, headers=H).json()["case_id"]
    r2 = c.post(f"/v1/cases/{cid}/close", json={"checklist": {"outcome_recorded": True}}, headers=H_SUP)
    assert r2.status_code == 409, r2.text  # BR-CASE-05


def t_evidence_generic():
    cid = c.post("/v1/cases", json={"conversation_id": "CNV-SMOKE", "category": "TRANSACTION_DISPUTE",
                                    "severity_proposed": "MEDIUM", "description": "sengketa"}, headers=H).json()["case_id"]
    r2 = c.post(f"/v1/cases/{cid}/evidence-requests", json={"items": [{"description": "bukti"}], "reason": "x"}, headers=H)
    assert r2.status_code == 400 and r2.json()["error_code"] == "E_VALIDATION", r2.text  # BR-EV-01


def t_sla_monday():
    r = c.post("/v1/sla/calculate", json={"object_type": "CASE", "category": "TRANSACTION_DISPUTE",
                                          "severity": "HIGH", "created_at": "2026-03-06T09:30:00+00:00"}, headers=H)
    assert "2026-03-09" in r.json()["first_response_due_at"], r.text  # US-SLA-01


def t_handoff_defect():
    r = c.post("/v1/handoffs", json={"conversation_id": "CNV-SMOKE", "reason_code": "CUSTOMER_REQUEST",
                                     "recent_turns": []}, headers=H)
    assert r.status_code == 200 and "package_complete" in r.json(), r.text  # BR-HO-01/06


def t_self_approval():
    aid = c.post("/v1/approvals", json={"conversation_id": "CNV-1", "tool_name": "card_status_update",
                                        "args": {"a": 1}}, headers=H).json()["approval_id"]
    r2 = c.post(f"/v1/approvals/{aid}/decide",
                json={"approver_id": "agent-1", "decision": "GRANTED", "comment": "ok"},
                headers={"X-Role": "supervisor", "X-Actor-Type": "HUMAN_AGENT", "X-Actor-Id": "agent-1"})
    assert r2.status_code in (401, 403), r2.text  # RBAC-02


for n, f in [("BR-CASE-09 AI HIGH perlu konfirmasi", t_ai_high),
             ("BR-CASE-05 close ditolak + daftar kurang", t_close_refused),
             ("BR-EV-01 bukti generik ditolak", t_evidence_generic),
             ("US-SLA-01 Jumat 16:30 -> Senin", t_sla_monday),
             ("BR-HO-01/06 handoff defect bukan blokir", t_handoff_defect),
             ("RBAC-02 self-approval diblokir", t_self_approval)]:
    check(n, f)

print(f"\n{sum(1 for _, ok, _ in checks if ok)}/{len(checks)} lolos")
raise SystemExit(0 if all(ok for _, ok, _ in checks) else 1)
