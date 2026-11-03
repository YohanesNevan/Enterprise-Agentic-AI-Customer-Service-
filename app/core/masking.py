"""FR-SEC-003 klasifikasi + masking. SECRET tidak pernah keluar."""
def mask_account(n: str) -> str: return "****" + (n[-4:] if n else "----")
def mask_email(e: str) -> str:
    try: u, d = e.split("@"); return f"{u[:1]}***@{d[:1]}***.test"
    except Exception: return "***"
def mask_phone(p: str) -> str: return "+62***" + (p[-4:] if p else "----")
def masked_args(d: dict) -> dict:
    out = {}
    for k, v in (d or {}).items():
        if any(s in k for s in ("account", "card", "otp", "token", "key", "secret")):
            out[k] = "***"
        else: out[k] = v
    return out
