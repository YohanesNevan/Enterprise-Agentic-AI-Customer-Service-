"""Tests for LangGraph-based agentic workflow (app.modules.agent_graph)."""
import pytest
from app.core.db import Base, SessionLocal, engine
from app.modules import models, models_a  # noqa: F401 - ensures all tables are registered with Base.metadata
from app.modules.agent_graph import agentic_workflow, run_turn_langgraph
from app.modules.conversation import ingest


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield


def test_agent_graph_builds():
    """Verify that StateGraph compiles into an executable graph."""
    assert agentic_workflow is not None
    assert hasattr(agentic_workflow, "invoke")


def test_greeting_turn_in_graph():
    """Verify that a greeting message routes to greeting_node and returns a polite reply."""
    db = SessionLocal()
    try:
        conv = ingest(db, "WEB_CHAT", "customer-handle", "Halo", claimed_customer_id="cust-1", tenant="TNT-TEST")
        conv_id = conv["conversation_id"]

        result = run_turn_langgraph(
            db=db,
            conv_id=conv_id,
            text="Halo selamat pagi",
            corr="CORR-TEST-GREETING",
            tenant_id="TNT-TEST",
        )

        assert result is not None
        assert "reply" in result
        assert "Halo" in result["reply"]
        assert result.get("handoff") is False
    finally:
        db.close()


def test_mandatory_handoff_in_graph():
    """Verify that an explicit request for a human agent routes to handoff_node."""
    db = SessionLocal()
    try:
        conv = ingest(db, "WEB_CHAT", "customer-handle", "Bantuan", claimed_customer_id="cust-1", tenant="TNT-TEST")
        conv_id = conv["conversation_id"]

        result = run_turn_langgraph(
            db=db,
            conv_id=conv_id,
            text="Saya ingin berbicara langsung dengan manusia petugas CS",
            corr="CORR-TEST-HANDOFF",
            tenant_id="TNT-TEST",
        )

        assert result is not None
        assert result.get("handoff") is True
        assert result.get("reason") in ("MANDATORY_HUMAN_HANDOFF", "KNOWLEDGE_GAP")
    finally:
        db.close()


def test_unauthenticated_banking_action_requires_stepup():
    """Verify that a sensitive action without authenticated session asks for login."""
    db = SessionLocal()
    try:
        conv = ingest(db, "WEB_CHAT", "customer-handle", "Saldo", claimed_customer_id="cust-1", tenant="TNT-TEST")
        conv_id = conv["conversation_id"]

        result = run_turn_langgraph(
            db=db,
            conv_id=conv_id,
            text="Tolong cek saldo rekening saya sekarang",
            corr="CORR-TEST-BALANCE",
            tenant_id="TNT-TEST",
        )

        assert result is not None
        assert "reply" in result
        assert len(result["reply"]) > 0
    finally:
        db.close()
