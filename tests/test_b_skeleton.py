"""E2E-11 tulang punggung keluhan + E2E-12 SLA + kontrak §16. TRD §13.6."""
from fastapi.testclient import TestClient
from app.main import app

c = TestClient(app)
from tests.auth_helpers import auth_headers
H = auth_headers("cs_agent", "agent-1")
H_AI = auth_headers("ai_agent", "orchestrator")

def _seed_conversation(conversation_id):
    from app.core.db import SessionLocal
    from app.modules.models_a import ConversationRow
    db = SessionLocal()
    if db.query(ConversationRow).filter_by(conversation_id=conversation_id, tenant_id="TNT-TEST").first() is None:
        db.add(ConversationRow(conversation_id=conversation_id, tenant_id="TNT-TEST",
                               customer_id="CUS-TEST", status="ACTIVE_AI"))
        db.commit()
    db.close()

def test_create_case_ai_high_requires_confirm():
    _seed_conversation("CNV-TEST")
    r = c.post("/v1/cases", json={"conversation_id": "CNV-TEST", "category": "TRANSACTION_DISPUTE",
        "severity_proposed": "HIGH", "description": "tidak kenal transaksi"}, headers=H_AI)
    assert r.status_code == 200, r.text
    assert r.json()["severity_confirmed"] is None
    assert r.json()["severity_confirmation_required"] is True

def test_closure_refused_lists_missing():
    _seed_conversation("CNV-TEST")
    r = c.post("/v1/cases", json={"conversation_id": "CNV-TEST", "category": "GENERAL",
        "severity_proposed": "LOW", "description": "x"}, headers=H)
    cid = r.json()["case_id"]
    r2 = c.post(f"/v1/cases/{cid}/close", json={"checklist": {"outcome_recorded": True}}, headers=auth_headers("supervisor", "sup-1"))
    assert r2.status_code == 409
    assert "evidence_adjudicated" in r2.json()["message"] or "missing" in r2.json()["message"]

def test_evidence_generic_rejected():
    _seed_conversation("CNV-TEST")
    r = c.post("/v1/cases", json={"conversation_id": "CNV-TEST", "category": "TRANSACTION_DISPUTE",
        "severity_proposed": "MEDIUM", "description": "sengketa"}, headers=H)
    cid = r.json()["case_id"]
    r2 = c.post(f"/v1/cases/{cid}/evidence-requests", json={"items": [{"description": "bukti"}], "reason": "x"}, headers=H)
    assert r2.status_code == 400
    assert r2.json()["error_code"] == "E_VALIDATION"

def test_sla_friday_1630_falls_monday():
    r = c.post("/v1/sla/calculate", json={"object_type": "CASE", "category": "TRANSACTION_DISPUTE",
        "severity": "HIGH", "created_at": "2026-03-06T09:30:00+00:00"}, headers=H)
    assert r.status_code == 200
    due = r.json()["first_response_due_at"]
    assert "2026-03-09" in due, due  # Senin, bukan akhir pekan (US-SLA-01)

def test_handoff_incomplete_is_defect_not_block():
    r = c.post("/v1/handoffs", json={"conversation_id": "CNV-TEST", "reason_code": "CUSTOMER_REQUEST",
        "recent_turns": []}, headers=H)
    assert r.status_code == 200
    assert "package_complete" in r.json()

def test_self_approval_blocked():
    from app.core.db import SessionLocal
    from app.modules.models_a import ConversationRow
    db = SessionLocal()
    db.add(ConversationRow(conversation_id="CNV-1", tenant_id="TNT-TEST"))
    db.commit(); db.close()
    r = c.post("/v1/approvals", json={"conversation_id": "CNV-1", "tool_name": "card_status_update",
        "args": {"a": 1}}, headers=H)
    aid = r.json()["approval_id"]
    r2 = c.post(f"/v1/approvals/{aid}/decide",
                json={"approver_id": "agent-1", "decision": "GRANTED", "comment": "ok"},
                headers=auth_headers("supervisor", "agent-1"))
    assert r2.status_code in (401, 403)


def test_ticket_creation_success_returns_persisted_status_and_reference():
    from app.core.db import SessionLocal
    from app.modules.models import TicketRow

    _seed_conversation("ticket-success-conversation")
    response = c.post("/v1/tickets", json={
        "conversation_id": "ticket-success-conversation",
        "description": "Pelanggan meminta tindak lanjut layanan.",
    }, headers=H_AI)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ticket_id"]
    assert body["status"] == "OPEN"

    db = SessionLocal()
    try:
        row = db.query(TicketRow).filter_by(ticket_id=body["ticket_id"], tenant_id="TNT-TEST").one()
        assert row.status == body["status"]
        assert row.conversation_id == "ticket-success-conversation"
    finally:
        db.close()


def test_ticket_creation_failure_returns_error_without_success_claim(monkeypatch):
    from fastapi.testclient import TestClient
    from app.core.errors import AppError
    from app.core.db import SessionLocal
    from app.modules import store as Store
    from app.modules.models import TicketRow

    def fail_create(*args, **kwargs):
        raise AppError("E_UPSTREAM", "ticket storage unavailable", customer_message_id="TICKET.UNAVAILABLE")

    _seed_conversation("ticket-failure-conversation")
    monkeypatch.setattr(Store, "create_ticket_db", fail_create)
    failing_client = TestClient(app, raise_server_exceptions=False)
    response = failing_client.post("/v1/tickets", json={
        "conversation_id": "ticket-failure-conversation",
        "description": "Pelanggan meminta tindak lanjut layanan.",
    }, headers=H_AI)
    assert response.status_code >= 400
    body = response.json()
    assert "ticket_id" not in body
    assert "created" not in str(body).lower()

    db = SessionLocal()
    try:
        assert db.query(TicketRow).filter_by(conversation_id="ticket-failure-conversation").count() == 0
    finally:
        db.close()
