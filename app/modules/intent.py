"""FR-INT-001..009 [A]: klasifikasi taksonomi tertutup, multi-intent, klarifikasi max 2,
ambang 0.75/0.45, konteks slot+ringkasan, sentimen/urgensi, kerentanan, kontak berulang.
TRD §4.5: dua tahap disederhanakan jadi rule terkalibrasi + validasi enum (BR-INT-01)."""
from __future__ import annotations
import re
from ..core.ids import new_id
from ..core import audit as audit_svc

TAXONOMY = ["INFO_PRODUCT_POLICY", "INFO_ACCOUNT_BALANCE", "INFO_TRANSACTION_HISTORY",
            "INFO_CASE_STATUS", "REQ_STATEMENT_DOCUMENT", "REQ_CARD_BLOCK",
            "REQ_CARD_REPLACEMENT", "REQ_LIMIT_CHANGE", "REQ_PROFILE_UPDATE",
            "CMP_TRANSACTION_DISPUTE", "CMP_SERVICE_FAILURE", "CMP_STAFF_CONDUCT",
            "CMP_FRAUD_SUSPICION", "GEN_SMALL_TALK_OTHER"]
CATEGORY = {"INFO_PRODUCT_POLICY": "INQUIRY", "INFO_ACCOUNT_BALANCE": "INQUIRY",
            "INFO_TRANSACTION_HISTORY": "INQUIRY", "INFO_CASE_STATUS": "INQUIRY",
            "REQ_STATEMENT_DOCUMENT": "REQUEST", "REQ_CARD_BLOCK": "REQUEST",
            "REQ_CARD_REPLACEMENT": "REQUEST", "REQ_LIMIT_CHANGE": "REQUEST",
            "REQ_PROFILE_UPDATE": "REQUEST", "CMP_TRANSACTION_DISPUTE": "COMPLAINT",
            "CMP_SERVICE_FAILURE": "COMPLAINT", "CMP_STAFF_CONDUCT": "COMPLAINT",
            "CMP_FRAUD_SUSPICION": "COMPLAINT", "GEN_SMALL_TALK_OTHER": "INQUIRY"}
MANDATORY_HANDOFF = {"CMP_FRAUD_SUSPICION", "CMP_STAFF_CONDUCT"}
ACT_T, CLAR_FLOOR = 0.75, 0.45

KEYWORDS = {
    # Include the exact supported seed-article topic as a phrase. A single
    # broad token ("biaya") otherwise stays in CLARIFY despite a clear query.
    "INFO_PRODUCT_POLICY": ["biaya", "biaya transfer", "transfer internasional", "fee", "bunga", "syarat", "ketentuan", "policy", "tarif"],
    "INFO_ACCOUNT_BALANCE": ["saldo", "balance", "dana tersedia", "sisa uang", "sisa saldo", "cek saldo", "informasi saldo", "saldo rekening"],
    "INFO_TRANSACTION_HISTORY": ["transaksi", "mutasi", "riwayat", "history", "transaction"],
    "INFO_CASE_STATUS": ["status", "tiket", "kasus", "referensi", "reference", "laporan saya"],
    "REQ_STATEMENT_DOCUMENT": ["rekening koran", "statement", "surat", "sertifikat", "dokumen"],
    "REQ_CARD_BLOCK": ["blokir", "block", "hilang", "dicuri", "kartu hilang"],
    "REQ_CARD_REPLACEMENT": ["ganti kartu", "replacement", "kartu baru", "penggantian kartu"],
    "REQ_LIMIT_CHANGE": ["limit", "batas", "naikkan limit", "ubah limit"],
    "REQ_PROFILE_UPDATE": ["alamat", "address", "update profil", "ubah data", "nomor hp", "email baru"],
    "CMP_TRANSACTION_DISPUTE": ["tidak kenal", "tidak merasa", "dispute", "sengketa", "salah debet", "ditolak", "gagal transfer"],
    "CMP_SERVICE_FAILURE": ["gagal", "error", "tidak bisa", "lemot", "gangguan", "rusak"],
    "CMP_STAFF_CONDUCT": ["petugas kasar", "staff", "cs jutek", "pelayanan buruk", "komplain petugas"],
    "CMP_FRAUD_SUSPICION": ["penipuan", "fraud", "dipaksa", "ditipu", "scam", "phising", "phishing"],
    "GEN_SMALL_TALK_OTHER": ["halo", "hai", "pagi", "siang", "sore", "malam",
                             "permisi", "terima kasih", "thanks", "hello", "hi"],
}
_contexts: dict[str, dict] = {}

_GREETING_TOKEN = r"(?:halo|hallo|helo|hello|hai|hay|hi|hii|hey|permisi|selamat\s+(?:pagi|siang|sore|malam|malem))"
_GREETING_PREFIX = re.compile(rf"^\s*{_GREETING_TOKEN}\b", re.IGNORECASE)


def _strip_greeting_prefix(text: str) -> str:
    """Remove leading salutations so mixed turns classify by their question/action."""
    remainder = (text or "").strip()
    while True:
        match = _GREETING_PREFIX.match(remainder)
        if not match:
            break
        remainder = remainder[match.end():].lstrip(" \t,.;:!?—–-")
    return remainder


def _is_greeting_only(text: str) -> bool:
    remainder = _strip_greeting_prefix(text)
    normalized = re.sub(r"[\s,.;:!?—–-]+", " ", remainder.casefold()).strip()
    if not normalized:
        return True
    return normalized in {"apa kabar", "ada orang", "tes ada orang", "test ada orang",
                          "testing ada orang", "ada orang ya", "ada orang di sana"}

def _info_request_phrase(t: str) -> bool:
    """Imperative information requests ("beritahu saya profil perusahaan") are retrieval questions,
    not unknown intents. Retrieval + grounding still decide whether an answer or a knowledge-gap handoff follows."""
    return bool(re.search(
        r"\b(?:beritahu|beri\s+tahu|ceritakan|sebutkan|jelaskan|informasikan|tolong\s+jelaskan|"
        r"saya\s+(?:ingin|mau|butuh)\s+(?:tahu|mengetahui|informasi)|info(?:rmasi)?\s+(?:tentang|mengenai|soal))\b"
        r"|\b(?:profil|sejarah|visi|misi|latar\s+belakang)\s+(?:perusahaan|bank|kami|ini)\b", t))


def _human_agent_requested(text: str) -> bool:
    import re
    t = (text or "").casefold()
    patterns = (
        r"\b(?:bicara|ngobrol|terhubung|sambung|sambungkan|hubungkan|berbicara)\s+(?:ke\s+|dengan\s+|sama\s+)?(?:petugas|manusia|cs|customer service|staf|staff|operator|agen)\b",
        r"\b(?:butuh|minta|ingin|mau)\s+(?:bantuan\s+)?(?:petugas|manusia|cs|customer service|staf|staff|operator|agen)\b",
        r"\b(?:petugas|manusia|customer service|operator)\s+(?:saja|asli|langsung)\b",
        r"\btransfer\s+(?:ke\s+)?(?:manusia|petugas|operator|cs)\b",
        r"\bbicara\s+langsung\b",
    )
    return any(re.search(p, t) for p in patterns)

def _human_action_requested(text: str) -> bool:
    """Only route to a human when the customer asks us to execute a restricted action."""
    import re
    t = (text or "").casefold()
    action_patterns = (
        r"\b(?:tolong\s+)?(?:proses|ajukan|lakukan|eksekusi|jalankan)\s+(?:permintaan\s+)?refund\b",
        r"\b(?:saya|kami)\s+(?:ingin|minta)\s+refund\b",
        r"\b(?:kembalikan|balikkan)\s+(?:dana|uang)\b",
        r"\b(?:batalkan|reversal)\s+(?:transaksi|transfer)\b",
    )
    return any(re.search(pattern, t) for pattern in action_patterns)

def _repeat_contact_explicit(text: str) -> bool:
    """Escalate explicit unresolved repeat-contact signals, not message frequency."""
    t = (text or "").casefold()
    return any(phrase in t for phrase in (
        "sudah bertanya berkali-kali", "sudah menghubungi berkali-kali",
        "sudah beberapa kali menghubungi", "sudah berulang kali bertanya",
        "masih belum dibantu", "sudah tanya berkali-kali",
    ))

def _score(text: str, words: list[str]) -> float:
    t = text.lower()
    hits = sum(1 for w in words if w in t)
    if not hits: return 0.0
    return min(0.95, 0.55 + 0.15 * hits)

def sentiment(text: str) -> tuple[str, str]:
    t = text.lower()
    very_neg = ["kecewa berat", "marah", "benci", "parah", "ancam", "lapor polisi", "viral"]
    neg = ["kecewa", "kesal", "lama", "buruk", "gagal", "bodoh"]
    if any(w in t for w in very_neg): s = "very_negative"
    elif any(w in t for w in neg): s = "negative"
    elif any(w in t for w in ["terima kasih", "bagus", "puas", "thanks"]): s = "positive"
    else: s = "neutral"
    urg = "high" if any(w in t for w in ["segera", "urgent", "darurat", "sekarang", "dipaksa"]) else ("medium" if s in ("negative", "very_negative") else "low")
    return s, urg

def vulnerability(text: str) -> tuple[bool, bool, str | None]:
    t = text.lower()
    if any(w in t for w in ["dipaksa", "diancam", "disandera", "bunuh", "menyakiti diri", "self-harm"]):
        return True, True, "SAFETY"
    if any(w in t for w in ["dipaksa transfer", "ditipu", "pinjol", "tidak makan", "phk", "bangkrut"]):
        return True, False, "VULNERABILITY"
    return False, False, None

def classify(text: str, conversation_id: str, corr: str = "COR-?") -> dict:
    """Mengembalikan intent primer + sekunder, confidence, decision ACT/CLARIFY/HANDOFF."""
    scores = {k: _score(text, v) for k, v in KEYWORDS.items()}
    ranked = sorted(scores.items(), key=lambda x: -x[1])
    top, top_c = ranked[0]
    second, second_c = ranked[1]
    # Questions asking for information belong to retrieval even when the topic is
    # not in the closed action taxonomy (e.g. "Apa itu NPB?"). Keep explicit
    # complaint, fraud, staff-conduct, and vulnerability routing in control.
    t = text.casefold().strip()
    human_action = _human_action_requested(t)
    human_agent_req = _human_agent_requested(t)
    reverse_what_question = bool(re.search(r"\b[\w-]+\s+itu\s+apa[?.!]*$", t))
    generic_question = (top_c < 0.30 and len(t.split()) >= 3 and t.endswith("?")
                        and not human_action)
    informational = (t.startswith(("apa ", "apa?", "bagaimana ", "bagaimana?", "berapa ",
                                   "berapa?", "bolehkah ", "apakah ", "siapa ", "kapan ",
                                   "di mana ", "dimana ", "mengapa ", "mengapa?", "kenapa ",
                                   "kenapa?", "jelaskan ", "maksudnya ", "what ", "how ",
                                   "where ", "why "))
                     or any(p in t for p in ("apa itu ", "apa yang harus saya lakukan", "bagaimana bisa "))
                     or _info_request_phrase(t)
                     or reverse_what_question or generic_question)
    forced_intents = {"CMP_FRAUD_SUSPICION", "CMP_STAFF_CONDUCT"}
    dispute_patterns = (
        r"\b(?:saldo|dana|uang)\b.*\b(?:terpotong|kepotong|berkurang|hilang)\b",
        r"\b(?:uang|dana)\b.*\b(?:tidak|gak|nggak|belum)\b.*\b(?:keluar|masuk|sampai)\b",
        r"\b(?:gagal|batal|error)\b.*\b(?:tarik|transfer|debet|debit|kirim)\b",
        r"\btransaksi\b.*\bgagal\b",
        r"\bsalah\b.*\bdebet\b",
    )
    is_dispute = any(re.search(p, t, re.IGNORECASE) for p in dispute_patterns) or any(
        s in t for s in ("gagal transfer", "transaksi gagal", "salah debet", "saldo kepotong", "saldo berkurang", "saldo terpotong", "tidak masuk")
    )
    if human_action:
        top, top_c, second_c = "CMP_TRANSACTION_DISPUTE", 0.95, 0.0
    elif is_dispute:
        top, top_c, second_c = "CMP_TRANSACTION_DISPUTE", 0.90, 0.0
    elif informational and top not in forced_intents and not any(w in t for w in ("ditipu", "penipuan", "diancam", "dipaksa", "saldo", "rekening", "blokir", "mutasi")):
        top, top_c, second_c = "INFO_PRODUCT_POLICY", 0.80, 0.0
    # di luar taksonomi atau permintaan langsung bantuan manusia
    if human_agent_req:
        res = {"intent_code": "OTHER_UNCLASSIFIED", "category": "INQUIRY", "confidence": 0.95,
               "decision": "HANDOFF", "handoff_reason": "CUSTOMER_REQUEST", "entities": {}, "multi": []}
    elif top_c < 0.30:
        res = {"intent_code": "OTHER_UNCLASSIFIED", "category": "INQUIRY", "confidence": 0.30,
               "decision": "HANDOFF", "entities": {}, "multi": []}
    else:
        # hampir-seri dalam 0.10 -> paksa klarifikasi (TRD §4.5)
        near_tie = (top_c - second_c) < 0.10 and second_c >= 0.45
        if human_agent_req:
            dec = "HANDOFF"
        elif human_action:
            dec = "HANDOFF"
        elif top in MANDATORY_HANDOFF:
            dec = "HANDOFF"
        elif top == "GEN_SMALL_TALK_OTHER" and top_c >= CLAR_FLOOR:
            dec = "ACT"
        elif near_tie:
            dec = "CLARIFY"
        elif top_c >= ACT_T: dec = "ACT"
        elif top_c >= CLAR_FLOOR: dec = "CLARIFY"
        else: dec = "HANDOFF"
        multi = []
        if second_c >= ACT_T and second != top:
            multi = [{"intent_code": second, "confidence": second_c}]
        res = {"intent_code": top, "category": CATEGORY[top], "confidence": round(top_c, 3),
               "decision": dec, "entities": _slots(text), "multi": multi}
    # klarifikasi count max 2
    ctx = _contexts.setdefault(conversation_id, {"clarification_count": 0, "slots": {}, "summary": ""})
    if res["decision"] == "CLARIFY":
        if ctx["clarification_count"] >= 2:
            res["decision"] = "HANDOFF"; res["handoff_reason"] = "LOW_CONFIDENCE"
    s, urg = sentiment(text)
    vuln, safety, sig = vulnerability(text)
    if vuln or safety:
        res["decision"] = "HANDOFF"; res["handoff_reason"] = "VULNERABILITY"
        res["vulnerability_flag"] = True
    res.update({"sentiment": s, "urgency": urg, "safety_flag": safety})
    if res.get("vulnerability_flag"):
        res["handoff_reason"] = "VULNERABILITY"
    elif human_agent_req:
        res["decision"] = "HANDOFF"
        res["handoff_reason"] = "CUSTOMER_REQUEST"
    elif human_action:
        res["handoff_reason"] = "HUMAN_ACTION_REQUIRED"
    elif _repeat_contact_explicit(text):
        res["decision"] = "HANDOFF"; res["handoff_reason"] = "REPEAT_CONTACT"
    elif informational and res["decision"] != "HANDOFF":
        res["routing_reason"] = "INFORMATIONAL_INQUIRY"
    elif res["decision"] == "HANDOFF":
        res["handoff_reason"] = res.get("handoff_reason", "INTENT_REQUIRES_HANDOFF")
    else:
        res["routing_reason"] = "CLASSIFIED_INTENT"
    audit_svc.emit("TNT-TEST", corr, "SYSTEM", "intent-svc", "intent.classified",
                   "message", conversation_id, "intent-svc", conversation_id=conversation_id,
                   after={"intent": res["intent_code"], "conf": res["confidence"], "decision": res["decision"],
                          "routing_reason": res.get("handoff_reason", res.get("routing_reason"))})
    return res

def _slots(text: str) -> dict:
    import re
    t = (text or "").lower()
    out = {}
    m2 = re.search(r"(trx|ref|transaksi|tx)[-:\s#]*([a-zA-Z0-9_-]+)", t)
    if m2:
        out["reference"] = m2.group(2).upper()
    else:
        m_code = re.search(r"\b(trx-?[a-zA-Z0-9]+|ref-?[a-zA-Z0-9]+)\b", t, re.IGNORECASE)
        if m_code:
            out["reference"] = m_code.group(1).upper()

    m = re.search(r"(\d{4})(?!.*\d)", text or "")
    if m and "kartu" in t:
        out["card_last4"] = m.group(1)
    elif m and not out.get("reference"):
        out["card_last4"] = m.group(1)

    m_amt = re.search(r"(?:rp\.?\s*|sebesar\s+|senilai\s+)(\d{1,3}(?:[.,]\d{3})*|\d+)", t)
    if not m_amt:
        m_amt = re.search(r"\b(\d+)\s*(?:ribu|rb|juta|jt)\b", t)
    if m_amt:
        raw_amt = m_amt.group(1).replace(".", "").replace(",", "")
        out["amount"] = raw_amt
    if "besok" in t: out["date_hint"] = "tomorrow"
    return out

def update_context(conversation_id: str, text: str, cls: dict) -> dict:
    ctx = _contexts.setdefault(conversation_id, {"clarification_count": 0, "slots": {}, "summary": ""})
    if cls["decision"] == "CLARIFY":
        ctx["clarification_count"] += 1
    else:
        ctx["clarification_count"] = 0
    ctx["slots"].update(cls.get("entities", {}))
    # ringkasan bergulir: tanpa fakta baru (BR-INT-08) — potong 300 char
    ctx["summary"] = (ctx["summary"] + " | " + text.strip())[-300:]
    return ctx

def get_context(conversation_id: str) -> dict:
    return _contexts.get(conversation_id, {"clarification_count": 0, "slots": {}, "summary": ""})
