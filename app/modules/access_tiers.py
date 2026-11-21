"""Customer access tiers for the live-chat journey.

The tiers are the server-side source of truth for *how much verification* a
request needs before the assistant may continue:

    Tier 1 - Public Information  : no login, knowledge-only answers.
    Tier 2 - Personal Inquiry    : authenticated customer session (AL1).
    Tier 3 - Sensitive Request   : step-up OTP (AL2) + recorded consent.
    Tier 4 - High-Risk Action    : AI prepares a request only; a human must
                                   approve or an approved external process runs.

Security question is never used as the sole control: the required assurance
increases with impact. This module contains no data access and no execution;
it only classifies intents/tools and describes the required control.
"""
from __future__ import annotations

from .tool_gateway import PROHIBITED

TIER_PUBLIC = 1
TIER_PERSONAL = 2
TIER_SENSITIVE = 3
TIER_HIGH_RISK = 4

TIERS: dict[int, dict] = {
    TIER_PUBLIC: {
        "code": "PUBLIC_INFORMATION",
        "label": "Informasi Publik",
        "description": "Informasi produk dan jam layanan tanpa login.",
        "required_assurance": "AL0",
        "methods": ["NONE"],
        "requires_consent": False,
        "human_approval": False,
    },
    TIER_PERSONAL: {
        "code": "PERSONAL_INQUIRY",
        "label": "Pertanyaan Pribadi",
        "description": "Status order atau transaksi milik akun yang sudah masuk.",
        "required_assurance": "AL1",
        "methods": ["SESSION_LOGIN"],
        "requires_consent": False,
        "human_approval": False,
    },
    TIER_SENSITIVE: {
        "code": "SENSITIVE_REQUEST",
        "label": "Permintaan Sensitif",
        "description": "Perubahan data atau pemblokiran layanan dengan verifikasi tambahan.",
        "required_assurance": "AL2",
        "methods": ["STEP_UP_OTP"],
        "requires_consent": True,
        "human_approval": False,
    },
    TIER_HIGH_RISK: {
        "code": "HIGH_RISK_ACTION",
        "label": "Tindakan Berisiko Tinggi",
        "description": "AI hanya menyiapkan permintaan; wajib persetujuan petugas.",
        "required_assurance": None,
        "methods": ["HUMAN_APPROVAL"],
        # Human approval is the control; the customer is not asked to consent to
        # an execution the AI will never perform.
        "requires_consent": False,
        "human_approval": True,
    },
}

INTENT_TIER: dict[str, int] = {
    "INFO_PRODUCT_POLICY": TIER_PUBLIC,
    "GEN_SMALL_TALK_OTHER": TIER_PUBLIC,
    "OTHER_UNCLASSIFIED": TIER_PUBLIC,
    "INFO_ACCOUNT_BALANCE": TIER_PERSONAL,
    "INFO_TRANSACTION_HISTORY": TIER_PERSONAL,
    "INFO_CASE_STATUS": TIER_PERSONAL,
    "REQ_STATEMENT_DOCUMENT": TIER_PERSONAL,
    "CMP_TRANSACTION_DISPUTE": TIER_PERSONAL,
    "CMP_SERVICE_FAILURE": TIER_PERSONAL,
    "CMP_STAFF_CONDUCT": TIER_PERSONAL,
    "REQ_CARD_BLOCK": TIER_SENSITIVE,
    "REQ_CARD_REPLACEMENT": TIER_SENSITIVE,
    "REQ_LIMIT_CHANGE": TIER_SENSITIVE,
    "REQ_PROFILE_UPDATE": TIER_SENSITIVE,
    # Fraud is safety-critical: the mandatory handoff runs before tier gating.
    "CMP_FRAUD_SUSPICION": TIER_SENSITIVE,
}

TOOL_TIER: dict[str, int] = {
    "knowledge_search": TIER_PUBLIC,
    "account_lookup": TIER_PERSONAL,
    "transaction_lookup": TIER_PERSONAL,
    "order_claim_lookup": TIER_PERSONAL,
    "customer_profile_lookup": TIER_PERSONAL,
    "case_lookup": TIER_PERSONAL,
    "crm_ticket_lookup": TIER_PERSONAL,
    "create_crm_ticket": TIER_PERSONAL,
    "update_crm_ticket": TIER_PERSONAL,
    "create_case": TIER_PERSONAL,
    "evidence_request": TIER_PERSONAL,
    "notification_send": TIER_PERSONAL,
    "evidence_upload_link": TIER_PERSONAL,
    "sla_calculate": TIER_PUBLIC,
    "handoff_request": TIER_PUBLIC,
    "auth_challenge": TIER_PUBLIC,
    "auth_verify": TIER_PUBLIC,
    "card_status_update": TIER_SENSITIVE,
}

# Every prohibited action is high risk by definition. The gateway still denies
# it; this mapping lets the conversation explain the approval boundary.
for _tool in PROHIBITED:
    TOOL_TIER[_tool] = TIER_HIGH_RISK


def tier_for(intent_code: str | None, tool_name: str | None = None) -> int:
    """Return the highest tier implied by the intent and the proposed tool."""
    intent_tier = INTENT_TIER.get(intent_code or "", TIER_PUBLIC)
    tool_tier = TOOL_TIER.get(tool_name or "", TIER_PUBLIC)
    return max(intent_tier, tool_tier)


def tier_meta(tier: int) -> dict:
    return TIERS.get(tier, TIERS[TIER_PUBLIC])


def required_assurance(tier: int) -> str | None:
    return tier_meta(tier).get("required_assurance")


def requires_consent(tier: int) -> bool:
    return bool(tier_meta(tier).get("requires_consent"))


def needs_human_approval(tier: int) -> bool:
    return bool(tier_meta(tier).get("human_approval"))


def verification_method(tier: int, current_assurance: str, authenticated: bool) -> str | None:
    """Return the next control the customer must satisfy, or None if ready.

    Tier 4 is not a customer verification step: it is always routed to human
    approval, so no step-up control is proposed for it.
    """
    if needs_human_approval(tier):
        return None
    required = required_assurance(tier)
    if required is None:
        return None
    order = ["AL0", "AL1", "AL2", "AL3"]
    current = current_assurance if current_assurance in order else "AL0"
    if order.index(current) >= order.index(required):
        return None
    if required == "AL1":
        return "SESSION_LOGIN"
    return "STEP_UP_OTP"
