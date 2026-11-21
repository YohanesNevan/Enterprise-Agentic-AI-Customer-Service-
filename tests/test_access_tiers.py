"""Four-tier customer access model regression tests.

Tier 1: public information without login (signed guest session).
Tier 2: personal inquiry requires an authenticated customer session.
Tier 3: sensitive request requires OTP step-up and recorded consent.
Tier 4: high-risk action is prepared for a human, never executed by the AI.
"""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.core import audit as audit_svc
from app.core.db import Base, engine
from app.main import app
from app.modules import models, models_a  # noqa: F401 - register all tables
from tests.auth_helpers import auth_headers

c = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield


def _idem():
    return {"Idempotency-Key": uuid.uuid4().hex}


def _guest_post(text, token=None):
    headers = _idem()
    if token:
        headers["X-Guest-Session"] = token
    return c.post("/v1/chat/messages", json={"text": text}, headers=headers)


def test_guest_public_information_without_login_and_signed_session():
    response = _guest_post("Layanan cloud apa saja yang tersedia di NEXORA?")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["authenticated"] is False
    assert body["access_tier"] == 1
    assert body["assurance_level"] == "AL0"
    assert body["conversation_id"]
    token = body["guest_session"]["session_token"]
    assert body["guest_session"]["conversation_id"] == body["conversation_id"]

    rm = c.get(f"/v1/conversations/{body['conversation_id']}/read-model",
               headers={"X-Guest-Session": token})
    assert rm.status_code == 200, rm.text
    assert rm.json()["messages"]

    # Possession of the conversation id alone must not expose the transcript.
    denied = c.get(f"/v1/conversations/{body['conversation_id']}/read-model")
    assert denied.status_code == 401

    assert any(record["action"] == "access.tier_evaluated"
               for record in audit_svc._store), "tier evaluation must be audited"


def test_guest_personal_inquiry_is_escalated_to_login():
    response = _guest_post("Berapa saldo rekening saya?")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["access_tier"] == 2
    assert body["authenticated"] is False
    assert body["verification_required"]["method"] == "SESSION_LOGIN"
    assert body["stepup_required"] == "AL1"
    assert "masuk" in body["reply"].lower()
    assert not any(
        record["action"] == "tool.called"
        and record.get("conversation_id") == body["conversation_id"]
        for record in audit_svc._store
    ), "a guest turn must not execute account tools"


def test_authenticated_personal_inquiry_reaches_account_tool():
    headers = {**auth_headers("customer", "cust-tier2", "TNT-TEST"), **_idem()}
    response = c.post("/v1/chat/messages", json={"text": "Berapa saldo rekening saya?"},
                      headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["authenticated"] is True
    assert body["access_tier"] == 2
    assert not body.get("verification_required")
    assert body.get("stepup_required") in (None, "AL1", "AL2")


def test_sensitive_request_requires_step_up_and_consent(monkeypatch):
    monkeypatch.setenv("TEST_MODE", "true")
    headers = auth_headers("customer", "cust-tier3", "TNT-TEST")
    first = c.post("/v1/chat/messages", json={"text": "Blokir kartu saya 4821"},
                   headers={**headers, **_idem()})
    assert first.status_code == 200, first.text
    body = first.json()
    conv = body["conversation_id"]
    assert body["access_tier"] == 3
    assert body["verification_required"]["method"] == "STEP_UP_OTP"
    assert body["stepup_required"] == "AL2"
    assert "diblokir" not in body["reply"].lower()

    challenge = c.post("/v1/customer/chat/step-up/challenge",
                       json={"conversation_id": conv, "purpose": "SENSITIVE_REQUEST"},
                       headers=headers)
    assert challenge.status_code == 200, challenge.text
    ch = challenge.json()
    assert ch["simulated_delivery"] is True
    assert ch["simulated_code"] == "123456"

    verified = c.post("/v1/customer/chat/step-up/verify",
                      json={"conversation_id": conv, "challenge_id": ch["challenge_id"],
                            "code": ch["simulated_code"]},
                      headers=headers)
    assert verified.status_code == 200, verified.text
    assert verified.json()["verified"] is True
    assert verified.json()["assurance_level"] == "AL2"
    assert verified.json()["expires_at"]

    session = c.get(f"/v1/customer/chat/session?conversation_id={conv}", headers=headers)
    assert session.status_code == 200, session.text
    assert session.json()["assurance_level"] == "AL2"
    assert session.json()["al_expires_at"]
    assert session.json()["session_lock"] == "NONE"

    second = c.post("/v1/chat/messages", json={"text": "Blokir kartu saya 4821",
                                               "conversation_id": conv},
                    headers={**headers, **_idem()})
    assert second.status_code == 200, second.text
    second_body = second.json()
    assert second_body["access_tier"] == 3
    assert second_body["consent_required"]["purpose"] == "SENSITIVE_REQUEST"
    assert "diblokir" not in second_body["reply"].lower()

    consent = c.post("/v1/customer/chat/consent",
                     json={"conversation_id": conv, "purpose": "SENSITIVE_REQUEST",
                           "granted": True, "text_version": "v1"},
                     headers=headers)
    assert consent.status_code == 200, consent.text
    assert consent.json()["granted"] is True

    third = c.post("/v1/chat/messages",
                   json={"text": "Kartu saya hilang, tolong blokir 4821",
                         "conversation_id": conv},
                   headers={**headers, **_idem()})
    assert third.status_code == 200, third.text
    assert "diblokir sementara" in third.json()["reply"].lower()


def test_sensitive_request_without_otp_stays_blocked():
    headers = auth_headers("customer", "cust-tier3-blocked", "TNT-TEST")
    response = c.post("/v1/chat/messages", json={"text": "Blokir kartu saya 4821"},
                      headers={**headers, **_idem()})
    body = response.json()
    assert body["verification_required"]["method"] == "STEP_UP_OTP"
    challenge = c.post("/v1/customer/chat/step-up/challenge",
                       json={"conversation_id": body["conversation_id"],
                             "purpose": "SENSITIVE_REQUEST"}, headers=headers)
    assert challenge.status_code == 200, challenge.text
    wrong = c.post("/v1/customer/chat/step-up/verify",
                   json={"conversation_id": body["conversation_id"],
                         "challenge_id": challenge.json()["challenge_id"], "code": "000000"},
                   headers=headers)
    assert wrong.status_code == 200, wrong.text
    assert wrong.json()["verified"] is False
    assert wrong.json()["attempts_remaining"] == 2


def test_high_risk_action_requires_human_approval_only():
    headers = auth_headers("customer", "cust-tier4", "TNT-TEST")
    response = c.post("/v1/chat/messages",
                      json={"text": "Tolong proses refund untuk transaksi saya"},
                      headers={**headers, **_idem()})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["access_tier"] == 4
    assert body.get("human_approval_required") is True
    assert not body.get("consent_required")
    assert body.get("reason") in ("HUMAN_ACTION_REQUIRED", "MANDATORY_HUMAN_HANDOFF")
    assert body.get("handoff") is True
    assert "setuju" in body["reply"].lower() or "persetujuan" in body["reply"].lower()
    assert "telah diproses" not in body["reply"].lower()


def test_guest_conversation_can_be_claimed_only_with_signed_token():
    guest = _guest_post("Halo, saya ingin bertanya tentang layanan NEXORA")
    body = guest.json()
    conv = body["conversation_id"]
    token = body["guest_session"]["session_token"]
    headers = auth_headers("customer", "cust-claim", "TNT-TEST")

    wrong = c.post("/v1/customer/guest-session/claim",
                   json={"conversation_id": conv, "guest_session_token": "not-a-token"},
                   headers=headers)
    assert wrong.status_code == 404

    claimed = c.post("/v1/customer/guest-session/claim",
                     json={"conversation_id": conv, "guest_session_token": token},
                     headers=headers)
    assert claimed.status_code == 200, claimed.text
    assert claimed.json()["claimed"] is True

    # The signed-in customer can continue the claimed conversation.
    follow_up = c.post("/v1/chat/messages", json={"text": "Terima kasih",
                                                  "conversation_id": conv},
                       headers={**headers, **_idem()})
    assert follow_up.status_code == 200, follow_up.text

    # The anonymous token no longer grants access after the claim.
    replay = c.post("/v1/chat/messages",
                    json={"text": "Halo lagi", "conversation_id": conv},
                    headers={**_idem(), "X-Guest-Session": token})
    assert replay.status_code == 404
