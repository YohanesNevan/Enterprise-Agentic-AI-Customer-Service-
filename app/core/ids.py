"""TRD §16.1 Kontrak identitas — ULID + prefiks tipe. ADR-13 tenancy."""
from __future__ import annotations
import re

_PREFIXES = {
    "customer": "CUS-", "conversation": "CNV-", "channel_session": "CHS-",
    "message": "MSG-", "intent": "INT-", "tool_call": "TLC-",
    "policy_decision": "PDC-", "ticket": "TKT-", "case": "CAS-",
    "evidence_request": "EVR-", "evidence": "EVI-", "handoff": "HDO-",
    "approval": "APR-", "sla": "SLA-", "escalation": "ESC-",
    "qa_review": "QAR-", "audit": "AUD-", "correlation": "COR-",
    "turn": "TRN-", "knowledge_document": "KDO-", "knowledge_chunk": "KCH-",
}

_ULID_RE = re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}$")

def new_id(kind: str) -> str:
    """Buat ID baru: PREFIX + ULID(26). kind wajib ada di _PREFIXES (ID-2)."""
    if kind not in _PREFIXES:
        raise ValueError(f"unknown id kind: {kind}")
    try:
        import ulid as ulid_pkg
        raw = str(ulid_pkg.new())
    except Exception:
        # fallback deterministik sederhana (bukan ULID murni, cukup untuk skeleton)
        import time, random, string
        alphabet = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
        raw = "".join(random.choice(alphabet) for _ in range(26))
    return f"{_PREFIXES[kind]}{raw}"

def short_reference(kind: str, suffix: str) -> str:
    """ID-5: referensi pendek ber-checksum untuk nasabah. C-XXXX-NN / T-XXXX-NN."""
    base = suffix.replace("-", "")[:4].upper().ljust(4, "X")
    check = sum(ord(c) for c in suffix) % 97
    prefix = "C" if kind == "case" else "T"
    return f"{prefix}-{base}-{check:02d}"

def assert_valid(prefix: str, value: str) -> None:
    assert value.startswith(prefix), f"{value} harus berprefiks {prefix}"
    assert _ULID_RE.match(value[len(prefix):]), f"{value} bukan ULID valid"
