"""Tests untuk ingest dokumen pengetahuan (Unit 11): unggah, ekstraksi,
chunk, status, retry, pencarian, sitasi, isolasi tenant, RBAC."""
import io
import zipfile
import xml.etree.ElementTree as ET

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.db import Base, engine, SessionLocal
from app.modules.models_a import KnowledgeDocumentRow, KnowledgeChunkRow
from tests.auth_helpers import auth_headers

client = TestClient(app)
STAFF_WORKSPACE_ROLES = (
    "cs_agent", "supervisor", "complaint_officer", "knowledge_manager",
    "qa_analyst", "management", "admin",
)


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def _make_txt(content: str) -> bytes:
    return content.encode("utf-8")


def _make_docx(text: str) -> bytes:
    ns_w = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    doc_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:document xmlns:w="{ns_w}"><w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body></w:document>'
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("word/document.xml", doc_xml)
        zf.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types></Types>')
        zf.writestr("_rels/.rels", '<?xml version="1.0"?><Relationships></Relationships>')
    return buf.getvalue()


# ---------------- RBAC & otorisasi ----------------

@pytest.mark.parametrize("role", STAFF_WORKSPACE_ROLES)
def test_staff_workspace_roles_can_read_and_upload_documents(role):
    headers = auth_headers(role, f"{role}-1", "TNT-TEST")
    response = client.post(
        "/v1/knowledge/documents/upload",
        files={"file": (f"{role}.txt", _make_txt(f"Dokumen staf untuk role {role}."), "text/plain")},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "ready"
    assert body["document_id"]
    assert body["chunk_count"] >= 1
    listed = client.get("/v1/knowledge/documents", headers=headers)
    assert listed.status_code == 200, listed.text
    assert any(item["document_id"] == body["document_id"] for item in listed.json()["items"])
    detail = client.get(f"/v1/knowledge/documents/{body['document_id']}", headers=headers)
    assert detail.status_code == 200, detail.text
    assert detail.json()["document_id"] == body["document_id"]


def test_customer_cannot_upload_document():
    headers = auth_headers("customer", "customer-a", "TNT-TEST")
    response = client.post(
        "/v1/knowledge/documents/upload",
        files={"file": ("sop.txt", _make_txt("isi rahasia"), "text/plain")},
        headers=headers,
    )
    assert response.status_code == 403, response.text


def test_customer_cannot_read_or_retry_knowledge_documents():
    headers = auth_headers("customer", "customer-a", "TNT-TEST")
    assert client.get("/v1/knowledge/search?q=informasi", headers=headers).status_code == 403
    assert client.get("/v1/knowledge/documents", headers=headers).status_code == 403
    assert client.get("/v1/knowledge/documents/KDO-NOT-OWNED", headers=headers).status_code == 403
    assert client.post("/v1/knowledge/documents/KDO-NOT-OWNED/retry", headers=headers).status_code == 403
    article = client.post("/v1/knowledge/articles", json={
        "title": "Artikel", "body": "Isi", "expires_at": "2030-01-01T00:00:00+00:00",
    }, headers=headers)
    assert article.status_code == 403, article.text


def test_customer_cannot_spoof_staff_role_for_upload():
    headers = {**auth_headers("customer", "customer-a", "TNT-TEST"), "X-Role": "admin"}
    response = client.post(
        "/v1/knowledge/documents/upload",
        files={"file": ("sop.txt", _make_txt("isi rahasia"), "text/plain")},
        headers=headers,
    )
    assert response.status_code == 403, response.text


def test_unauthenticated_upload_rejected():
    response = client.post(
        "/v1/knowledge/documents/upload",
        files={"file": ("sop.txt", _make_txt("isi"), "text/plain")},
    )
    assert response.status_code == 401, response.text


def test_ai_service_role_is_not_staff_and_cannot_upload_document():
    headers = auth_headers("ai_agent", "orchestrator", "TNT-TEST", token_use="service")
    response = client.post(
        "/v1/knowledge/documents/upload",
        files={"file": ("sop.txt", _make_txt("isi"), "text/plain")},
        headers=headers,
    )
    assert response.status_code == 403, response.text


def test_only_staff_workspace_roles_receive_document_ingest_permission():
    from app.core.rbac import ROLE_PERMS
    allowed = {role for role, permissions in ROLE_PERMS.items()
               if "knowledge.document.ingest" in permissions}
    assert allowed == set(STAFF_WORKSPACE_ROLES)
    assert "knowledge.document.ingest" not in ROLE_PERMS["customer"]
    assert "knowledge.document.ingest" not in ROLE_PERMS["ai_agent"]


def test_document_ingest_permission_does_not_grant_article_authoring():
    headers = auth_headers("cs_agent", "agent-1", "TNT-TEST")
    response = client.post("/v1/knowledge/articles", json={
        "title": "Artikel", "body": "Isi", "expires_at": "2030-01-01T00:00:00+00:00",
    }, headers=headers)
    assert response.status_code == 403, response.text


# ---------------- validasi berkas ----------------

def test_unsupported_format_rejected():
    headers = auth_headers("knowledge_manager", "km-1", "TNT-TEST")
    response = client.post(
        "/v1/knowledge/documents/upload",
        files={"file": ("malware.exe", b"\x4d\x5a\x90\x00", "application/x-msdownload")},
        headers=headers,
    )
    assert response.status_code == 400, response.text
    assert "tidak didukung" in response.text or "UNSUPPORTED" in response.text


def test_empty_file_rejected():
    headers = auth_headers("knowledge_manager", "km-1", "TNT-TEST")
    response = client.post(
        "/v1/knowledge/documents/upload",
        files={"file": ("empty.txt", b"", "text/plain")},
        headers=headers,
    )
    assert response.status_code == 400, response.text


def test_file_too_large_rejected(monkeypatch):
    import app.modules.knowledge as Km
    monkeypatch.setattr(Km, "MAX_FILE_SIZE", 100)
    headers = auth_headers("knowledge_manager", "km-1", "TNT-TEST")
    response = client.post(
        "/v1/knowledge/documents/upload",
        files={"file": ("big.txt", b"x" * 1000, "text/plain")},
        headers=headers,
    )
    assert response.status_code == 400, response.text


# ---------------- ekstraksi teks ----------------

def test_txt_upload_extracts_text_and_creates_chunks():
    headers = auth_headers("knowledge_manager", "km-1", "TNT-TEST")
    content = "Biaya transfer internasional adalah Rp25.000 per transaksi. Berlaku sejak 2026-01-01. " * 10
    response = client.post(
        "/v1/knowledge/documents/upload",
        files={"file": ("biaya.txt", _make_txt(content), "text/plain")},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "ready"
    assert body["chunk_count"] >= 1

    db = SessionLocal()
    try:
        doc = db.query(KnowledgeDocumentRow).filter_by(document_id=body["document_id"]).first()
        assert doc is not None
        assert doc.status == "ready"
        assert doc.chunk_count >= 1
        chunks = db.query(KnowledgeChunkRow).filter_by(document_id=doc.document_id).all()
        assert len(chunks) >= 1
        assert any("Rp25.000" in c.content for c in chunks)
    finally:
        db.close()


def test_docx_upload_extracts_text():
    headers = auth_headers("knowledge_manager", "km-1", "TNT-TEST")
    docx_bytes = _make_docx("Panduan pembukaan rekening koran dikirim ke email dalam 1x24 jam.")
    response = client.post(
        "/v1/knowledge/documents/upload",
        files={"file": ("panduan.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "ready", response.text
    assert body["chunk_count"] >= 1


def test_pdf_without_text_fails_gracefully():
    """PDF yang valid tetapi tanpa teks diekstrak -> gagal, bukan siap."""
    headers = auth_headers("knowledge_manager", "km-1", "TNT-TEST")
    pdf_minimal = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\n"
        b"xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000111 00000 n \n"
        b"trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n178\n%%EOF\n"
    )
    response = client.post(
        "/v1/knowledge/documents/upload",
        files={"file": ("notext.pdf", pdf_minimal, "application/pdf")},
        headers=headers,
    )
    assert response.status_code == 422, response.text
    body = response.json()
    assert body["status"] == "failed"


# ---------------- idempotensi & retry ----------------

def test_same_file_upload_is_idempotent():
    headers = auth_headers("knowledge_manager", "km-1", "TNT-TEST")
    content = "Dokumen unik untuk pengujian idempotensi ingest."
    r1 = client.post(
        "/v1/knowledge/documents/upload",
        files={"file": ("uniq.txt", _make_txt(content), "text/plain")},
        headers=headers,
    )
    assert r1.status_code == 200
    doc_id = r1.json()["document_id"]
    assert r1.json().get("replayed") is False

    r2 = client.post(
        "/v1/knowledge/documents/upload",
        files={"file": ("uniq.txt", _make_txt(content), "text/plain")},
        headers=headers,
    )
    assert r2.status_code == 200
    assert r2.json()["document_id"] == doc_id
    assert r2.json().get("replayed") is True

    db = SessionLocal()
    try:
        assert db.query(KnowledgeDocumentRow).filter_by(document_id=doc_id).count() == 1
        assert db.query(KnowledgeChunkRow).filter_by(document_id=doc_id).count() >= 1
    finally:
        db.close()


def test_retry_failed_document():
    headers = auth_headers("knowledge_manager", "km-1", "TNT-TEST")
    pdf_minimal = (
        b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\n"
        b"xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000111 00000 n \n"
        b"trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n178\n%%EOF\n"
    )
    r = client.post(
        "/v1/knowledge/documents/upload",
        files={"file": ("notext.pdf", pdf_minimal, "application/pdf")},
        headers=headers,
    )
    assert r.status_code == 422
    doc_id = r.json()["document_id"]

    # Retry dengan PDF yang sama (tidak ada teks) masih gagal
    r2 = client.post(
        f"/v1/knowledge/documents/{doc_id}/retry",
        headers=headers,
    )
    assert r2.status_code == 422
    assert r2.json()["status"] == "failed"

    db = SessionLocal()
    try:
        doc = db.query(KnowledgeDocumentRow).filter_by(document_id=doc_id).first()
        assert doc.status == "failed"
    finally:
        db.close()


def test_retry_nonexistent_document():
    headers = auth_headers("knowledge_manager", "km-1", "TNT-TEST")
    response = client.post("/v1/knowledge/documents/KDO-XXXXXXXXXXXXXXXX/retry", headers=headers)
    assert response.status_code == 404, response.text


# ---------------- daftar & detail ----------------

def test_list_documents_requires_read_permission():
    headers = auth_headers("knowledge_manager", "km-1", "TNT-TEST")
    # Unggah dulu
    client.post(
        "/v1/knowledge/documents/upload",
        files={"file": ("a.txt", _make_txt("konten a"), "text/plain")},
        headers=headers,
    )
    response = client.get("/v1/knowledge/documents", headers=headers)
    assert response.status_code == 200, response.text
    items = response.json()["items"]
    assert len(items) >= 1


def test_customer_cannot_list_documents():
    headers = auth_headers("customer", "customer-a", "TNT-TEST")
    response = client.get("/v1/knowledge/documents", headers=headers)
    assert response.status_code == 403, response.text


def test_staff_role_can_retry_failed_document():
    manager_headers = auth_headers("knowledge_manager", "km-1", "TNT-TEST")
    uploaded = client.post(
        "/v1/knowledge/documents/upload",
        files={"file": ("retry.txt", _make_txt("Konten untuk uji retry staf."), "text/plain")},
        headers=manager_headers,
    )
    assert uploaded.status_code == 200, uploaded.text
    document_id = uploaded.json()["document_id"]
    db = SessionLocal()
    try:
        document = db.query(KnowledgeDocumentRow).filter_by(document_id=document_id).one()
        document.status = "failed"
        document.error_message = "simulated retry fixture"
        db.commit()
    finally:
        db.close()

    staff_headers = auth_headers("cs_agent", "agent-1", "TNT-TEST")
    retried = client.post(f"/v1/knowledge/documents/{document_id}/retry", headers=staff_headers)
    assert retried.status_code == 200, retried.text
    assert retried.json()["status"] == "ready"


def test_ai_service_keeps_retrieval_read_but_cannot_manage_documents():
    headers = auth_headers("ai_agent", "orchestrator", "TNT-TEST", token_use="service")
    assert client.get("/v1/knowledge/search?q=informasi", headers=headers).status_code == 200
    assert client.get("/v1/knowledge/documents", headers=headers).status_code == 403
    upload = client.post(
        "/v1/knowledge/documents/upload",
        files={"file": ("sop.txt", _make_txt("isi"), "text/plain")},
        headers=headers,
    )
    assert upload.status_code == 403, upload.text


def test_service_token_with_staff_role_still_cannot_manage_documents(monkeypatch):
    import json
    monkeypatch.setenv("SERVICE_TOKEN_SCOPES", json.dumps({
        "test-worker": ["knowledge.read", "knowledge.document.ingest"],
    }))
    headers = auth_headers(
        "supervisor", "test-worker", "TNT-TEST", token_use="service",
        extra=["knowledge.read", "knowledge.document.ingest"],
    )
    assert client.get("/v1/knowledge/documents", headers=headers).status_code == 403
    response = client.post(
        "/v1/knowledge/documents/upload",
        files={"file": ("sop.txt", _make_txt("isi"), "text/plain")},
        headers=headers,
    )
    assert response.status_code == 403, response.text


def test_get_document_detail():
    headers = auth_headers("knowledge_manager", "km-1", "TNT-TEST")
    r = client.post(
        "/v1/knowledge/documents/upload",
        files={"file": ("detail.txt", _make_txt("isi detail dokumen untuk pengujian."), "text/plain")},
        headers=headers,
    )
    doc_id = r.json()["document_id"]
    response = client.get(f"/v1/knowledge/documents/{doc_id}", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["document_id"] == doc_id
    assert body["status"] == "ready"
    assert body["title"] == "detail.txt"
    assert "file_path" not in body
    assert "download_url" not in body


# ---------------- pencarian & sitasi dari dokumen ----------------

def test_search_finds_uploaded_document_content():
    headers = auth_headers("knowledge_manager", "km-1", "TNT-TEST")
    client.post(
        "/v1/knowledge/documents/upload",
        files={"file": ("sop.txt", _make_txt("Prosedur escalasi fraud harus divalidasi oleh supervisor."), "text/plain")},
        headers=headers,
    )
    from app.modules import knowledge as KmSvc
    db = SessionLocal()
    try:
        result = KmSvc.search(db, "escalasi fraud supervisor", language="id", tenant_id="TNT-TEST")
        assert result["zero_result"] is False
        doc_results = [x for x in result["results"] if x.get("source_type") == "document"]
        assert len(doc_results) >= 1
        assert any("escalasi" in x["body"].lower() for x in doc_results)
    finally:
        db.close()


def test_cite_includes_document_fields():
    headers = auth_headers("knowledge_manager", "km-1", "TNT-TEST")
    client.post(
        "/v1/knowledge/documents/upload",
        files={"file": ("cite.txt", _make_txt("Cetak rekening koran tersedia dalam 1x24 jam setelah verifikasi AL2."), "text/plain")},
        headers=headers,
    )
    from app.modules import knowledge as KmSvc
    db = SessionLocal()
    try:
        result = KmSvc.search(db, "cetak rekening koran AL2", language="id", tenant_id="TNT-TEST")
        citations = KmSvc.cite(result["results"])
        doc_citations = [c for c in citations if c.get("source_type") == "document"]
        assert len(doc_citations) >= 1
        c = doc_citations[0]
        assert "document_id" in c
        assert "version_no" in c
        assert "chunk_index" in c
        assert "title" in c
        assert "retrieval_score" in c
    finally:
        db.close()


def test_failed_document_excluded_from_search():
    headers = auth_headers("knowledge_manager", "km-1", "TNT-TEST")
    pdf_minimal = (
        b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\n"
        b"xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000111 00000 n \n"
        b"trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n178\n%%EOF\n"
    )
    r = client.post(
        "/v1/knowledge/documents/upload",
        files={"file": ("bad.pdf", pdf_minimal, "application/pdf")},
        headers=headers,
    )
    assert r.status_code == 422
    failed_doc_id = r.json()["document_id"]
    from app.modules import knowledge as KmSvc
    db = SessionLocal()
    try:
        # Verify the document exists with failed status
        doc = db.query(KnowledgeDocumentRow).filter_by(document_id=failed_doc_id).first()
        assert doc is not None
        assert doc.status == "failed"
        # Search must not return chunks from the failed document
        result = KmSvc.search(db, "apapun", language="id", tenant_id="TNT-TEST")
        doc_results = [x for x in result["results"] if x.get("source_type") == "document"]
        failed_ids = [x for x in doc_results if x.get("document_id") == failed_doc_id]
        assert len(failed_ids) == 0
        # No chunks exist for the failed document
        chunks = db.query(KnowledgeChunkRow).filter_by(document_id=failed_doc_id).all()
        assert len(chunks) == 0
    finally:
        db.close()


# ---------------- isolasi tenant ----------------

def test_tenant_isolation_documents():
    headers_a = auth_headers("knowledge_manager", "km-a", "TNT-A")
    headers_b = auth_headers("knowledge_manager", "km-b", "TNT-B")
    client.post(
        "/v1/knowledge/documents/upload",
        files={"file": ("a.txt", _make_txt("konten tenant A"), "text/plain")},
        headers=headers_a,
    )
    client.post(
        "/v1/knowledge/documents/upload",
        files={"file": ("b.txt", _make_txt("konten tenant B"), "text/plain")},
        headers=headers_b,
    )

    response_a = client.get("/v1/knowledge/documents", headers=headers_a)
    assert response_a.status_code == 200
    items_a = response_a.json()["items"]
    assert all(item["title"] == "a.txt" for item in items_a)

    response_b = client.get("/v1/knowledge/documents", headers=headers_b)
    assert response_b.status_code == 200
    items_b = response_b.json()["items"]
    assert all(item["title"] == "b.txt" for item in items_b)
    document_a_id = items_a[0]["document_id"]
    assert client.get(f"/v1/knowledge/documents/{document_a_id}", headers=headers_b).status_code == 404
    assert client.post(f"/v1/knowledge/documents/{document_a_id}/retry", headers=headers_b).status_code == 404

    from app.modules import knowledge as KmSvc
    db = SessionLocal()
    try:
        result_b = KmSvc.search(db, "konten tenant A", language="id", tenant_id="TNT-B")
        tenant_b_docs = [item for item in result_b["results"] if item.get("source_type") == "document"]
        assert all("konten tenant a" not in item["body"].lower() for item in tenant_b_docs)
    finally:
        db.close()


# ---------------- end-to-end chat retrieval ----------------

def test_end_to_end_chat_retrieves_uploaded_document_with_citations():
    """Upload a document, then verify /v1/chat/messages retrieves it with document citations."""
    staff_headers = auth_headers("cs_agent", "agent-1", "TNT-TEST")
    ai_headers = auth_headers("ai_agent", "orchestrator", "TNT-TEST", token_use="service")

    content = ("Tarif layanan administrasi bulanan adalah Rp15.000 per bulan. "
               "Biaya ini berlaku untuk semua jenis rekening nasabah aktif.")
    r = client.post(
        "/v1/knowledge/documents/upload",
        files={"file": ("tarif_admin.txt", _make_txt(content), "text/plain")},
        headers=staff_headers,
    )
    assert r.status_code == 200, r.text
    doc_id = r.json()["document_id"]
    assert r.json()["status"] == "ready"

    # Ask about it via the existing chat orchestration flow
    response = client.post(
        "/v1/chat/messages",
        json={"text": "Biaya tarif layanan administrasi bulanan rekening?", "channel": "WEB_CHAT"},
        headers=ai_headers,
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result.get("reason") != "KNOWLEDGE_GAP", result
    citations = result.get("citations", [])
    doc_citations = [c for c in citations if c.get("source_type") == "document"]
    assert len(doc_citations) >= 1
    c = doc_citations[0]
    assert c["document_id"] == doc_id
    assert "version_no" in c
    assert "chunk_index" in c
    assert "title" in c
    assert "retrieval_score" in c


# ---------------- missing knowledge fallback (orchestrator) ----------------

def test_knowledge_gap_triggers_handoff_not_case():
    from app.modules import orchestrator as Orc
    from app.modules.models_a import ConversationRow, ChannelSessionRow
    from app.modules.models import HandoffRow, TicketRow, CaseRow
    db = SessionLocal()
    try:
        db.add(ConversationRow(conversation_id="CNV-KGAP", tenant_id="TNT-TEST", customer_id="cust-1"))
        db.add(ChannelSessionRow(channel_session_id="CHS-KGAP", conversation_id="CNV-KGAP", channel="WEB_CHAT"))
        db.commit()
        # "bunga tarif" -> INFO_PRODUCT_POLICY (INQUIRY, ACT, no tool needed), but no article/chunk matches
        result = Orc.run_turn(db, "CNV-KGAP", "Berapa bunga tarif tabungan?",
                              "COR-KGAP", "WEB_CHAT", tenant_id="TNT-TEST")
        assert result["reason"] == "KNOWLEDGE_GAP", result
        assert result["handoff"] is True
        assert "ticket_id" not in result
        assert db.query(TicketRow).filter_by(conversation_id="CNV-KGAP").count() == 0
        assert db.query(CaseRow).filter_by(origin_conversation_id="CNV-KGAP").count() == 0
    finally:
        db.close()


# ---------------- edit, replace, & delete dokumen ----------------

def test_edit_and_delete_knowledge_document():
    headers = auth_headers("knowledge_manager", "km-1", "TNT-TEST")
    other_tenant = auth_headers("knowledge_manager", "km-2", "TNT-OTHER")
    customer = auth_headers("customer", "cust-1", "TNT-TEST")

    up = client.post(
        "/v1/knowledge/documents/upload",
        files={"file": ("kebijakan_awal.txt", _make_txt("Bunga deposito awal adalah 4 persen per tahun."), "text/plain")},
        headers=headers,
    )
    assert up.status_code == 200, up.text
    doc_id = up.json()["document_id"]
    assert up.json()["status"] == "ready"

    # Customer cannot edit or delete
    assert client.put(f"/v1/knowledge/documents/{doc_id}", json={"title": "Baru", "content": "Isi"}, headers=customer).status_code == 403
    assert client.delete(f"/v1/knowledge/documents/{doc_id}", headers=customer).status_code == 403

    # Cross-tenant cannot edit or delete
    assert client.put(f"/v1/knowledge/documents/{doc_id}", json={"title": "Baru", "content": "Isi"}, headers=other_tenant).status_code == 404
    assert client.delete(f"/v1/knowledge/documents/{doc_id}", headers=other_tenant).status_code == 404

    # Edit title and content directly
    edited = client.put(
        f"/v1/knowledge/documents/{doc_id}",
        json={"title": "Kebijakan Deposito Revisi", "content": "Bunga deposito revisi terbaru adalah 6 persen per tahun untuk nasabah prioritas."},
        headers=headers,
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["version_no"] == 2
    assert edited.json()["title"] == "Kebijakan Deposito Revisi"

    detail = client.get(f"/v1/knowledge/documents/{doc_id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["version_no"] == 2
    assert "6 persen" in detail.json()["content"]

    # Replace file with a new upload
    replaced = client.post(
        f"/v1/knowledge/documents/{doc_id}/replace",
        files={"file": ("kebijakan_v3.txt", _make_txt("Bunga deposito versi tiga adalah 7 persen khusus tenor 12 bulan."), "text/plain")},
        data={"title": "Kebijakan Deposito V3"},
        headers=headers,
    )
    assert replaced.status_code == 200, replaced.text
    assert replaced.json()["version_no"] == 3
    assert replaced.json()["title"] == "Kebijakan Deposito V3"

    # Delete document
    deleted = client.delete(f"/v1/knowledge/documents/{doc_id}", headers=headers)
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["deleted"] is True

    # Document is gone from detail and list
    assert client.get(f"/v1/knowledge/documents/{doc_id}", headers=headers).status_code == 404
    listed = client.get("/v1/knowledge/documents", headers=headers).json()["items"]
    assert all(item["document_id"] != doc_id for item in listed)

