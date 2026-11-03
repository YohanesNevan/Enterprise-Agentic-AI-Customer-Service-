import time
import uuid
import os

from fastapi.testclient import TestClient
from jose import jwt

from app.main import app
from app.core.db import Base, engine, SessionLocal
from app.modules.models import CaseRow, TicketRow
from app.modules.models_a import ConversationRow
from tests.auth_helpers import auth_headers

client = TestClient(app)

def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

def test_protected_routes_reject_missing_and_invalid_credentials():
    assert client.get("/v1/knowledge/search", params={"q": "x"}).status_code == 401
    assert client.get("/v1/knowledge/search", params={"q": "x"}, headers={"Authorization": "Bearer broken"}).status_code == 401

def test_expired_and_wrong_purpose_tokens_rejected():
    now = int(time.time())
    common = {"sub": "user-1", "iss": "eaics-tests", "aud": "eaics-api", "iat": now-50,
              "exp": now-1, "jti": str(uuid.uuid4()), "tenant_id": "TNT-TEST", "role": "cs_agent", "token_use": "access"}
    expired = jwt.encode(common, "unit-test-signing-key-0123456789abcdef", algorithm="HS256")
    assert client.get("/v1/knowledge/search", params={"q": "x"}, headers={"Authorization": f"Bearer {expired}"}).status_code == 401
    wrong = auth_headers("cs_agent", "user-1", extra={"token_use": "refresh"})
    assert client.get("/v1/knowledge/search", params={"q": "x"}, headers=wrong).status_code == 401

def test_refresh_rotates_once_and_rejects_replay(monkeypatch):
    import redis
    used = set()
    class FakeRedis:
        @classmethod
        def from_url(cls, *args, **kwargs): return cls()
        def set(self, key, value, ex, nx):
            if key in used: return None
            used.add(key); return True
    monkeypatch.setattr(redis.Redis, "from_url", FakeRedis.from_url)
    now = int(time.time())
    claims = {"sub": "staff-1", "iss": os.environ["JWT_ISSUER"], "aud": os.environ["JWT_AUDIENCE"],
              "iat": now, "exp": now + 3600, "jti": uuid.uuid4().hex, "tenant_id": "TNT-TEST",
              "role": "cs_agent", "token_use": "refresh"}
    raw = jwt.encode(claims, os.environ["JWT_SIGNING_KEY"], algorithm="HS256")
    first = client.post("/v1/auth/refresh", headers={"Authorization": f"Bearer {raw}"})
    assert first.status_code == 200
    assert first.json()["expires_in"] == 900
    replay = client.post("/v1/auth/refresh", headers={"Authorization": f"Bearer {raw}"})
    assert replay.status_code == 401

def test_identity_headers_cannot_upgrade_role_or_impersonate_actor():
    headers = {**auth_headers("qa_analyst", "qa-1"), "X-Role": "admin", "X-Actor-Id": "victim"}
    assert client.post("/v1/knowledge/articles", json={"title": "x", "body": "y", "expires_at": "2030-01-01T00:00:00Z"}, headers=headers).status_code == 403
    # The authenticated principal's actor ID, not the header, is recorded on the operation.
    db = SessionLocal()
    db.add(ConversationRow(conversation_id="CNV-X", tenant_id="TNT-TEST"))
    db.commit(); db.close()
    assert client.post("/v1/workspace/queue/enqueue", json={"conversation_id": "CNV-X"}, headers={**auth_headers("cs_agent", "agent-1"), "X-Actor-Id": "victim"}).status_code == 200
    from app.core import audit
    assert audit._store[-1]["actor_id"] == "agent-1"

def test_customer_resource_ownership_and_tenant_checks():
    db = SessionLocal()
    db.add(CaseRow(case_id="case-1", tenant_id="TNT-TEST", customer_id="customer-a", customer_reference="REF-A", category="GENERAL", severity_proposed="LOW"))
    db.add(TicketRow(ticket_id="ticket-1", tenant_id="TNT-TEST", customer_id="customer-a"))
    db.commit(); db.close()
    own = auth_headers("customer", "customer-a")
    other = auth_headers("customer", "customer-b")
    assert client.get("/v1/cases/case-1", headers=own).status_code == 200
    assert client.get("/v1/cases/case-1", headers=other).status_code == 404
    assert client.get("/v1/tickets/ticket-1", headers=other).status_code == 404
    assert client.get("/v1/cases/case-1", headers=auth_headers("customer", "customer-a", tenant="OTHER")).status_code == 404

def test_customer_cannot_read_or_append_to_another_conversation():
    db = SessionLocal()
    db.add(ConversationRow(conversation_id="private-conv", tenant_id="TNT-TEST", customer_id="customer-a"))
    db.commit(); db.close()
    attacker = auth_headers("customer", "customer-b")
    assert client.get("/v1/conversations/private-conv/read-model", headers=attacker).status_code == 404
    assert client.post("/v1/chat/messages", json={"conversation_id": "private-conv", "text": "intrude"}, headers=attacker).status_code == 404

def test_role_policy_knowledge_manager_and_admin_content_separation():
    body = {"title": "Knowledge", "body": "Article", "expires_at": "2030-01-01T00:00:00Z"}
    assert client.post("/v1/knowledge/articles", json=body, headers=auth_headers("knowledge_manager", "km-1")).status_code == 200
    assert client.post("/v1/knowledge/articles", json=body, headers=auth_headers("admin", "admin-1")).status_code == 403
    assert client.get("/v1/conversations/missing/read-model", headers=auth_headers("admin", "admin-1")).status_code == 403

def test_scoped_service_token_and_queue_actor_body_spoofing():
    forged = auth_headers("supervisor", "test-worker", token_use="service", extra=["analytics.read"])
    assert client.get("/internal/outbox-status", headers=forged).status_code == 401
    service = auth_headers("supervisor", "test-worker", token_use="service", extra=[])
    assert client.get("/internal/outbox-status", headers=service).status_code == 403
    broad = auth_headers("supervisor", "test-worker", token_use="service", extra=["sla.read"])
    assert client.get("/internal/outbox-status", headers=broad).status_code == 200
    db = SessionLocal()
    db.add(ConversationRow(conversation_id="CNV-Z", tenant_id="TNT-TEST", status="ACTIVE_AI"))
    db.commit(); db.close()
    enq = client.post("/v1/workspace/queue/enqueue", json={"conversation_id": "CNV-Z"}, headers=auth_headers("cs_agent", "real-agent"))
    accepted = client.post(f"/v1/workspace/handoffs/{enq.json()['handoff_id']}/accept", json={"agent_id": "attacker"}, headers=auth_headers("cs_agent", "real-agent"))
    assert accepted.status_code == 200
    assert accepted.json()["accepted_by"] == "real-agent"

def test_status_route_never_trusts_assurance_header_or_returns_internal_status():
    db = SessionLocal()
    db.add(CaseRow(case_id="case-2", tenant_id="TNT-TEST", customer_id="customer-a", customer_reference="REF-B", category="GENERAL", severity_proposed="LOW", status="INTERNAL_REVIEW", customer_visible_status="BEING_INVESTIGATED"))
    db.commit(); db.close()
    response = client.get("/v1/status/REF-B", headers={"X-Assurance": "AL3"})
    assert response.status_code == 200
    assert response.json() == {"reference": "REF-B", "status": "BEING_INVESTIGATED"}
