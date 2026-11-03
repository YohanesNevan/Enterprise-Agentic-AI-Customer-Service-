"""TRD §6.3.6 + §6.3.9 tabel B: ticket, case, sla_record, sla_event, crm_outbox, escalation. Enum = text + CHECK (VOC-01)."""
from __future__ import annotations
from sqlalchemy import String, Text, DateTime, Integer, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column
from ..core.db import Base
import datetime

def _ts(): return datetime.datetime.now(datetime.timezone.utc)

class TicketRow(Base):
    __tablename__ = "ticket"
    ticket_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(30), default="TNT-TEST", index=True)
    customer_id: Mapped[str | None] = mapped_column(String(30), nullable=True)
    conversation_id: Mapped[str | None] = mapped_column(String(30))
    case_id: Mapped[str | None] = mapped_column(String(30), nullable=True)
    type: Mapped[str] = mapped_column(String(60), default="GENERAL")
    sub_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    priority: Mapped[str] = mapped_column(String(20), default="NORMAL")
    status: Mapped[str] = mapped_column(String(30), default="OPEN", index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    owner_queue: Mapped[str] = mapped_column(String(60), default="GENERAL")
    sla_id: Mapped[str | None] = mapped_column(String(30), nullable=True)
    pending_system_action: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=_ts)

class CaseRow(Base):
    __tablename__ = "case_tbl"
    case_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(30), default="TNT-TEST", index=True)
    customer_id: Mapped[str | None] = mapped_column(String(30), nullable=True)
    origin_conversation_id: Mapped[str | None] = mapped_column(String(30))
    customer_reference: Mapped[str] = mapped_column(String(20), unique=True)
    category: Mapped[str] = mapped_column(String(60))
    sub_category: Mapped[str | None] = mapped_column(String(60), nullable=True)
    severity_proposed: Mapped[str] = mapped_column(String(20))
    severity_confirmed: Mapped[str | None] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="LOGGED", index=True)
    customer_visible_status: Mapped[str] = mapped_column(String(40), default="RECEIVED")
    owner_queue: Mapped[str] = mapped_column(String(60), default="GENERAL")
    logged_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=_ts)
    reopen_count: Mapped[int] = mapped_column(Integer, default=0)
    sla_config_version: Mapped[str] = mapped_column(String(20), default="1.2.0")

class SlaRecordRow(Base):
    __tablename__ = "sla_record"
    sla_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(30), default="TNT-TEST")
    object_type: Mapped[str] = mapped_column(String(20))  # CASE/TICKET
    object_id: Mapped[str] = mapped_column(String(30), index=True)
    sla_config_version: Mapped[str] = mapped_column(String(20), default="1.2.0")
    started_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=_ts)
    first_response_due_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True))
    resolution_due_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True))
    first_response_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    state: Mapped[str] = mapped_column(String(20), default="RUNNING", index=True)

class SlaEventRow(Base):
    __tablename__ = "sla_event"
    sla_event_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    sla_id: Mapped[str] = mapped_column(String(30), index=True)
    type: Mapped[str] = mapped_column(String(20), index=True)  # AT_RISK/BREACHED/MET/...
    occurred_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=_ts)
    computed_from: Mapped[str] = mapped_column(String(30), default="")  # unik (sla_id,type,computed_from) dijaga di service
    reason_code: Mapped[str | None] = mapped_column(String(60), nullable=True)

class CrmOutboxRow(Base):
    __tablename__ = "crm_outbox"
    outbox_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    object_type: Mapped[str] = mapped_column(String(20))
    object_id: Mapped[str] = mapped_column(String(30), index=True)
    operation: Mapped[str] = mapped_column(String(20), default="CREATE")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    state: Mapped[str] = mapped_column(String(20), default="PENDING", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=_ts)
    sent_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

class EscalationRow(Base):
    __tablename__ = "escalation"
    escalation_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    object_type: Mapped[str] = mapped_column(String(20))
    object_id: Mapped[str] = mapped_column(String(30), index=True)
    level: Mapped[str] = mapped_column(String(10))
    trigger_type: Mapped[str] = mapped_column(String(40))
    target_role: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=_ts)
    acknowledged_by: Mapped[str | None] = mapped_column(String(60), nullable=True)

class ApprovalRow(Base):
    """FR-ORC-005: persisten snapshot persetujuan agar survive restart."""
    __tablename__ = "approval"
    approval_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(String(30), index=True)
    requested_by: Mapped[str] = mapped_column(String(60))
    tool_name: Mapped[str] = mapped_column(String(60))
    arguments_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    arguments_hash: Mapped[str] = mapped_column(String(64))
    justification: Mapped[str] = mapped_column(Text, default="")
    risk_class: Mapped[str] = mapped_column(String(30), default="WRITE_MEDIUM")
    decision: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    approver_id: Mapped[str | None] = mapped_column(String(60), nullable=True)
    decision_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=_ts)
    expires_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True))
    decided_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

class HandoffRow(Base):
    """FR-WS-001/002 antrean alih tangan. state: QUEUED/OFFERED/ACCEPTED/TIMED_OUT."""
    __tablename__ = "handoff"
    handoff_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(30), default="TNT-TEST", index=True)
    conversation_id: Mapped[str] = mapped_column(String(30), index=True)
    reason_code: Mapped[str] = mapped_column(String(40), index=True)
    priority_score: Mapped[int] = mapped_column(Integer, default=0, index=True)
    queue_id: Mapped[str] = mapped_column(String(40), default="Q-GENERAL", index=True)
    skill_tags: Mapped[list] = mapped_column(JSON, default=list)
    language: Mapped[str] = mapped_column(String(10), default="id")
    severity: Mapped[str] = mapped_column(String(20), default="MEDIUM")
    vulnerability_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    state: Mapped[str] = mapped_column(String(20), default="QUEUED", index=True)
    package_complete: Mapped[bool] = mapped_column(Boolean, default=True)
    queued_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=_ts)
    offered_to: Mapped[str | None] = mapped_column(String(60), nullable=True)
    accepted_by: Mapped[str | None] = mapped_column(String(60), nullable=True)
    transfer_note: Mapped[str | None] = mapped_column(Text, nullable=True)

class QaSampleRow(Base):
    __tablename__ = "qa_sample"
    sample_run_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    method: Mapped[str] = mapped_column(String(60), default="10pct_random+100pct_risk")
    seed: Mapped[int] = mapped_column(Integer, default=42)
    selected: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=_ts)

class QaReviewRow(Base):
    __tablename__ = "qa_review"
    review_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    item_id: Mapped[str] = mapped_column(String(30), index=True)
    reviewer_id: Mapped[str] = mapped_column(String(60))
    scores: Mapped[dict] = mapped_column(JSON, default=dict)
    total: Mapped[int] = mapped_column(Integer, default=0)
    auto_fail: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_fail_criterion: Mapped[str | None] = mapped_column(String(60), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=_ts)

class QaFindingRow(Base):
    __tablename__ = "qa_finding"
    finding_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    review_id: Mapped[str] = mapped_column(String(30), index=True)
    type: Mapped[str] = mapped_column(String(40))  # knowledge_gap/process_defect/ai_defect/...
    severity: Mapped[str] = mapped_column(String(20), default="MEDIUM")
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="OPEN", index=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=_ts)
