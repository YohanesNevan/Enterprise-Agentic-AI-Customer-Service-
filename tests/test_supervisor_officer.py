"""Unit 09: Test Supervisor and Complaint Officer Operations."""
import os
os.environ["DATABASE_URL"] = "sqlite:///./eaics_test_q.db"
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.db import Base, engine, SessionLocal
from app.modules import models, models_a
from app.modules.conversation import ingest
from app.modules import store as Store
from app.modules import escalation as EscSvc
from tests.auth_helpers import auth_headers

client = TestClient(app)

SUPERVISOR_HEADERS = auth_headers("supervisor", "spv-1")
OFFICER_HEADERS = auth_headers("complaint_officer", "officer-1")
AGENT_HEADERS = auth_headers("cs_agent", "agent-1")
CUSTOMER_HEADERS = auth_headers("customer", "customer-u09")


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield


def test_supervisor_and_officer_access_control():
    # 1. Unauthenticated request is rejected with 401 or 403
    r_unauth = client.get("/v1/workspace/escalations")
    assert r_unauth.status_code in (401, 403)

    # 2. Customer role is strictly forbidden from accessing escalations
    r_customer = client.get("/v1/workspace/escalations", headers=CUSTOMER_HEADERS)
    assert r_customer.status_code == 403

    # 3. CS Agent cannot access escalations (reserved for supervisor/officer)
    r_agent = client.get("/v1/workspace/escalations", headers=AGENT_HEADERS)
    assert r_agent.status_code == 403


def test_escalation_workflow():
    db = SessionLocal()
    try:
        # Create an escalation for SUPERVISOR
        e = EscSvc.raise_escalation(
            object_type="CASE",
            object_id="CAS-TEST-ESC-1",
            level="L1",
            trigger="SLA_BREACH_REPEAT",
            ctx={"tenant_id": "TNT-TEST", "actor_type": "SYSTEM", "actor_id": "system"},
            corr="CORR-U09-ESC",
            db=db,
        )
        eid = e["escalation_id"]

        # Supervisor queries escalations
        res = client.get("/v1/workspace/escalations", headers=SUPERVISOR_HEADERS)
        assert res.status_code == 200, res.text
        data = res.json()
        assert "items" in data
        assert any(item["escalation_id"] == eid for item in data["items"])

        # Supervisor acknowledges escalation
        ack_res = client.post(f"/v1/workspace/escalations/{eid}/acknowledge", headers=SUPERVISOR_HEADERS)
        assert ack_res.status_code == 200, ack_res.text
        assert ack_res.json()["status"] == "ACKNOWLEDGED"
        assert ack_res.json()["acknowledged_by"] == "spv-1"
    finally:
        db.close()


def test_sla_risk_monitoring():
    db = SessionLocal()
    try:
        # Create a case with SLA via Store
        conv = ingest(
            db,
            channel="WEB_CHAT",
            from_handle="cust-sla-test",
            text="Keluhan gagal transaksi",
            claimed_customer_id="cust-sla-test",
            tenant="TNT-TEST",
            force_new=True,
        )
        from app.modules.cases import CreateCaseIn
        from app.contracts.vocabularies import Severity
        case_in = CreateCaseIn(
            conversation_id=conv["conversation_id"],
            customer_id="cust-sla-test",
            category="TRANSACTION_DISPUTE",
            severity_proposed=Severity.HIGH,
            description="Uang hilang saat transfer",
        )
        c = Store.create_case_db(db, case_in, {"actor_type": "STAFF", "actor_id": "agent-1"}, "CORR-SLA", "TNT-TEST")
        cid = c["case_id"]

        # Supervisor reads SLA records
        res = client.get("/v1/workspace/sla/records", headers=SUPERVISOR_HEADERS)
        assert res.status_code == 200, res.text
        items = res.json().get("items", [])
        assert len(items) >= 1
        assert any(item["object_id"] == cid for item in items)
    finally:
        db.close()


def test_ticket_reassignment():
    db = SessionLocal()
    try:
        conv = ingest(
            db,
            channel="WEB_CHAT",
            from_handle="cust-reassign",
            text="Kendala teknis portal",
            claimed_customer_id="cust-reassign",
            tenant="TNT-TEST",
            force_new=True,
        )
        from app.modules.cases import CreateTicketIn
        t_in = CreateTicketIn(
            conversation_id=conv["conversation_id"],
            customer_id="cust-reassign",
            type="GENERAL",
            description="Portal tidak bisa diakses",
        )
        t = Store.create_ticket_db(db, t_in, {"actor_type": "STAFF", "actor_id": "agent-1"}, "CORR-T-REASSIGN", "TNT-TEST")
        tid = t["ticket_id"]

        # Supervisor reassigns ticket to 'SPECIALIST_TIER2'
        res = client.patch(
            f"/v1/tickets/{tid}/assign",
            json={"owner_queue": "SPECIALIST_TIER2", "reason": "Kendala jaringan kompleks butuh eskalasi"},
            headers=SUPERVISOR_HEADERS,
        )
        assert res.status_code == 200, res.text
        assert res.json()["owner_queue"] == "SPECIALIST_TIER2"
        assert res.json()["updated_by"] == "spv-1"
    finally:
        db.close()


def test_complaint_officer_case_adjudication():
    db = SessionLocal()
    try:
        conv = ingest(
            db,
            channel="WEB_CHAT",
            from_handle="cust-dispute-adj",
            text="Sanggahan tagihan kartu kredit",
            claimed_customer_id="cust-dispute-adj",
            tenant="TNT-TEST",
            force_new=True,
        )
        from app.modules.cases import CreateCaseIn
        from app.contracts.vocabularies import Severity
        case_in = CreateCaseIn(
            conversation_id=conv["conversation_id"],
            customer_id="cust-dispute-adj",
            category="TRANSACTION_DISPUTE",
            severity_proposed=Severity.HIGH,
            description="Transaksi tidak dikenal Rp500.000",
        )
        c = Store.create_case_db(db, case_in, {"actor_type": "STAFF", "actor_id": "agent-1"}, "CORR-ADJ", "TNT-TEST")
        cid = c["case_id"]

        # CS Agent cannot adjudicate (reserved for complaint_officer / supervisor)
        r_agent = client.post(
            f"/v1/cases/{cid}/adjudicate",
            json={"decision": "UPHELD", "compensation_amount": 500000, "notes": "Disetujui ganti rugi"},
            headers=AGENT_HEADERS,
        )
        assert r_agent.status_code == 403

        # Complaint Officer adjudicates dispute as UPHELD
        res = client.post(
            f"/v1/cases/{cid}/adjudicate",
            json={
                "decision": "UPHELD",
                "compensation_amount": 500000,
                "notes": "Bukti transfer nasabah valid, sengketa diterima penuh.",
                "customer_explanation": "Klaim sanggahan transaksi Anda telah kami terima dan dana sebesar Rp500.000 telah dikreditkan kembali.",
            },
            headers=OFFICER_HEADERS,
        )
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["adjudication_decision"] == "UPHELD"
        assert data["status"] == "RESOLVED"
        assert data["customer_visible_status"] == "RESOLVED"
        assert data["adjudicated_by"] == "officer-1"

        # Verify SLA record is marked as MET
        sla_rec = db.query(models.SlaRecordRow).filter_by(object_id=cid, tenant_id="TNT-TEST").first()
        assert sla_rec is not None
        assert sla_rec.state == "MET"
    finally:
        db.close()
