"""Unit 06: Test Customer Complaint and Ticket Ownership APIs."""
import pytest
from app.core.db import Base, engine, SessionLocal
from app.modules import models, models_a  # noqa: F401
from app.modules.cases import CreateTicketIn
from app.modules.store import create_ticket_db
from app.modules.conversation import ingest


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield


def test_customer_can_create_complaint_ticket():
    db = SessionLocal()
    try:
        conv = ingest(
            db,
            channel="WEB_CHAT",
            from_handle="customer-test-user",
            text="Saya ingin mengajukan komplain resmi transaksi gagal tapi saldo terpotong",
            claimed_customer_id="customer-test-user",
            tenant="TNT-TEST",
        )
        conv_id = conv["conversation_id"]

        ticket_in = CreateTicketIn(
            conversation_id=conv_id,
            customer_id="customer-test-user",
            type="TRANSACTION_DISPUTE",
            sub_type="TRX-12345",
            priority="HIGH",
            description="Debit ganda di minimarket, saldo terpotong dua kali.",
            source_channel="WEB_CHAT",
        )
        ctx = {
            "actor_type": "CUSTOMER",
            "actor_id": "customer-test-user",
            "role": "customer",
            "tenant_id": "TNT-TEST",
        }

        created = create_ticket_db(db, ticket_in, ctx, "CORR-TEST-COMPLAINT-1", tenant="TNT-TEST")
        assert created is not None
        assert "ticket_id" in created
        assert "customer_reference" in created
        assert created["status"] == "OPEN"
        assert "sla" in created
        assert created["sla"]["first_response_due_at"] is not None

        # Verify query isolation by customer_id
        tickets = db.query(models.TicketRow).filter_by(
            tenant_id="TNT-TEST", customer_id="customer-test-user"
        ).all()
        assert len(tickets) >= 1
        assert created["ticket_id"] in [t.ticket_id for t in tickets]
        assert all(t.customer_id == "customer-test-user" for t in tickets)
    finally:
        db.close()


def test_customer_ticket_tenant_and_cross_customer_isolation():
    db = SessionLocal()
    try:
        conv_a = ingest(db, "WEB_CHAT", "customer-A", "Komplain A", claimed_customer_id="customer-A", tenant="TNT-TEST")
        conv_b = ingest(db, "WEB_CHAT", "customer-B", "Komplain B", claimed_customer_id="customer-B", tenant="TNT-TEST")

        t_in_a = CreateTicketIn(
            conversation_id=conv_a["conversation_id"],
            customer_id="customer-A",
            type="CARD_ISSUE",
            description="Kartu tertelan",
            source_channel="WEB_CHAT",
        )
        t_in_b = CreateTicketIn(
            conversation_id=conv_b["conversation_id"],
            customer_id="customer-B",
            type="BILLING_ISSUE",
            description="Tagihan tidak sesuai",
            source_channel="WEB_CHAT",
        )

        ctx_a = {"actor_type": "CUSTOMER", "actor_id": "customer-A", "tenant_id": "TNT-TEST"}
        ctx_b = {"actor_type": "CUSTOMER", "actor_id": "customer-B", "tenant_id": "TNT-TEST"}

        res_a = create_ticket_db(db, t_in_a, ctx_a, "CORR-A", tenant="TNT-TEST")
        res_b = create_ticket_db(db, t_in_b, ctx_b, "CORR-B", tenant="TNT-TEST")

        # Customer A list must contain ONLY A's tickets
        tickets_a = db.query(models.TicketRow).filter_by(tenant_id="TNT-TEST", customer_id="customer-A").all()
        ids_a = [t.ticket_id for t in tickets_a]
        assert res_a["ticket_id"] in ids_a
        assert res_b["ticket_id"] not in ids_a

        # Customer B list must contain ONLY B's tickets
        tickets_b = db.query(models.TicketRow).filter_by(tenant_id="TNT-TEST", customer_id="customer-B").all()
        ids_b = [t.ticket_id for t in tickets_b]
        assert res_b["ticket_id"] in ids_b
        assert res_a["ticket_id"] not in ids_b
    finally:
        db.close()
