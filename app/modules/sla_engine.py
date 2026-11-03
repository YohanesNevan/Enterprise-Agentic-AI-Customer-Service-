"""TRD §4.15 Mesin SLA — satu implementasi kalender kerja (ADR-12). FR-SLA-001..008."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from ..contracts.vocabularies import Severity

# FRD §13.5 default (disederhanakan, jam kerja Asia/Jakarta Sen–Jum 08:00–17:00)
DEFAULT_TARGETS = {
    ("TICKET", "GENERAL", "LOW"): (240, 48),
    ("TICKET", "GENERAL", "MEDIUM"): (120, 24),
    ("CASE", "TRANSACTION_DISPUTE", "HIGH"): (120, 72),
    ("CASE", "TRANSACTION_DISPUTE", "CRITICAL"): (30, 24),
    ("CASE", "GENERAL", "LOW"): (480, 120),
    ("CASE", "GENERAL", "MEDIUM"): (240, 72),
    ("CASE", "GENERAL", "HIGH"): (120, 48),
}
CAL_ID = "CAL-JKT-STD"
CONFIG_VERSION = "1.2.0"
JKT = ZoneInfo("Asia/Jakarta")

def _is_work_time(dt_jkt: datetime) -> bool:
    if dt_jkt.weekday() >= 5: return False
    return 8 <= dt_jkt.hour < 17

def add_business_minutes(start_utc: datetime, minutes: int) -> datetime:
    cur = start_utc.astimezone(JKT)
    remaining = minutes
    while remaining > 0:
        if _is_work_time(cur): remaining -= 1
        cur += timedelta(minutes=1)
    # mundur 1 menit karena loop overshoot
    cur -= timedelta(minutes=1)
    return cur.astimezone(timezone.utc)

def calculate(object_type: str, category: str, severity: str | Severity,
              created_at: datetime, timezone_name: str = "Asia/Jakarta") -> dict:
    sev = severity.value if isinstance(severity, Severity) else severity
    key = (object_type, category, sev)
    fr, reso = DEFAULT_TARGETS.get(key, (240, 72))
    is_default = key not in DEFAULT_TARGETS
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    fr_due = add_business_minutes(created_at, fr)
    reso_due = add_business_minutes(created_at, reso * 60)
    expl = (f"Logged {created_at.astimezone(JKT):%A %H:%M} local; "
            f"{fr} business-min to first response.")
    return {"first_response_due_at": fr_due.isoformat(),
            "update_cadence_hours": 24,
            "resolution_due_at": reso_due.isoformat(),
            "calendar_id": CAL_ID, "sla_config_version": CONFIG_VERSION,
            "is_default": is_default, "explanation": expl}
