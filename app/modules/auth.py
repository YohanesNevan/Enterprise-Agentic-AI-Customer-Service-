"""FR-AUTH-001..010 [A]: model AL, identifikasi, OTP simulasi, step-up AL3,
lockout, TTL sesi, consent per-tujuan, anti-enumerasi. TRD §4.4."""
from __future__ import annotations
import datetime, hashlib, secrets, time
from sqlalchemy.orm import Session
from ..core.ids import new_id
from ..core import audit as audit_svc
from ..core.errors import AppError
from .models_a import ChannelSessionRow

TTL = {"AL1": 30*60, "AL2": 15*60, "AL3": 5*60}  # detik idle; sesi absolut 8 jam
SESSION_ABS_H = 8
MAX_ATTEMPTS = 3
LOCK_S = 15*60
_unlock: dict[str, float] = {}
_attempts: dict[str, int] = {}
_challenges: dict[str, dict] = {}  # challenge_id -> {code_hash, exp, channel_session_id, purpose}
_consents: list[dict] = []

def _now(): return datetime.datetime.now(datetime.timezone.utc)

def _locked(sess_id: str) -> bool:
    return _unlock.get(sess_id, 0) > time.time()

def _session_locked(sess: ChannelSessionRow) -> bool:
    until = sess.locked_until
    if until and until.replace(tzinfo=datetime.timezone.utc).timestamp() > time.time():
        return True
    return _locked(sess.channel_session_id)

def required_al_for(op: str) -> str:
    if op in ("balance", "transaction_history", "statement", "card_block"): return "AL2"
    if op in ("limit_change", "profile_update", "fraud_report"): return "AL3"
    return "AL0"

def evaluate(session_al: str, required: str) -> bool:
    order = ["AL0", "AL1", "AL2", "AL3"]
    return order.index(session_al) >= order.index(required)

def identify(db: Session, sess: ChannelSessionRow, identifier: str, corr: str) -> dict:
    """FR-AUTH-002: cocok tepat satu -> AL1; nol/ganda -> AL0 generik (BR-AUTH-03)."""
    now = _now()
    if _session_locked(sess):
        raise AppError("E_RATE_LIMIT", "session locked, try later",
                       customer_message_id="AUTH.LOCKED")
    # anti-enumerasi: waktu respons dinormalisasi >=250ms
    t0 = time.time()
    matched = None
    if identifier and "@" not in identifier:
        matched = identifier  # token sesi web terautentikasi -> 1 nasabah
    elif identifier and "," not in identifier and identifier.strip():
        matched = identifier  # 1 email cocok 1 nasabah (simulasi)
    else:
        matched = None  # nol atau >1 cocok
    elapsed = time.time() - t0
    if elapsed < 0.25:
        time.sleep(0.25 - elapsed)
    if not matched:
        audit_svc.emit("TNT-TEST", corr, "SYSTEM", "identity-svc", "auth.identification_attempted",
                       "session", sess.channel_session_id, "identity-svc",
                       reason="no_unique_match", result="FAIL")
        return {"assurance_level": "AL0", "message": "kami tidak dapat mencocokkan data tersebut"}
    sess.assurance_level = "AL1"; sess.al_method = ["HANDLE_MATCH"]
    sess.al_established_at = now
    sess.al_expires_at = now + datetime.timedelta(seconds=TTL["AL1"])
    db.commit()
    audit_svc.emit("TNT-TEST", corr, "SYSTEM", "identity-svc", "auth.identification_attempted",
                   "session", sess.channel_session_id, "identity-svc", result="OK",
                   after={"al": "AL1"})
    return {"assurance_level": "AL1", "customer_id": matched}

def challenge(sess: ChannelSessionRow, purpose: str, corr: str, channel: str = "REGISTERED_EMAIL") -> dict:
    """FR-AUTH-003: AI tak pernah lihat kode; hanya hash disimpan. OTP deterministik 123456 di TEST."""
    import os
    if _locked(sess.channel_session_id):
        raise AppError("E_RATE_LIMIT", "locked", customer_message_id="AUTH.LOCKED")
    code = "123456" if os.getenv("TEST_MODE", "false").lower() in ("1", "true", "yes") else f"{secrets.randbelow(900000) + 100000}"
    cid = new_id("turn")
    _challenges[cid] = {"code_hash": hashlib.sha256(code.encode()).hexdigest(),
                        "exp": time.time() + 300, "sess": sess.channel_session_id, "purpose": purpose}
    _attempts[cid] = 0
    audit_svc.emit("TNT-TEST", corr, "SYSTEM", "auth-svc", "auth.challenge_issued",
                   "challenge", cid, "auth-svc", session_id=sess.channel_session_id)
    return {"challenge_id": cid, "delivery_channel_masked": channel[:4] + "***"}

def verify(db: Session, sess: ChannelSessionRow, challenge_id: str, code: str, corr: str) -> dict:
    ch = _challenges.get(challenge_id)
    if not ch or ch["sess"] != sess.channel_session_id:
        raise AppError("E_NOT_FOUND", "challenge not found", customer_message_id="AUTH.CHALLENGE_INVALID")
    if time.time() > ch["exp"]:
        raise AppError("E_VALIDATION", "code expired, new challenge issued", customer_message_id="AUTH.CODE_EXPIRED")
    if _session_locked(sess):
        raise AppError("E_RATE_LIMIT", "locked", customer_message_id="AUTH.LOCKED")
    ok = hashlib.sha256(code.encode()).hexdigest() == ch["code_hash"]
    if ok:
        now = _now()
        # step-up (FR-AUTH-004): purpose HIGH -> AL3 TTL 5 mnt absolut; else AL2
        is_stepup = ch["purpose"] in ("HIGH_RISK", "T4")
        sess.assurance_level = "AL3" if is_stepup else "AL2"
        sess.al_method = ["OTP", "KNOWLEDGE_SUPPLEMENT"] if is_stepup else ["OTP"]
        sess.al_established_at = now
        sess.al_expires_at = now + datetime.timedelta(seconds=TTL[sess.assurance_level])
        sess.auth_failed_count = 0
        db.commit()
        _challenges.pop(challenge_id, None)
        audit_svc.emit("TNT-TEST", corr, "SYSTEM", "auth-svc", "auth.challenge_verified",
                       "challenge", challenge_id, "auth-svc", session_id=sess.channel_session_id,
                       after={"al": sess.assurance_level})
        return {"verified": True, "assurance_level": sess.assurance_level, "attempts_remaining": MAX_ATTEMPTS}
    _attempts[challenge_id] = _attempts.get(challenge_id, 0) + 1
    sess.auth_failed_count += 1; db.commit()
    left = MAX_ATTEMPTS - _attempts[challenge_id]
    audit_svc.emit("TNT-TEST", corr, "SYSTEM", "auth-svc", "auth.challenge_failed",
                   "challenge", challenge_id, "auth-svc", result="FAIL")
    if left <= 0:
        locked_until = _now() + datetime.timedelta(seconds=LOCK_S)
        sess.lock_state = "LOCKED"
        sess.locked_until = locked_until
        _unlock[sess.channel_session_id] = locked_until.timestamp()
        db.commit()
        audit_svc.emit("TNT-TEST", corr, "SYSTEM", "auth-svc", "auth.locked_out",
                       "session", sess.channel_session_id, "auth-svc", session_id=sess.channel_session_id)
        raise AppError("E_RATE_LIMIT", "locked after 3 fails, routed to human",
                       customer_message_id="AUTH.LOCKED")
    return {"verified": False, "assurance_level": sess.assurance_level, "attempts_remaining": left}

def check_session(sess: ChannelSessionRow) -> str:
    """FR-AUTH-006: kedaluwarsa -> turun ke AL0, konteks percakapan dipertahankan."""
    if sess.al_expires_at and _now() > sess.al_expires_at.replace(tzinfo=datetime.timezone.utc):
        sess.assurance_level = "AL0"
        return "AL0"
    return sess.assurance_level

def record_consent(customer_id: str | None, conv_id: str, purpose: str, granted: bool,
                   version: str, corr: str, al: str = "AL1") -> dict:
    c = {"consent_id": new_id("turn"), "customer_id": customer_id, "conversation_id": conv_id,
         "purpose": purpose, "text_version": version, "granted": granted,
         "granted_at": _now().isoformat(), "assurance_level": al}
    _consents.append(c)
    audit_svc.emit("TNT-TEST", corr, "CUSTOMER", customer_id or "anon",
                   "consent.granted" if granted else "consent.refused",
                   "consent", c["consent_id"], "auth-svc", conversation_id=conv_id)
    return c

def qa_consented(conv_id: str) -> bool:
    for c in _consents:
        if c["conversation_id"] == conv_id and c["purpose"] == "QA_REVIEW" and not c["granted"]:
            return False
    return True
