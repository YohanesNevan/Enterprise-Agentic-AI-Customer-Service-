"""End-to-end RAG regression tests: authenticated upload -> retrieval -> chat response."""
import uuid
from fastapi.testclient import TestClient

from app.main import app
from app.core.db import Base, engine, SessionLocal
from app.modules.models_a import KnowledgeDocumentRow
from tests.auth_helpers import auth_headers

client = TestClient(app)


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


class GroundedFakeProvider:
    """Deterministic F4 provider that echoes one retrieved source as grounded text."""
    def __init__(self):
        self.calls = []

    def generate(self, function, payload, *, timeout_ms=None):
        self.calls.append((function.value, payload))
        source = payload.sources[0]
        return {"text": source.text,
                "claim_map": [{"claim": source.text, "source_ids": [source.source_id]}]}


def _upload(text, tenant="TNT-TEST", filename="knowledge.txt"):
    return client.post("/v1/knowledge/documents/upload",
                       files={"file": (filename, text.encode("utf-8"), "text/plain")},
                       headers=auth_headers("cs_agent", "staff-rag", tenant))


def _answer_with_source(monkeypatch, text, tenant="TNT-TEST"):
    from app.modules import llm_provider
    provider = GroundedFakeProvider()
    monkeypatch.setattr(llm_provider, "build_provider", lambda *args, **kwargs: provider)
    response = client.post("/v1/chat/messages", json={"text": text},
                           headers={**auth_headers("customer", "customer-rag", tenant),
                                    "Idempotency-Key": uuid.uuid4().hex})
    return response, provider


def test_a_customer_question_uses_uploaded_npb_knowledge_and_returns_citation(monkeypatch):
    content = "NPB adalah Nusantara Prima Bank. NPB merupakan lingkungan sintetis untuk MVP akademik."
    uploaded = _upload(content)
    assert uploaded.status_code == 200 and uploaded.json()["status"] == "ready"
    response, provider = _answer_with_source(monkeypatch, "Apa itu NPB?")
    assert response.status_code == 200, response.text
    result = response.json()
    assert "Nusantara Prima Bank" in result["reply"]
    assert result["citations"][0]["document_id"] == uploaded.json()["document_id"]
    assert provider.calls[0][0] == "F4"
    assert provider.calls[0][1].question == "Apa itu NPB?"
    history = client.get(f"/v1/conversations/{result['conversation_id']}/read-model",
                         headers=auth_headers("customer", "customer-rag", "TNT-TEST"))
    assert any("Nusantara Prima Bank" in message["content"] and message["citations"]
               for message in history.json()["messages"] if message["direction"] == "OUTBOUND")


def test_b_failed_transfer_advice_is_grounded_and_does_not_promise_refund(monkeypatch):
    content = "Jika transfer gagal, periksa status transaksi dan simpan bukti. Hubungi petugas bila dana terdebit; pengembalian dana tidak dijamin otomatis."
    assert _upload(content, filename="transaction.txt").json()["status"] == "ready"
    response, _ = _answer_with_source(monkeypatch, "Apa yang harus saya lakukan jika transfer saya gagal?")
    assert response.status_code == 200
    assert "tidak dijamin otomatis" in response.json()["reply"]
    assert "pasti kembali" not in response.json()["reply"].casefold()
    assert response.json()["citations"]


def test_refund_policy_question_remains_grounded_on_repeated_and_fresh_turns(monkeypatch):
    policy = ("Jika transaksi gagal, jangan menjanjikan bahwa dana pasti kembali. Jangan menjanjikan refund, "
              "pengembalian dana, atau hasil investigasi tertentu.")
    assert _upload(policy, filename="refund-policy.txt").json()["status"] == "ready"
    from app.modules import llm_provider
    provider = GroundedFakeProvider()
    monkeypatch.setattr(llm_provider, "build_provider", lambda *args, **kwargs: provider)
    question = "Apakah saya pasti mendapatkan refund jika transaksi gagal?"
    headers = auth_headers("customer", "customer-refund-repeat", "TNT-TEST")
    first = client.post("/v1/chat/messages", json={"text": question},
                        headers={**headers, "Idempotency-Key": uuid.uuid4().hex})
    assert first.status_code == 200, first.text
    first_body = first.json()
    assert first_body["intent"]["intent_code"] == "INFO_PRODUCT_POLICY"
    assert first_body["intent"]["decision"] == "ACT"
    assert first_body.get("handoff") is not True
    assert first_body["reply"] == policy and first_body["citations"]

    repeated = client.post("/v1/chat/messages",
                           json={"text": question, "conversation_id": first_body["conversation_id"]},
                           headers={**headers, "Idempotency-Key": uuid.uuid4().hex})
    assert repeated.status_code == 200, repeated.text
    repeated_body = repeated.json()
    assert repeated_body["intent"]["intent_code"] == first_body["intent"]["intent_code"]
    assert repeated_body["intent"]["decision"] == first_body["intent"]["decision"]
    assert repeated_body.get("handoff") is not True
    assert repeated_body["reply"] == first_body["reply"]
    assert repeated_body["citations"] == first_body["citations"]

    third = client.post("/v1/chat/messages",
                        json={"text": question, "conversation_id": first_body["conversation_id"]},
                        headers={**headers, "Idempotency-Key": uuid.uuid4().hex})
    assert third.status_code == 200, third.text
    assert third.json().get("handoff") is not True
    assert third.json()["reply"] == first_body["reply"]

    fresh = client.post("/v1/chat/messages", json={"text": question},
                        headers={**auth_headers("customer", "customer-refund-fresh", "TNT-TEST"),
                                 "Idempotency-Key": uuid.uuid4().hex})
    assert fresh.status_code == 200, fresh.text
    assert fresh.json()["reply"] == first_body["reply"]
    assert fresh.json()["intent"]["decision"] == first_body["intent"]["decision"]

    eligibility = client.post("/v1/chat/messages", json={"text": "Apakah saya bisa minta refund jika transfer gagal?"},
                              headers={**auth_headers("customer", "customer-refund-eligibility", "TNT-TEST"),
                                       "Idempotency-Key": uuid.uuid4().hex})
    assert eligibility.status_code == 200
    assert eligibility.json().get("handoff") is not True
    assert eligibility.json()["citations"]


def test_short_followup_uses_previous_customer_question_as_retrieval_context(monkeypatch):
    policy = "Pengembalian dana tidak dijamin otomatis jika transaksi gagal."
    assert _upload(policy, filename="followup-policy.txt").json()["status"] == "ready"
    from app.modules import llm_provider
    provider = GroundedFakeProvider()
    monkeypatch.setattr(llm_provider, "build_provider", lambda *args, **kwargs: provider)
    headers = auth_headers("customer", "customer-refund-followup", "TNT-TEST")
    first = client.post("/v1/chat/messages", json={"text": "Apakah refund pasti jika transaksi gagal?"},
                        headers={**headers, "Idempotency-Key": uuid.uuid4().hex})
    assert first.status_code == 200, first.text
    followup = client.post("/v1/chat/messages", json={"text": "Mengapa?", "conversation_id": first.json()["conversation_id"]},
                           headers={**headers, "Idempotency-Key": uuid.uuid4().hex})
    assert followup.status_code == 200, followup.text
    body = followup.json()
    assert body["intent"]["intent_code"] == "INFO_PRODUCT_POLICY"
    assert body.get("handoff") is not True
    assert body["citations"]
    assert "Pengembalian dana tidak dijamin otomatis" in body["reply"]
    assert "Mengapa?" in provider.calls[-1][1].question
    assert "Apakah refund pasti jika transaksi gagal?" in provider.calls[-1][1].question


def test_explicit_refund_execution_request_hands_off_with_action_reason():
    response = client.post("/v1/chat/messages", json={"text": "Tolong proses refund transaksi saya sekarang."},
                           headers={**auth_headers("customer", "customer-refund-action", "TNT-TEST"),
                                    "Idempotency-Key": uuid.uuid4().hex})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["intent"]["intent_code"] == "CMP_TRANSACTION_DISPUTE"
    assert body["intent"]["handoff_reason"] == "HUMAN_ACTION_REQUIRED"
    assert body["handoff_status"] in {"QUEUED", "OFFERED", "ACCEPTED"}


def test_explicit_unresolved_repeat_contact_still_hands_off():
    response = client.post("/v1/chat/messages", json={"text": "Saya sudah menghubungi berkali-kali dan masih belum dibantu."},
                           headers={**auth_headers("customer", "customer-repeat-contact", "TNT-TEST"),
                                    "Idempotency-Key": uuid.uuid4().hex})
    assert response.status_code == 200, response.text
    assert response.json()["intent"]["handoff_reason"] == "REPEAT_CONTACT"
    assert response.json()["handoff_status"] in {"QUEUED", "OFFERED", "ACCEPTED"}


def test_c_and_d_unsupported_fee_and_phone_number_do_not_invent_facts():
    for question in ("Berapa biaya transfer internasional di NPB?",
                     "Berapa nomor telepon Customer Service NPB?"):
        response = client.post("/v1/chat/messages", json={"text": question},
                                   headers={**auth_headers("customer", "customer-rag", "TNT-TEST"),
                                            "Idempotency-Key": uuid.uuid4().hex})
        assert response.status_code == 200
        body = response.json()
        assert body.get("reason") == "KNOWLEDGE_GAP"
        assert not body.get("citations")
        assert "25000" not in body["reply"] and "25.000" not in body["reply"]
        assert not any(len(token) >= 8 and token.isdigit() for token in body["reply"].split())


def test_e_otp_question_uses_uploaded_security_rule(monkeypatch):
    content = "Jangan pernah memberikan OTP kepada chatbot atau siapa pun. OTP hanya digunakan sendiri pada kanal verifikasi resmi."
    assert _upload(content, filename="security.txt").json()["status"] == "ready"
    response, _ = _answer_with_source(monkeypatch, "Bolehkah saya memberikan OTP kepada chatbot?")
    assert response.status_code == 200
    assert "Jangan pernah memberikan OTP" in response.json()["reply"]
    assert "otp" not in response.json()["reply"].casefold() or "jangan" in response.json()["reply"].casefold()


def test_relevant_sources_with_unavailable_llm_return_error_not_handoff():
    assert _upload("NPB adalah Nusantara Prima Bank.", filename="npb.txt").json()["status"] == "ready"
    response = client.post("/v1/chat/messages", json={"text": "Apa itu NPB?"},
                           headers={**auth_headers("customer", "customer-rag", "TNT-TEST"),
                                    "Idempotency-Key": uuid.uuid4().hex})
    assert response.status_code == 200
    assert response.json().get("reason") == "ANSWER_GENERATION_ERROR"
    assert response.json().get("handoff") is False
    assert response.json().get("citations")
    assert "coba kembali" in response.json()["reply"]


def test_f_missing_knowledge_hands_off_without_creating_case():
    response = client.post("/v1/chat/messages", json={"text": "Bagaimana cara merawat tanaman anggrek?"},
                           headers={**auth_headers("customer", "customer-rag", "TNT-TEST"),
                                    "Idempotency-Key": uuid.uuid4().hex})
    assert response.status_code == 200
    body = response.json()
    assert body.get("reason") == "KNOWLEDGE_GAP"
    assert body.get("handoff_status") == "QUEUED"
    assert "case_id" not in body and "ticket_id" not in body


def test_g_retrieval_and_chat_respect_tenant_isolation(monkeypatch):
    content = "NPB berarti Nusantara Prima Bank untuk lingkungan akademik sintetis."
    assert _upload(content, "TNT-ONE", "private.txt").json()["status"] == "ready"
    response = client.post("/v1/chat/messages", json={"text": "Apa itu NPB?"},
                           headers={**auth_headers("customer", "customer-other", "TNT-TWO"),
                                    "Idempotency-Key": uuid.uuid4().hex})
    assert response.status_code == 200
    assert response.json().get("reason") == "KNOWLEDGE_GAP"
    assert not response.json().get("citations")


def test_h_failed_pdf_ingestion_is_visible_and_never_searchable():
    response = client.post("/v1/knowledge/documents/upload",
                           files={"file": ("broken.pdf", b"not a valid PDF", "application/pdf")},
                           headers=auth_headers("cs_agent", "staff-rag", "TNT-TEST"))
    assert response.status_code >= 400
    db = SessionLocal()
    try:
        failed = db.query(KnowledgeDocumentRow).filter_by(tenant_id="TNT-TEST", status="failed").one()
        from app.modules import knowledge as KmSvc
        result = KmSvc.search(db, "broken PDF", tenant_id="TNT-TEST")
        assert result["zero_result"]
        assert failed.error_message and failed.error_details
    finally:
        db.close()


def test_i_chat_returns_actual_f4_answer_and_read_model_content(monkeypatch):
    text = "NPB adalah Nusantara Prima Bank, sebuah lingkungan akademik sintetis."
    assert _upload(text).json()["status"] == "ready"
    response, provider = _answer_with_source(monkeypatch, "Apa itu NPB?")
    assert provider.calls and provider.calls[0][0] == "F4"
    assert response.json()["reply"] == text
    conversation = response.json()["conversation_id"]
    read = client.get(f"/v1/conversations/{conversation}/read-model",
                      headers=auth_headers("customer", "customer-rag", "TNT-TEST"))
    outbound = [item for item in read.json()["messages"] if item["direction"] == "OUTBOUND"]
    assert outbound[-1]["content"] == text
    assert outbound[-1]["citations"] == response.json()["citations"]


def test_j_mandatory_fraud_handoff_is_preserved():
    response = client.post("/v1/chat/messages", json={"text": "Saya ditipu dan dipaksa transfer sekarang"},
                           headers={**auth_headers("customer", "customer-rag", "TNT-TEST"),
                                    "Idempotency-Key": uuid.uuid4().hex})
    assert response.status_code == 200
    assert response.json().get("handoff_status") == "QUEUED"
    assert response.json().get("reason") == "VULNERABILITY"
