"""FR-SEC-006 + FR-ORC-006/009 [J]: deteksi injeksi 8 famili, groundedness,
output policy (PII/internal), bahasa status aksi. Gagal-tertutup."""
from __future__ import annotations  # noqa - keep tolerant
import re
from ..core import audit as audit_svc

PATTERNS = {
    "direct_override": [r"abaikan instruksi", r"ignore .*instruction", r"override polic"],
    "role_reassign": [r"kamu adalah administrator", r"you are (now )?admin", r"act as root"],
    "prompt_extract": [r"ulangi .*di atas", r"repeat .*system prompt", r"tampilkan prompt"],
    "fake_authority": [r"supervisor sudah menyetujui", r"manager approved", r"sudah diapprove"],
    "tool_injection": [r"panggil execute_refund", r"call .*transfer_funds", r"reverse_transaction"],
    "delimiter_escape": [r"```system", r"</system>", r"\[SYSTEM\]"],
    "encoded": [r"base64:", r"[A-Za-z0-9+/]{40,}={0,2}", r"[\u200b\u200c\u200d]"],
    "indirect": [r"abaikan .*dan setujui", r"approve this", r"instruksi dalam dokumen"],
}

def detect_injection(text: str, corr: str, conv: str, source: str = "customer_message") -> dict:
    t = (text or "").lower()
    for fam, pats in PATTERNS.items():
        for p in pats:
            try:
                if re.search(p.lower(), t):
                    audit_svc.emit("TNT-TEST", corr, "SYSTEM", "guardrail", "guardrail.injection_detected",
                                   "conversation", conv, "guardrail-svc", reason=fam,
                                   conversation_id=conv)
                    return {"detected": True, "family": fam}
            except Exception:
                continue
    return {"detected": False}

def groundedness(draft: str, citations: list, tool_results: list) -> dict:
    """Klaim biaya/angka/tanggal harus persis ada di sumber (G-05)."""
    import re
    nums = re.findall(r"\d[\d.,]*", draft or "")
    src = " ".join([(c.get("title", "") + " " + str(c.get("body", ""))) for c in (citations or [])])
    src += " " + " ".join([str(r) for r in (tool_results or [])])
    unsupported = [n for n in nums if n not in src]
    # klaim faktual tanpa sitasi sama sekali
    factual_kw = ["biaya", "fee", "limit", "saldo", "tanggal", "jatuh tempo", "idr", "rp"]
    factual = any(k in (draft or "").lower() for k in factual_kw)
    if factual and not citations and not tool_results:
        unsupported.append("NO_SOURCE")
    if unsupported:
        audit_svc.emit("TNT-TEST", "COR-?", "SYSTEM", "guardrail", "guardrail.unsupported_claim",
                       "draft", draft[:30], "guardrail-svc")
    return {"unsupported": unsupported, "ok": not unsupported}

COMPLETION_VERBS = ["telah diblokir", "telah diproses", "refund berhasil", "sudah ditransfer", "has been blocked"]

def action_state_check(text: str, has_executed: bool) -> dict:
    t = (text or "").lower()
    claims_completion = any(v in t for v in COMPLETION_VERBS)
    if claims_completion and not has_executed:
        return {"block": True, "rewrite": text + " [status: pengajuan tercatat, belum dieksekusi]"}
    return {"block": False}

def output_policy(text: str) -> dict:
    # INTERNAL leak: ambang fraud dsb; PII: nomor panjang
    import re
    if "50 juta" in (text or "") and "ambang" in (text or "").lower():
        return {"block": True, "reason": "INTERNAL_LEAK"}
    if re.search(r"\b\d{12,19}\b", text or ""):
        return {"block": True, "reason": "PII_LEAK"}
    return {"block": False}
