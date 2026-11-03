"""TRD §6.3.2-6.3.5 tabel A: conversation, session, message, intent, knowledge, tool/policy.
Enum = text (VOC-01). tenant_id wajib (ADR-13)."""
from __future__ import annotations
from sqlalchemy import String, Text, DateTime, Integer, Boolean, JSON, Float
from sqlalchemy.orm import Mapped, mapped_column
from ..core.db import Base
import datetime

def _ts(): return datetime.datetime.now(datetime.timezone.utc)

class ConversationRow(Base):
    __tablename__ = "conversation"
    conversation_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(30), default="TNT-TEST", index=True)
    customer_id: Mapped[str | None] = mapped_column(String(30), nullable=True)
    claimed_customer_id: Mapped[str | None] = mapped_column(String(30), nullable=True)
    origin_channel: Mapped[str] = mapped_column(String(20), default="WEB_CHAT")
    current_channel: Mapped[str] = mapped_column(String(20), default="WEB_CHAT")
    status: Mapped[str] = mapped_column(String(40), default="NEW", index=True)
    status_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str] = mapped_column(String(10), default="id")
    intent_current: Mapped[str | None] = mapped_column(String(60), nullable=True)
    vulnerability_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    safety_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    reopen_count: Mapped[int] = mapped_column(Integer, default=0)
    link_candidate_of: Mapped[str | None] = mapped_column(String(30), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=_ts)
    last_activity_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=_ts, index=True)
    closed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

class ChannelSessionRow(Base):
    __tablename__ = "channel_session"
    channel_session_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(String(30), index=True)
    channel: Mapped[str] = mapped_column(String(20))
    assurance_level: Mapped[str] = mapped_column(String(10), default="AL0", index=True)
    al_method: Mapped[list] = mapped_column(JSON, default=list)
    al_established_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    al_expires_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    auth_failed_count: Mapped[int] = mapped_column(Integer, default=0)
    lock_state: Mapped[str] = mapped_column(String(20), default="NONE")
    locked_until: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=_ts)

class MessageRow(Base):
    __tablename__ = "message"
    message_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(String(30), index=True)
    channel_session_id: Mapped[str | None] = mapped_column(String(30), nullable=True)
    sequence_no: Mapped[int] = mapped_column(Integer, default=0)
    channel: Mapped[str] = mapped_column(String(20), default="WEB_CHAT")
    direction: Mapped[str] = mapped_column(String(20), default="INBOUND")
    author_type: Mapped[str] = mapped_column(String(20), default="CUSTOMER")
    author_id: Mapped[str] = mapped_column(String(60), default="customer")
    content: Mapped[str] = mapped_column(Text, default="")
    language: Mapped[str] = mapped_column(String(10), default="id")
    provider_message_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    citations: Mapped[list] = mapped_column(JSON, default=list)
    tool_call_ids: Mapped[list] = mapped_column(JSON, default=list)
    occurred_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=_ts)

class CustomerRequestRow(Base):
    """Scoped idempotency ledger for customer web-chat turns."""
    __tablename__ = "customer_chat_request"
    request_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(30), index=True)
    actor_id: Mapped[str] = mapped_column(String(60), index=True)
    request_hash: Mapped[str] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(20), default="PROCESSING")
    response: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=_ts)

class IntentRow(Base):
    __tablename__ = "intent_classification"
    intent_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    message_id: Mapped[str] = mapped_column(String(30), index=True)
    conversation_id: Mapped[str] = mapped_column(String(30), index=True)
    intent_code: Mapped[str] = mapped_column(String(60), index=True)
    intent_category: Mapped[str] = mapped_column(String(20))
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=True)
    decision: Mapped[str] = mapped_column(String(20), default="ACT")
    entities: Mapped[dict] = mapped_column(JSON, default=dict)
    model_version: Mapped[str] = mapped_column(String(30), default="rule-1.0.0")
    taxonomy_version: Mapped[str] = mapped_column(String(20), default="1.0.0")
    classified_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=_ts)

class KnowledgeArticleRow(Base):
    __tablename__ = "knowledge_article"
    article_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(30), default="TNT-TEST")
    title: Mapped[str] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(Text, default="")
    language: Mapped[str] = mapped_column(String(10), default="id")
    intents: Mapped[list] = mapped_column(JSON, default=list)
    access_level: Mapped[str] = mapped_column(String(20), default="CUSTOMER")
    status: Mapped[str] = mapped_column(String(20), default="PUBLISHED", index=True)
    current_version_id: Mapped[str | None] = mapped_column(String(30), nullable=True)
    expires_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

class KnowledgeVersionRow(Base):
    __tablename__ = "article_version"
    version_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    article_id: Mapped[str] = mapped_column(String(30), index=True)
    version_no: Mapped[int] = mapped_column(Integer, default=1)
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="PUBLISHED")
    effective_from: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=_ts)
    expires_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

class KnowledgeDocumentRow(Base):
    """Dokumen yang diunggah oleh Knowledge Manager dengan status pemrosesan."""
    __tablename__ = "knowledge_document"
    document_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(30), default="TNT-TEST", index=True)
    title: Mapped[str] = mapped_column(Text)
    original_filename: Mapped[str] = mapped_column(Text)
    file_path: Mapped[str] = mapped_column(Text)
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    mime_type: Mapped[str] = mapped_column(String(60), default="")
    file_hash: Mapped[str] = mapped_column(String(64), default="", index=True)
    version_no: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    uploaded_by: Mapped[str | None] = mapped_column(String(60), nullable=True)
    uploaded_by_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=_ts)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=_ts, onupdate=_ts)
    processed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class KnowledgeChunkRow(Base):
    """Potongan teks diekstrak dari dokumen, terhubung ke dokumen dan versi."""
    __tablename__ = "knowledge_chunk"
    chunk_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    document_id: Mapped[str] = mapped_column(String(30), index=True)
    version_no: Mapped[int] = mapped_column(Integer, default=1)
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    content: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64), default="")
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=_ts)


class ToolCallRow(Base):
    __tablename__ = "tool_call"
    tool_call_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(String(30), index=True)
    tool_name: Mapped[str] = mapped_column(String(60), index=True)
    tool_version: Mapped[str] = mapped_column(String(20), default="1.0.0")
    policy_decision_id: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(20), default="SUCCESS")
    error_code: Mapped[str | None] = mapped_column(String(30), nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    correlation_id: Mapped[str] = mapped_column(String(30), index=True)
    called_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=_ts)

class PolicyDecisionRow(Base):
    __tablename__ = "policy_decision"
    policy_decision_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(String(30), index=True)
    tool_name: Mapped[str] = mapped_column(String(60))
    decision: Mapped[str] = mapped_column(String(30))
    reason_code: Mapped[str | None] = mapped_column(String(60), nullable=True)
    assurance_level: Mapped[str] = mapped_column(String(10), default="AL0")
    policy_version: Mapped[str] = mapped_column(String(20), default="1.0.0")
    evaluated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=_ts)
