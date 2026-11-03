"""Routes Kelompok A [CONV/AUTH/INT/KM/ORC/TOOL/SVC] — FRD §6.2-6.8, TRD §4.1-4.10, §7.
Diregistrasi dari app.main agar B tetap utuh (satu kesatuan project, ADR-01)."""
from __future__ import annotations
import base64
import hashlib
import hmac
import json
import logging
import os
import re
from datetime import datetime
from fastapi import Depends, Request, UploadFile, File, Form
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import or_, and_, func
from ..core.rbac import require_human_perm, require_perm, optional_principal
from ..core.errors import AppError
from ..core.db import SessionLocal, safe_database_identity
from ..core import audit as audit_svc

_logger = logging.getLogger("eaics.knowledge")
_logger.setLevel(logging.INFO)

def _log_knowledge_diagnostic(db, tenant_id: str, event: str, outcome: str = "ok") -> None:
    """Operational counters only: no credentials, customer text, or file contents."""
    from ..modules.models_a import KnowledgeDocumentRow
    try:
        rows = (db.query(KnowledgeDocumentRow.status, func.count(KnowledgeDocumentRow.document_id))
                .filter(KnowledgeDocumentRow.tenant_id == tenant_id)
                .group_by(KnowledgeDocumentRow.status).all())
    except Exception as exc:
        _logger.warning("knowledge_diag event=%s environment=%s database=%s tenant_id=%s outcome=count_error error_type=%s",
                        event, os.getenv("ENVIRONMENT", "unset"), safe_database_identity(),
                        tenant_id, type(exc).__name__)
        return
    counts = {str(status): int(count) for status, count in rows}
    _logger.warning("knowledge_diag event=%s environment=%s database=%s tenant_id=%s documents=%d statuses=%s outcome=%s",
                 event, os.getenv("ENVIRONMENT", "unset"), safe_database_identity(), tenant_id,
                 sum(counts.values()), json.dumps(counts, sort_keys=True, separators=(",", ":")), outcome)

def register(app):
    from ..core.rbac import rotate_refresh_token, HUMAN_ROLES
    from ..core.dev_auth import validate_dev_customer_auth_config, issue_dev_access_token, dev_auth_client_allowed
    from ..modules import conversation as ConvSvc
    from ..modules import auth as AuthSvc
    from ..modules import intent as IntentSvc
    from ..modules import knowledge as KmSvc
    from ..modules import orchestrator as Orc
    from ..modules import tool_gateway as Gw
    from ..modules import corebank as Sim
    from ..modules import workflows as Wf
    from ..modules.models_a import ConversationRow, ChannelSessionRow, MessageRow, IntentRow, CustomerRequestRow
    from ..modules import models as BModels
    from ..modules.models_a import KnowledgeArticleRow, KnowledgeDocumentRow

    class DevLoginIn(BaseModel):
        username: str = Field(min_length=1, max_length=100)
        password: str = Field(min_length=1, max_length=256)

    class CustomerChatIn(BaseModel):
        text: str = Field(min_length=1, max_length=4000)
        conversation_id: str | None = Field(default=None, min_length=1, max_length=30)
        channel: str = "WEB_CHAT"

    def dev_auth_enabled():
        enabled = os.getenv("DEV_CUSTOMER_AUTH_ENABLED", "").lower() == "true"
        env = os.getenv("ENVIRONMENT", "")
        validate_dev_customer_auth_config(env, "true" if enabled else "false")
        return enabled and env.lower() == "development"

    @app.post("/v1/dev-auth/customer/login")
    async def dev_customer_login(body: dict, request: Request):
        if not dev_auth_enabled() or not dev_auth_client_allowed(request.client.host if request.client else None):
            raise AppError("E_UNAVAILABLE", "local customer sign-in is not enabled", customer_message_id="AUTH.DEV_UNAVAILABLE")
        try:
            credentials = DevLoginIn.model_validate(body) if hasattr(DevLoginIn, "model_validate") else DevLoginIn.parse_obj(body)
        except ValidationError as exc:
            raise AppError("E_VALIDATION", "username and password are required", customer_message_id="AUTH.LOGIN_INVALID") from exc
        try:
            accounts = json.loads(os.getenv("DEV_CUSTOMER_ACCOUNTS", "{}"))
        except (ValueError, TypeError):
            accounts = None
        if not isinstance(accounts, dict) or len(accounts) > 50:
            raise AppError("E_UNAVAILABLE", "local customer sign-in is not configured", customer_message_id="AUTH.DEV_UNAVAILABLE")
        account = accounts.get(credentials.username)
        if account is None:
            # Preserve the original one-account development configuration for existing setups.
            account = {"password": os.getenv("DEV_CUSTOMER_PASSWORD", ""),
                       "actor_id": os.getenv("DEV_CUSTOMER_ID", ""),
                       "tenant_id": os.getenv("DEV_TENANT_ID", "")}
            configured_username = os.getenv("DEV_CUSTOMER_USERNAME", "")
            if credentials.username != configured_username:
                account = None
        if not isinstance(account, dict):
            raise AppError("E_UNAUTHORISED", "invalid sign-in credentials", customer_message_id="AUTH.INVALID_CREDENTIALS")
        password, actor, tenant = (account.get("password"), account.get("actor_id"),
                                   account.get("tenant_id"))
        key = os.getenv("JWT_SIGNING_KEY", "")
        if (not isinstance(password, str) or len(password) < 20 or len(key) < 32 or
                not isinstance(actor, str) or not actor or not isinstance(tenant, str) or not tenant or
                len(actor) > 30 or len(tenant) > 30):
            raise AppError("E_UNAVAILABLE", "local customer sign-in is not configured", customer_message_id="AUTH.DEV_UNAVAILABLE")
        if not hmac.compare_digest(credentials.password.encode(), password.encode()):
            raise AppError("E_UNAUTHORISED", "invalid sign-in credentials", customer_message_id="AUTH.INVALID_CREDENTIALS")
        try:
            token, lifetime = issue_dev_access_token(actor, tenant, "customer")
        except ValueError as exc:
            raise AppError("E_UNAVAILABLE", "local customer sign-in is not configured", customer_message_id="AUTH.DEV_UNAVAILABLE") from exc
        return {"access_token": token, "token_type": "Bearer", "expires_in": lifetime,
                "principal": {"actor_id": actor, "role": "customer", "tenant_id": tenant}}

    @app.post("/v1/dev-auth/staff/login")
    async def dev_staff_login(body: dict, request: Request):
        enabled = os.getenv("DEV_STAFF_AUTH_ENABLED", "").lower() == "true"
        env = os.getenv("ENVIRONMENT", "")
        validate_dev_customer_auth_config(env, staff_enabled="true" if enabled else "false")
        if not enabled or env.lower() != "development" or not dev_auth_client_allowed(request.client.host if request.client else None):
            raise AppError("E_UNAVAILABLE", "local staff sign-in is not enabled", customer_message_id="AUTH.DEV_UNAVAILABLE")
        try:
            credentials = DevLoginIn.model_validate(body) if hasattr(DevLoginIn, "model_validate") else DevLoginIn.parse_obj(body)
        except ValidationError as exc:
            raise AppError("E_VALIDATION", "username and password are required", customer_message_id="AUTH.LOGIN_INVALID") from exc
        try:
            accounts = json.loads(os.getenv("DEV_STAFF_ACCOUNTS", "{}"))
        except (ValueError, TypeError):
            accounts = None
        if not isinstance(accounts, dict) or len(accounts) > 50:
            raise AppError("E_UNAVAILABLE", "local staff sign-in is not configured", customer_message_id="AUTH.DEV_UNAVAILABLE")
        account = accounts.get(credentials.username)
        if not isinstance(account, dict):
            raise AppError("E_UNAUTHORISED", "invalid sign-in credentials", customer_message_id="AUTH.INVALID_CREDENTIALS")
        actor, tenant, role, password = (account.get("actor_id"), account.get("tenant_id"),
                                         account.get("role"), account.get("password"))
        staff_roles = HUMAN_ROLES - {"customer"}
        if (not isinstance(actor, str) or not 1 <= len(actor) <= 60 or
                not isinstance(tenant, str) or not 1 <= len(tenant) <= 30 or
                not isinstance(role, str) or role not in staff_roles or
                not isinstance(password, str) or len(password) < 20):
            raise AppError("E_UNAVAILABLE", "local staff sign-in configuration is invalid", customer_message_id="AUTH.DEV_UNAVAILABLE")
        if not hmac.compare_digest(credentials.password.encode(), password.encode()):
            raise AppError("E_UNAUTHORISED", "invalid sign-in credentials", customer_message_id="AUTH.INVALID_CREDENTIALS")
        try:
            token, lifetime = issue_dev_access_token(actor, tenant, role)
        except ValueError as exc:
            raise AppError("E_UNAVAILABLE", "local staff sign-in is not configured", customer_message_id="AUTH.DEV_UNAVAILABLE") from exc
        _logger.warning("staff_login_succeeded role=%s tenant_id=%s environment=%s database=%s",
                     role, tenant, env.lower(), safe_database_identity())
        return {"access_token": token, "token_type": "Bearer", "expires_in": lifetime,
                "principal": {"actor_id": actor, "role": role, "tenant_id": tenant}}

    @app.post("/v1/dev-auth/login")
    async def dev_universal_login(body: dict, request: Request):
        try:
            credentials = DevLoginIn.model_validate(body) if hasattr(DevLoginIn, "model_validate") else DevLoginIn.parse_obj(body)
        except ValidationError as exc:
            raise AppError("E_VALIDATION", "username and password are required", customer_message_id="AUTH.LOGIN_INVALID") from exc

        client_host = request.client.host if request.client else None
        if not dev_auth_client_allowed(client_host):
            raise AppError("E_UNAVAILABLE", "local sign-in is not allowed from this host", customer_message_id="AUTH.DEV_UNAVAILABLE")

        # 1. First check if credentials match an enabled staff account
        staff_enabled = os.getenv("DEV_STAFF_AUTH_ENABLED", "").lower() == "true"
        env = os.getenv("ENVIRONMENT", "")
        if staff_enabled and env.lower() == "development":
            try:
                staff_accounts = json.loads(os.getenv("DEV_STAFF_ACCOUNTS", "{}"))
            except (ValueError, TypeError):
                staff_accounts = {}
            if isinstance(staff_accounts, dict) and credentials.username in staff_accounts:
                st_acc = staff_accounts[credentials.username]
                if isinstance(st_acc, dict):
                    actor, tenant, role, pwd = (st_acc.get("actor_id"), st_acc.get("tenant_id"),
                                                st_acc.get("role"), st_acc.get("password"))
                    staff_roles = HUMAN_ROLES - {"customer"}
                    if (isinstance(pwd, str) and len(pwd) >= 20 and
                            role in staff_roles and actor and tenant and
                            hmac.compare_digest(credentials.password.encode(), pwd.encode())):
                        token, lifetime = issue_dev_access_token(actor, tenant, role)
                        _logger.warning("universal_login_succeeded type=staff role=%s tenant_id=%s environment=%s",
                                        role, tenant, env.lower())
                        return {
                            "access_token": token,
                            "token_type": "Bearer",
                            "expires_in": lifetime,
                            "principal": {"actor_id": actor, "role": role, "tenant_id": tenant}
                        }

        # 2. Check customer accounts
        if dev_auth_enabled():
            try:
                cust_accounts = json.loads(os.getenv("DEV_CUSTOMER_ACCOUNTS", "{}"))
            except (ValueError, TypeError):
                cust_accounts = {}
            cust_acc = None
            if isinstance(cust_accounts, dict) and credentials.username in cust_accounts:
                cust_acc = cust_accounts[credentials.username]
            elif credentials.username == os.getenv("DEV_CUSTOMER_USERNAME", ""):
                cust_acc = {
                    "password": os.getenv("DEV_CUSTOMER_PASSWORD", ""),
                    "actor_id": os.getenv("DEV_CUSTOMER_ID", ""),
                    "tenant_id": os.getenv("DEV_TENANT_ID", "")
                }

            if isinstance(cust_acc, dict):
                pwd = cust_acc.get("password")
                actor = cust_acc.get("actor_id")
                tenant = cust_acc.get("tenant_id")
                key = os.getenv("JWT_SIGNING_KEY", "")
                if (isinstance(pwd, str) and len(pwd) >= 20 and len(key) >= 32 and
                        actor and tenant and len(actor) <= 30 and len(tenant) <= 30 and
                        hmac.compare_digest(credentials.password.encode(), pwd.encode())):
                    token, lifetime = issue_dev_access_token(actor, tenant, "customer")
                    _logger.warning("universal_login_succeeded type=customer tenant_id=%s environment=%s",
                                    tenant, env.lower())
                    return {
                        "access_token": token,
                        "token_type": "Bearer",
                        "expires_in": lifetime,
                        "principal": {"actor_id": actor, "role": "customer", "tenant_id": tenant}
                    }

        raise AppError("E_UNAUTHORISED", "invalid sign-in credentials", customer_message_id="AUTH.INVALID_CREDENTIALS")

    def authorized_session(db, session_id: str, ctx):
        session = db.query(ChannelSessionRow).filter_by(channel_session_id=session_id).first()
        if not session:
            return None
        conversation = db.query(ConversationRow).filter_by(
            conversation_id=session.conversation_id, tenant_id=ctx["tenant_id"]).first()
        if not conversation or (ctx["role"] == "customer" and conversation.customer_id != ctx["actor_id"]):
            return None
        return session

    @app.post("/v1/auth/refresh")
    async def auth_refresh(request: Request):
        authorization = request.headers.get("Authorization", "")
        if not authorization.startswith("Bearer "):
            from ..core.rbac import _unauthenticated
            raise _unauthenticated()
        return rotate_refresh_token(authorization[7:].strip())

    # ---- CONV: inbound kanal (FR-CONV-001/004) ----
    @app.post("/v1/channels/{channel}/inbound")
    async def channel_inbound(channel: str, body: dict, request: Request,
                              ctx=Depends(require_perm("conversation.write"))):
        db = SessionLocal()
        try:
            if ctx["role"] == "customer":
                raise AppError("E_PROHIBITED", "customers must use the authenticated chat endpoint", customer_message_id="CONV.CHANNEL_ADAPTER_ONLY")
            ch = channel.upper()
            if ch not in ("WEB_CHAT", "EMAIL", "CONTACT_FORM", "WHATSAPP_SIM"):
                raise AppError("E_VALIDATION", "unknown channel", customer_message_id="CONV.CHANNEL_INVALID")
            # validasi lampiran: tolak exe/oversize (FR-CONV-004 AC1)
            for att in body.get("attachments", []):
                mime = (att.get("mime") or "").lower(); size = att.get("size_bytes", 0)
                if mime in ("application/x-msdownload", "application/x-executable") or att.get("filename", "").endswith(".exe") or size > 10*1024*1024:
                    audit_svc.emit("TNT-TEST", request.state.correlation_id, ctx["actor_type"], ctx["actor_id"],
                                   "attachment.rejected", "attachment", att.get("filename", "?"),
                                   "conversation-svc", conversation_id=None)
                    raise AppError("E_VALIDATION", "attachment rejected: format/ukuran tidak diizinkan. Terima: png/jpg/pdf <10MB",
                                   customer_message_id="CONV.ATTACHMENT_REJECTED")
            actor_handle = ctx["actor_id"] if ctx["role"] == "customer" else body.get("from_handle", "anon")
            return ConvSvc.ingest(db, ch, actor_handle, body.get("text", ""),
                                  body.get("provider_message_id"), body.get("subject"),
                                  ctx, request.state.correlation_id,
                                  tenant=ctx["tenant_id"],
                                  claimed_customer_id=(ctx["actor_id"] if ctx["role"] == "customer" else body.get("claimed_customer_id")))
        finally:
            db.close()

    # ---- Chat turn orkestrasi (FR-ORC) ----
    @app.post("/v1/chat/messages")
    async def chat_message(body: dict, request: Request, ctx=Depends(require_perm("conversation.write"))):
        db = SessionLocal()
        try:
            if ctx["role"] == "customer":
                try:
                    parsed = CustomerChatIn.model_validate(body) if hasattr(CustomerChatIn, "model_validate") else CustomerChatIn.parse_obj(body)
                except ValidationError as exc:
                    raise AppError("E_VALIDATION", "message must contain 1 to 4000 characters", customer_message_id="CONV.MESSAGE_INVALID") from exc
                if not parsed.text.strip():
                    raise AppError("E_VALIDATION", "message must contain non-whitespace text", customer_message_id="CONV.MESSAGE_INVALID")
                if parsed.channel != "WEB_CHAT":
                    raise AppError("E_VALIDATION", "customer web chat only supports WEB_CHAT", customer_message_id="CONV.CHANNEL_INVALID")
                if parsed.conversation_id:
                    owned = db.query(ConversationRow).filter_by(conversation_id=parsed.conversation_id,
                        tenant_id=ctx["tenant_id"], customer_id=ctx["actor_id"]).first()
                    if not owned: raise AppError("E_NOT_FOUND", "conversation not found", customer_message_id="CONV.NOT_FOUND")
                if parsed.conversation_id:
                    owned = db.query(ConversationRow).filter_by(conversation_id=parsed.conversation_id,
                        tenant_id=ctx["tenant_id"], customer_id=ctx["actor_id"]).first()
                    if not owned: raise AppError("E_NOT_FOUND", "conversation not found", customer_message_id="CONV.NOT_FOUND")
                key_header = request.headers.get("Idempotency-Key", "")
                if not re.fullmatch(r"[A-Za-z0-9._~-]{16,128}", key_header):
                    raise AppError("E_VALIDATION", "a valid Idempotency-Key is required", customer_message_id="CONV.IDEMPOTENCY_KEY_REQUIRED")
                request_id = hashlib.sha256(f'{ctx["tenant_id"]}\0{ctx["actor_id"]}\0{key_header}'.encode()).hexdigest()
                fingerprint = hashlib.sha256(json.dumps(parsed.model_dump() if hasattr(parsed, "model_dump") else parsed.dict(), sort_keys=True, separators=(",", ":")).encode()).hexdigest()
                prior = db.query(CustomerRequestRow).filter_by(request_id=request_id).first()
                if prior:
                    if prior.request_hash != fingerprint:
                        raise AppError("E_CONFLICT", "idempotency key was used with different content", customer_message_id="CONV.IDEMPOTENCY_CONFLICT")
                    if prior.state != "COMPLETE" or prior.response is None:
                        raise AppError("E_CONFLICT", "request is already being processed or did not complete", customer_message_id="CONV.REQUEST_IN_PROGRESS")
                    return prior.response
                ledger = CustomerRequestRow(request_id=request_id, tenant_id=ctx["tenant_id"], actor_id=ctx["actor_id"], request_hash=fingerprint, state="PROCESSING")
                db.add(ledger)
                try:
                    db.commit()
                except Exception:
                    db.rollback()
                    prior = db.query(CustomerRequestRow).filter_by(request_id=request_id).first()
                    if prior and prior.request_hash == fingerprint and prior.state == "COMPLETE": return prior.response
                    raise AppError("E_CONFLICT", "request is already being processed", customer_message_id="CONV.REQUEST_IN_PROGRESS")
                body = {"text": parsed.text, "channel": parsed.channel, "conversation_id": parsed.conversation_id}
            conv_id = body.get("conversation_id")
            actor_handle = ctx["actor_id"] if ctx["role"] == "customer" else body.get("from_handle", "anon")
            if not conv_id:
                # auto-ingest bila belum ada percakapan
                r = ConvSvc.ingest(db, body.get("channel", "WEB_CHAT"), actor_handle,
                                   body.get("text", ""), body.get("provider_message_id"),
                                   None, ctx, request.state.correlation_id,
                                   tenant=ctx["tenant_id"],
                                   claimed_customer_id=(ctx["actor_id"] if ctx["role"] == "customer" else body.get("claimed_customer_id")))
                conv_id = r["conversation_id"]
            else:
                # append inbound manual
                ConvSvc.ingest(db, body.get("channel", "WEB_CHAT"), actor_handle,
                               body.get("text", ""), body.get("provider_message_id"),
                               None, ctx, request.state.correlation_id,
                               tenant=ctx["tenant_id"],
                               conversation_id=conv_id,
                               claimed_customer_id=(ctx["actor_id"] if ctx["role"] == "customer" else body.get("claimed_customer_id")))
            result = Orc.run_turn(db, conv_id, body.get("text", ""), request.state.correlation_id,
                                  body.get("channel", "WEB_CHAT"), tenant_id=ctx["tenant_id"])
            result = {**result, "conversation_id": conv_id}
            if ctx["role"] == "customer":
                ledger.state = "COMPLETE"; ledger.response = result; db.commit()
            return result
        except Exception:
            if ctx.get("role") == "customer":
                try:
                    failed = db.query(CustomerRequestRow).filter_by(request_id=locals().get("request_id", "")).first()
                    if failed and failed.state == "PROCESSING":
                        failed.state = "FAILED"; db.commit()
                except Exception: db.rollback()
            raise
        finally:
            db.close()

    @app.get("/v1/customer/conversations")
    async def customer_conversations(limit: int = 20, cursor: str | None = None,
                                     ctx=Depends(require_perm("conversation.read"))):
        if ctx["role"] != "customer": raise AppError("E_PROHIBITED", "customer access required")
        if not 1 <= limit <= 50: raise AppError("E_VALIDATION", "limit must be between 1 and 50", customer_message_id="CONV.LIMIT_INVALID")
        db = SessionLocal()
        try:
            query = db.query(ConversationRow).filter_by(tenant_id=ctx["tenant_id"], customer_id=ctx["actor_id"])
            if cursor:
                try:
                    stamp, conv_cursor = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode().split("|", 1)
                    boundary = datetime.fromisoformat(stamp)
                except Exception: raise AppError("E_VALIDATION", "invalid cursor", customer_message_id="CONV.CURSOR_INVALID")
                query = query.filter((ConversationRow.last_activity_at < boundary) | ((ConversationRow.last_activity_at == boundary) & (ConversationRow.conversation_id < conv_cursor)))
            rows = query.order_by(ConversationRow.last_activity_at.desc(), ConversationRow.conversation_id.desc()).limit(limit + 1).all()
            more = len(rows) > limit; rows = rows[:limit]
            next_cursor = None
            if more and rows:
                last = rows[-1]
                raw = f"{last.last_activity_at.isoformat()}|{last.conversation_id}".encode()
                next_cursor = base64.urlsafe_b64encode(raw).decode().rstrip("=")
            return {"items": [{"conversation_id": row.conversation_id, "status": row.status, "language": row.language,
                               "origin_channel": row.origin_channel, "current_channel": row.current_channel,
                               "created_at": row.created_at.isoformat(), "last_activity_at": row.last_activity_at.isoformat()} for row in rows],
                    "next_cursor": next_cursor}
        finally: db.close()

    # ---- Read-model I-11 (TRD §7.3) — A produksi, B konsumsi ----
    @app.get("/v1/conversations/{conv_id}/read-model")
    async def read_model(conv_id: str, request: Request, limit: int = 50, cursor: str | None = None,
                         ctx=Depends(require_perm("conversation.read"))):
        db = SessionLocal()
        try:
            c = db.query(ConversationRow).filter_by(conversation_id=conv_id).first()
            if not c:
                raise AppError("E_NOT_FOUND", "conversation not found", customer_message_id="CONV.NOT_FOUND")
            if c.tenant_id != ctx["tenant_id"] or (ctx["role"] == "customer" and c.customer_id != ctx["actor_id"]):
                raise AppError("E_NOT_FOUND", "conversation not found", customer_message_id="CONV.NOT_FOUND")
            sess = db.query(ChannelSessionRow).filter_by(conversation_id=conv_id).all()
            msgs_query = db.query(MessageRow).filter_by(conversation_id=conv_id).order_by(MessageRow.sequence_no, MessageRow.message_id)
            ints = db.query(IntentRow).filter_by(conversation_id=conv_id).all()
            cases = db.query(BModels.CaseRow).filter_by(origin_conversation_id=conv_id).all()
            if ctx["role"] == "customer":
                if not 1 <= limit <= 100:
                    raise AppError("E_VALIDATION", "limit must be between 1 and 100", customer_message_id="CONV.LIMIT_INVALID")
                start_sequence, start_message = -1, ""
                if cursor:
                    try:
                        raw_cursor = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode()
                        sequence_text, start_message = raw_cursor.split("|", 1)
                        start_sequence = int(sequence_text)
                        if start_sequence < 0 or not start_message: raise ValueError("invalid cursor")
                    except Exception: raise AppError("E_VALIDATION", "invalid cursor", customer_message_id="CONV.CURSOR_INVALID")
                if cursor:
                    msgs_query = msgs_query.filter(or_(MessageRow.sequence_no > start_sequence,
                        and_(MessageRow.sequence_no == start_sequence, MessageRow.message_id > start_message)))
                msgs = msgs_query.limit(limit + 1).all()
                more = len(msgs) > limit
                msgs = msgs[:limit]
                next_cursor = base64.urlsafe_b64encode(f"{msgs[-1].sequence_no}|{msgs[-1].message_id}".encode()).decode().rstrip("=") if more and msgs else None
                return {"conversation": {"conversation_id": c.conversation_id, "status": c.status,
                                         "language": c.language},
                        "messages": [{"message_id": m.message_id, "sequence_no": m.sequence_no, "channel": m.channel, "direction": m.direction,
                                      "author_type": m.author_type, "content": m.content, "language": m.language,
                                      "occurred_at": m.occurred_at.isoformat(), "citations": m.citations}
                                     for m in msgs], "next_cursor": next_cursor}
            msgs = msgs_query.all()
            return {"conversation": {"conversation_id": c.conversation_id, "status": c.status,
                                     "language": c.language, "vulnerability_flag": c.vulnerability_flag,
                                     "reopen_count": c.reopen_count},
                    "customer": {"customer_id": c.customer_id},
                    "channel_sessions": [{"channel": s.channel, "assurance_level": s.assurance_level,
                                          "al_method": s.al_method, "lock_state": s.lock_state} for s in sess],
                    "messages": [{"sequence_no": m.sequence_no, "channel": m.channel, "direction": m.direction,
                                  "author_type": m.author_type, "content": m.content,
                                  "citations": m.citations, "tool_call_ids": m.tool_call_ids} for m in msgs],
                    "intents": [{"intent_code": i.intent_code, "confidence": i.confidence,
                                 "decision": i.decision} for i in ints],
                    "linked_objects": {"case_ids": [x.case_id for x in cases]},
                    "open_items": []}
        finally:
            db.close()

    # ---- AUTH (FR-AUTH) ----
    @app.post("/v1/auth/identify")
    async def auth_identify(body: dict, request: Request, ctx=Depends(require_perm("conversation.write"))):
        db = SessionLocal()
        try:
            s = authorized_session(db, body["channel_session_id"], ctx)
            if not s: raise AppError("E_NOT_FOUND", "session not found", customer_message_id="AUTH.SESSION_INVALID")
            return AuthSvc.identify(db, s, body.get("identifier", ""), request.state.correlation_id)
        finally:
            db.close()

    @app.post("/v1/auth/challenge")
    async def auth_challenge(body: dict, request: Request, ctx=Depends(require_perm("conversation.write"))):
        db = SessionLocal()
        try:
            s = authorized_session(db, body["channel_session_id"], ctx)
            if not s: raise AppError("E_NOT_FOUND", "session not found", customer_message_id="AUTH.SESSION_INVALID")
            return AuthSvc.challenge(s, body.get("purpose", "AL2"), request.state.correlation_id)
        finally:
            db.close()

    @app.post("/v1/auth/verify")
    async def auth_verify(body: dict, request: Request, ctx=Depends(require_perm("conversation.write"))):
        db = SessionLocal()
        try:
            s = authorized_session(db, body["channel_session_id"], ctx)
            if not s: raise AppError("E_NOT_FOUND", "session not found", customer_message_id="AUTH.SESSION_INVALID")
            return AuthSvc.verify(db, s, body["challenge_id"], body["code"], request.state.correlation_id)
        finally:
            db.close()

    @app.post("/v1/auth/consent")
    async def auth_consent(body: dict, request: Request, ctx=Depends(require_perm("conversation.write"))):
        db = SessionLocal()
        try:
            conversation_id = body.get("conversation_id", "")
            conversation = db.query(ConversationRow).filter_by(conversation_id=conversation_id,
                                                                tenant_id=ctx["tenant_id"]).first()
            if not conversation or (ctx["role"] == "customer" and conversation.customer_id != ctx["actor_id"]):
                raise AppError("E_NOT_FOUND", "conversation not found", customer_message_id="CONV.NOT_FOUND")
            customer_id = ctx["actor_id"] if ctx["role"] == "customer" else body.get("customer_id")
            return AuthSvc.record_consent(customer_id, conversation_id,
                                      body.get("purpose", "QA_REVIEW"), body.get("granted", True),
                                      body.get("text_version", "v1"), request.state.correlation_id)
        finally:
            db.close()

    # ---- KM (FR-KM) ----
    @app.post("/v1/knowledge/articles")
    async def km_create(body: dict, request: Request, ctx=Depends(require_perm("knowledge.write"))):
        db = SessionLocal()
        try:
            return KmSvc.create_article(db, body["title"], body["body"], body.get("language", "id"),
                                        body.get("intents", []), body.get("access_level", "CUSTOMER"),
                                        body.get("expires_at"), request.state.correlation_id, ctx["tenant_id"])
        finally:
            db.close()

    @app.get("/v1/knowledge/search")
    async def km_search(q: str, lang: str = "id", request: Request = None,
                        ctx=Depends(require_perm("knowledge.read"))):
        db = SessionLocal()
        try:
            for_agent = ctx["role"] in ("cs_agent", "supervisor")
            return KmSvc.search(db, q, lang, for_agent, request.state.correlation_id if request else "COR-?", ctx["tenant_id"])
        finally:
            db.close()

    # ---- KM: dokumen unggahan (FR-KM, Unit 11) ----
    @app.post("/v1/knowledge/documents/upload")
    async def km_upload_document(file: UploadFile = File(...), request: Request = None,
                                 ctx=Depends(require_human_perm("knowledge.document.ingest"))):
        db = SessionLocal()
        try:
            data = await file.read()
            filename = file.filename or "dokumen"
            result = KmSvc.ingest_document(db, data, filename, ctx,
                                           request.state.correlation_id if request else "COR-?",
                                           ctx["tenant_id"])
            _log_knowledge_diagnostic(db, ctx["tenant_id"], "upload", result.get("status", "unknown"))
            status_code = 200 if result.get("status") in ("ready",) and not result.get("replayed") else 200
            if result.get("status") == "failed":
                from fastapi.responses import JSONResponse
                return JSONResponse(status_code=422, content=result)
            return result
        except Exception as exc:
            _log_knowledge_diagnostic(db, ctx["tenant_id"], "upload", getattr(exc, "error_code", "error"))
            raise
        finally:
            db.close()

    @app.get("/v1/knowledge/documents")
    async def km_list_documents(status: str | None = None, request: Request = None,
                                ctx=Depends(require_human_perm("knowledge.read"))):
        db = SessionLocal()
        try:
            items = KmSvc.list_documents(db, ctx["tenant_id"], status)
            _log_knowledge_diagnostic(db, ctx["tenant_id"], "list", "ok")
            return {"items": items}
        finally:
            db.close()

    @app.get("/v1/knowledge/documents/{document_id}")
    async def km_get_document(document_id: str, request: Request = None,
                              ctx=Depends(require_human_perm("knowledge.read"))):
        db = SessionLocal()
        try:
            doc = KmSvc.get_document(db, document_id, ctx["tenant_id"])
            if not doc:
                raise AppError("E_NOT_FOUND", "dokumen tidak ditemukan",
                               customer_message_id="KM.DOCUMENT_NOT_FOUND")
            return doc
        finally:
            db.close()

    @app.post("/v1/knowledge/documents/{document_id}/retry")
    async def km_retry_document(document_id: str, request: Request = None,
                                ctx=Depends(require_human_perm("knowledge.document.ingest"))):
        db = SessionLocal()
        try:
            result = KmSvc.retry_document(db, document_id, ctx,
                                          request.state.correlation_id if request else "COR-?",
                                          ctx["tenant_id"])
            if result.get("status") == "failed":
                from fastapi.responses import JSONResponse
                return JSONResponse(status_code=422, content=result)
            return result
        finally:
            db.close()

    @app.put("/v1/knowledge/documents/{document_id}")
    @app.patch("/v1/knowledge/documents/{document_id}")
    async def km_update_document(document_id: str, body: dict, request: Request = None,
                                 ctx=Depends(require_human_perm("knowledge.document.ingest"))):
        db = SessionLocal()
        try:
            if not isinstance(body, dict):
                raise AppError("E_VALIDATION", "format permintaan tidak valid", customer_message_id="KM.INVALID_BODY")
            result = KmSvc.update_document(
                db, document_id, ctx,
                title=body.get("title"),
                content=body.get("content"),
                corr=request.state.correlation_id if request else "COR-?",
                tenant_id=ctx["tenant_id"],
            )
            _log_knowledge_diagnostic(db, ctx["tenant_id"], "update", result.get("status", "ok"))
            return result
        finally:
            db.close()

    @app.post("/v1/knowledge/documents/{document_id}/replace")
    async def km_replace_document_file(document_id: str, file: UploadFile = File(...),
                                       title: str | None = Form(None), request: Request = None,
                                       ctx=Depends(require_human_perm("knowledge.document.ingest"))):
        db = SessionLocal()
        try:
            data = await file.read()
            filename = file.filename or "dokumen"
            result = KmSvc.update_document(
                db, document_id, ctx,
                title=title,
                file_data=data,
                filename=filename,
                corr=request.state.correlation_id if request else "COR-?",
                tenant_id=ctx["tenant_id"],
            )
            _log_knowledge_diagnostic(db, ctx["tenant_id"], "replace", result.get("status", "ok"))
            return result
        finally:
            db.close()

    @app.delete("/v1/knowledge/documents/{document_id}")
    async def km_delete_document(document_id: str, request: Request = None,
                                 ctx=Depends(require_human_perm("knowledge.document.ingest"))):
        db = SessionLocal()
        try:
            result = KmSvc.delete_document(
                db, document_id, ctx,
                corr=request.state.correlation_id if request else "COR-?",
                tenant_id=ctx["tenant_id"],
            )
            _log_knowledge_diagnostic(db, ctx["tenant_id"], "delete", "ok")
            return result
        finally:
            db.close()

    # ---- TOOL registry + invoke (FR-TOOL) ----
    @app.get("/v1/tools/registry")
    async def tool_registry(ctx=Depends(require_perm("tool.invoke"))):
        _ = ctx
        return {"tools": [{"name": k, **v} for k, v in Gw.REGISTRY.items()],
                "prohibited": sorted(Gw.PROHIBITED)}

    @app.post("/v1/tools/invoke")
    async def tool_invoke(body: dict, request: Request, ctx=Depends(require_perm("tool.invoke"))):
        db = SessionLocal()
        try:
            tool, args = body["tool_name"], body.get("arguments", {})
            conv = body.get("conversation_id", "CNV-?")
            if not db.query(ConversationRow).filter_by(conversation_id=conv, tenant_id=ctx["tenant_id"]).first():
                raise AppError("E_NOT_FOUND", "conversation not found", customer_message_id="CONV.NOT_FOUND")
            sess = db.query(ChannelSessionRow).filter_by(conversation_id=conv).order_by(ChannelSessionRow.started_at.desc()).first()
            al = sess.assurance_level if sess else "AL0"
            dec = Gw.evaluate(tool, args, al, ctx, request.state.correlation_id, conv)
            if dec["decision"] != "ALLOW":
                return {"decision": dec, "executed": False}
            hit = Gw.idem_lookup(conv, tool, args)
            if hit:
                Gw.record_call(conv, tool, args, "REPLAYED", request.state.correlation_id, dec["policy_decision_id"])
                return {"decision": dec, "executed": True, "replayed": True, "result": hit}
            Gw.record_call(conv, tool, args, "SUCCESS", request.state.correlation_id, dec["policy_decision_id"])
            if tool == "customer_profile_lookup":
                res = Sim.profile_lookup(args.get("customer_id", "?"), request.state.correlation_id)
            elif tool == "account_lookup":
                res = Sim.account_lookup(args.get("ref", ""), request.state.correlation_id)
            elif tool == "transaction_lookup":
                res = Sim.transaction_lookup(args.get("ref", ""), request.state.correlation_id)
            elif tool == "card_status_update":
                res = Sim.card_block(args.get("last4", "4821"), args.get("action", "TEMP_BLOCK"), request.state.correlation_id)
            else:
                res = {"ok": True}
            Gw.idem_store(conv, tool, args, res)
            return {"decision": dec, "executed": True, "result": res}
        finally:
            db.close()

    # ---- CRM lookup/update/list + evidence link (tool milik B yang belum ada) ----
    @app.get("/v1/tickets")
    async def ticket_list(request: Request, conversation_id: str | None = None,
                          status: str | None = None, limit: int = 50,
                          ctx=Depends(require_perm("ticket.read"))):
        _ = request
        db = SessionLocal()
        try:
            from ..core.ids import short_reference
            q = db.query(BModels.TicketRow).filter_by(tenant_id=ctx["tenant_id"])
            if ctx["role"] == "customer":
                q = q.filter_by(customer_id=ctx["actor_id"])
            if conversation_id:
                q = q.filter_by(conversation_id=conversation_id)
            if status:
                q = q.filter_by(status=status)
            items = q.order_by(BModels.TicketRow.created_at.desc()).limit(limit).all()
            return [
                {
                    "ticket_id": t.ticket_id,
                    "customer_reference": short_reference("ticket", t.ticket_id),
                    "customer_id": t.customer_id,
                    "conversation_id": t.conversation_id,
                    "case_id": t.case_id,
                    "type": t.type,
                    "sub_type": t.sub_type,
                    "priority": t.priority,
                    "status": t.status,
                    "description": t.description,
                    "owner_queue": t.owner_queue,
                    "created_at": t.created_at.isoformat() if t.created_at else None,
                }
                for t in items
            ]
        finally:
            db.close()

    @app.get("/v1/tickets/{tid}")
    async def ticket_lookup(tid: str, request: Request, ctx=Depends(require_perm("ticket.read"))):
        _ = request
        db = SessionLocal()
        try:
            from ..core.ids import short_reference
            t = db.query(BModels.TicketRow).filter_by(ticket_id=tid, tenant_id=ctx["tenant_id"]).first()
            if t and ctx["role"] == "customer" and t.customer_id != ctx["actor_id"]: t = None
            if not t: raise AppError("E_NOT_FOUND", "ticket not found", customer_message_id="TICKET.NOT_FOUND")
            return {
                "ticket_id": t.ticket_id,
                "customer_reference": short_reference("ticket", t.ticket_id),
                "customer_id": t.customer_id,
                "conversation_id": t.conversation_id,
                "case_id": t.case_id,
                "status": t.status,
                "type": t.type,
                "priority": t.priority,
                "description": t.description,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
        finally:
            db.close()

    @app.patch("/v1/tickets/{tid}")
    async def ticket_update(tid: str, body: dict, request: Request, ctx=Depends(require_perm("ticket.update"))):
        db = SessionLocal()
        try:
            t = db.query(BModels.TicketRow).filter_by(ticket_id=tid, tenant_id=ctx["tenant_id"]).first()
            if not t: raise AppError("E_NOT_FOUND", "ticket not found", customer_message_id="TICKET.NOT_FOUND")
            if "status" in body: t.status = body["status"]
            db.commit()
            audit_svc.emit("TNT-TEST", request.state.correlation_id, ctx["actor_type"], ctx["actor_id"],
                           "ticket.status_changed", "ticket", tid, "ticket-svc")
            return {"ticket_id": tid, "status": t.status}
        finally:
            db.close()

    @app.get("/v1/cases")
    async def case_list(request: Request, conversation_id: str | None = None,
                        status: str | None = None, limit: int = 50,
                        ctx=Depends(require_perm("case.read"))):
        _ = request
        db = SessionLocal()
        try:
            q = db.query(BModels.CaseRow).filter_by(tenant_id=ctx["tenant_id"])
            if ctx["role"] == "customer":
                q = q.filter_by(customer_id=ctx["actor_id"])
            if conversation_id:
                q = q.filter_by(origin_conversation_id=conversation_id)
            if status:
                q = q.filter_by(status=status)
            items = q.order_by(BModels.CaseRow.logged_at.desc()).limit(limit).all()
            return [
                {
                    "case_id": c.case_id,
                    "customer_reference": c.customer_reference,
                    "customer_id": c.customer_id,
                    "conversation_id": c.origin_conversation_id,
                    "category": c.category,
                    "sub_category": c.sub_category,
                    "severity_proposed": c.severity_proposed,
                    "severity_confirmed": c.severity_confirmed,
                    "status": c.status,
                    "customer_visible_status": c.customer_visible_status,
                    "owner_queue": c.owner_queue,
                    "logged_at": c.logged_at.isoformat() if c.logged_at else None,
                }
                for c in items
            ]
        finally:
            db.close()

    @app.get("/v1/cases/{cid}")
    async def case_lookup(cid: str, request: Request, ctx=Depends(require_perm("case.read"))):
        _ = request
        db = SessionLocal()
        try:
            c = db.query(BModels.CaseRow).filter_by(case_id=cid, tenant_id=ctx["tenant_id"]).first()
            if c and ctx["role"] == "customer" and c.customer_id != ctx["actor_id"]: c = None
            if not c: raise AppError("E_NOT_FOUND", "case not found", customer_message_id="CASE.NOT_FOUND")
            return {
                "case_id": c.case_id,
                "customer_reference": c.customer_reference,
                "customer_id": c.customer_id,
                "conversation_id": c.origin_conversation_id,
                "category": c.category,
                "sub_category": c.sub_category,
                "status": c.status,
                "customer_visible_status": c.customer_visible_status,
                "logged_at": c.logged_at.isoformat() if c.logged_at else None
            }
        finally:
            db.close()

    @app.patch("/v1/cases/{cid}")
    async def case_update(cid: str, body: dict, request: Request, ctx=Depends(require_perm("case.update"))):
        db = SessionLocal()
        try:
            c = db.query(BModels.CaseRow).filter_by(case_id=cid, tenant_id=ctx["tenant_id"]).first()
            if not c: raise AppError("E_NOT_FOUND", "case not found", customer_message_id="CASE.NOT_FOUND")
            if "status" in body:
                c.status = body["status"]
                from .cases import INTERNAL_TO_CUSTOMER
                c.customer_visible_status = INTERNAL_TO_CUSTOMER.get(body["status"], c.customer_visible_status)
            if "severity_confirmed" in body:
                c.severity_confirmed = body["severity_confirmed"]
            db.commit()
            audit_svc.emit("TNT-TEST", request.state.correlation_id, ctx["actor_type"], ctx["actor_id"],
                           "case.status_changed", "case", cid, "case-svc")
            return {"case_id": cid, "status": c.status, "customer_visible_status": c.customer_visible_status}
        finally:
            db.close()

    @app.post("/v1/evidence/upload-link")
    async def evidence_link(body: dict, request: Request, ctx=Depends(require_perm("evidence.request"))):
        return {"upload_url": "/v1/attachments", "evidence_request_id": body.get("evidence_request_id"),
                "ttl_s": 300}

    # ---- SVC bantu: status kasar AL0 vs detail AL2 (BR-SVC-07) ----
    @app.get("/v1/status/{reference}")
    async def status_page(reference: str, request: Request, principal=Depends(optional_principal)):
        from ..modules import store as _  # noqa
        db = SessionLocal()
        try:
            c = db.query(BModels.CaseRow).filter_by(customer_reference=reference).first()
            if not c:
                return {"reference": reference, "status": "UNKNOWN"}
            if principal and (principal["tenant_id"] != c.tenant_id or
                              (principal["role"] == "customer" and principal["actor_id"] != c.customer_id)):
                return {"reference": reference, "status": "UNKNOWN"}
            return {"reference": reference, "status": c.customer_visible_status}
        finally:
            db.close()

    # ---- chaos/sim profile ----
    @app.post("/internal/sim-profile")
    async def sim_profile(body: dict, request: Request, ctx=Depends(require_perm("sla.read"))):
        _ = request
        if ctx["identity_type"] != "human" or ctx["role"] not in {"supervisor", "admin"}:
            from ..core.rbac import _forbidden
            raise _forbidden(ctx["role"], "human.simulation.configure")
        Sim.PROFILE["value"] = body.get("profile", "healthy")
        return {"sim_profile": Sim.PROFILE["value"]}

    return app
