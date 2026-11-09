"""FR-KM-001..010 [A]: artikel+versi immutable, expiry enforced saat query+job,
akses PUBLIC/CUSTOMER/INTERNAL/RESTRICTED, sitasi wajib, gap detection. TRD §4.6.
Ditambah: ingest dokumen unggahan (PDF/DOCX/TXT), ekstraksi teks, chunking,
status pemrosesan, dan pencarian atas potongan dokumen siap pakai."""
from __future__ import annotations
import datetime
import hashlib
import io
import logging
import os
import re
import zipfile
import xml.etree.ElementTree as ET
from sqlalchemy.orm import Session
from ..core.ids import new_id
from ..core import audit as audit_svc
from ..core.errors import AppError
from ..core.db import safe_database_identity
from .models_a import KnowledgeArticleRow, KnowledgeVersionRow, KnowledgeDocumentRow, KnowledgeChunkRow

try:  # pypdf sudah terpasang di lingkungan lokal
    from pypdf import PdfReader
except Exception:  # pragma: no cover - fallback jika pypdf tidak tersedia
    PdfReader = None  # type: ignore

GENERIC_DENY = {"bukti", "dokumen", "berkas bukti", "data saja"}
ACCESS_ORDER = ["PUBLIC", "CUSTOMER", "INTERNAL", "RESTRICTED"]

# ---- konfigurasi ingest ----
UPLOAD_DIR = os.getenv("KNOWLEDGE_UPLOAD_DIR", os.path.join(os.getcwd(), "data", "uploads"))
MAX_FILE_SIZE = int(os.getenv("KNOWLEDGE_MAX_FILE_SIZE_MB", "10")) * 1024 * 1024
CHUNK_SIZE = int(os.getenv("KNOWLEDGE_CHUNK_SIZE", "1000"))
CHUNK_OVERLAP = int(os.getenv("KNOWLEDGE_CHUNK_OVERLAP", "200"))
SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt"}
MAX_CHUNKS_PER_DOC = int(os.getenv("KNOWLEDGE_MAX_CHUNKS_PER_DOC", "500"))

DOC_STATUS_PENDING = "pending"
DOC_STATUS_PROCESSING = "processing"
DOC_STATUS_READY = "ready"
DOC_STATUS_FAILED = "failed"
_logger = logging.getLogger("eaics.knowledge")
_logger.setLevel(logging.INFO)
_SEARCH_STOPWORDS = {"apa", "itu", "yang", "harus", "saya", "lakukan", "jika", "di", "ke", "dari", "dan", "atau", "untuk", "dengan", "pada", "ini", "kepada", "the", "what", "is", "how", "do", "i", "if", "my", "in", "of", "a", "an", "berapa", "bolehkah", "apakah", "jelaskan", "jelasin", "dong", "sih", "deh", "ya", "kan", "ceritakan", "ceritain", "sebutkan", "sebutin", "tolong", "beritahu", "kasih", "tahu", "tau", "info", "informasi", "mengenai", "tentang", "soal", "mohon"}

def _search_terms(value: str) -> list[str]:
    return [word for word in re.findall(r"[\w]+", value.casefold(), flags=re.UNICODE)
            if len(word) > 1 and word not in _SEARCH_STOPWORDS]

def _now(): return datetime.datetime.now(datetime.timezone.utc)

def _as_utc(value):
    if value is None: return None
    return value.replace(tzinfo=datetime.timezone.utc) if value.tzinfo is None else value.astimezone(datetime.timezone.utc)

def _ensure_upload_dir():
    try:
        os.makedirs(UPLOAD_DIR, exist_ok=True)
    except OSError as exc:
        raise AppError("E_UNAVAILABLE", "direktori penyimpanan berkas tidak dapat dibuat",
                       customer_message_id="KM.STORAGE_UNAVAILABLE") from exc

def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def _detect_mime_from_content(data: bytes, filename: str) -> str:
    """Deteksi MIME dari isi berkas (magic bytes), bukan hanya nama/MIME klien."""
    if data.startswith(b"%PDF"):
        return "application/pdf"
    if data.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                names = set(zf.namelist())
                if "word/document.xml" in names:
                    return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        except Exception:
            pass
        return "application/zip"
    # Tekst: coba dekode UTF-8
    try:
        data.decode("utf-8")
        return "text/plain"
    except UnicodeDecodeError:
        return "application/octet-stream"

def _validate_extension(filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise AppError("E_VALIDATION", f"ekstensi berkas tidak didukung: {ext}. Terima: {', '.join(sorted(SUPPORTED_EXTENSIONS))}",
                       customer_message_id="KM.UNSUPPORTED_FORMAT",
                       details=[{"field": "filename", "rule": "SUPPORTED_EXTENSION", "allowed": sorted(SUPPORTED_EXTENSIONS)}])
    return ext

def _validate_file(data: bytes, filename: str) -> str:
    """Validasi berkas unggahan: ukuran, ekstensi, MIME dari konten, kosong, terenkripsi."""
    if not data:
        raise AppError("E_VALIDATION", "berkas kosong tidak dapat diproses",
                       customer_message_id="KM.EMPTY_FILE",
                       details=[{"field": "file", "rule": "NON_EMPTY"}])
    if len(data) > MAX_FILE_SIZE:
        raise AppError("E_VALIDATION", f"berkas terlalu besar ({len(data)} byte, maks {MAX_FILE_SIZE} byte)",
                       customer_message_id="KM.FILE_TOO_LARGE",
                       details=[{"field": "file", "rule": "MAX_SIZE", "max_bytes": MAX_FILE_SIZE}])
    ext = _validate_extension(filename)
    mime = _detect_mime_from_content(data, filename)
    # Konsistensi ekstensi vs MIME terdeteksi
    expected = {".pdf": "application/pdf", ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".txt": "text/plain"}
    if ext in expected and mime != expected[ext] and mime not in ("application/zip",):
        # Dokumen terenkripsi/corrupt sering terdeteksi sebagai zip umum atau octet-stream
        if mime == "application/octet-stream":
            raise AppError("E_VALIDATION", "format berkas tidak dikenali atau berkas terenkripsi/korup",
                           customer_message_id="KM.UNREADABLE_FORMAT",
                           details=[{"field": "file", "rule": "READABLE_FORMAT"}])
    return mime

def _extract_text(data: bytes, filename: str, mime: str) -> str:
    """Ekstrak teks terbaca dari berkas. Mengembalikan string kosong jika tidak ada teks bermakna."""
    ext = os.path.splitext(filename)[1].lower()
    if ext == ".pdf":
        return _extract_pdf(data)
    if ext == ".docx":
        return _extract_docx(data)
    if ext == ".txt":
        return data.decode("utf-8", errors="replace")
    return ""

def _extract_pdf(data: bytes) -> str:
    if PdfReader is None:
        raise AppError("E_UNAVAILABLE", "pengurai PDF tidak tersedia di server",
                       customer_message_id="KM.PARSER_UNAVAILABLE")
    try:
        reader = PdfReader(io.BytesIO(data))
        parts = []
        for page in reader.pages:
            try:
                text = page.extract_text() or ""
            except Exception:
                text = ""
            if text.strip():
                parts.append(text)
        return "\n".join(parts)
    except Exception as exc:
        raise AppError("E_VALIDATION", "gagal mengekstrak teks dari PDF (berkas mungkin terenkripsi atau korup)",
                       customer_message_id="KM.PDF_EXTRACTION_FAILED",
                       details=[{"field": "file", "rule": "PDF_READABLE"}]) from exc

def _extract_docx(data: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            if "word/document.xml" not in zf.namelist():
                raise AppError("E_VALIDATION", "berkas DOCX tidak valid (tidak ada word/document.xml)",
                               customer_message_id="KM.DOCX_INVALID",
                               details=[{"field": "file", "rule": "DOCX_STRUCTURE"}])
            xml_content = zf.read("word/document.xml")
        root = ET.fromstring(xml_content)
        ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        texts = []
        for t in root.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"):
            texts.append(t.text or "")
        return "\n".join(texts)
    except AppError:
        raise
    except ET.ParseError as exc:
        raise AppError("E_VALIDATION", "gagal menguraikan berkas DOCX (korup)",
                       customer_message_id="KM.DOCX_PARSE_FAILED",
                       details=[{"field": "file", "rule": "DOCX_READABLE"}]) from exc
    except Exception as exc:
        raise AppError("E_VALIDATION", "gagal membaca berkas DOCX",
                       customer_message_id="KM.DOCX_READ_FAILED",
                       details=[{"field": "file", "rule": "DOCX_READABLE"}]) from exc

def _normalize_text(text: str) -> str:
    """Normalisasi teks tanpa merusak makna: hapus baris berlebih, spasi ganda, karakter kontrol."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    text = text.replace("\t", " ")
    text = re.sub(r"[ ]{2,}", " ", text)
    lines = [line.strip() for line in text.split("\n")]
    lines = [line for line in lines if line]
    return "\n".join(lines)

def _chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Bagi teks menjadi potongan untuk pengambilan, dengan overlap di antaranya."""
    if not text:
        return []
    chunks = []
    start = 0
    text_len = len(text)
    while start < text_len:
        end = min(start + chunk_size, text_len)
        chunk = text[start:end]
        # Coba potong di batas kalimat/spasi terakhir
        if end < text_len:
            last_space = chunk.rfind(" ")
            last_period = max(chunk.rfind(". "), chunk.rfind(".\n"), chunk.rfind("! "), chunk.rfind("? "))
            cut = max(last_space, last_period)
            if cut > start + chunk_size // 2:
                end = cut + 1
                chunk = text[start:end]
        chunks.append(chunk.strip())
        if end >= text_len:
            break
        start = end - overlap
        if start < 0:
            start = 0
    return chunks[:MAX_CHUNKS_PER_DOC]

def _store_file(data: bytes, file_hash: str, filename: str) -> str:
    """Simpan berkas asli ke direktori unggahan dengan nama berdasarkan hash (hindari traversal/duplikat)."""
    _ensure_upload_dir()
    safe_name = f"{file_hash[:16]}_{os.path.basename(filename)}"
    # Hindari path traversal: pakai basename dan hash sebagai prefiks
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", safe_name)
    path = os.path.join(UPLOAD_DIR, safe_name)
    if not os.path.exists(path):
        with open(path, "wb") as f:
            f.write(data)
    return path

def _find_existing_document(db: Session, file_hash: str, tenant_id: str) -> KnowledgeDocumentRow | None:
    return db.query(KnowledgeDocumentRow).filter_by(file_hash=file_hash, tenant_id=tenant_id).first()

def ingest_document(db: Session, file_data: bytes, filename: str, ctx: dict,
                    corr: str = "COR-?", tenant_id: str = "TNT-TEST") -> dict:
    """Pipeline ingest dokumen lengkap: validasi -> simpan -> ekstrak -> normalisasi -> chunk -> simpan -> siap."""
    actor_id = ctx.get("actor_id", "system")
    actor_type = ctx.get("actor_type", "SYSTEM")

    # 1. Validasi berkas
    mime = _validate_file(file_data, filename)
    file_hash = _sha256(file_data)

    # 2. Idempotensi: dokumen dengan hash yang sama sudah ada
    existing = _find_existing_document(db, file_hash, tenant_id)
    if existing:
        audit_svc.emit(tenant_id, corr, actor_type, actor_id, "knowledge.document.duplicate_skipped",
                       "document", existing.document_id, "knowledge-svc",
                       after={"status": existing.status, "document_id": existing.document_id})
        return {"document_id": existing.document_id, "status": existing.status,
                "message": "Dokumen dengan konten yang sama sudah ada", "replayed": True,
                "chunk_count": existing.chunk_count}

    # 3. Buat catatan dokumen (pending)
    document_id = new_id("knowledge_document")
    try:
        file_path = _store_file(file_data, file_hash, filename)
    except AppError:
        raise
    except Exception as exc:
        raise AppError("E_UNAVAILABLE", "gagal menyimpan berkas berkas",
                       customer_message_id="KM.STORAGE_FAILED",
                       details=[{"field": "file", "rule": "STORAGE_WRITE"}]) from exc

    doc = KnowledgeDocumentRow(document_id=document_id, tenant_id=tenant_id,
                               title=filename, original_filename=filename,
                               file_path=file_path, file_size=len(file_data),
                               mime_type=mime, file_hash=file_hash,
                               status=DOC_STATUS_PENDING,
                               uploaded_by=actor_id, uploaded_by_type=actor_type)
    db.add(doc)
    db.commit()
    audit_svc.emit(tenant_id, corr, actor_type, actor_id, "knowledge.document.created",
                   "document", document_id, "knowledge-svc",
                   after={"filename": filename, "size": len(file_data), "mime": mime})

    # 4. Pemrosesan (processing)
    doc.status = DOC_STATUS_PROCESSING
    db.commit()

    try:
        # 5. Ekstraksi teks
        raw_text = _extract_text(file_data, filename, mime)
        text = _normalize_text(raw_text)

        if not text or not text.strip():
            doc.status = DOC_STATUS_FAILED
            doc.error_message = "Tidak ada teks yang dapat diekstrak dari berkas"
            doc.error_details = {"reason": "NO_TEXT", "mime": mime}
            db.commit()
            audit_svc.emit(tenant_id, corr, actor_type, actor_id, "knowledge.document.extraction_empty",
                           "document", document_id, "knowledge-svc")
            return {"document_id": document_id, "status": DOC_STATUS_FAILED,
                    "error": "Tidak ada teks yang dapat diekstrak", "replayed": False}

        # 6. Chunking
        chunks = _chunk_text(text)
        if not chunks:
            doc.status = DOC_STATUS_FAILED
            doc.error_message = "Tidak dapat membuat potongan teks dari berkas"
            doc.error_details = {"reason": "NO_CHUNKS", "mime": mime}
            db.commit()
            return {"document_id": document_id, "status": DOC_STATUS_FAILED,
                    "error": "Tidak dapat membuat potongan teks", "replayed": False}

        # 7. Simpan potongan
        chunk_objs = []
        for index, chunk_content in enumerate(chunks):
            chunk_id = new_id("knowledge_chunk")
            chunk_objs.append(KnowledgeChunkRow(
                chunk_id=chunk_id, document_id=document_id, version_no=1,
                chunk_index=index, content=chunk_content,
                content_hash=_sha256(chunk_content.encode("utf-8")),
                token_count=len(chunk_content.split())))
        db.add_all(chunk_objs)

        # 8. Tandai siap
        doc.status = DOC_STATUS_READY
        doc.chunk_count = len(chunk_objs)
        doc.processed_at = _now()
        db.commit()

        audit_svc.emit(tenant_id, corr, actor_type, actor_id, "knowledge.document.indexed",
                       "document", document_id, "knowledge-svc",
                       after={"chunk_count": len(chunk_objs), "status": DOC_STATUS_READY})
        return {"document_id": document_id, "status": DOC_STATUS_READY,
                "message": "Dokumen berhasil diproses dan diindex", "replayed": False,
                "chunk_count": len(chunk_objs)}

    except AppError:
        doc.status = DOC_STATUS_FAILED
        doc.error_message = "Pemrosesan dokumen gagal; lihat detail validasi unggahan."
        doc.error_details = {"reason": "EXTRACTION_OR_PROCESSING_FAILED"}
        db.commit()
        raise
    except Exception as exc:
        doc.status = DOC_STATUS_FAILED
        doc.error_message = str(exc)[:500]
        doc.error_details = {"reason": "PROCESSING_ERROR", "type": type(exc).__name__}
        db.commit()
        audit_svc.emit(tenant_id, corr, actor_type, actor_id, "knowledge.document.processing_failed",
                       "document", document_id, "knowledge-svc",
                       error_code="PROCESSING_ERROR", after={"error": doc.error_message})
        return {"document_id": document_id, "status": DOC_STATUS_FAILED,
                "error": "Gagal memproses dokumen", "replayed": False}

def retry_document(db: Session, document_id: str, ctx: dict,
                   corr: str = "COR-?", tenant_id: str = "TNT-TEST") -> dict:
    """Coba ulang pemrosesan dokumen yang gagal. Idempoten: tidak membuat duplikat potongan."""
    actor_id = ctx.get("actor_id", "system")
    actor_type = ctx.get("actor_type", "SYSTEM")
    doc = db.query(KnowledgeDocumentRow).filter_by(document_id=document_id, tenant_id=tenant_id).first()
    if not doc:
        raise AppError("E_NOT_FOUND", "dokumen tidak ditemukan",
                       customer_message_id="KM.DOCUMENT_NOT_FOUND")
    if doc.status == DOC_STATUS_READY:
        return {"document_id": document_id, "status": DOC_STATUS_READY,
                "message": "Dokumen sudah siap", "replayed": True,
                "chunk_count": doc.chunk_count}
    if doc.status == DOC_STATUS_PROCESSING:
        return {"document_id": document_id, "status": DOC_STATUS_PROCESSING,
                "message": "Sedang diproses", "replayed": True,
                "chunk_count": doc.chunk_count}

    # Hapus potongan lama jika ada (hindari campuran versi)
    db.query(KnowledgeChunkRow).filter_by(document_id=document_id).delete()
    db.commit()

    # Baca ulang berkas asli
    if not os.path.exists(doc.file_path):
        doc.status = DOC_STATUS_FAILED
        doc.error_message = "Berkas asli tidak tersedia di penyimpanan"
        doc.error_details = {"reason": "FILE_MISSING"}
        db.commit()
        return {"document_id": document_id, "status": DOC_STATUS_FAILED,
                "error": "Berkas asli tidak tersedia", "replayed": False}

    with open(doc.file_path, "rb") as f:
        file_data = f.read()

    doc.status = DOC_STATUS_PROCESSING
    doc.error_message = None
    doc.error_details = None
    db.commit()

    try:
        raw_text = _extract_text(file_data, doc.original_filename, doc.mime_type)
        text = _normalize_text(raw_text)
        if not text or not text.strip():
            doc.status = DOC_STATUS_FAILED
            doc.error_message = "Tidak ada teks yang dapat diekstrak dari berkas"
            doc.error_details = {"reason": "NO_TEXT", "mime": doc.mime_type}
            db.commit()
            return {"document_id": document_id, "status": DOC_STATUS_FAILED,
                    "error": "Tidak ada teks yang dapat diekstrak", "replayed": False}

        chunks = _chunk_text(text)
        if not chunks:
            doc.status = DOC_STATUS_FAILED
            doc.error_message = "Tidak dapat membuat potongan teks dari berkas"
            doc.error_details = {"reason": "NO_CHUNKS", "mime": doc.mime_type}
            db.commit()
            return {"document_id": document_id, "status": DOC_STATUS_FAILED,
                    "error": "Tidak dapat membuat potongan teks", "replayed": False}

        chunk_objs = []
        for index, chunk_content in enumerate(chunks):
            chunk_id = new_id("knowledge_chunk")
            chunk_objs.append(KnowledgeChunkRow(
                chunk_id=chunk_id, document_id=document_id, version_no=doc.version_no,
                chunk_index=index, content=chunk_content,
                content_hash=_sha256(chunk_content.encode("utf-8")),
                token_count=len(chunk_content.split())))
        db.add_all(chunk_objs)

        doc.status = DOC_STATUS_READY
        doc.chunk_count = len(chunk_objs)
        doc.processed_at = _now()
        db.commit()

        audit_svc.emit(tenant_id, corr, actor_type, actor_id, "knowledge.document.retry_indexed",
                       "document", document_id, "knowledge-svc",
                       after={"chunk_count": len(chunk_objs), "status": DOC_STATUS_READY})
        return {"document_id": document_id, "status": DOC_STATUS_READY,
                "message": "Dokumen berhasil diproses ulang dan diindex", "replayed": False,
                "chunk_count": len(chunk_objs)}

    except AppError:
        doc.status = DOC_STATUS_FAILED
        doc.error_message = "Pemrosesan ulang dokumen gagal; lihat detail validasi unggahan."
        doc.error_details = {"reason": "RETRY_PROCESSING_FAILED"}
        db.commit()
        raise
    except Exception as exc:
        doc.status = DOC_STATUS_FAILED
        doc.error_message = str(exc)[:500]
        doc.error_details = {"reason": "PROCESSING_ERROR", "type": type(exc).__name__}
        db.commit()
        return {"document_id": document_id, "status": DOC_STATUS_FAILED,
                "error": "Gagal memproses ulang dokumen", "replayed": False}

def get_document(db: Session, document_id: str, tenant_id: str) -> dict | None:
    doc = db.query(KnowledgeDocumentRow).filter_by(document_id=document_id, tenant_id=tenant_id).first()
    if not doc:
        return None
    chunks = (db.query(KnowledgeChunkRow).filter_by(document_id=document_id)
              .order_by(KnowledgeChunkRow.chunk_index.asc()).all())
    return {"document_id": doc.document_id, "title": doc.title, "original_filename": doc.original_filename,
            "file_size": doc.file_size, "mime_type": doc.mime_type, "version_no": doc.version_no,
            "status": doc.status, "error_message": doc.error_message,
            "chunk_count": doc.chunk_count, "uploaded_by": doc.uploaded_by,
            "uploaded_by_type": doc.uploaded_by_type, "created_at": doc.created_at.isoformat() if doc.created_at else None,
            "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
            "processed_at": doc.processed_at.isoformat() if doc.processed_at else None,
            "content": "\n\n".join(c.content for c in chunks),
            "chunks": [{"chunk_index": c.chunk_index, "content": c.content, "token_count": c.token_count} for c in chunks]}

def update_document(db: Session, document_id: str, ctx: dict,
                    title: str | None = None, content: str | None = None,
                    file_data: bytes | None = None, filename: str | None = None,
                    corr: str = "COR-?", tenant_id: str = "TNT-TEST") -> dict:
    """Perbarui judul, isi teks, atau ganti berkas dokumen pengetahuan dan indeks ulang potongan."""
    actor_id = ctx.get("actor_id", "system")
    actor_type = ctx.get("actor_type", "SYSTEM")
    doc = db.query(KnowledgeDocumentRow).filter_by(document_id=document_id, tenant_id=tenant_id).first()
    if not doc:
        raise AppError("E_NOT_FOUND", "dokumen tidak ditemukan",
                       customer_message_id="KM.DOCUMENT_NOT_FOUND")
    if title is None and content is None and file_data is None:
        raise AppError("E_VALIDATION", "tidak ada perubahan yang diberikan",
                       customer_message_id="KM.UPDATE_EMPTY",
                       details=[{"field": "body", "rule": "NON_EMPTY"}])

    if title is not None:
        cleaned_title = title.strip()
        if not cleaned_title:
            raise AppError("E_VALIDATION", "judul dokumen tidak boleh kosong",
                           customer_message_id="KM.TITLE_EMPTY",
                           details=[{"field": "title", "rule": "NON_EMPTY"}])
        doc.title = cleaned_title

    if file_data is not None:
        eff_filename = filename or doc.original_filename
        mime = _validate_file(file_data, eff_filename)
        file_hash = _sha256(file_data)
        raw_text = _extract_text(file_data, eff_filename, mime)
        text = _normalize_text(raw_text)
        if not text or not text.strip():
            raise AppError("E_VALIDATION", "tidak ada teks yang dapat diekstrak dari berkas baru",
                           customer_message_id="KM.EMPTY_FILE",
                           details=[{"field": "file", "rule": "EXTRACTABLE_TEXT"}])
        chunks = _chunk_text(text)
        if not chunks:
            raise AppError("E_VALIDATION", "tidak dapat membuat potongan teks dari berkas baru",
                           customer_message_id="KM.EMPTY_FILE",
                           details=[{"field": "file", "rule": "CHUNKABLE"}])
        file_path = _store_file(file_data, file_hash, eff_filename)
        db.query(KnowledgeChunkRow).filter_by(document_id=document_id).delete()
        doc.version_no = (doc.version_no or 1) + 1
        doc.original_filename = eff_filename
        if title is None:
            doc.title = eff_filename
        doc.file_path = file_path
        doc.file_size = len(file_data)
        doc.mime_type = mime
        doc.file_hash = file_hash
        chunk_objs = [
            KnowledgeChunkRow(
                chunk_id=new_id("knowledge_chunk"), document_id=document_id,
                version_no=doc.version_no, chunk_index=idx, content=ch,
                content_hash=_sha256(ch.encode("utf-8")), token_count=len(ch.split())
            )
            for idx, ch in enumerate(chunks)
        ]
        db.add_all(chunk_objs)
        doc.status = DOC_STATUS_READY
        doc.error_message = None
        doc.error_details = None
        doc.chunk_count = len(chunk_objs)
        doc.processed_at = _now()
        doc.updated_at = _now()
    elif content is not None:
        text = _normalize_text(content)
        if not text or not text.strip():
            raise AppError("E_VALIDATION", "isi teks dokumen tidak boleh kosong",
                           customer_message_id="KM.EMPTY_CONTENT",
                           details=[{"field": "content", "rule": "NON_EMPTY"}])
        chunks = _chunk_text(text)
        if not chunks:
            raise AppError("E_VALIDATION", "tidak dapat membuat potongan teks dari konten",
                           customer_message_id="KM.EMPTY_CONTENT",
                           details=[{"field": "content", "rule": "CHUNKABLE"}])
        encoded = text.encode("utf-8")
        file_hash = _sha256(encoded)
        db.query(KnowledgeChunkRow).filter_by(document_id=document_id).delete()
        doc.version_no = (doc.version_no or 1) + 1
        chunk_objs = [
            KnowledgeChunkRow(
                chunk_id=new_id("knowledge_chunk"), document_id=document_id,
                version_no=doc.version_no, chunk_index=idx, content=ch,
                content_hash=_sha256(ch.encode("utf-8")), token_count=len(ch.split())
            )
            for idx, ch in enumerate(chunks)
        ]
        db.add_all(chunk_objs)
        doc.file_hash = file_hash
        doc.file_size = len(encoded)
        doc.status = DOC_STATUS_READY
        doc.error_message = None
        doc.error_details = None
        doc.chunk_count = len(chunk_objs)
        doc.processed_at = _now()
        doc.updated_at = _now()
    else:
        doc.updated_at = _now()

    db.commit()
    audit_svc.emit(tenant_id, corr, actor_type, actor_id, "knowledge.document.updated",
                   "document", document_id, "knowledge-svc",
                   after={"title": doc.title, "version_no": doc.version_no,
                          "chunk_count": doc.chunk_count, "status": doc.status})
    return {"document_id": doc.document_id, "title": doc.title, "original_filename": doc.original_filename,
            "version_no": doc.version_no, "status": doc.status, "chunk_count": doc.chunk_count,
            "message": "Dokumen pengetahuan berhasil diperbarui"}

def delete_document(db: Session, document_id: str, ctx: dict,
                    corr: str = "COR-?", tenant_id: str = "TNT-TEST") -> dict:
    """Hapus dokumen pengetahuan beserta seluruh potongan indeksnya dari tenant."""
    actor_id = ctx.get("actor_id", "system")
    actor_type = ctx.get("actor_type", "SYSTEM")
    doc = db.query(KnowledgeDocumentRow).filter_by(document_id=document_id, tenant_id=tenant_id).first()
    if not doc:
        raise AppError("E_NOT_FOUND", "dokumen tidak ditemukan",
                       customer_message_id="KM.DOCUMENT_NOT_FOUND")
    file_path = doc.file_path
    title = doc.title
    deleted_chunks = db.query(KnowledgeChunkRow).filter_by(document_id=document_id).delete()
    db.delete(doc)
    db.commit()

    if file_path and os.path.exists(file_path):
        still_used = db.query(KnowledgeDocumentRow).filter_by(file_path=file_path).first()
        if not still_used:
            try:
                os.remove(file_path)
            except OSError:
                pass

    audit_svc.emit(tenant_id, corr, actor_type, actor_id, "knowledge.document.deleted",
                   "document", document_id, "knowledge-svc",
                   after={"title": title, "deleted_chunks": deleted_chunks})
    return {"document_id": document_id, "deleted": True, "deleted_chunks": deleted_chunks,
            "message": "Dokumen pengetahuan berhasil dihapus"}

def list_documents(db: Session, tenant_id: str, status: str | None = None) -> list[dict]:
    query = db.query(KnowledgeDocumentRow).filter_by(tenant_id=tenant_id)
    if status:
        query = query.filter_by(status=status)
    rows = query.order_by(KnowledgeDocumentRow.created_at.desc()).all()
    return [{"document_id": r.document_id, "title": r.title, "original_filename": r.original_filename,
             "file_size": r.file_size, "mime_type": r.mime_type, "version_no": r.version_no,
             "status": r.status, "error_message": r.error_message, "chunk_count": r.chunk_count,
             "uploaded_by": r.uploaded_by, "created_at": r.created_at.isoformat() if r.created_at else None,
             "processed_at": r.processed_at.isoformat() if r.processed_at else None} for r in rows]


def create_article(db: Session, title: str, body: str, language: str = "id",
                   intents: list | None = None, access: str = "CUSTOMER",
                   expires_at: str | None = None, corr: str = "COR-?", tenant_id: str = "TNT-TEST") -> dict:
    if not expires_at:
        raise AppError("E_VALIDATION", "expiry required (BR-KM-01)",
                       customer_message_id="KM.EXPIRY_REQUIRED",
                       details=[{"field": "expires_at", "rule": "REQUIRED"}])
    aid = new_id("turn"); vid = new_id("turn")
    exp = datetime.datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    a = KnowledgeArticleRow(article_id=aid, tenant_id=tenant_id, title=title, summary=body[:200], language=language,
                            intents=intents or [], access_level=access, status="PUBLISHED",
                            current_version_id=vid, expires_at=exp)
    v = KnowledgeVersionRow(version_id=vid, article_id=aid, version_no=1, body=body,
                            status="PUBLISHED", expires_at=exp)
    db.add(a); db.add(v); db.commit()
    audit_svc.emit(tenant_id, corr, "HUMAN_AGENT", "km-manager", "knowledge.version_published",
                   "article", aid, "knowledge-svc")
    return {"article_id": aid, "version_id": vid}


def seed_baseline(db: Session, tenant_id: str = "TNT-TEST"):
    if db.query(KnowledgeArticleRow).filter_by(tenant_id=tenant_id).count() > 0: return
    base = [
        ("Biaya transfer internasional", "Biaya transfer internasional adalah Rp25.000 per transaksi. Berlaku sejak 2026-01-01.", "id", ["INFO_PRODUCT_POLICY"], "CUSTOMER", 365),
        ("International transfer fees", "International transfer fee is IDR 25,000 per transaction.", "en", ["INFO_PRODUCT_POLICY"], "CUSTOMER", 365),
        ("Syarat rekening koran", "Rekening koran dikirim ke email terdaftar dalam 1x24 jam. Butuh AL2.", "id", ["REQ_STATEMENT_DOCUMENT"], "CUSTOMER", 365),
        ("SOP sengketa transaksi", "Langkah: verifikasi AL2, buat kasus, minta bukti detail transaksi + surat pernyataan.", "id", ["CMP_TRANSACTION_DISPUTE"], "INTERNAL", 365),
        ("Ambang fraud internal", "Ambang tinjauan fraud adalah 50 juta. INTERNAL ONLY.", "id", ["CMP_FRAUD_SUSPICION"], "INTERNAL", 365),
        ("Promo kedaluwarsa", "Promo cashback 2024 telah berakhir.", "id", ["INFO_PRODUCT_POLICY"], "CUSTOMER", -10),
    ]
    for title, body, lang, intents, acc, exp_days in base:
        exp = _now() + datetime.timedelta(days=exp_days)
        aid, vid = new_id("turn"), new_id("turn")
        db.add(KnowledgeArticleRow(article_id=aid, tenant_id=tenant_id, title=title, summary=body[:200], language=lang,
                                   intents=intents, access_level=acc, status="PUBLISHED",
                                   current_version_id=vid, expires_at=exp))
        db.add(KnowledgeVersionRow(version_id=vid, article_id=aid, version_no=1, body=body,
                                   status="PUBLISHED", expires_at=exp))
    db.commit()

# ---- pencarian atas potongan dokumen (lexical) ----

def _score_text(query: str, text: str) -> float:
    q = query.lower()
    t = text.lower()
    words = [w for w in q.split() if len(w) > 2]
    if not words:
        return 0.0
    hits = sum(1 for w in words if w in t)
    title_boost = 0.0
    score = hits / max(1, len(words))
    return score

def search_chunks(db: Session, query: str, tenant_id: str, limit: int = 5,
                  language: str = "id", corr: str = "COR-?") -> list[dict]:
    """Cari potongan dokumen yang statusnya ready, bahasa id/en, skor keyword."""
    now = _now()
    words = _search_terms(query)
    scored = []
    rows = (db.query(KnowledgeChunkRow)
            .join(KnowledgeDocumentRow, KnowledgeChunkRow.document_id == KnowledgeDocumentRow.document_id)
            .filter(KnowledgeDocumentRow.tenant_id == tenant_id,
                    KnowledgeDocumentRow.status == DOC_STATUS_READY).all())
    for c in rows:
        body = (c.content or "").casefold()
        doc = db.query(KnowledgeDocumentRow).filter_by(document_id=c.document_id,
                                                        tenant_id=tenant_id).first()
        if not doc:
            continue
        title_terms = set(_search_terms(doc.title or ""))
        hits = sum(1 for w in words if w in body or w in title_terms)
        score = hits / max(1, len(words)) if words else 0.0
        if hits >= 1 and (score >= 0.20 or hits >= len(words) * 0.3 or hits >= 2):
            lang_boost = 0.1 if language == "id" else 0
            scored.append((min(1.0, score + lang_boost), c, doc))
    scored.sort(key=lambda x: -x[0])
    top = scored[:limit]
    results = []
    for s, c, doc in top:
        results.append({"document_id": c.document_id, "version_no": c.version_no,
                        "chunk_index": c.chunk_index, "title": doc.title if doc else "",
                        "original_filename": doc.original_filename if doc else "",
                        "passage_ref": f"chunk-{c.chunk_index}", "body": c.content,
                        "score": round(s, 3), "source_type": "document"})
    return results

# ---- pencarian gabungan (artikel + dokumen) ----

def search(db: Session, query: str, language: str = "id", for_agent: bool = False,
           corr: str = "COR-?", tenant_id: str = "TNT-TEST") -> dict:
    """Retrieval hibrida: artikel publik + potongan dokumen siap pakai, skor keyword, floor relevansi."""
    # Demo policy articles contain invented sample facts. They must never be
    # silently added to a real tenant's evidence corpus.
    if os.getenv("KNOWLEDGE_SEED_DEMO", "false").casefold() == "true":
        seed_baseline(db, tenant_id)
    now = _now()
    query_terms = _search_terms(query)
    allowed = ["PUBLIC", "CUSTOMER", "INTERNAL"] if for_agent else ["PUBLIC", "CUSTOMER"]
    scored = []
    # Artikel pengetahuan
    for a in db.query(KnowledgeArticleRow).filter_by(tenant_id=tenant_id).all():
        if a.status != "PUBLISHED": continue
        if a.access_level not in allowed: continue
        if _as_utc(a.expires_at) and _as_utc(a.expires_at) < now: continue
        v = db.query(KnowledgeVersionRow).filter_by(version_id=a.current_version_id).first()
        if not v: continue
        if v.status != "PUBLISHED": continue
        if _as_utc(v.effective_from) and _as_utc(v.effective_from) > now: continue
        if _as_utc(v.expires_at) and _as_utc(v.expires_at) < now: continue
        body = (v.body or "").casefold()
        title_terms = set(_search_terms(a.title or ""))
        hits = sum(1 for w in query_terms if w in body or w in title_terms)
        score = hits / max(1, len(query_terms)) if query_terms else 0.0
        if hits >= 1 and (score >= 0.20 or hits >= len(query_terms) * 0.3 or hits >= 2):
            lang_boost = 0.1 if a.language == language else 0
            scored.append((score + lang_boost, a, v, "article"))
    # Potongan dokumen siap pakai
    for c in db.query(KnowledgeChunkRow).join(KnowledgeDocumentRow,
                                              KnowledgeChunkRow.document_id == KnowledgeDocumentRow.document_id).filter(
            KnowledgeDocumentRow.tenant_id == tenant_id,
            KnowledgeDocumentRow.status == DOC_STATUS_READY).all():
        doc = db.query(KnowledgeDocumentRow).filter_by(document_id=c.document_id).first()
        if not doc: continue
        body = (c.content or "").casefold()
        words = query_terms
        title_terms = set(_search_terms(doc.title or ""))
        hits = sum(1 for w in words if w in body or w in title_terms)
        score = hits / max(1, len(words)) if words else 0.0
        if hits >= 1 and (score >= 0.20 or hits >= len(words) * 0.3 or hits >= 2):
            lang_boost = 0.1 if language == "id" else 0
            scored.append((score + lang_boost, c, doc, "document"))
    scored.sort(key=lambda x: -x[0])
    top = scored[:5]
    _logger.warning("knowledge_retrieval environment=%s database=%s tenant_id=%s query_terms=%d results=%d article_results=%d document_results=%d",
                 os.getenv("ENVIRONMENT", "unset"), safe_database_identity(), tenant_id,
                 len(query_terms), len(top),
                 sum(1 for _, _, _, kind in top if kind == "article"),
                 sum(1 for _, _, _, kind in top if kind == "document"))
    audit_svc.emit("TNT-TEST", corr, "SYSTEM", "rag-svc", "knowledge.retrieved",
                   "retrieval", corr, "retrieval-svc", after={"hits": len(top)})
    if not top:
        audit_svc.emit("TNT-TEST", corr, "SYSTEM", "rag-svc", "knowledge.gap_detected",
                       "retrieval", corr, "retrieval-svc")
        return {"results": [], "zero_result": True}
    results = []
    for s, item, ref, src in top:
        if src == "article":
            results.append({"article_id": item.article_id, "version_id": ref.version_id, "title": item.title,
                            "last_updated": (ref.effective_from.isoformat() if ref.effective_from else ""),
                            "passage_ref": "body", "body": ref.body, "score": round(s, 3),
                            "source_type": "article"})
        else:
            results.append({"document_id": item.document_id, "version_no": item.version_no,
                            "chunk_index": item.chunk_index, "title": ref.title,
                            "original_filename": ref.original_filename,
                            "last_updated": (ref.created_at.isoformat() if ref.created_at else ""),
                            "passage_ref": f"chunk-{item.chunk_index}", "body": item.content,
                            "score": round(s, 3), "source_type": "document"})
    return {"results": results, "zero_result": False}

def cite(results: list) -> list:
    out = []
    for r in results:
        if r.get("source_type") == "document":
            out.append({"document_id": r["document_id"], "version_no": r["version_no"],
                        "chunk_index": r["chunk_index"], "title": r["title"],
                        "original_filename": r.get("original_filename", ""),
                        "last_updated": r.get("last_updated", ""),
                        "passage_ref": r["passage_ref"], "retrieval_score": r["score"],
                        "source_type": "document"})
        else:
            out.append({"article_id": r["article_id"], "version_id": r["version_id"], "title": r["title"],
                        "last_updated": r["last_updated"], "passage_ref": r["passage_ref"],
                        "retrieval_score": r["score"], "source_type": "article"})
    return out
