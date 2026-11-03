"""FR-ORC-005 + FR-WS-005 gerbang persetujuan persisten.

BR-ORC-07 mengikat keputusan ke snapshot argumen; RBAC-02 melarang self-approval.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone, timedelta

from sqlalchemy.orm import Session

from ..core import audit as audit_svc
from ..core.errors import AppError
from ..core.ids import new_id
from ..core.rbac import assert_not_self_approval
from .models import ApprovalRow


def _h(args: dict) -> str:
    return hashlib.sha256(json.dumps(args, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def _as_dict(row: ApprovalRow) -> dict:
    return {
        "approval_id": row.approval_id,
        "conversation_id": row.conversation_id,
        "requested_by": row.requested_by,
        "tool_name": row.tool_name,
        "arguments_snapshot": row.arguments_snapshot,
        "arguments_hash": row.arguments_hash,
        "justification": row.justification,
        "risk_class": row.risk_class,
        "decision": row.decision,
        "approver_id": row.approver_id,
        "decision_comment": row.decision_comment,
        "requested_at": row.requested_at.isoformat(),
        "expires_at": row.expires_at.isoformat(),
        "decided_at": row.decided_at.isoformat() if row.decided_at else None,
    }


def request_approval(db: Session, conversation_id: str, tool_name: str, args: dict,
                     justification: str, risk: str, ctx: dict, corr: str) -> dict:
    now = datetime.now(timezone.utc)
    row = ApprovalRow(
        approval_id=new_id("approval"), conversation_id=conversation_id,
        requested_by=ctx["actor_id"], tool_name=tool_name,
        arguments_snapshot=args, arguments_hash=_h(args),
        justification=justification, risk_class=risk,
        requested_at=now, expires_at=now + timedelta(hours=4),
    )
    db.add(row)
    db.commit()
    audit_svc.emit("TNT-TEST", corr, ctx["actor_type"], ctx["actor_id"], "approval.requested",
                   "approval", row.approval_id, "approval-svc", conversation_id=conversation_id)
    return _as_dict(row)


def list_approvals(db: Session, state: str | None = None, tenant_id: str | None = None) -> list[dict]:
    query = db.query(ApprovalRow)
    if tenant_id is not None:
        from .models_a import ConversationRow
        query = query.join(ConversationRow, ApprovalRow.conversation_id == ConversationRow.conversation_id).filter(ConversationRow.tenant_id == tenant_id)
    if state == "pending":
        query = query.filter(ApprovalRow.decision.is_(None))
    elif state in {"GRANTED", "DENIED"}:
        query = query.filter_by(decision=state)
    return [_as_dict(row) for row in query.order_by(ApprovalRow.requested_at.desc()).all()]


def get_approval(db: Session, approval_id: str, tenant_id: str | None = None) -> dict:
    query = db.query(ApprovalRow).filter_by(approval_id=approval_id)
    if tenant_id is not None:
        from .models_a import ConversationRow
        query = query.join(ConversationRow, ApprovalRow.conversation_id == ConversationRow.conversation_id).filter(ConversationRow.tenant_id == tenant_id)
    row = query.first()
    if row is None:
        raise AppError("E_NOT_FOUND", "approval not found", customer_message_id="APPROVAL.NOT_FOUND")
    return _as_dict(row)


def decide(db: Session, approval_id: str, decision: str, comment: str,
           ctx: dict, corr: str) -> dict:
    from .models_a import ConversationRow
    row = (db.query(ApprovalRow).join(ConversationRow, ApprovalRow.conversation_id == ConversationRow.conversation_id)
           .filter(ApprovalRow.approval_id == approval_id, ConversationRow.tenant_id == ctx["tenant_id"]).first())
    if row is None:
        raise AppError("E_NOT_FOUND", "approval not found", customer_message_id="APPROVAL.NOT_FOUND")
    approver_id = ctx["actor_id"]
    assert_not_self_approval(row.requested_by, approver_id)
    if row.decision is not None:
        raise AppError("E_CONFLICT", "approval already decided", customer_message_id="APPROVAL.ALREADY_DECIDED")
    if decision not in {"GRANTED", "DENIED"}:
        raise AppError("E_VALIDATION", "decision must be GRANTED or DENIED", customer_message_id="APPROVAL.DECISION_INVALID")
    if not comment or not comment.strip():
        raise AppError("E_VALIDATION", "comment required", customer_message_id="APPROVAL.COMMENT_REQUIRED")
    now = datetime.now(timezone.utc)
    expires = row.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if now >= expires:
        raise AppError("E_CONFLICT", "approval expired", customer_message_id="APPROVAL.EXPIRED")
    row.approver_id = approver_id
    row.decision = decision
    row.decision_comment = comment.strip()
    row.decided_at = now
    db.commit()
    audit_svc.emit("TNT-TEST", corr, ctx["actor_type"], approver_id,
                   f"approval.{decision.lower()}", "approval", approval_id, "approval-svc")
    return _as_dict(row)


def check_hash_for_execution(db: Session, approval_id: str, args_now: dict) -> None:
    row = db.query(ApprovalRow).filter_by(approval_id=approval_id).first()
    if row is None or row.decision != "GRANTED":
        raise AppError("E_APPROVAL_REQUIRED", "no granted approval", customer_message_id="APPROVAL.REQUIRED")
    expires = row.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) >= expires:
        raise AppError("E_APPROVAL_REQUIRED", "approval expired", customer_message_id="APPROVAL.EXPIRED")
    if _h(args_now) != row.arguments_hash:
        raise AppError("E_APPROVAL_ARGS_MISMATCH", "args changed after approval",
                       customer_message_id="APPROVAL.ARGS_MISMATCH")
