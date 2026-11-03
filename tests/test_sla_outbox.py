"""SLA Beat dari timestamp + outbox tahan CRM mati. TRD §4.15, FR-SLA-003/005, FR-CASE-001 AC2."""
import os
os.environ.setdefault("DATABASE_URL", "sqlite:///./eaics_test.db")
import datetime
from fastapi.testclient import TestClient

def _client():
    # DB bersih per import
    try: os.remove("./eaics_test.db")
    except FileNotFoundError: pass
    from app.main import app
    return TestClient(app)

from tests.auth_helpers import auth_headers
H = auth_headers("cs_agent", "agent-1")
HSUP = auth_headers("supervisor", "sup-1")

def _ensure_conversation(conversation_id="CNV-1"):
    from app.core.db import SessionLocal
    from app.modules.models_a import ConversationRow
    db = SessionLocal()
    if db.query(ConversationRow).filter_by(conversation_id=conversation_id, tenant_id="TNT-TEST").first() is None:
        db.add(ConversationRow(conversation_id=conversation_id, tenant_id="TNT-TEST", status="ACTIVE_AI"))
        db.commit()
    db.close()

def test_outbox_pending_saat_crm_mati_lalu_sent():
    c = _client()
    _ensure_conversation()
    from app.modules import outbox as O
    O.CRM_AVAILABLE["value"] = False
    r = c.post("/v1/cases", json={"conversation_id": "CNV-1", "category": "GENERAL",
        "severity_proposed": "LOW", "description": "x"}, headers=H)
    assert r.status_code == 200, r.text
    assert r.json()["crm_pending"] is True
    s = c.get("/internal/outbox-status", headers=HSUP)
    assert s.json()["pending"] >= 1
    d = c.post("/internal/outbox-drain", json={}, headers=HSUP)
    assert d.json()["pending"] >= 1  # masih pending karena CRM mati
    O.CRM_AVAILABLE["value"] = True
    d2 = c.post("/internal/outbox-drain", json={}, headers=HSUP)
    assert d2.json()["sent"] >= 1
    s2 = c.get("/internal/outbox-status", headers=HSUP)
    assert s2.json()["pending"] == 0

def test_sla_tick_breach_dari_timestamp():
    c = _client()
    _ensure_conversation()
    # buat case lalu mundurkan started_at + due agar overdue
    r = c.post("/v1/cases", json={"conversation_id": "CNV-1", "category": "GENERAL",
        "severity_proposed": "LOW", "description": "y"}, headers=H)
    sla_id = r.json()["sla"]["sla_id"]
    from app.core.db import SessionLocal
    from app.modules.models import SlaRecordRow
    db = SessionLocal()
    rec = db.query(SlaRecordRow).filter_by(sla_id=sla_id).one()
    past = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=10)
    rec.started_at = past
    rec.first_response_due_at = past + datetime.timedelta(hours=1)
    rec.resolution_due_at = past + datetime.timedelta(hours=2)
    db.commit(); db.close()
    t = c.post("/internal/sla-tick", json={}, headers=HSUP)
    assert t.json()["breached"] >= 1
    t2 = c.post("/internal/sla-tick", json={}, headers=HSUP)
    assert t2.json()["breached"] == 0  # idempoten: tak ada duplikat BREACHED
