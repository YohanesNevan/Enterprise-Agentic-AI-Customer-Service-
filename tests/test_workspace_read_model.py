"""Unit 08: Test Agent Workspace Read Model and Queue with Handoff Context Package."""
import os
os.environ["DATABASE_URL"] = "sqlite:///./eaics_test_q.db"
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.db import Base, engine, SessionLocal
from app.modules import models, models_a
from app.modules.conversation import ingest
from app.modules import queue as QueueSvc
from tests.auth_helpers import auth_headers

client = TestClient(app)

STAFF_HEADERS = auth_headers("cs_agent", "agent-1")
SUPERVISOR_HEADERS = auth_headers("supervisor", "spv-1")
CUSTOMER_HEADERS = auth_headers("customer", "customer-dev-001")


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield


def test_workspace_read_model_access_control():
    # 1. Unauthenticated request is rejected
    r_unauth = client.get("/v1/workspace/conversations/CNV-TEST-NONEXIST")
    assert r_unauth.status_code in (401, 403)

    # 2. Customer role is forbidden from accessing agent workspace
    r_customer = client.get("/v1/workspace/conversations/CNV-TEST-NONEXIST", headers=CUSTOMER_HEADERS)
    assert r_customer.status_code == 403


def test_workspace_read_model_includes_handoff_package():
    db = SessionLocal()
    try:
        conv = ingest(
            db,
            channel="WEB_CHAT",
            from_handle="customer-test-user",
            text="Saya ingin kartu saya diblokir karena hilang",
            claimed_customer_id="customer-test-user",
            tenant="TNT-TEST",
        )
        conv_id = conv["conversation_id"]

        # Enqueue handoff
        QueueSvc.enqueue(
            db,
            conversation_id=conv_id,
            reason_code="CUSTOMER_REQUEST",
            ctx={"tenant_id": "TNT-TEST", "actor_type": "CUSTOMER", "actor_id": "customer-test-user"},
            corr="CORR-U08-TEST",
            severity="HIGH",
            package_complete=True,
        )

        # Staff reads conversation read model
        res = client.get(f"/v1/workspace/conversations/{conv_id}", headers=STAFF_HEADERS)
        assert res.status_code == 200, res.text
        data = res.json()

        assert "conversation_id" in data
        assert data["conversation_id"] == conv_id
        assert "handoff_package" in data

        pkg = data["handoff_package"]
        assert pkg["customer_id"] == "customer-test-user"
        assert "summary" in pkg
        assert "Saya ingin kartu saya diblokir karena hilang" in pkg["summary"]
        assert "intent_code" in pkg
        assert "urgency" in pkg
        assert "sentiment" in pkg
        assert "tools_called" in pkg
        assert "recommended_action" in pkg
        assert pkg["package_complete"] is True
    finally:
        db.close()


def test_workspace_queue_enriched_items():
    db = SessionLocal()
    try:
        conv = ingest(
            db,
            channel="WEB_CHAT",
            from_handle="customer-test-queue",
            text="Tolong cek status pembayaran saya yang belum masuk",
            claimed_customer_id="customer-test-queue",
            tenant="TNT-TEST",
        )
        conv_id = conv["conversation_id"]

        QueueSvc.enqueue(
            db,
            conversation_id=conv_id,
            reason_code="CMP_TRANSACTION_DISPUTE",
            ctx={"tenant_id": "TNT-TEST", "actor_type": "CUSTOMER", "actor_id": "customer-test-queue"},
            corr="CORR-U08-QUEUE",
            severity="MEDIUM",
            package_complete=True,
            queue_id="Q-GENERAL",
        )

        res = client.get("/v1/workspace/queue", headers=STAFF_HEADERS)
        assert res.status_code == 200, res.text
        items = res.json().get("items", [])
        assert len(items) >= 1

        matched = next((it for it in items if it["conversation_id"] == conv_id), None)
        assert matched is not None
        assert matched["package_complete"] is True
        assert "summary_snippet" in matched
        assert "status pembayaran" in matched["summary_snippet"]
        assert "priority_score" in matched
        assert "wait_s" in matched
    finally:
        db.close()
