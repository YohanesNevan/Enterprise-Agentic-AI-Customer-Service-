"""EAICS modular monolith — PRODUK BERSAMA A+B (FRD/TRD compliant). TRD §4, ADR-01."""
from fastapi import FastAPI, Request, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from datetime import datetime, timezone
import logging
import os
from importlib.metadata import PackageNotFoundError, version as package_version
from .core.correlation import CorrelationMiddleware
from .core.errors import AppError
from .core.rbac import require_perm, require_human_perm, _forbidden
from .core.dev_auth import validate_dev_customer_auth_config
from .contracts.vocabularies import Severity
from .modules import cases as CaseSvc
from .modules import evidence as EvSvc
from .modules import handoff as HoSvc
from .modules import sla_engine as SlaSvc
from .modules import sla_tick as SlaTick
from .modules import escalation as EscSvc
from .modules import approvals as ApSvc
from .modules import qa as QaSvc
from .modules import qa_db as QaDb
from .modules import analytics_copilot as AnaSvc
from .modules import analytics_db as AnaDb
from .modules import store as Store
from .modules import outbox as Outbox
from .modules import queue as QueueSvc
from .modules import knowledge as Knowledge
from .core import audit as audit_svc
from .core.db import Base, engine, SessionLocal, safe_database_identity
from .modules import models as _models  # noqa: F401 — registrasi tabel
from .modules import models_a as _models_a  # noqa: F401 — tabel Kelompok A
from .modules.routes_a import register as register_a

app = FastAPI(title="EAICS-B", version="0.3.0",
              description="Kelompok B: case/ticket, evidence, handoff, SLA Beat, outbox, approval, QA, analitik. Kontrak TRD §16.")
validate_dev_customer_auth_config()
app.add_middleware(CorrelationMiddleware)
cors_origins = [origin.strip() for origin in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",") if origin.strip()]
if cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Correlation-Id", "Idempotency-Key"],
    )

# TRD §14.2: create_all untuk skeleton; Alembic single-head untuk migrasi benaran (lihat alembic/)
Base.metadata.create_all(bind=engine)
register_a(app)

def _runtime_llm_sdk_version() -> str:
    try:
        return package_version("google-genai")
    except PackageNotFoundError:
        return "not-installed"

_runtime_logger = logging.getLogger("eaics.runtime")
_runtime_logger.setLevel(logging.INFO)
_runtime_logger.warning(
    "runtime_started environment=%s database=%s knowledge_upload_dir=%s llm_provider=%s llm_model=%s llm_timeout_ms=%s llm_endpoint=%s llm_sdk=%s llm_key_configured=%s",
    os.getenv("ENVIRONMENT", "unset"), safe_database_identity(), Knowledge.UPLOAD_DIR,
    os.getenv("LLM_PROVIDER", "stub"), os.getenv("LLM_MODEL", "unset"),
    os.getenv("LLM_TIMEOUT_MS", "10000"), "https://generativelanguage.googleapis.com",
    _runtime_llm_sdk_version(), bool(os.getenv("LLM_API_KEY", "").strip()))

@app.exception_handler(AppError)
async def app_error_handler(_: Request, exc: AppError):
    return JSONResponse(status_code=exc.http_status, content=exc.envelope())

@app.get("/healthz")
async def healthz(): return {"status": "ok", "time": datetime.now(timezone.utc).isoformat()}

@app.get("/", include_in_schema=False)
async def index():
    """Landing agar buka http://localhost:8000/ tidak 404 — arahkan ke endpoint yang benar."""
    return {"service": "EAICS-B", "version": "0.3.0",
            "docs": "/docs", "openapi": "/openapi.json",
            "health": "/healthz", "ready": "/readyz",
            "workspace_ui_dev": "http://localhost:5173",
            "note": "Protected API routes require a bearer token issued by a configured trusted issuer."}

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    from fastapi.responses import Response
    return Response(status_code=204)

@app.get("/readyz")
async def readyz():
    from sqlalchemy import text
    db_ok = True
    try:
        with engine.connect() as c:
            c.execute(text("SELECT 1"))
    except Exception:
        db_ok = False
    return {"api": "up", "db": "up" if db_ok else "down", "sla_engine": "up",
            "outbox": "available" if db_ok else "unavailable"}

# ---- I-01..I-10 tool milik B (dipanggil A via gateway) ----
@app.post("/v1/tickets")
async def create_ticket(body: CaseSvc.CreateTicketIn, request: Request,
                        ctx=Depends(require_perm("ticket.create"))):
    db = SessionLocal()
    try:
        from .modules.models_a import ConversationRow
        conversation = db.query(ConversationRow).filter_by(
            conversation_id=body.conversation_id, tenant_id=ctx["tenant_id"]).first()
        if (not conversation or (ctx["role"] == "customer" and conversation.customer_id != ctx["actor_id"])
                or (body.customer_id and body.customer_id != conversation.customer_id)):
            raise AppError("E_NOT_FOUND", "conversation not found", customer_message_id="CONV.NOT_FOUND")
        body = body.model_copy(update={"customer_id": conversation.customer_id})
        if ctx["role"] == "customer":
            body = body.model_copy(update={"customer_id": ctx["actor_id"]})
        return Store.create_ticket_db(db, body, ctx, request.state.correlation_id, tenant=ctx["tenant_id"])
    finally:
        db.close()

@app.post("/v1/cases")
async def create_case(body: CaseSvc.CreateCaseIn, request: Request,
                      ctx=Depends(require_perm("case.create"))):
    db = SessionLocal()
    try:
        from .modules.models_a import ConversationRow
        conversation = db.query(ConversationRow).filter_by(
            conversation_id=body.conversation_id, tenant_id=ctx["tenant_id"]).first()
        if (not conversation or (ctx["role"] == "customer" and conversation.customer_id != ctx["actor_id"])
                or (body.customer_id and body.customer_id != conversation.customer_id)):
            raise AppError("E_NOT_FOUND", "conversation not found", customer_message_id="CONV.NOT_FOUND")
        body = body.model_copy(update={"customer_id": conversation.customer_id})
        if ctx["role"] == "customer":
            body = body.model_copy(update={"customer_id": ctx["actor_id"]})
        return Store.create_case_db(db, body, ctx, request.state.correlation_id, tenant=ctx["tenant_id"])
    finally:
        db.close()

@app.post("/v1/cases/{case_id}/evidence-requests")
async def evidence_request(case_id: str, body: dict, request: Request,
                           ctx=Depends(require_perm("evidence.request"))):
    db = SessionLocal()
    try:
        if not db.query(_models.CaseRow).filter_by(case_id=case_id, tenant_id=ctx["tenant_id"]).first():
            raise AppError("E_NOT_FOUND", "case not found", customer_message_id="CASE.NOT_FOUND")
    finally:
        db.close()
    return EvSvc.create_request(case_id, body.get("items", []), body.get("reason", ""),
                                body.get("due_at"), ctx, request.state.correlation_id)

@app.post("/v1/sla/calculate")
async def sla_calculate(body: dict, request: Request, ctx=Depends(require_perm("sla.read"))):
    from datetime import datetime as dt
    created = dt.fromisoformat(body["created_at"])
    return SlaSvc.calculate(body["object_type"], body.get("category", "GENERAL"),
                            body.get("severity", "MEDIUM"), created, body.get("timezone", "Asia/Jakarta"))

@app.post("/v1/handoffs")
async def handoff_request(body: dict, request: Request, ctx=Depends(require_perm("handoff.initiate"))):
    return HoSvc.build_package(body.get("conversation_id", "CNV-?"), request.state.correlation_id,
                               body.get("reason_code", "CUSTOMER_REQUEST"), ctx, body)

@app.post("/v1/notifications")
async def notifications(body: dict, request: Request, ctx=Depends(require_perm("sla.read"))):
    ch = body.get("channel", "")
    if not ch.startswith("REGISTERED_"):
        raise AppError("E_VALIDATION", "only REGISTERED_* channels allowed",
                       customer_message_id="NOTIF.CHANNEL_INVALID")
    return {"notification_id": "NTF-stub", "state": "QUEUED"}

# ---- workspace B ----
@app.post("/v1/cases/{case_id}/close")
async def close_case(case_id: str, body: dict, request: Request, ctx=Depends(require_perm("case.close"))):
    db = SessionLocal()
    try:
        return Store.close_case_db(db, case_id, body.get("checklist", {}), ctx, request.state.correlation_id)
    finally:
        db.close()

@app.post("/v1/cases/{case_id}/reopen")
async def reopen_case(case_id: str, body: dict, request: Request, ctx=Depends(require_perm("case.update"))):
    db = SessionLocal()
    try:
        return Store.reopen_case_db(db, case_id, body.get("reason", ""), ctx, request.state.correlation_id)
    finally:
        db.close()

@app.post("/v1/approvals")
async def approval_request(body: dict, request: Request, ctx=Depends(require_perm("case.update"))):
    db = SessionLocal()
    try:
        from .modules.models_a import ConversationRow
        if not db.query(ConversationRow).filter_by(conversation_id=body["conversation_id"], tenant_id=ctx["tenant_id"]).first():
            raise AppError("E_NOT_FOUND", "conversation not found", customer_message_id="CONV.NOT_FOUND")
        return ApSvc.request_approval(db, body["conversation_id"], body["tool_name"], body.get("args", {}),
                                      body.get("justification", ""), body.get("risk_class", "WRITE_MEDIUM"),
                                      ctx, request.state.correlation_id)
    finally:
        db.close()

@app.post("/v1/approvals/{aid}/decide")
async def approval_decide(aid: str, body: dict, request: Request,
                          ctx=Depends(require_perm("tool.invoke_write_sensitive"))):
    db = SessionLocal()
    try:
        return ApSvc.decide(db, aid, body["decision"], body.get("comment", ""),
                            ctx, request.state.correlation_id)
    finally:
        db.close()

@app.get("/v1/analytics/operational")
async def analytics_operational(ctx=Depends(require_perm("analytics.read"))):
    _ = ctx
    db = SessionLocal()
    try:
        return AnaDb.operational(db, ctx["tenant_id"])
    finally:
        db.close()

@app.get("/v1/analytics/driver-tree")
async def analytics_tree(ctx=Depends(require_perm("analytics.read"))):
    _ = ctx
    db = SessionLocal()
    try:
        return AnaDb.driver_tree(db, ctx["tenant_id"])
    finally:
        db.close()

@app.get("/v1/analytics/resolution")
async def analytics_resolution(ctx=Depends(require_perm("analytics.read"))):
    _ = ctx
    db = SessionLocal()
    try:
        return AnaDb.resolution(db, ctx["tenant_id"])
    finally:
        db.close()

@app.get("/v1/analytics/handoff")
async def analytics_handoff(ctx=Depends(require_perm("analytics.read"))):
    _ = ctx
    db = SessionLocal()
    try:
        return AnaDb.handoff_stats(db, ctx["tenant_id"])
    finally:
        db.close()

@app.get("/v1/analytics/qa")
async def analytics_qa(ctx=Depends(require_perm("analytics.read"))):
    _ = ctx
    db = SessionLocal()
    try:
        return QaDb.summary_db(db, ctx["tenant_id"])
    finally:
        db.close()

@app.get("/v1/analytics/export.csv")
async def analytics_export(kind: str = "cases", ctx=Depends(require_perm("analytics.read"))):
    from fastapi.responses import PlainTextResponse
    _ = ctx
    db = SessionLocal()
    try:
        if kind == "cases":
            rows = [{"case_id": c.case_id, "status": c.status, "category": c.category,
                     "severity": c.severity_confirmed, "reopen_count": c.reopen_count}
                    for c in db.query(_models.CaseRow).filter_by(tenant_id=ctx["tenant_id"]).all()]
        else:
            rows = [{"handoff_id": h.handoff_id, "reason": h.reason_code, "priority": h.priority_score,
                     "state": h.state} for h in db.query(_models.HandoffRow).filter_by(tenant_id=ctx["tenant_id"]).all()]
        return PlainTextResponse(AnaDb.to_csv(rows), media_type="text/csv")
    finally:
        db.close()

@app.get("/v1/approvals")
async def approvals_list(state: str | None = None, ctx=Depends(require_perm("case.update"))):
    _ = ctx
    db = SessionLocal()
    try:
        return {"items": ApSvc.list_approvals(db, state, ctx["tenant_id"])}
    finally:
        db.close()

@app.get("/v1/approvals/{aid}")
async def approvals_detail(aid: str, ctx=Depends(require_perm("case.update"))):
    _ = ctx
    db = SessionLocal()
    try:
        a = ApSvc.get_approval(db, aid, ctx["tenant_id"])
        return {**a, "note": "argumen persis yang akan dieksekusi + hash — bandingkan sebelum setujui (BR-ORC-07)"}
    finally:
        db.close()

@app.post("/v1/qa/sample")
async def qa_sample(body: dict, request: Request, ctx=Depends(require_perm("qa.review"))):
    _ = ctx
    db = SessionLocal()
    try:
        return QaDb.draw_sample_db(db, seed=int(body.get("seed", 42)), corr=request.state.correlation_id,
                                   tenant_id=ctx["tenant_id"])
    finally:
        db.close()

@app.post("/v1/qa/reviews")
async def qa_review(body: dict, request: Request, ctx=Depends(require_perm("qa.review"))):
    db = SessionLocal()
    try:
        if not db.query(_models.CaseRow).filter_by(case_id=body["item_id"], tenant_id=ctx["tenant_id"]).first():
            raise AppError("E_NOT_FOUND", "case not found", customer_message_id="CASE.NOT_FOUND")
        return QaDb.score_db(db, body["item_id"], body.get("scores", {}),
                             ctx["actor_id"], request.state.correlation_id,
                             auto_fail=body.get("auto_fail"))
    finally:
        db.close()

@app.post("/v1/qa/findings")
async def qa_finding(body: dict, request: Request, ctx=Depends(require_perm("qa.review"))):
    db = SessionLocal()
    try:
        from .modules.models import QaReviewRow
        review = db.query(QaReviewRow).filter_by(review_id=body["review_id"]).first()
        case = db.query(_models.CaseRow).filter_by(case_id=review.item_id, tenant_id=ctx["tenant_id"]).first() if review else None
        if not case:
            raise AppError("E_NOT_FOUND", "review not found", customer_message_id="QA.NOT_FOUND")
        return QaDb.add_finding_db(db, body["review_id"], body["type"],
                                   body.get("severity", "MEDIUM"),
                                   body.get("description", ""),
                                   request.state.correlation_id, ctx)
    finally:
        db.close()

@app.post("/v1/copilot/suggest")
async def copilot_suggest(body: dict, request: Request, ctx=Depends(require_perm("case.read"))):
    return AnaSvc.suggest_reply(body.get("conversation_id", "CNV-?"), request.state.correlation_id)

@app.get("/v1/audit/trail/{correlation_id}")
async def audit_trail(correlation_id: str, reason: str, ctx=Depends(require_perm("audit.read"))):
    if len(reason.strip()) < 8:
        raise AppError("E_VALIDATION", "audit read reason is required", customer_message_id="AUDIT.REASON_REQUIRED")
    audit_svc.emit(ctx["tenant_id"], correlation_id, ctx["actor_type"], ctx["actor_id"],
                   "audit.trail_read", "audit_trail", correlation_id, "audit-api", reason=reason.strip())
    return {"trail": audit_svc.trail(correlation_id, ctx["tenant_id"])}

# ---- ops B: SLA Beat + outbox (TRD §4.15, FR-SLA-003/005) ----
@app.post("/internal/sla-tick")
async def sla_tick(request: Request, ctx=Depends(require_perm("sla.read"))):
    _ = ctx
    db = SessionLocal()
    try:
        return SlaTick.tick(db, corr=request.state.correlation_id)
    finally:
        db.close()

@app.get("/internal/outbox-status")
async def outbox_status(ctx=Depends(require_perm("sla.read"))):
    _ = ctx
    db = SessionLocal()
    try:
        pending = Outbox.tenant_query(db, ctx["tenant_id"]).filter_by(state="PENDING").count()
        sent = Outbox.tenant_query(db, ctx["tenant_id"]).filter_by(state="SENT").count()
        return {"pending": pending, "sent": sent}
    finally:
        db.close()

@app.post("/internal/outbox-drain")
async def outbox_drain(request: Request, ctx=Depends(require_perm("sla.read"))):
    _ = ctx
    db = SessionLocal()
    try:
        return Outbox.drain(db, corr=request.state.correlation_id, tenant_id=ctx["tenant_id"])
    finally:
        db.close()

# ---- workspace B: antrean + aksi agen (FR-WS-002..006) ----
@app.post("/v1/workspace/queue/enqueue")
async def ws_enqueue(body: dict, request: Request, ctx=Depends(require_perm("handoff.initiate"))):
    db = SessionLocal()
    try:
        from .modules.models_a import ConversationRow
        if not db.query(ConversationRow).filter_by(conversation_id=body["conversation_id"], tenant_id=ctx["tenant_id"]).first():
            raise AppError("E_NOT_FOUND", "conversation not found", customer_message_id="CONV.NOT_FOUND")
        return QueueSvc.enqueue(db, body["conversation_id"], body.get("reason_code", "CUSTOMER_REQUEST"),
                                ctx, request.state.correlation_id,
                                severity=body.get("severity", "MEDIUM"),
                                skill_tags=body.get("skill_tags", []),
                                language=body.get("language", "id"),
                                vulnerability_flag=body.get("vulnerability_flag", False),
                                package_complete=body.get("package_complete", True),
                                queue_id=body.get("queue_id", "Q-GENERAL"))
    finally:
        db.close()

@app.get("/v1/workspace/queue")
async def ws_queue(queue_id: str | None = None, skills: str | None = None,
                   ctx=Depends(require_perm("handoff.accept"))):
    _ = ctx
    db = SessionLocal()
    try:
        agent_skills = skills.split(",") if skills else None
        return {"items": QueueSvc.list_queue(db, ctx["tenant_id"], queue_id, agent_skills)}
    finally:
        db.close()

@app.post("/v1/workspace/handoffs/{hid}/accept")
async def ws_accept(hid: str, body: dict, request: Request, ctx=Depends(require_human_perm("handoff.accept"))):
    if ctx["role"] not in {"cs_agent", "supervisor"}:
        raise _forbidden(ctx["role"], "handoff.accept")
    db = SessionLocal()
    try:
        return QueueSvc.accept(db, hid, ctx["actor_id"], ctx, request.state.correlation_id)
    finally:
        db.close()

@app.post("/v1/workspace/handoffs/{hid}/transfer")
async def ws_transfer(hid: str, body: dict, request: Request, ctx=Depends(require_human_perm("case.update"))):
    if ctx["role"] not in {"cs_agent", "supervisor"}:
        raise _forbidden(ctx["role"], "case.update")
    db = SessionLocal()
    try:
        return QueueSvc.transfer(db, hid, body.get("to_queue", "Q-GENERAL"),
                                 body.get("reason", ""), body.get("note", ""),
                                 ctx, request.state.correlation_id)
    finally:
        db.close()

@app.post("/v1/workspace/conversations/{conv_id}/messages")
async def ws_agent_message(conv_id: str, body: dict, request: Request,
                           ctx=Depends(require_human_perm("conversation.write"))):
    if ctx["role"] not in {"cs_agent", "supervisor"}:
        raise _forbidden(ctx["role"], "conversation.write")
    content = body.get("content") if isinstance(body, dict) else None
    if not isinstance(content, str) or not content.strip() or len(content) > 4000:
        raise AppError("E_VALIDATION", "message must contain 1 to 4000 non-whitespace characters",
                       customer_message_id="CONV.MESSAGE_INVALID")
    db = SessionLocal()
    try:
        from .modules import conversation as ConvSvc
        return ConvSvc.append_agent_reply(db, conv_id, content, ctx["actor_id"],
                                          ctx["tenant_id"], request.state.correlation_id)
    finally:
        db.close()

@app.post("/v1/workspace/conversations/{conv_id}/resolve")
async def ws_resolve_conversation(conv_id: str, request: Request,
                                  ctx=Depends(require_human_perm("conversation.write"))):
    if ctx["role"] not in {"cs_agent", "supervisor"}:
        raise _forbidden(ctx["role"], "conversation.write")
    db = SessionLocal()
    try:
        from .modules.models_a import ConversationRow
        conversation = db.query(ConversationRow).filter_by(
            conversation_id=conv_id, tenant_id=ctx["tenant_id"]).first()
        if not conversation:
            raise AppError("E_NOT_FOUND", "conversation not found", customer_message_id="CONV.NOT_FOUND")
        handoff = (db.query(_models.HandoffRow).filter_by(
            conversation_id=conv_id, tenant_id=ctx["tenant_id"])
            .order_by(_models.HandoffRow.queued_at.desc()).first())
        if not handoff or handoff.state != "ACCEPTED" or handoff.accepted_by != ctx["actor_id"]:
            raise AppError("E_CONFLICT", "active handoff is not assigned to this agent",
                           customer_message_id="HANDOFF.NOT_ASSIGNED")
        if conversation.status != "ACTIVE_HUMAN":
            raise AppError("E_CONFLICT", "conversation is not in active human handling",
                           customer_message_id="CONV.STATE")
        from .modules import conversation as ConvSvc
        return ConvSvc.transition(db, conv_id, "RESOLVED_PENDING_CONFIRMATION",
                                  "agent_marked_handled", ctx, request.state.correlation_id)
    finally:
        db.close()

@app.get("/v1/workspace/conversations/{conv_id}")
async def ws_read_model(conv_id: str, ctx=Depends(require_perm("conversation.read"))):
    """FR-WS-003 satu layar: alasan handoff + ringkasan + SLA + kasus/tiket + audit.
    Stub read-model A (transkrip/intent/tool) — diganti kontrak I-11 asli saat A siap."""
    if ctx["role"] == "customer":
        from .core.rbac import _forbidden
        raise _forbidden(ctx["role"], "agent.workspace.read")
    db = SessionLocal()
    try:
        from .modules.models_a import ConversationRow, MessageRow, IntentRow, ToolCallRow
        conversation = db.query(ConversationRow).filter_by(conversation_id=conv_id, tenant_id=ctx["tenant_id"]).first()
        if not conversation:
            raise AppError("E_NOT_FOUND", "conversation not found", customer_message_id="CONV.NOT_FOUND")
        h = db.query(_models.HandoffRow).filter_by(conversation_id=conv_id, tenant_id=ctx["tenant_id"]).order_by(_models.HandoffRow.queued_at.desc()).first()
        cases = db.query(_models.CaseRow).filter_by(origin_conversation_id=conv_id, tenant_id=ctx["tenant_id"]).all()
        tickets = db.query(_models.TicketRow).filter_by(conversation_id=conv_id, tenant_id=ctx["tenant_id"]).all()
        messages = (db.query(MessageRow).filter_by(conversation_id=conv_id)
                    .order_by(MessageRow.sequence_no.desc()).limit(100).all())
        messages.reverse()
        intents = db.query(IntentRow).filter_by(conversation_id=conv_id).order_by(IntentRow.classified_at).all()
        tool_calls = db.query(ToolCallRow).filter_by(conversation_id=conv_id).order_by(ToolCallRow.called_at).all()
        sla_ids = [c.case_id for c in cases] + [t.ticket_id for t in tickets]
        from .core.ids import short_reference
        sla = db.query(_models.SlaRecordRow).filter(_models.SlaRecordRow.object_id.in_(sla_ids)).all() if sla_ids else []
        # Assemble Handoff Context Package (TRD §16.4 & Mitra Slide 20)
        customer_msgs = [m.content for m in messages if m.author_type == "CUSTOMER" and m.content]
        customer_problem = customer_msgs[0] if customer_msgs else "Tidak ada pesan keluhan yang tercatat."
        last_customer_msg = customer_msgs[-1] if customer_msgs else ""
        primary_intent = intents[-1] if intents else None

        intent_code_str = primary_intent.intent_code if primary_intent else (conversation.intent_current or "OTHER_UNCLASSIFIED")
        rec_action = "Lakukan verifikasi data pelanggan dan tanyakan rincian kendala lebih lanjut."
        if "BLOCK" in intent_code_str:
            rec_action = "Periksa status pemblokiran kartu pada sistem kartu. Tawarkan pembuatan kartu pengganti jika diperlukan."
        elif "DISPUTE" in intent_code_str or "REFUND" in intent_code_str:
            rec_action = "Periksa detail mutasi/transaksi yang disengketakan dan pastikan bukti bayar telah diverifikasi."
        elif "BALANCE" in intent_code_str or "HISTORY" in intent_code_str:
            rec_action = "Lakukan verifikasi identitas nasabah sebelum mengonfirmasi rincian saldo atau mutasi rekening."
        elif "STATEMENT" in intent_code_str:
            rec_action = "Konfirmasi alamat email terdaftar nasabah untuk pengiriman rekening koran resmi."
        elif h and h.reason_code == "KNOWLEDGE_GAP":
            rec_action = "Eskalasi akibat informasi di Knowledge Base belum lengkap. Jelaskan kebijakan resmi perusahaan kepada nasabah."

        urgency_level = "HIGH" if (conversation.safety_flag or (h and h.severity == "CRITICAL")) else ("MEDIUM" if (h and h.severity == "HIGH") else "LOW")
        sentiment_level = "NEGATIVE" if (conversation.safety_flag or ("DISPUTE" in intent_code_str or "BLOCK" in intent_code_str)) else "NEUTRAL"

        handoff_pkg = {
            "customer_id": conversation.customer_id or "ANONYMOUS",
            "customer_name": conversation.customer_id or "Nasabah",
            "intent_code": intent_code_str,
            "confidence": primary_intent.confidence if primary_intent else 0.85,
            "decision": primary_intent.decision if primary_intent else "HANDOFF",
            "urgency": urgency_level,
            "sentiment": sentiment_level,
            "summary": customer_problem,
            "last_message": last_customer_msg,
            "reason": h.reason_code if h else "DIRECT_ASSISTANCE",
            "tools_called": [t.tool_name for t in tool_calls],
            "package_complete": h.package_complete if h else True,
            "recommended_action": rec_action,
        }

        return {"conversation_id": conv_id,
                "conversation": {"status": conversation.status, "language": conversation.language,
                                 "intent_current": conversation.intent_current,
                                 "vulnerability_flag": conversation.vulnerability_flag,
                                 "safety_flag": conversation.safety_flag} if conversation else None,
                "handoff": {"handoff_id": h.handoff_id, "reason_code": h.reason_code, "priority_score": h.priority_score,
                            "severity": h.severity, "state": h.state,
                            "accepted_by": h.accepted_by} if h else None,
                "handoff_package": handoff_pkg,
                "cases": [{"case_id": c.case_id, "customer_reference": c.customer_reference, "status": c.status, "severity_confirmed": c.severity_confirmed, "category": c.category} for c in cases],
                "tickets": [{"ticket_id": t.ticket_id, "customer_reference": short_reference("ticket", t.ticket_id), "status": t.status, "type": t.type, "priority": t.priority, "description": t.description} for t in tickets],
                "messages": [{"message_id": m.message_id, "sequence_no": m.sequence_no, "direction": m.direction,
                              "author_type": m.author_type, "author_id": m.author_id, "content": m.content,
                              "citations": m.citations, "tool_call_ids": m.tool_call_ids,
                              "occurred_at": m.occurred_at.isoformat()} for m in messages],
                "intents": [{"intent_code": i.intent_code, "confidence": i.confidence,
                             "decision": i.decision, "classified_at": i.classified_at.isoformat()} for i in intents],
                "tool_calls": [{"tool_call_id": t.tool_call_id, "tool_name": t.tool_name,
                                "status": t.status, "error_code": t.error_code,
                                "correlation_id": t.correlation_id, "called_at": t.called_at.isoformat()}
                               for t in tool_calls],
                "sla": [{"sla_id": s.sla_id, "state": s.state,
                         "resolution_due_at": s.resolution_due_at.isoformat()} for s in sla],
                "read_model_version": "1.0"}
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Unit 09: Supervisor & Complaint Officer Operations
# ---------------------------------------------------------------------------
@app.get("/v1/workspace/escalations")
async def ws_escalations(role_target: str | None = None, ctx=Depends(require_perm("sla.read"))):
    """Retrieve escalations filtered for supervisor or complaint officer."""
    if ctx["role"] not in {"supervisor", "complaint_officer", "admin", "management"}:
        raise _forbidden(ctx["role"], "escalation.read")
    db = SessionLocal()
    try:
        from .modules import escalation as EscSvc
        target = role_target or ("SUPERVISOR" if ctx["role"] == "supervisor" else ("COMPLAINT_OFFICER" if ctx["role"] == "complaint_officer" else None))
        items = EscSvc.list_escalations_db(db, target_role=target, tenant_id=ctx["tenant_id"])
        return {"items": items, "count": len(items)}
    finally:
        db.close()


@app.post("/v1/workspace/escalations/{eid}/acknowledge")
async def ws_ack_escalation(eid: str, request: Request, ctx=Depends(require_human_perm("sla.read"))):
    """Acknowledge an escalation alert."""
    if ctx["role"] not in {"supervisor", "complaint_officer", "admin"}:
        raise _forbidden(ctx["role"], "escalation.acknowledge")
    db = SessionLocal()
    try:
        from .modules import escalation as EscSvc
        res = EscSvc.acknowledge_escalation_db(db, eid, ctx["actor_id"], request.state.correlation_id, ctx["tenant_id"])
        if not res:
            raise AppError("E_NOT_FOUND", "escalation not found", customer_message_id="ESCALATION.NOT_FOUND")
        return res
    finally:
        db.close()


@app.get("/v1/workspace/sla/records")
async def ws_sla_records(status: str | None = None, ctx=Depends(require_perm("sla.read"))):
    """Retrieve active SLA records and impending breach alerts."""
    if ctx["role"] not in {"supervisor", "complaint_officer", "cs_agent", "admin", "management"}:
        raise _forbidden(ctx["role"], "sla.read")
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        query = db.query(_models.SlaRecordRow).filter_by(tenant_id=ctx["tenant_id"])
        if status:
            query = query.filter(_models.SlaRecordRow.state == status.upper())
        records = query.order_by(_models.SlaRecordRow.resolution_due_at.asc()).limit(100).all()
        items = []
        for r in records:
            reso_due = r.resolution_due_at
            if reso_due.tzinfo is None:
                reso_due = reso_due.replace(tzinfo=timezone.utc)
            remaining_mins = int((reso_due - now).total_seconds() / 60)
            is_breached = (now > reso_due and r.state not in ("MET", "PAUSED"))
            is_at_risk = (not is_breached and remaining_mins <= 120 and r.state == "RUNNING")
            effective_state = "BREACHED" if is_breached else ("AT_RISK" if is_at_risk else r.state)
            items.append({
                "sla_id": r.sla_id,
                "object_type": r.object_type,
                "object_id": r.object_id,
                "state": effective_state,
                "started_at": r.started_at.isoformat() if r.started_at else "",
                "first_response_due_at": r.first_response_due_at.isoformat() if r.first_response_due_at else "",
                "resolution_due_at": r.resolution_due_at.isoformat() if r.resolution_due_at else "",
                "remaining_minutes": remaining_mins,
                "is_breached": is_breached,
                "is_at_risk": is_at_risk,
            })
        return {"items": items, "count": len(items)}
    finally:
        db.close()


@app.patch("/v1/tickets/{tid}/assign")
async def ws_reassign_ticket(tid: str, body: dict, request: Request, ctx=Depends(require_human_perm("ticket.update"))):
    """Supervisor ticket assignment and queue transfer."""
    if ctx["role"] not in {"supervisor", "complaint_officer", "admin"}:
        raise _forbidden(ctx["role"], "ticket.assign")
    owner_queue = body.get("owner_queue")
    if not owner_queue or not str(owner_queue).strip():
        raise AppError("E_VALIDATION", "owner_queue is required", customer_message_id="TICKET.QUEUE_REQUIRED")
    db = SessionLocal()
    try:
        ticket = db.query(_models.TicketRow).filter_by(ticket_id=tid, tenant_id=ctx["tenant_id"]).first()
        if not ticket:
            raise AppError("E_NOT_FOUND", "ticket not found", customer_message_id="TICKET.NOT_FOUND")
        old_queue = ticket.owner_queue
        ticket.owner_queue = str(owner_queue).strip()
        db.commit()
        audit_svc.emit(ctx["tenant_id"], request.state.correlation_id, "STAFF", ctx["actor_id"],
                       "ticket.reassigned", "ticket", tid, "ticket-svc",
                       before={"owner_queue": old_queue}, after={"owner_queue": ticket.owner_queue, "reason": body.get("reason", "")})
        return {
            "ticket_id": tid,
            "owner_queue": ticket.owner_queue,
            "status": ticket.status,
            "updated_by": ctx["actor_id"],
        }
    finally:
        db.close()


@app.post("/v1/cases/{cid}/adjudicate")
async def ws_adjudicate_case(cid: str, body: dict, request: Request, ctx=Depends(require_human_perm("case.close"))):
    """Complaint Officer formal case adjudication and dispute settlement."""
    if ctx["role"] not in {"complaint_officer", "supervisor"}:
        raise _forbidden(ctx["role"], "case.adjudicate")
    decision = (body.get("decision") or "").upper()
    if decision not in {"UPHELD", "REJECTED", "SETTLED"}:
        raise AppError("E_VALIDATION", "decision must be UPHELD, REJECTED, or SETTLED", customer_message_id="CASE.DECISION_INVALID")
    db = SessionLocal()
    try:
        case_obj = db.query(_models.CaseRow).filter_by(case_id=cid, tenant_id=ctx["tenant_id"]).first()
        if not case_obj:
            raise AppError("E_NOT_FOUND", "case not found", customer_message_id="CASE.NOT_FOUND")
        now = datetime.now(timezone.utc)
        case_obj.status = "RESOLVED" if decision != "REJECTED" else "CLOSED"
        case_obj.customer_visible_status = "RESOLVED" if decision != "REJECTED" else "CLOSED"
        case_obj.severity_confirmed = case_obj.severity_proposed
        
        # Mark corresponding SLA record as MET
        sla_rec = db.query(_models.SlaRecordRow).filter_by(object_id=cid, tenant_id=ctx["tenant_id"]).first()
        if sla_rec:
            sla_rec.state = "MET"
        
        db.commit()
        audit_svc.emit(ctx["tenant_id"], request.state.correlation_id, "STAFF", ctx["actor_id"],
                       "case.adjudicated", "case", cid, "complaint-svc",
                       after={
                           "decision": decision,
                           "compensation_amount": body.get("compensation_amount"),
                           "notes": body.get("notes", ""),
                           "customer_explanation": body.get("customer_explanation", ""),
                       })
        return {
            "case_id": cid,
            "customer_reference": case_obj.customer_reference,
            "adjudication_decision": decision,
            "status": case_obj.status,
            "customer_visible_status": case_obj.customer_visible_status,
            "adjudicated_by": ctx["actor_id"],
            "adjudicated_at": now.isoformat(),
        }
    finally:
        db.close()

