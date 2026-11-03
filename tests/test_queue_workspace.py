"""FR-WS-002 prioritas antrean + BR-WS-04 catatan transfer wajib + FR-WS-003 satu layar."""
import os
os.environ.setdefault("DATABASE_URL", "sqlite:///./eaics_test_q.db")
from fastapi.testclient import TestClient

def _client():
    from app.main import app
    from app.core.db import Base, engine
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    return TestClient(app)

def _seed_conversation(conversation_id, tenant_id="TNT-TEST", status="ACTIVE_AI", customer_id="CUS-TEST"):
    from app.core.db import SessionLocal
    from app.modules.models_a import ConversationRow
    db = SessionLocal()
    db.add(ConversationRow(conversation_id=conversation_id, tenant_id=tenant_id,
                           status=status, customer_id=customer_id))
    db.commit(); db.close()

from tests.auth_helpers import auth_headers
H = auth_headers("cs_agent", "agent-1")
HSUP = auth_headers("supervisor", "sup-1")

def test_critical_didahulukan_dari_low():
    c = _client()
    _seed_conversation("CNV-LOW"); _seed_conversation("CNV-CRIT")
    c.post("/v1/workspace/queue/enqueue", json={"conversation_id": "CNV-LOW", "severity": "LOW"}, headers=H)
    c.post("/v1/workspace/queue/enqueue", json={"conversation_id": "CNV-CRIT", "severity": "CRITICAL"}, headers=H)
    r = c.get("/v1/workspace/queue", headers=HSUP)
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert items[0]["conversation_id"] == "CNV-CRIT"  # FR-WS-002 AC1

def test_transfer_tanpa_catatan_ditolak():
    c = _client()
    _seed_conversation("CNV-T")
    e = c.post("/v1/workspace/queue/enqueue", json={"conversation_id": "CNV-T", "severity": "MEDIUM"}, headers=H)
    hid = e.json()["handoff_id"]
    r = c.post(f"/v1/workspace/handoffs/{hid}/transfer",
               json={"to_queue": "Q-DISPUTES", "reason": "x", "note": ""}, headers=HSUP)
    assert r.status_code == 400
    assert r.json()["error_code"] == "E_VALIDATION"

def test_read_model_satu_layar():
    c = _client()
    from app.core.db import SessionLocal
    from app.modules.models_a import ConversationRow
    db = SessionLocal()
    db.add(ConversationRow(conversation_id="CNV-RM", tenant_id="TNT-TEST", customer_id="CUS-TEST"))
    db.commit(); db.close()
    c.post("/v1/cases", json={"conversation_id": "CNV-RM", "category": "GENERAL",
        "severity_proposed": "LOW", "description": "z"}, headers=H)
    c.post("/v1/workspace/queue/enqueue", json={"conversation_id": "CNV-RM", "severity": "HIGH",
        "reason_code": "CUSTOMER_REQUEST"}, headers=H)
    r = c.get("/v1/workspace/conversations/CNV-RM", headers=HSUP)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["handoff"]["reason_code"] == "CUSTOMER_REQUEST"
    assert len(body["cases"]) == 1
    assert body["sla"][0]["state"] in ("RUNNING", "AT_RISK", "BREACHED")


def test_accept_handoff_moves_conversation_to_active_human_and_checks_tenant():
    c = _client()
    _seed_conversation("CNV-ACCEPT", status="PENDING_HANDOFF")
    queued = c.post("/v1/workspace/queue/enqueue", json={"conversation_id": "CNV-ACCEPT"}, headers=H)
    assert queued.status_code == 200, queued.text
    hid = queued.json()["handoff_id"]
    accepted = c.post(f"/v1/workspace/handoffs/{hid}/accept", json={}, headers=H)
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["state"] == "ACCEPTED"
    assert accepted.json()["conversation_status"] == "ACTIVE_HUMAN"

    from app.core.db import SessionLocal
    from app.modules.models_a import ConversationRow
    db = SessionLocal()
    try:
        assert db.query(ConversationRow).filter_by(conversation_id="CNV-ACCEPT").one().status == "ACTIVE_HUMAN"
    finally:
        db.close()
    denied = c.post(f"/v1/workspace/handoffs/{hid}/accept", json={},
                    headers=auth_headers("cs_agent", "other-tenant-agent", "OTHER-TENANT"))
    assert denied.status_code == 404


def test_agent_reply_persists_verified_author_and_resolves_to_existing_state():
    c = _client()
    _seed_conversation("CNV-REPLY", status="PENDING_HANDOFF")
    queued = c.post("/v1/workspace/queue/enqueue", json={"conversation_id": "CNV-REPLY"}, headers=H)
    hid = queued.json()["handoff_id"]
    assert c.post(f"/v1/workspace/handoffs/{hid}/accept", json={}, headers=H).status_code == 200

    blank = c.post("/v1/workspace/conversations/CNV-REPLY/messages", json={"content": "   "}, headers=H)
    assert blank.status_code == 400
    wrong_agent = c.post("/v1/workspace/conversations/CNV-REPLY/messages", json={"content": "Saya bantu cek."},
                         headers=auth_headers("cs_agent", "agent-2", "TNT-TEST"))
    assert wrong_agent.status_code == 409
    customer = c.post("/v1/workspace/conversations/CNV-REPLY/messages", json={"content": "Tidak berhak."},
                      headers=auth_headers("customer", "CUS-TEST"))
    assert customer.status_code == 403
    foreign = c.post("/v1/workspace/conversations/CNV-REPLY/messages", json={"content": "Tenant lain."},
                     headers=auth_headers("cs_agent", "agent-1", "OTHER-TENANT"))
    assert foreign.status_code == 404

    sent = c.post("/v1/workspace/conversations/CNV-REPLY/messages",
                  json={"content": "Saya akan membantu meninjau permintaan Anda."}, headers=H)
    assert sent.status_code == 200, sent.text
    assert sent.json()["author_type"] == "HUMAN_AGENT"
    assert sent.json()["author_id"] == "agent-1"
    transcript = c.get("/v1/workspace/conversations/CNV-REPLY", headers=H)
    assert transcript.status_code == 200
    assert transcript.json()["messages"][-1]["content"] == sent.json()["content"]
    assert transcript.json()["messages"][-1]["author_type"] == "HUMAN_AGENT"

    resolved = c.post("/v1/workspace/conversations/CNV-REPLY/resolve", json={}, headers=H)
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["to"] == "RESOLVED_PENDING_CONFIRMATION"
    after = c.get("/v1/workspace/conversations/CNV-REPLY", headers=H)
    assert after.json()["conversation"]["status"] == "RESOLVED_PENDING_CONFIRMATION"
    blocked = c.post("/v1/workspace/conversations/CNV-REPLY/messages", json={"content": "Setelah selesai."}, headers=H)
    assert blocked.status_code == 409


def test_case_and_ticket_create_links_only_conversations_in_agent_tenant():
    c = _client()
    _seed_conversation("CNV-OWN", customer_id="CUS-OWN")
    _seed_conversation("CNV-FOREIGN", tenant_id="OTHER-TENANT", customer_id="CUS-OTHER")
    case_body = {"conversation_id": "CNV-OWN", "category": "GENERAL",
                 "severity_proposed": "LOW", "description": "Tindak lanjut petugas."}
    case = c.post("/v1/cases", json=case_body, headers=H)
    assert case.status_code == 200, case.text
    ticket = c.post("/v1/tickets", json={"conversation_id": "CNV-OWN", "description": "Tindak lanjut layanan."}, headers=H)
    assert ticket.status_code == 200, ticket.text
    for endpoint, body in (("/v1/cases", {**case_body, "conversation_id": "CNV-FOREIGN"}),
                           ("/v1/tickets", {"conversation_id": "CNV-FOREIGN", "description": "Tidak boleh."})):
        assert c.post(endpoint, json=body, headers=H).status_code == 404

    from app.core.db import SessionLocal
    from app.modules.models import CaseRow, TicketRow
    db = SessionLocal()
    try:
        stored_case = db.query(CaseRow).filter_by(case_id=case.json()["case_id"]).one()
        stored_ticket = db.query(TicketRow).filter_by(ticket_id=ticket.json()["ticket_id"]).one()
        assert stored_case.customer_id == "CUS-OWN"
        assert stored_ticket.customer_id == "CUS-OWN"
        assert stored_case.tenant_id == stored_ticket.tenant_id == "TNT-TEST"
    finally:
        db.close()
