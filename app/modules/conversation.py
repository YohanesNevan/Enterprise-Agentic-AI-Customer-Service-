"""FR-CONV-001..010 [A]: identitas percakapan terpadu, kontinuitas 72h, reopen 7d,
dedup provider_message_id, mesin status, bahasa, retensi. TRD §4.2."""
from __future__ import annotations
import datetime
from sqlalchemy.orm import Session
from ..core.ids import new_id
from ..core import audit as audit_svc
from ..core.errors import AppError
from .models_a import ConversationRow, ChannelSessionRow, MessageRow

CONTINUITY_H = 72
REOPEN_D = 7
VALID_TRANSITIONS = {
    "NEW": {"ACTIVE_AI", "CLOSED"},
    "ACTIVE_AI": {"AWAITING_CUSTOMER", "AWAITING_AUTH", "AWAITING_EVIDENCE",
                  "PENDING_HANDOFF", "ACTIVE_HUMAN", "RESOLVED_PENDING_CONFIRMATION", "CLOSED", "ABANDONED"},
    "AWAITING_CUSTOMER": {"ACTIVE_AI", "ABANDONED"},
    "AWAITING_AUTH": {"ACTIVE_AI", "PENDING_HANDOFF"},
    "AWAITING_EVIDENCE": {"ACTIVE_AI"},
    "PENDING_HANDOFF": {"ACTIVE_HUMAN", "ACTIVE_AI"},
    "ACTIVE_HUMAN": {"RESOLVED_PENDING_CONFIRMATION", "ACTIVE_AI", "CLOSED"},
    "RESOLVED_PENDING_CONFIRMATION": {"CLOSED", "ACTIVE_AI", "ACTIVE_HUMAN"},
    "CLOSED": {"REOPENED"},
    "REOPENED": {"ACTIVE_AI", "ACTIVE_HUMAN"},
    "ABANDONED": {"REOPENED"},
}

def _now():
    return datetime.datetime.now(datetime.timezone.utc)

def detect_language(text: str) -> str:
    t = (text or "").lower()
    id_markers = ["saya", "kartu", "saldo", "tolong", "tidak", "berapa", "transfer", "rekening", "keluhan", "blokir"]
    return "id" if any(m in t for m in id_markers) else ("id" if any(ord(c) > 127 for c in t) else "en" if t else "id")

def _session(db: Session, conv_id: str, channel: str) -> ChannelSessionRow:
    s = (db.query(ChannelSessionRow).filter_by(conversation_id=conv_id, channel=channel)
         .order_by(ChannelSessionRow.started_at.desc()).first())
    if s is None:
        s = ChannelSessionRow(channel_session_id=new_id("channel_session"),
                              conversation_id=conv_id, channel=channel, assurance_level="AL0")
        db.add(s); db.flush()
    return s

def ingest(db: Session, channel: str, from_handle: str, text: str,
           provider_message_id: str | None = None, subject: str | None = None,
           ctx: dict | None = None, corr: str = "COR-?", tenant: str = "TNT-TEST",
           claimed_customer_id: str | None = None, conversation_id: str | None = None,
           force_new: bool = False) -> dict:
    """FR-CONV-001: normalisasi -> resolusi identitas -> continuity/reopen -> append."""
    ctx = ctx or {"actor_type": "SYSTEM", "actor_id": "channel-adapter"}
    now = _now()
    # dedup idempoten (BR-CONV)
    if provider_message_id:
        dup = (db.query(MessageRow).join(ConversationRow, MessageRow.conversation_id == ConversationRow.conversation_id)
               .filter(MessageRow.provider_message_id == provider_message_id,
                       MessageRow.channel == channel, ConversationRow.tenant_id == tenant).first())
        if dup:
            if (ctx.get("role") == "customer" and
                    db.query(ConversationRow).filter_by(conversation_id=dup.conversation_id,
                        tenant_id=tenant, customer_id=ctx.get("actor_id")).first() is None):
                raise AppError("E_CONFLICT", "message identifier already used", customer_message_id="CONV.DUPLICATE")
            return {"conversation_id": dup.conversation_id, "message_id": dup.message_id, "replayed": True}
        # A global channel/provider-ID collision must never reveal the other tenant's conversation.
        collision = (db.query(MessageRow.message_id).filter_by(
            provider_message_id=provider_message_id, channel=channel).first())
        if collision:
            raise AppError("E_CONFLICT", "message identifier already used", customer_message_id="CONV.DUPLICATE")
    # Existing conversation IDs are resolved inside the trusted tenant/owner boundary.
    if conversation_id:
        conv = db.query(ConversationRow).filter_by(conversation_id=conversation_id, tenant_id=tenant).first()
        if not conv or (ctx.get("role") == "customer" and conv.customer_id != ctx.get("actor_id")):
            raise AppError("E_NOT_FOUND", "conversation not found", customer_message_id="CONV.NOT_FOUND")
        if claimed_customer_id and claimed_customer_id != conv.customer_id:
            raise AppError("E_NOT_FOUND", "conversation not found", customer_message_id="CONV.NOT_FOUND")
        customer_id = conv.customer_id
    else:
        conv = None
        # resolusi identitas: handle email cocok ganda -> null disimulasikan via claimed
        customer_id = claimed_customer_id
    # continuity: cari percakapan terbuka milik customer dalam 72h (BR-CONV-01)
    if conv is None and customer_id and not force_new:
        window = now - datetime.timedelta(hours=CONTINUITY_H)
        conv = (db.query(ConversationRow)
                .filter(ConversationRow.tenant_id == tenant,
                        ConversationRow.customer_id == customer_id,
                        ConversationRow.last_activity_at >= window,
                        ConversationRow.status.notin_(["CLOSED", "ABANDONED"]))
                .order_by(ConversationRow.last_activity_at.desc()).first())
    if conv is None and customer_id and not force_new:
        # PR-01: reopen 7 hari sebelum continuity — cocok sederhana: percakapan CLOSED < 7d
        window_r = now - datetime.timedelta(days=REOPEN_D)
        closed = (db.query(ConversationRow)
                  .filter(ConversationRow.tenant_id == tenant,
                          ConversationRow.customer_id == customer_id,
                          ConversationRow.status == "CLOSED",
                          ConversationRow.closed_at != None,
                          ConversationRow.closed_at >= window_r)
                  .order_by(ConversationRow.closed_at.desc()).first())
        if closed:
            closed.status = "REOPENED"; closed.reopen_count += 1
            closed.last_activity_at = now; closed.current_channel = channel
            audit_svc.emit(tenant, corr, ctx["actor_type"], ctx["actor_id"],
                           "conversation.reopened", "conversation", closed.conversation_id,
                           "conversation-svc", conversation_id=closed.conversation_id)
            conv = closed
    link_candidate = False
    if conv is None:
        # identitas ambigu (claimed berisi koma = 2 nasabah) -> AL0 link_candidate (US-CONV-02)
        if claimed_customer_id and "," in claimed_customer_id:
            customer_id = None; link_candidate = True
        conv = ConversationRow(conversation_id=new_id("conversation"), tenant_id=tenant,
                               customer_id=customer_id, claimed_customer_id=claimed_customer_id,
                               origin_channel=channel, current_channel=channel, status="ACTIVE_AI",
                               language=detect_language(text),
                               link_candidate_of="AMBIGUOUS" if link_candidate else None,
                               created_at=now, last_activity_at=now)
        db.add(conv); db.flush()
        audit_svc.emit(tenant, corr, ctx["actor_type"], ctx["actor_id"], "conversation.created",
                       "conversation", conv.conversation_id, "conversation-svc",
                       conversation_id=conv.conversation_id)
        if link_candidate:
            audit_svc.emit(tenant, corr, ctx["actor_type"], ctx["actor_id"],
                           "conversation.link_candidate_flagged", "conversation",
                           conv.conversation_id, "conversation-svc",
                           conversation_id=conv.conversation_id)
    conv.last_activity_at = now; conv.current_channel = channel
    sess = _session(db, conv.conversation_id, channel)
    seq = db.query(MessageRow).filter_by(conversation_id=conv.conversation_id).count()
    m = MessageRow(message_id=new_id("message"), conversation_id=conv.conversation_id,
                   channel_session_id=sess.channel_session_id, sequence_no=seq,
                   channel=channel, direction="INBOUND", author_type="CUSTOMER",
                   author_id=from_handle, content=text or "", language=detect_language(text or ""),
                   provider_message_id=provider_message_id, occurred_at=now)
    db.add(m); db.commit()
    audit_svc.emit(tenant, corr, ctx["actor_type"], ctx["actor_id"], "conversation.message_appended",
                   "message", m.message_id, "conversation-svc", conversation_id=conv.conversation_id)
    return {"conversation_id": conv.conversation_id, "message_id": m.message_id,
            "customer_id": conv.customer_id, "status": conv.status,
            "link_candidate": link_candidate, "replayed": False}

def transition(db: Session, conv_id: str, to_state: str, reason: str, ctx: dict, corr: str) -> dict:
    c = db.query(ConversationRow).filter_by(conversation_id=conv_id).first()
    if not c:
        raise AppError("E_NOT_FOUND", "conversation not found", customer_message_id="CONV.NOT_FOUND")
    allowed = VALID_TRANSITIONS.get(c.status, set())
    if to_state not in allowed:
        # BR-CONV-04: tutup saat kasus terbuka ditolak — dicek di orchestrator; di sini generic
        raise AppError("E_INVALID_TRANSITION", f"{c.status} -> {to_state} illegal: {reason}",
                       customer_message_id="CONV.TRANSITION_INVALID")
    before = c.status
    c.status = to_state; c.status_reason = reason; c.last_activity_at = _now()
    if to_state == "CLOSED":
        c.closed_at = _now()
    db.commit()
    audit_svc.emit(c.tenant_id, corr, ctx["actor_type"], ctx["actor_id"], "conversation.status_changed",
                   "conversation", conv_id, "conversation-svc",
                   reason=reason, before={"status": before}, after={"status": to_state},
                   conversation_id=conv_id)
    return {"conversation_id": conv_id, "from": before, "to": to_state}

def append_agent_reply(db: Session, conv_id: str, text: str, agent_id: str,
                       tenant_id: str, corr: str) -> dict:
    """Persist an outbound human reply only for the agent's own accepted handoff."""
    from .models import HandoffRow
    conv = db.query(ConversationRow).filter_by(
        conversation_id=conv_id, tenant_id=tenant_id).first()
    if conv is None:
        raise AppError("E_NOT_FOUND", "conversation not found", customer_message_id="CONV.NOT_FOUND")
    handoff = (db.query(HandoffRow).filter_by(conversation_id=conv_id, tenant_id=tenant_id)
               .order_by(HandoffRow.queued_at.desc()).first())
    if not handoff or handoff.state != "ACCEPTED" or handoff.accepted_by != agent_id:
        raise AppError("E_CONFLICT", "active handoff is not assigned to this agent",
                       customer_message_id="HANDOFF.NOT_ASSIGNED")
    if conv.status != "ACTIVE_HUMAN":
        raise AppError("E_CONFLICT", "conversation is not in active human handling",
                       customer_message_id="CONV.STATE")
    session = (db.query(ChannelSessionRow).filter_by(
        conversation_id=conv_id, channel=conv.current_channel)
        .order_by(ChannelSessionRow.started_at.desc()).first())
    last_sequence = (db.query(MessageRow.sequence_no).filter_by(conversation_id=conv_id)
                     .order_by(MessageRow.sequence_no.desc()).first())
    now = _now()
    message = MessageRow(
        message_id=new_id("message"), conversation_id=conv_id,
        channel_session_id=session.channel_session_id if session else None,
        sequence_no=(last_sequence[0] + 1) if last_sequence else 0,
        channel=conv.current_channel or "WEB_CHAT", direction="OUTBOUND",
        author_type="HUMAN_AGENT", author_id=agent_id, content=text.strip(),
        language=conv.language or "id", citations=[], tool_call_ids=[], occurred_at=now)
    db.add(message)
    conv.last_activity_at = now
    db.commit()
    audit_svc.emit(tenant_id, corr, "HUMAN_AGENT", agent_id, "conversation.agent_reply_sent",
                   "message", message.message_id, "conversation-svc",
                   conversation_id=conv_id, after={"handoff_id": handoff.handoff_id,
                                                   "author_type": "HUMAN_AGENT"})
    return {"message_id": message.message_id, "conversation_id": conv_id,
            "sequence_no": message.sequence_no, "direction": message.direction,
            "author_type": message.author_type, "author_id": message.author_id,
            "content": message.content, "occurred_at": now.isoformat()}

def append_outbound(db: Session, conv_id: str, text: str, citations: list | None = None,
                    tool_ids: list | None = None, author: str = "AI_AGENT") -> dict:
    now = _now()
    c = db.query(ConversationRow).filter_by(conversation_id=conv_id).first()
    seq = db.query(MessageRow).filter_by(conversation_id=conv_id).count()
    m = MessageRow(message_id=new_id("message"), conversation_id=conv_id, sequence_no=seq,
                   channel=c.current_channel if c else "WEB_CHAT", direction="OUTBOUND",
                   author_type=author, author_id="orchestrator" if author == "AI_AGENT" else "agent",
                   content=text, citations=citations or [], tool_call_ids=tool_ids or [], occurred_at=now)
    db.add(m)
    if c: c.last_activity_at = now
    db.commit()
    return {"message_id": m.message_id}
