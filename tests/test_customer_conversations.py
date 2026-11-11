import os
import time
import uuid

from fastapi.testclient import TestClient

from app.main import app
from app.core.db import Base, engine, SessionLocal
from app.modules.models_a import ConversationRow, MessageRow
from tests.auth_helpers import auth_headers

client = TestClient(app)


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def test_dev_customer_login_issues_fixed_customer_access_token(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("DEV_CUSTOMER_AUTH_ENABLED", "true")
    monkeypatch.setenv("DEV_CUSTOMER_USERNAME", "local-customer")
    monkeypatch.setenv("DEV_CUSTOMER_PASSWORD", "test-only-password-longer-than-20")
    monkeypatch.setenv("DEV_CUSTOMER_ID", "dev-customer-1")
    monkeypatch.setenv("DEV_TENANT_ID", "TNT-DEV")
    response = client.post("/v1/dev-auth/customer/login", json={
        "username": "local-customer", "password": "test-only-password-longer-than-20",
        "role": "admin", "actor_id": "other-user", "tenant_id": "OTHER",
    })
    assert response.status_code == 200, response.text
    assert response.json()["principal"] == {"actor_id": "dev-customer-1", "role": "customer", "tenant_id": "TNT-DEV"}
    token = response.json()["access_token"]
    assert client.get("/v1/customer/conversations", headers={"Authorization": f"Bearer {token}"}).status_code == 200
    created = client.post("/v1/chat/messages", json={"text": "Saya ditipu dan dipaksa transfer sekarang"},
                          headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "devlogin-1234567890123"})
    assert created.status_code == 200, created.text
    assert created.json().get("conversation_id")
    own_history = client.get("/v1/customer/conversations", headers={"Authorization": f"Bearer {token}"})
    assert created.json()["conversation_id"] in [item["conversation_id"] for item in own_history.json()["items"]]
    invalid = client.post("/v1/dev-auth/customer/login", json={"username": "local-customer", "password": "wrong"})
    assert invalid.status_code == 401


def test_dev_customer_login_disabled_without_explicit_flag(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("DEV_CUSTOMER_AUTH_ENABLED", raising=False)
    response = client.post("/v1/dev-auth/customer/login", json={"username": "x", "password": "x"})
    assert response.status_code == 503


def test_dev_customer_login_supports_an_additional_server_allowlisted_account(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("DEV_CUSTOMER_AUTH_ENABLED", "true")
    monkeypatch.setenv("DEV_CUSTOMER_ACCOUNTS", '{"efrant":{"actor_id":"customer-efrant-001","tenant_id":"TNT-DEV","password":"efrant-test-password-longer-than-20"}}')
    response = client.post("/v1/dev-auth/customer/login", json={
        "username": "efrant", "password": "efrant-test-password-longer-than-20",
        "role": "admin", "actor_id": "forged", "tenant_id": "OTHER",
    })
    assert response.status_code == 200, response.text
    assert response.json()["principal"] == {
        "actor_id": "customer-efrant-001", "role": "customer", "tenant_id": "TNT-DEV"}
    invalid = client.post("/v1/dev-auth/customer/login", json={
        "username": "efrant", "password": "wrong-password-longer-than-20"})
    assert invalid.status_code == 401


def test_dev_customer_auth_configuration_rejects_production():
    from app.core.dev_auth import validate_dev_customer_auth_config
    import pytest
    with pytest.raises(RuntimeError, match="only when ENVIRONMENT=development"):
        validate_dev_customer_auth_config("production", "true")
    with pytest.raises(RuntimeError, match="only when ENVIRONMENT=development"):
        validate_dev_customer_auth_config("production", "false", "true")


def test_dev_auth_trusts_only_loopback_or_configured_exact_client(monkeypatch):
    from app.core.dev_auth import dev_auth_client_allowed
    monkeypatch.setenv("DEV_AUTH_TRUSTED_CLIENTS", "172.18.0.1")
    assert dev_auth_client_allowed("127.0.0.1")
    assert dev_auth_client_allowed("::1")
    assert dev_auth_client_allowed("172.18.0.1")
    assert not dev_auth_client_allowed("172.18.0.2")
    assert not dev_auth_client_allowed("192.168.1.10")
    assert not dev_auth_client_allowed(None)


def test_dev_staff_login_uses_server_allowlist_and_role_permissions(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("DEV_STAFF_AUTH_ENABLED", "true")
    monkeypatch.setenv("DEV_STAFF_ACCOUNTS", '{"management-local":{"actor_id":"mgr-local","tenant_id":"TNT-DEV","role":"management","password":"staff-test-password-more-than-20"}}')
    response = client.post("/v1/dev-auth/staff/login", json={
        "username": "management-local", "password": "staff-test-password-more-than-20",
        "role": "admin", "actor_id": "forged", "tenant_id": "OTHER",
    })
    assert response.status_code == 200, response.text
    assert response.json()["principal"] == {"actor_id": "mgr-local", "role": "management", "tenant_id": "TNT-DEV"}
    token = response.json()["access_token"]
    assert client.get("/v1/conversations/not-readable/read-model", headers={"Authorization": f"Bearer {token}"}).status_code == 403
    assert client.post("/v1/dev-auth/staff/login", json={"username": "management-local", "password": "incorrect"}).status_code == 401


def test_dev_staff_login_rejects_customer_and_ai_roles_in_allowlist(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("DEV_STAFF_AUTH_ENABLED", "true")
    for role in ("customer", "ai_agent"):
        monkeypatch.setenv("DEV_STAFF_ACCOUNTS", '{"bad":{"actor_id":"bad","tenant_id":"TNT-DEV","role":"' + role + '","password":"staff-test-password-more-than-20"}}')
        response = client.post("/v1/dev-auth/staff/login", json={"username": "bad", "password": "staff-test-password-more-than-20"})
        assert response.status_code == 503


def test_customer_chat_persists_and_replays_idempotently():
    headers = {**auth_headers("customer", "customer-a", "TNT-TEST"), "Idempotency-Key": "turn-123456789012345"}
    body = {"text": "Saya ditipu dan dipaksa transfer sekarang"}
    first = client.post("/v1/chat/messages", json=body, headers=headers)
    assert first.status_code == 200, first.text
    result = first.json()
    assert result["conversation_id"]
    assert result.get("handoff") is True
    replay = client.post("/v1/chat/messages", json=body, headers=headers)
    assert replay.status_code == 200
    assert replay.json() == result
    db = SessionLocal()
    try:
        assert db.query(MessageRow).select_from(MessageRow).join(ConversationRow, MessageRow.conversation_id == ConversationRow.conversation_id).filter(
            ConversationRow.conversation_id == result["conversation_id"], MessageRow.direction == "INBOUND").count() == 1
    finally:
        db.close()


def test_customer_idempotency_rejects_changed_content_and_validates_channel():
    h = {**auth_headers("customer", "customer-a"), "Idempotency-Key": "turn-123456789012345"}
    assert client.post("/v1/chat/messages", json={"text": "help"}, headers=h).status_code == 200
    changed = client.post("/v1/chat/messages", json={"text": "different"}, headers=h)
    assert changed.status_code == 409
    bad_channel = client.post("/v1/chat/messages", json={"text": "help", "channel": "EMAIL"},
                               headers={**auth_headers("customer", "customer-b"), "Idempotency-Key": "turn-223456789012345"})
    assert bad_channel.status_code == 400
    assert client.post("/v1/chat/messages", json={"text": "help"}, headers=auth_headers("customer", "customer-c")).status_code == 400
    invalid_text = client.post("/v1/chat/messages", json={"text": " "}, headers={**auth_headers("customer", "customer-d"), "Idempotency-Key": "turn-523456789012345"})
    too_long = client.post("/v1/chat/messages", json={"text": "x" * 4001}, headers={**auth_headers("customer", "customer-e"), "Idempotency-Key": "turn-623456789012345"})
    assert invalid_text.status_code == 400 and too_long.status_code == 400


def test_customer_history_and_detail_enforce_owner_and_tenant():
    headers = {**auth_headers("customer", "customer-a", "TNT-TEST"), "Idempotency-Key": "turn-323456789012345"}
    sent = client.post("/v1/chat/messages", json={"text": "Saya ditipu dan dipaksa transfer sekarang"}, headers=headers)
    conv_id = sent.json()["conversation_id"]
    listing = client.get("/v1/customer/conversations", headers=auth_headers("customer", "customer-a", "TNT-TEST"))
    assert listing.status_code == 200
    assert [row["conversation_id"] for row in listing.json()["items"]] == [conv_id]
    own = client.get(f"/v1/conversations/{conv_id}/read-model", headers=auth_headers("customer", "customer-a", "TNT-TEST"))
    assert own.status_code == 200
    assert all("tool_call_ids" not in item and "author_id" not in item for item in own.json()["messages"])
    assert client.get(f"/v1/conversations/{conv_id}/read-model", headers=auth_headers("customer", "customer-b", "TNT-TEST")).status_code == 404
    assert client.get(f"/v1/conversations/{conv_id}/read-model", headers=auth_headers("customer", "customer-a", "OTHER")).status_code == 404
    assert client.get("/v1/customer/conversations", headers=auth_headers("cs_agent", "agent-1")).status_code == 403


def test_customer_message_history_uses_bounded_keyset_cursor():
    db = SessionLocal()
    db.add(ConversationRow(conversation_id="paged-conversation", tenant_id="TNT-TEST", customer_id="customer-page"))
    db.flush()
    for index in range(3):
        db.add(MessageRow(message_id=f"page-message-{index}", conversation_id="paged-conversation",
                          sequence_no=index, content=f"message {index}", occurred_at=__import__("datetime").datetime.now()))
    db.commit(); db.close()
    headers = auth_headers("customer", "customer-page", "TNT-TEST")
    first = client.get("/v1/conversations/paged-conversation/read-model?limit=2", headers=headers)
    assert first.status_code == 200
    assert [m["content"] for m in first.json()["messages"]] == ["message 0", "message 1"]
    next_page = client.get(f"/v1/conversations/paged-conversation/read-model?limit=2&cursor={first.json()['next_cursor']}", headers=headers)
    assert [m["content"] for m in next_page.json()["messages"]] == ["message 2"]
    invalid = client.get("/v1/conversations/paged-conversation/read-model?cursor=bad-cursor", headers=headers)
    assert invalid.status_code == 400


def test_customer_provider_replay_collision_does_not_disclose_conversation():
    db = SessionLocal()
    db.add(ConversationRow(conversation_id="private-replay", tenant_id="TENANT-PRIVATE", customer_id="customer-a"))
    db.add(MessageRow(message_id="private-message", conversation_id="private-replay", channel="WEB_CHAT",
                      sequence_no=0, provider_message_id="provider-collision", content="private"))
    db.commit(); db.close()
    response = client.post("/v1/channels/WEB_CHAT/inbound", json={"text": "hello", "provider_message_id": "provider-collision"},
                           headers=auth_headers("cs_agent", "agent-1", "TNT-TEST"))
    assert response.status_code == 409
    assert "private-replay" not in response.text


def test_customer_cannot_bypass_chat_idempotency_through_channel_adapter():
    response = client.post("/v1/channels/EMAIL/inbound", json={"text": "hello", "claimed_customer_id": "victim"},
                           headers=auth_headers("customer", "customer-a"))
    assert response.status_code == 403


def test_customer_continuity_does_not_cross_tenant():
    db = SessionLocal()
    db.add(ConversationRow(conversation_id="tenant-private", tenant_id="TENANT-A", customer_id="same-customer", status="ACTIVE_AI"))
    db.commit(); db.close()
    headers = {**auth_headers("customer", "same-customer", "TENANT-B"), "Idempotency-Key": "turn-423456789012345"}
    response = client.post("/v1/chat/messages", json={"text": "Saya ditipu dan dipaksa transfer sekarang"}, headers=headers)
    assert response.status_code == 200
    assert response.json()["conversation_id"] != "tenant-private"


def test_degraded_chat_does_not_claim_ticket_or_handoff_success(monkeypatch):
    from app.modules import orchestrator as Orc
    from app.modules.models import HandoffRow, TicketRow
    from app.modules.models_a import MessageRow

    monkeypatch.setitem(Orc.DEGRADED, "value", True)
    response = client.post("/v1/chat/messages", json={"from_handle": "degraded-user",
        "text": "Saya perlu bantuan", "channel": "WEB_CHAT"},
        headers=auth_headers("ai_agent", "orchestrator"))

    assert response.status_code == 200, response.text
    result = response.json()
    assert result["mode"] == "DEGRADED"
    assert result["handoff"] is False
    assert result["handoff_status"] == "NOT_ATTEMPTED"
    assert result["reply"] == (
        "Bantuan otomatis sedang terbatas. Permintaan ini belum dapat diproses. "
        "Saya belum dapat mengonfirmasi status tiket atau antrean petugas."
    )
    assert "ticket_id" not in result
    assert "petugas akan" not in result["reply"].lower()

    db = SessionLocal()
    try:
        outbound = db.query(MessageRow).filter_by(conversation_id=result["conversation_id"],
                                                   direction="OUTBOUND").one()
        assert outbound.content == result["reply"]
        assert db.query(TicketRow).filter_by(conversation_id=result["conversation_id"]).count() == 0
        assert db.query(HandoffRow).filter_by(conversation_id=result["conversation_id"]).count() == 0
    finally:
        db.close()


def test_action_fallback_requires_matching_success_evidence():
    from app.modules.orchestrator import _compose_action_answer

    card = {"intent_code": "REQ_CARD_BLOCK"}
    assert "telah diblokir sementara" in _compose_action_answer(
        card, [{"status": "TEMP_BLOCKED"}], "conversation")
    failed_card = _compose_action_answer(card, [{"status": "FAILED"}], "conversation")
    assert "belum dapat mengonfirmasi" in failed_card
    assert "tiket" not in failed_card.lower()

    statement = {"intent_code": "REQ_STATEMENT_DOCUMENT"}
    assert "telah dikirim" in _compose_action_answer(statement, [{"sent": True}], "conversation")
    failed_statement = _compose_action_answer(statement, [{"sent": False}], "conversation")
    assert "belum dapat mengonfirmasi" in failed_statement


def test_handoff_copy_distinguishes_queued_from_agent_acceptance():
    from app.modules.orchestrator import _handoff_reply

    queued = _handoff_reply("QUEUED")
    assert "masuk antrean" in queued
    assert "belum mengonfirmasi penerimaan" in queued
    accepted = _handoff_reply("ACCEPTED")
    assert "telah menerima" in accepted
    assert "masuk antrean" not in accepted


def test_customer_chat_force_new_creates_distinct_conversation():
    headers_base = auth_headers("customer", "customer-new-1")
    first = client.post(
        "/v1/chat/messages",
        json={"text": "halo"},
        headers={**headers_base, "Idempotency-Key": "force-new-test-key-0001"},
    )
    assert first.status_code == 200, first.text
    cid1 = first.json()["conversation_id"]

    # Without force_new, 72h continuity reuses cid1
    reused = client.post(
        "/v1/chat/messages",
        json={"text": "halo lagi"},
        headers={**headers_base, "Idempotency-Key": "force-new-test-key-0002"},
    )
    assert reused.status_code == 200, reused.text
    assert reused.json()["conversation_id"] == cid1

    # With force_new=True, creates a distinct conversation
    fresh = client.post(
        "/v1/chat/messages",
        json={"text": "Saya ingin berbicara dengan petugas", "force_new": True},
        headers={**headers_base, "Idempotency-Key": "force-new-test-key-0003"},
    )
    assert fresh.status_code == 200, fresh.text
    cid2 = fresh.json()["conversation_id"]
    assert cid2 != cid1
    assert fresh.json().get("handoff") is True
    assert fresh.json().get("handoff_status") == "QUEUED"
