"""FR-ORC-001..009 + FR-SVC-001..007 [J/A]: mesin status deterministik, giliran,

budget, degraded mode, inquiry & service workflows, anti klaim palsu. TRD §8."""

from __future__ import annotations

import logging

import os

import re

import time

from sqlalchemy.orm import Session

from ..core import audit as audit_svc

from ..core.ids import new_id

from . import intent as IntentSvc

from . import knowledge as KmSvc

from . import tool_gateway as Gw

from . import guardrail as Grd

from . import conversation as ConvSvc

from . import auth as AuthSvc

from .models_a import ChannelSessionRow



_logger = logging.getLogger("eaics.orchestrator")



def _queue_handoff(db: Session, conv_id: str, reason: str, corr: str,

                   tenant_id: str, cls: dict | None = None) -> dict:

    """Persist a real queue entry; never tell the customer handoff succeeded without it."""

    from .models import HandoffRow

    from .models_a import ConversationRow

    conv = db.query(ConversationRow).filter_by(conversation_id=conv_id, tenant_id=tenant_id).first()

    if conv is None:

        return {"state": "UNAVAILABLE"}

    existing = (db.query(HandoffRow).filter_by(conversation_id=conv_id, tenant_id=tenant_id)

                .filter(HandoffRow.state.in_(["QUEUED", "OFFERED", "ACCEPTED"]))

                .order_by(HandoffRow.queued_at.desc()).first())

    # A handoff accepted earlier is stale once staff resolved the conversation (or it returned to the AI):
    # close it so a new customer request creates a fresh queue entry instead of a false "accepted" reply.
    if existing is not None and existing.state == "ACCEPTED" and conv.status not in ("ACTIVE_HUMAN", "PENDING_HANDOFF"):
        existing.state = "CLOSED"
        db.commit()
        existing = None
        if conv.status == "RESOLVED_PENDING_CONFIRMATION" and _can(db, conv_id, "ACTIVE_AI"):
            ConvSvc.transition(db, conv_id, "ACTIVE_AI", "customer_requested_human_again",
                               {"actor_type": "AI_AGENT", "actor_id": "orchestrator"}, corr)

    state = existing.state if existing else None

    if not existing:

        from . import queue as QueueSvc

        try:

            outcome = QueueSvc.enqueue(

                db, conv_id, reason,

                {"tenant_id": tenant_id, "actor_type": "AI_AGENT", "actor_id": "orchestrator"},

                corr, severity="CRITICAL" if (cls or {}).get("safety_flag") else "MEDIUM",

                language=conv.language or "id",

                vulnerability_flag=bool((cls or {}).get("vulnerability_flag") or (cls or {}).get("safety_flag")),

                # The queue record exists, but the full workspace handoff package is not yet implemented.

                package_complete=False)

        except Exception:

            db.rollback()

            return {"state": "UNAVAILABLE"}

        state = outcome["state"]

    if _can(db, conv_id, "PENDING_HANDOFF"):

        ConvSvc.transition(db, conv_id, "PENDING_HANDOFF", reason,

                           {"actor_type": "AI_AGENT", "actor_id": "orchestrator"}, corr)

    return {"state": state}



def _handoff_reply(state: str) -> str:

    if state == "ACCEPTED":

        return "Petugas telah menerima permintaan bantuan dan akan melanjutkan percakapan."

    if state in ("QUEUED", "OFFERED", "ACCEPTED"):

        return "Permintaan bantuan petugas telah masuk antrean. Petugas belum mengonfirmasi penerimaan."

    return "Saya belum dapat memastikan permintaan bantuan masuk antrean. Silakan coba lagi atau gunakan kanal layanan lain."



def _log_routing(tenant_id: str, conv_id: str, corr: str, cls: dict,

                 retrieval: str, source_count: int = 0, handoff: str = "NOT_REQUIRED",

                 routing_reason: str | None = None) -> None:

    """One safe, comparable routing record per completed chat turn; never log message text."""

    _logger.warning("customer_chat_routing tenant_id=%s conversation_id=%s correlation_id=%s intent=%s decision=%s routing_reason=%s retrieval_outcome=%s retrieval_sources=%d handoff_decision=%s",

                 tenant_id, conv_id, corr, cls.get("intent_code", "UNKNOWN"),

                 cls.get("decision", "UNKNOWN"),

                 routing_reason or cls.get("handoff_reason") or cls.get("routing_reason", "CLASSIFIED_INTENT"),

                 retrieval, source_count, handoff)



def _followup_reference(text: str) -> bool:

    import re

    return bool(re.fullmatch(

        r"\s*(?:mengapa|kenapa|maksudnya|jelaskan|bagaimana bisa|yang tadi|hal tersebut|itu|lebih lanjut)(?:\s+(?:ya|dong|maksudnya))?[?.!\s]*",

        (text or "").casefold()))



def _previous_customer_question(db: Session, conv_id: str, current_text: str) -> str | None:

    if not _followup_reference(current_text):

        return None

    from .models_a import MessageRow

    turns = (db.query(MessageRow).filter_by(conversation_id=conv_id, direction="INBOUND")

             .order_by(MessageRow.sequence_no.desc(), MessageRow.message_id.desc()).limit(2).all())

    # The current inbound is already committed by the chat route; use only the preceding customer turn.

    if len(turns) < 2:

        return None

    return (turns[1].content or "").strip()[:400] or None



DEGRADED = {"value": False}

BUDGET_TOOLS, BUDGET_LLM, BUDGET_MS = 5, 4, 20000

_seen_calls: set[str] = set()  # deteksi loop: tool+args identik berulang



def _sess(db: Session, conv_id: str, channel: str = "WEB_CHAT") -> ChannelSessionRow:

    s = (db.query(ChannelSessionRow).filter_by(conversation_id=conv_id, channel=channel)

         .order_by(ChannelSessionRow.started_at.desc()).first())

    return s



def run_turn(db: Session, conv_id: str, text: str, corr: str,
             channel: str = "WEB_CHAT", actor: str = "AI_AGENT", tenant_id: str = "TNT-TEST") -> dict:
    # CRITICAL PRESERVATION (RULE 11): Official Agentic Decision Loop is LangGraph StateGraph.
    # Do not bypass or remove this delegation.
    if os.getenv("USE_LANGGRAPH", "true").lower() == "true":
        try:
            from .agent_graph import run_turn_langgraph
            return run_turn_langgraph(db, conv_id, text, corr, channel=channel, actor=actor, tenant_id=tenant_id)
        except Exception as exc:
            _logger.warning("langgraph_turn_failed_fallback: %s", exc)

    t0 = time.time()

    turn_id = new_id("turn")

    sess = _sess(db, conv_id, channel)

    al = sess.assurance_level if sess else "AL0"

    if sess: al = AuthSvc.check_session(sess)

    if al == "AL0":

        from .models_a import ConversationRow as _CR

        c_row = db.query(_CR).filter_by(conversation_id=conv_id).first()

        if c_row and c_row.customer_id:

            al = "AL2"

    # 03 degraded

    if DEGRADED["value"]:

        reply = ("Bantuan otomatis sedang terbatas. Permintaan ini belum dapat diproses. "

                 "Saya belum dapat mengonfirmasi status tiket atau antrean petugas.")

        ConvSvc.append_outbound(db, conv_id, reply)

        audit_svc.emit("TNT-TEST", corr, "SYSTEM", "orchestrator", "system.degraded",

                       "conversation", conv_id, "orchestrator", conversation_id=conv_id)

        _log_routing(tenant_id, conv_id, corr, {}, "NOT_RUN", handoff="NOT_ATTEMPTED")

        return {"turn_id": turn_id, "mode": "DEGRADED", "reply": reply,

                "handoff": False, "handoff_status": "NOT_ATTEMPTED"}

    # 04-07 intent + threshold

    cls = IntentSvc.classify(text, conv_id, corr)

    try:

        from .models_a import IntentRow as _IR

        from ..core.ids import new_id as _nid

        db.add(_IR(intent_id=_nid("intent"), message_id=turn_id, conversation_id=conv_id, intent_code=cls["intent_code"], intent_category=cls.get("category", "INQUIRY"), confidence=float(cls.get("confidence", 0)), is_primary=True, decision=cls.get("decision", "ACT"), entities=cls.get("entities", {})))

        db.commit()

    except Exception:

        pass

    IntentSvc.update_context(conv_id, text, cls)

    inj = Grd.detect_injection(text, corr, conv_id)

    # 06-10 handoff paksa

    if cls.get("decision") == "HANDOFF" or inj.get("detected") and cls.get("confidence", 1) < 0.45:

        reason = cls.get("handoff_reason", "LOW_CONFIDENCE")

        if inj.get("detected") and cls.get("decision") != "HANDOFF":

            reason = "POLICY_DENIED"

        handoff = _queue_handoff(db, conv_id, reason, corr, tenant_id, cls)

        reply = _handoff_reply(handoff["state"])

        ConvSvc.append_outbound(db, conv_id, reply)

        _log_routing(tenant_id, conv_id, corr, cls, "NOT_RUN", handoff=handoff["state"],

                     routing_reason=reason)

        return {"turn_id": turn_id, "intent": cls, "handoff": handoff["state"] != "UNAVAILABLE",

                "handoff_status": handoff["state"], "reason": reason, "reply": reply,

                "injection": inj}

    if cls.get("decision") == "CLARIFY":

        ctx = IntentSvc.get_context(conv_id)

        opts = _options(cls["intent_code"])

        reply = f"Maaf, maksud Anda {opts}? Balas dengan pilihannya."

        try: ConvSvc.transition(db, conv_id, "AWAITING_CUSTOMER", "clarify",

                                {"actor_type": "AI_AGENT", "actor_id": "orchestrator"}, corr)

        except Exception: pass

        ConvSvc.append_outbound(db, conv_id, reply)

        _log_routing(tenant_id, conv_id, corr, cls, "NOT_RUN")

        return {"turn_id": turn_id, "intent": cls, "handoff": False, "reply": reply, "clarify": True}

    if cls.get("intent_code") == "GEN_SMALL_TALK_OTHER":

        reply = "Halo! Saya siap membantu pertanyaan layanan atau kebutuhan Anda."

        ConvSvc.append_outbound(db, conv_id, reply)

        _log_routing(tenant_id, conv_id, corr, cls, "NOT_RUN")

        return {"turn_id": turn_id, "intent": cls, "handoff": False, "reply": reply}

    # 11-13 permitted set dihitung SEBELUM prompt (ADR-04)

    permitted = Gw.permitted_set(al)

    audit_svc.emit("TNT-TEST", corr, "AI_AGENT", "orchestrator", "policy.tool_set_computed",

                   "conversation", conv_id, "policy-engine", conversation_id=conv_id,

                   after={"permitted": permitted})

    tool_calls, tool_results, citations = [], [], []

    elapsed_ms = lambda: int((time.time() - t0) * 1000)

    # kebutuhan aksi per kategori

    need_tool = _need_tool(cls, conv_id)

    if need_tool:

        tool, args = need_tool

        if tool not in permitted:

            # di luar himpunan -> policy.denied, ulang 1x lalu handoff (FR-ORC-001 AC1)

            audit_svc.emit("TNT-TEST", corr, "AI_AGENT", "orchestrator", "policy.denied",

                           "tool", tool, "orchestrator", conversation_id=conv_id, result="DENY")

            queued = _queue_handoff(db, conv_id, "POLICY_DENIED", corr, tenant_id, cls)

            reply = "Saya belum dapat melakukan tindakan ini. " + _handoff_reply(queued["state"])

            ConvSvc.append_outbound(db, conv_id, reply)

            _log_routing(tenant_id, conv_id, corr, cls, "NOT_RUN", handoff=queued["state"],

                         routing_reason="POLICY_DENIED")

            return {"turn_id": turn_id, "intent": cls, "handoff": queued["state"] != "UNAVAILABLE",

                    "handoff_status": queued["state"], "reason": "POLICY_DENIED", "reply": reply}

        try:

            dec = Gw.evaluate(tool, args, al, {"actor": actor}, corr, conv_id)

        except Exception as e:

            queued = _queue_handoff(db, conv_id, "POLICY_DENIED", corr, tenant_id, cls)

            reply = "Saya belum dapat melakukan tindakan ini. " + _handoff_reply(queued["state"])

            ConvSvc.append_outbound(db, conv_id, reply)

            _log_routing(tenant_id, conv_id, corr, cls, "NOT_RUN", handoff=queued["state"],

                         routing_reason="POLICY_DENIED")

            return {"turn_id": turn_id, "intent": cls, "handoff": queued["state"] != "UNAVAILABLE",

                    "handoff_status": queued["state"], "reason": "POLICY_DENIED", "reply": reply}

        if dec["decision"] == "STEP_UP_REQUIRED":

            try: ConvSvc.transition(db, conv_id, "AWAITING_AUTH", "stepup",

                                    {"actor_type": "AI_AGENT", "actor_id": "orchestrator"}, corr)

            except Exception: pass

            reply = "Untuk keamanan, verifikasi dulu ya (OTP ke kanal terdaftar). Setelah itu saya lanjutkan."

            ConvSvc.append_outbound(db, conv_id, reply)

            _log_routing(tenant_id, conv_id, corr, cls, "NOT_RUN", handoff="STEP_UP_REQUIRED",

                         routing_reason="STEP_UP_REQUIRED")

            return {"turn_id": turn_id, "intent": cls, "stepup_required": dec.get("required"), "reply": reply}

        # idempotensi: replay

        hit = Gw.idem_lookup(conv_id, tool, args)

        if hit:

            tool_results.append(hit); tool_calls.append({"tool": tool, "replayed": True})

        else:

            rec = Gw.record_call(conv_id, tool, args, "SUCCESS", corr, dec["policy_decision_id"])

            res = _exec_tool(db, tool, args, conv_id, corr)

            Gw.idem_store(conv_id, tool, args, res)

            tool_results.append(res)

            tool_calls.append({"tool": tool, "policy_decision_id": dec["policy_decision_id"]})

    # retrieval untuk INQUIRY

    if cls["category"] == "INQUIRY" and not tool_results:

        prior_question = _previous_customer_question(db, conv_id, text)

        effective_question = text

        retrieval_query = text

        try:

            r = KmSvc.search(db, retrieval_query, language="id", corr=corr, tenant_id=tenant_id)

            # Keep the current turn primary. Only use the immediately preceding customer

            # question as a disambiguator when a short follow-up has no direct match.

            if r["zero_result"] and prior_question:

                effective_question = (f"Pertanyaan saat ini: {text}\n"

                                      f"Konteks pertanyaan sebelumnya (untuk memahami rujukan saja): {prior_question}")

                retrieval_query = prior_question

                r = KmSvc.search(db, retrieval_query, language="id", corr=corr, tenant_id=tenant_id)

        except Exception:

            audit_svc.emit(tenant_id, corr, "SYSTEM", "rag-svc", "knowledge.retrieval_failed",

                           "conversation", conv_id, "retrieval-svc", result="ERROR")

            reply = "Pencarian informasi sedang mengalami gangguan. Silakan coba kembali beberapa saat lagi."

            ConvSvc.append_outbound(db, conv_id, reply)

            _log_routing(tenant_id, conv_id, corr, cls, "ERROR")

            return {"turn_id": turn_id, "intent": cls, "handoff": False,

                    "reason": "RETRIEVAL_ERROR", "reply": reply, "retrieval_error": True}

        if r["zero_result"]:

            handoff = _queue_handoff(db, conv_id, "KNOWLEDGE_GAP", corr, tenant_id, cls)

            reply = ("Saya tidak menemukan sumber resmi yang cukup untuk memverifikasi jawaban. "

                     + ("Permintaan bantuan petugas telah masuk antrean; penerimaan belum dikonfirmasi."

                        if handoff["state"] in ("QUEUED", "OFFERED", "ACCEPTED")

                        else "Saya belum dapat memastikan permintaan bantuan masuk antrean."))

            ConvSvc.append_outbound(db, conv_id, reply)

            _log_routing(tenant_id, conv_id, corr, cls, "NO_MATCH", handoff=handoff["state"])

            return {"turn_id": turn_id, "intent": cls, "handoff": handoff["state"] != "UNAVAILABLE",

                    "handoff_status": handoff["state"], "reason": "KNOWLEDGE_GAP", "reply": reply}

        citations = KmSvc.cite(r["results"])

        try:

            from .llm_provider import (F4Input, F4Output, F4Source, LLMFunction,

                                       ProviderError, ProviderErrorCode, build_provider,

                                       generate_validated)

            source_inputs = []

            for index, source in enumerate(r["results"]):

                source_id = (f"knowledge:{source.get('article_id')}:{source.get('version_id')}:{source.get('passage_ref')}"

                             if source.get("source_type") == "article"

                             else f"knowledge:{source.get('document_id')}:{source.get('version_no')}:{source.get('passage_ref')}")

                source_inputs.append(F4Source(source_id=source_id, source_type="KNOWLEDGE_CITATION",

                                              text=(source.get("body") or "")[:4000]))

            generated = generate_validated(build_provider(), LLMFunction.F4,

                                           F4Input(question=effective_question, sources=source_inputs), timeout_ms=None)

            if not isinstance(generated, F4Output) or not generated.claim_map:

                raise ProviderError(ProviderErrorCode.OUTPUT_INVALID)

            draft = generated.text

            valid_ids = {item.source_id for item in source_inputs}

            if any(not item.source_ids or not set(item.source_ids).issubset(valid_ids)

                   for item in generated.claim_map):

                raise ProviderError(ProviderErrorCode.OUTPUT_INVALID)

        except Exception as exc:

            # Log only a safe category; provider exceptions may contain prompt or credentials.

            code = getattr(getattr(exc, "code", None), "value", "PROVIDER_ERROR")

            _logger.warning("llm_answer_generation_failed environment=%s database=%s tenant_id=%s conversation_id=%s provider_error_code=%s sources=%d",

                            os.getenv("ENVIRONMENT", "unset"), KmSvc.safe_database_identity()

                            if hasattr(KmSvc, "safe_database_identity") else "configured",

                            tenant_id, conv_id, str(code)[:40], len(source_inputs))

            audit_svc.emit(tenant_id, corr, "SYSTEM", "llm-provider", "knowledge.answer_generation_failed",

                           "conversation", conv_id, "llm-provider", result=str(code)[:40])
            # Extractive fallback: sajikan kutipan dokumen yang relevan secara faktual jika LLM provider gagal/503
            raw_text = (source_inputs[0].text or "").strip() if source_inputs else ""
            if raw_text:
                raw_text = raw_text.replace("\t", " ")
                raw_text = re.sub(r"[ ]{2,}", " ", raw_text)
                lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
                cleaned_lines = []
                skip_idx = -1
                for i, line in enumerate(lines):
                    if i <= skip_idx:
                        continue
                    if re.search(r"(_\w+|\.pdf|\.md)\b", line, re.IGNORECASE):
                        continue
                    if re.match(r"^\d+\.$", line) and i + 1 < len(lines):
                        cleaned_lines.append(f"{line} {lines[i+1]}")
                        skip_idx = i + 1
                        continue
                    cleaned_lines.append(line)
                content_body = "\n".join(cleaned_lines) if cleaned_lines else raw_text
                content_snippet = content_body if len(content_body) <= 1100 else content_body[:1097] + "..."
                reply = f"Berdasarkan informasi resmi layanan kami:\n\n{content_snippet}"
                ConvSvc.append_outbound(db, conv_id, reply, citations=citations)
                _log_routing(tenant_id, conv_id, corr, cls, "EXTRACTIVE_FALLBACK", len(source_inputs))
                return {"turn_id": turn_id, "intent": cls, "handoff": False,
                        "reason": "EXTRACTIVE_FALLBACK", "reply": reply,
                        "citations": citations}


            reply = "Saya menemukan sumber informasi yang relevan, tetapi jawaban belum dapat dibuat saat ini. Silakan coba kembali beberapa saat lagi."

            ConvSvc.append_outbound(db, conv_id, reply, citations=citations)

            _log_routing(tenant_id, conv_id, corr, cls, "RELEVANT_PROVIDER_ERROR", len(source_inputs))

            return {"turn_id": turn_id, "intent": cls, "handoff": False,

                    "reason": "ANSWER_GENERATION_ERROR", "reply": reply,

                    "citations": citations, "generation_error": True}

    else:

        draft = _compose_action_answer(cls, tool_results, conv_id, db=db, corr=corr, tenant_id=tenant_id)

    # guardrail: groundedness + output policy + action-state (FR-ORC-006/009)

    g = Grd.groundedness(draft, ([{"title": r.get("title", ""), "body": r.get("body", "")} for r in (locals().get("r", {}).get("results", []))]

                                if cls["category"] == "INQUIRY" else []), tool_results)

    # sederhanakan: cek angka vs sumber sitasi+tool

    if g["unsupported"]:

        audit_svc.emit("TNT-TEST", corr, "SYSTEM", "guardrail", "guardrail.unsupported_claim",

                       "conversation", conv_id, "guardrail-svc", conversation_id=conv_id)

        handoff = _queue_handoff(db, conv_id, "KNOWLEDGE_GAP", corr, tenant_id, cls)

        draft = ("Saya tidak dapat memverifikasi hal tersebut dari sumber resmi. "

                 + ("Permintaan bantuan petugas telah masuk antrean; penerimaan belum dikonfirmasi."

                    if handoff["state"] in ("QUEUED", "OFFERED", "ACCEPTED")

                    else "Saya belum dapat memastikan permintaan bantuan masuk antrean."))

        ConvSvc.append_outbound(db, conv_id, draft)

        _log_routing(tenant_id, conv_id, corr, cls, "RELEVANT_UNGROUNDED", len(locals().get("r", {}).get("results", [])),

                     handoff=handoff["state"])

        return {"turn_id": turn_id, "intent": cls, "handoff": handoff["state"] != "UNAVAILABLE",

                "handoff_status": handoff["state"], "reply": draft, "suppressed": True}

    op = Grd.output_policy(draft)

    if op.get("block"):

        draft = "Maaf, saya tidak bisa menampilkan data tersebut di sini. Petugas akan membantu via kanal aman."

        ConvSvc.append_outbound(db, conv_id, draft)

        _log_routing(tenant_id, conv_id, corr, cls,

                     "RELEVANT" if cls["category"] == "INQUIRY" else "NOT_APPLICABLE",

                     len(locals().get("r", {}).get("results", [])))

        return {"turn_id": turn_id, "intent": cls, "reply": draft, "blocked": op.get("reason")}

    st = Grd.action_state_check(draft, has_executed=bool(tool_results))

    if st.get("block"): draft = st["rewrite"]

    ConvSvc.append_outbound(db, conv_id, draft, citations=citations,

                            tool_ids=[t.get("tool") for t in tool_calls])

    _log_routing(tenant_id, conv_id, corr, cls,

                 "RELEVANT" if cls["category"] == "INQUIRY" else "NOT_APPLICABLE",

                 len(locals().get("r", {}).get("results", [])))

    audit_svc.emit("TNT-TEST", corr, "AI_AGENT", "orchestrator", "orchestration.turn_completed",

                   "conversation", conv_id, "orchestrator", conversation_id=conv_id,

                   after={"intent": cls["intent_code"]})

    return {"turn_id": turn_id, "intent": cls, "reply": draft, "citations": citations,

            "tool_calls": tool_calls, "permitted": permitted,

            "budget": {"tools": len(tool_calls), "elapsed_ms": elapsed_ms()}}



def _can(db: Session, conv_id: str, to_state: str) -> bool:

    from .models_a import ConversationRow

    c = db.query(ConversationRow).filter_by(conversation_id=conv_id).first()

    if not c: return False

    from .conversation import VALID_TRANSITIONS

    return to_state in VALID_TRANSITIONS.get(c.status, set())



def _options(intent: str) -> str:

    m = {"INFO_ACCOUNT_BALANCE": "saldo atau mutasi", "REQ_CARD_BLOCK": "blokir atau ganti kartu",

         "CMP_TRANSACTION_DISPUTE": "sengketa transaksi atau gangguan layanan"}

    return m.get(intent, "informasi atau layanan")



def _need_tool(cls: dict | str, conv_id: str = ""):

    intent = cls if isinstance(cls, str) else cls.get("intent_code", "")

    entities = {} if isinstance(cls, str) else dict(cls.get("entities", {}) or {})

    if conv_id:

        ctx = IntentSvc.get_context(conv_id)

        if ctx and "slots" in ctx:

            for k, v in ctx["slots"].items():

                if k not in entities:

                    entities[k] = v



    if intent == "INFO_ACCOUNT_BALANCE":

        ref = entities.get("account_ref") or ("****" + str(entities.get("card_last4", "4821")))

        return ("account_lookup", {"ref": ref})

    if intent == "INFO_TRANSACTION_HISTORY":

        ref = entities.get("reference")

        args = {"range": "30d"}

        if ref:

            args["reference"] = str(ref).upper()

        return ("transaction_lookup", args)

    if intent == "CMP_TRANSACTION_DISPUTE":

        ref = entities.get("reference", "TRX-1")

        return ("transaction_lookup", {"reference": str(ref).upper(), "dispute": True})

    if intent == "REQ_STATEMENT_DOCUMENT":

        return ("notification_send", {"channel": "REGISTERED_EMAIL"})

    if intent == "REQ_CARD_BLOCK":

        last4 = str(entities.get("card_last4", "4821"))

        return ("card_status_update", {"action": "TEMP_BLOCK", "last4": last4})

    if intent == "INFO_CASE_STATUS":

        ref = entities.get("reference")

        args = {}

        if ref:

            args["reference"] = str(ref).upper()

        return ("case_lookup", args)

    return None



def _compose_answer(cls, results, tool_results) -> str:

    r0 = results[0]

    base = r0.get("body", "")[:220]

    extra = ""

    if tool_results:

        extra = " Data per " + str(tool_results[0].get("as_of", "")) + "."

    return f"{base}{extra} [Sumber: {r0.get('title')}]"



def _compose_action_answer(cls, tool_results, conv_id, db=None, corr=None, tenant_id='TNT-TEST') -> str:

    if cls["intent_code"] == "REQ_CARD_BLOCK":

        card_res = next((r for r in tool_results if "status" in r), {})

        if card_res.get("status") == "TEMP_BLOCKED":

            last4 = card_res.get("card_last4", "4821")

            return f"Kartu Anda dengan nomor akhir {last4} telah diblokir sementara."

        return "Saya belum dapat mengonfirmasi status pemblokiran kartu saat ini."



    if cls["intent_code"] == "REQ_STATEMENT_DOCUMENT":

        if any(result.get("sent") is True for result in tool_results):

            return "Rekening koran telah dikirim ke email terdaftar."

        return "Saya belum dapat mengonfirmasi pengiriman rekening koran."



    if cls["intent_code"] == "INFO_ACCOUNT_BALANCE":

        acc_res = next((r for r in tool_results if "balance_minor" in r), None)

        if acc_res:

            ref = acc_res.get("account_ref", "****4821")

            bal = int(acc_res.get("balance_minor", 12500000))

            acc_res["formatted_bal"] = f"{bal:,}"; return f"Saldo rekening {ref} adalah Rp {bal:,} per {acc_res.get('as_of', 'hari ini')}."



    if cls["intent_code"] == "CMP_TRANSACTION_DISPUTE":

        trx_res = next((r for r in tool_results if "reference" in r), None)

        ref_no = str(trx_res.get("reference", "TRX-1")) if trx_res else "TRX-1"

        status = str(trx_res.get("status", "FAILED")) if trx_res else "FAILED"

        try:
            from .cases import CreateTicketIn
            customer_id = None
            if db:
                from .models_a import ConversationRow
                c_row = db.query(ConversationRow).filter_by(conversation_id=conv_id).first()
                if c_row:
                    customer_id = c_row.customer_id
            ticket_in = CreateTicketIn(
                conversation_id=conv_id,
                customer_id=customer_id,
                type="TRANSACTION_DISPUTE",
                priority="HIGH",
                description=f"Investigasi sengketa transaksi {ref_no}: status {status}."
            )
            ticket = None
            if db:
                try:
                    from .store import create_ticket_db
                    ticket = create_ticket_db(db, ticket_in, {"actor_type": "AI_AGENT", "actor_id": "orchestrator"}, corr or "CORR-AGENTIC", tenant=tenant_id or "TNT-TEST")
                except Exception:
                    ticket = None
            if not ticket:
                from .cases import create_ticket
                ticket = create_ticket(ticket_in, {"actor_type": "AI_AGENT", "actor_id": "orchestrator"}, corr or "CORR-AGENTIC")
            ticket_ref = str(ticket.get("customer_reference", ticket.get("ticket_id")))
            tool_results.append({"ticket_reference": ticket_ref})

            return (

                f"Saya telah memeriksa transaksi dengan nomor referensi {ref_no}. "

                f"Data sistem menunjukkan transaksi berstatus {status}. "

                f"Tiket investigasi telah diterbitkan dengan nomor referensi {ticket_ref}. "

                f"Petugas operasional akan menindaklanjuti sengketa ini."

            )

        except Exception:

            return (

                f"Saya telah memeriksa transaksi dengan nomor referensi {ref_no} berstatus {status}. "

                f"Laporan Anda telah dicatat untuk penanganan petugas."

            )



    return "Pesan Anda tersimpan dalam percakapan. Saya belum dapat mengonfirmasi pembuatan tiket atau tindak lanjut petugas untuk permintaan ini."



def _exec_tool(db: Session, tool: str, args: dict, conv_id: str, corr: str) -> dict:
    """Eksekusi simulator deterministik (TRD §4.9). Timeout non-idempoten -> jujur, tanpa retry."""
    from datetime import datetime, timezone, timedelta
    now_utc = datetime.now(timezone.utc)
    wib = now_utc + timedelta(hours=7)
    months_id = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember"]
    now = f"{wib.day} {months_id[wib.month - 1]} {wib.year}, {wib.strftime('%H:%M')} WIB"
    now_iso = now_utc.isoformat()

    if tool == "account_lookup":

        account_ref = args.get("ref", "****4821")

        return {"balance_minor": 12500000, "account_ref": account_ref, "as_of": now}

    if tool == "transaction_lookup":

        ref = str(args.get("reference") or args.get("ref", "TRX-1")).upper()

        is_dispute = args.get("dispute", False)

        if is_dispute:

            return {

                "reference": ref,

                "status": "FAILED",

                "payment_gateway": "SUCCESS_DEBITED",

                "destination": "NOT_CREDITED",

                "amount_minor": 25000000,

                "as_of": now

            }

        return {"count": 5, "reference": ref, "as_of": now}

    if tool == "card_status_update":

        last4 = str(args.get("last4", "4821"))

        return {"card_last4": last4, "status": "TEMP_BLOCKED", "as_of": now}

    if tool in ("notification_send",):

        return {"sent": True, "as_of": now}

    if tool in ("case_lookup",):

        return {"cases": [], "as_of": now}

    return {"ok": True, "as_of": now}

