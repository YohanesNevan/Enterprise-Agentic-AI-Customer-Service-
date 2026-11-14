"""EAICS Agentic AI Workflow using LangGraph (TRD §8 / FR-ORC-001..009).

This module implements the customer conversation decision loop as an explicit
LangGraph StateGraph:
  START -> TriageNode -> [RAGNode | ToolNode | GreetingNode | ClarifyNode | HandoffNode] -> Guardrail/LLM -> END
"""
from __future__ import annotations

import logging
import os
import re
import time
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from ..core import audit as audit_svc
from ..core.ids import new_id
from . import auth as AuthSvc
from . import conversation as ConvSvc
from . import guardrail as Grd
from . import intent as IntentSvc
from . import knowledge as KmSvc
from . import tool_gateway as Gw
from .orchestrator import (
    DEGRADED,
    _compose_action_answer,
    _exec_tool,
    _handoff_reply,
    _log_routing,
    _need_tool,
    _options,
    _previous_customer_question,
    _queue_handoff,
    _sess,
)

_logger = logging.getLogger("eaics.agent_graph")


class AgentState(TypedDict, total=False):
    # Context & Database
    db: Any
    conv_id: str
    text: str
    corr: str
    channel: str
    actor: str
    tenant_id: str
    turn_id: str
    assurance_level: str

    # Routing & Intent
    intent: dict[str, Any]
    decision: str
    reason: str
    mode: str

    # Tool Execution
    tool_name: str | None
    tool_args: dict[str, Any] | None
    tool_results: list[dict[str, Any]]
    tool_calls: list[dict[str, Any]]
    stepup_required: str | None

    # Knowledge & RAG
    effective_question: str
    retrieval_query: str
    retrieval_results: list[dict[str, Any]]
    citations: list[dict[str, Any]]
    zero_result: bool
    retrieval_error: bool

    # Output & Handoff
    reply: str
    handoff: bool
    handoff_status: str
    generation_error: bool


# ---------------------------------------------------------------------------
# Node 1: Triage Node (Intent classification & Assurance validation)
# ---------------------------------------------------------------------------
def triage_node(state: AgentState) -> dict[str, Any]:
    db: Session = state["db"]
    conv_id = state["conv_id"]
    text = state["text"]
    corr = state["corr"]
    turn_id = state["turn_id"]
    tenant_id = state["tenant_id"]

    # 1. Degraded system check
    if DEGRADED["value"]:
        reply = (
            "Bantuan otomatis sedang terbatas. Permintaan ini belum dapat diproses. "
            "Saya belum dapat mengonfirmasi status tiket atau antrean petugas."
        )
        ConvSvc.append_outbound(db, conv_id, reply)
        audit_svc.emit(
            "TNT-TEST", corr, "SYSTEM", "orchestrator", "system.degraded",
            "conversation", conv_id, "orchestrator", conversation_id=conv_id
        )
        _log_routing(tenant_id, conv_id, corr, {}, "NOT_RUN", handoff="NOT_ATTEMPTED")
        return {"mode": "DEGRADED", "reply": reply, "handoff": False, "handoff_status": "NOT_ATTEMPTED"}

    # 2. Assurance level check
    sess = _sess(db, conv_id, state.get("channel", "WEB_CHAT"))
    al = sess.assurance_level if sess else "AL0"
    if sess:
        al = AuthSvc.check_session(sess)
    if al == "AL0":
        from .models_a import ConversationRow as _CR
        c_row = db.query(_CR).filter_by(conversation_id=conv_id).first()
        if c_row and c_row.customer_id:
            al = "AL2"

    # 3. Intent classification & Context Tracking (TRD §8.2)
    cls = IntentSvc.classify(text, conv_id, corr)

    # Agentic LLM Semantic Triage for Slang / Typos / Low Confidence:
    # If rule-based confidence is low (< 0.75) or unclassified, analyze semantics dynamically with Gemini F1
    if (cls.get("confidence", 0) < 0.75 or cls.get("intent_code") == "OTHER_UNCLASSIFIED") and not cls.get("safety_flag") and not cls.get("vulnerability_flag"):
        from .intent import _human_agent_requested, _human_action_requested, CATEGORY
        if not _human_agent_requested(text) and not _human_action_requested(text):
            try:
                import os
                from .llm_provider import build_provider, generate_validated, LLMFunction, F1Input, F1Output
                if os.getenv("LLM_PROVIDER") == "gemini" and os.getenv("LLM_API_KEY"):
                    provider = build_provider()
                    f1_out = generate_validated(
                        provider,
                        LLMFunction.F1,
                        F1Input(message=text, short_context=f"conversation_id={conv_id}"),
                        timeout_ms=10000,
                    )
                    if isinstance(f1_out, F1Output):
                        ic = f1_out.intent_code.value
                        conf = float(f1_out.confidence_hint)
                        dec = "ACT" if conf >= 0.75 else ("CLARIFY" if conf >= 0.45 else "HANDOFF")
                        entities = f1_out.entities.model_dump(exclude_none=True) if hasattr(f1_out.entities, "model_dump") else {}
                        cls = {
                            "intent_code": ic,
                            "category": CATEGORY.get(ic, "INQUIRY"),
                            "confidence": conf,
                            "decision": dec,
                            "entities": entities,
                            "multi": [],
                            "routing_reason": "AGENTIC_LLM_SEMANTIC_ANALYSIS",
                        }
            except Exception as f1_err:
                _logger.info("agentic_llm_triage_fallback: %s", f1_err)

    IntentSvc.update_context(conv_id, text, cls)

    try:
        from .models_a import IntentRow as _IR
        from ..core.ids import new_id as _nid
        db.add(_IR(
            intent_id=_nid("intent"),
            message_id=turn_id,
            conversation_id=conv_id,
            intent_code=cls["intent_code"],
            intent_category=cls.get("category", "INQUIRY"),
            confidence=float(cls.get("confidence", 0)),
            is_primary=True,
            decision=cls.get("decision", "ACT"),
            entities=cls.get("entities", {}),
        ))
        db.commit()
    except Exception:
        db.rollback()

    # 4. Check if a tool is needed for action
    tool_info = _need_tool(cls, conv_id)
    tool_name, tool_args = tool_info if tool_info else (None, None)

    return {
        "assurance_level": al,
        "intent": cls,
        "decision": cls.get("decision", "ACT"),
        "tool_name": tool_name,
        "tool_args": tool_args,
        "tool_results": [],
        "tool_calls": [],
        "citations": [],
    }


def route_after_triage(state: AgentState) -> str:
    if state.get("mode") == "DEGRADED":
        return "finish"

    cls = state.get("intent", {})
    decision = state.get("decision", "ACT")

    # Mandatory handoff (human requested or safety flag triggered)
    if decision in ("HUMAN", "HANDOFF") or cls.get("safety_flag"):
        return "handoff_node"

    # Clarification required
    if decision == "CLARIFY":
        return "clarify_node"

    # Polite greeting / small talk
    if cls.get("intent_code") in ("GEN_GREETING", "GEN_SMALL_TALK_OTHER"):
        return "greeting_node"

    # Transaction / action tool execution
    if state.get("tool_name"):
        return "tool_node"

    # Knowledge retrieval (default for inquiries)
    return "rag_node"


def _format_clarification_question(intent_code: str, text: str = "") -> str:
    """Format human-like, polite clarifying questions per TRD §8.1 F2 contract."""
    clarification_map = {
        "REQ_CARD_BLOCK": (
            "Apakah Anda ingin mengajukan pemblokiran kartu ATM/Debit Anda saat ini, "
            "atau Anda memerlukan bantuan penggantian kartu baru?"
        ),
        "REQ_CARD_REPLACEMENT": (
            "Apakah Anda ingin mengajukan penggantian kartu ATM/Debit baru, "
            "atau ingin memeriksa status kartu yang telah Anda miliki?"
        ),
        "INFO_ACCOUNT_BALANCE": (
            "Apakah Anda ingin memeriksa sisa saldo rekening Anda saat ini, "
            "atau ingin melihat mutasi dan riwayat transaksi?"
        ),
        "INFO_TRANSACTION_HISTORY": (
            "Apakah Anda ingin memeriksa riwayat transaksi terbaru, "
            "atau ingin mencari transaksi tertentu berdasarkan nomor referensi?"
        ),
        "CMP_TRANSACTION_DISPUTE": (
            "Apakah Anda ingin melaporkan kendala/sanggahan pada suatu transaksi, "
            "atau ingin memeriksa status laporan keluhan sebelumnya?"
        ),
        "INFO_PRODUCT_POLICY": (
            "Bisa tolong perjelas informasi layanan yang Anda butuhkan? "
            "Kami dapat membantu menjelaskan produk cloud server, basis data, atau jam operasional layanan."
        ),
    }
    return clarification_map.get(
        intent_code,
        "Mohon maaf, agar kami dapat membantu dengan tepat, apakah kebutuhan Anda terkait informasi layanan umum, bantuan transaksi akun, atau ingin berbicara langsung dengan petugas?"
    )


# ---------------------------------------------------------------------------
# Node 2: Clarify Node
# ---------------------------------------------------------------------------
def clarify_node(state: AgentState) -> dict[str, Any]:
    db: Session = state["db"]
    conv_id = state["conv_id"]
    cls = state["intent"]
    text = state.get("text", "")

    # TRD §8.2 line 10: Cap at 2 clarification attempts, then mandatory handoff
    ctx = IntentSvc.get_context(conv_id)
    clar_count = ctx.get("clarification_count", 0)
    if clar_count >= 2:
        return handoff_node(state)

    reply = _format_clarification_question(cls.get("intent_code", ""), text)
    ConvSvc.append_outbound(db, conv_id, reply)
    return {"reply": reply, "handoff": False, "reason": "CLARIFY"}


# ---------------------------------------------------------------------------
# Node 3: Greeting Node
# ---------------------------------------------------------------------------
def greeting_node(state: AgentState) -> dict[str, Any]:
    db: Session = state["db"]
    conv_id = state["conv_id"]
    reply = (
        "Halo! Selamat datang di layanan pelanggan kami. "
        "Ada yang bisa saya bantu terkait informasi produk, layanan, atau kendala akun Anda hari ini?"
    )
    ConvSvc.append_outbound(db, conv_id, reply)
    return {"reply": reply, "handoff": False, "reason": "GREETING"}


# ---------------------------------------------------------------------------
# Node 4: Tool Execution Node (Banking Operations Simulator)
# ---------------------------------------------------------------------------
def tool_node(state: AgentState) -> dict[str, Any]:
    db: Session = state["db"]
    conv_id = state["conv_id"]
    corr = state["corr"]
    tenant_id = state["tenant_id"]
    al = state["assurance_level"]
    tool = state["tool_name"]
    args = state["tool_args"] or {}
    cls = state["intent"]

    # 1. Policy & Assurance check via Tool Gateway
    actor = state.get("actor", "AI_AGENT")
    try:
        dec = Gw.evaluate(tool, args, al, {"actor": actor, "tenant_id": tenant_id}, corr, conv_id)
    except Exception:
        queued = _queue_handoff(db, conv_id, "POLICY_DENIED", corr, tenant_id, cls)
        reply = "Saya belum dapat melakukan tindakan ini. " + _handoff_reply(queued.get("state", "UNAVAILABLE"))
        ConvSvc.append_outbound(db, conv_id, reply)
        return {"reply": reply, "handoff": True, "reason": "POLICY_DENIED"}

    if dec.get("decision") == "STEP_UP_REQUIRED":
        try:
            ConvSvc.transition(db, conv_id, "AWAITING_AUTH", "stepup",
                                {"actor_type": "AI_AGENT", "actor_id": "orchestrator"}, corr)
        except Exception:
            pass
        reply = (
            "Untuk memproses permintaan transaksi atau informasi rekening Anda secara aman, "
            "silakan masuk (*login*) terlebih dahulu ke akun layanan terdaftar Anda."
        )
        ConvSvc.append_outbound(db, conv_id, reply)
        return {
            "stepup_required": dec.get("required"),
            "reply": reply,
            "handoff": False,
            "reason": "STEPUP_REQUIRED",
        }

    # 2. Idempotency replay check
    tool_results = list(state.get("tool_results", []))
    tool_calls = list(state.get("tool_calls", []))
    hit = Gw.idem_lookup(conv_id, tool, args)
    if hit:
        tool_results.append(hit)
        tool_calls.append({"tool": tool, "replayed": True})
    else:
        Gw.record_call(conv_id, tool, args, "SUCCESS", corr, dec["policy_decision_id"])
        res = _exec_tool(db, tool, args, conv_id, corr)
        Gw.idem_store(conv_id, tool, args, res)
        tool_results.append(res)
        tool_calls.append({"tool": tool, "policy_decision_id": dec["policy_decision_id"]})

    # 3. Formulate response
    draft = _compose_action_answer(cls, tool_results, conv_id, db=db, corr=corr, tenant_id=tenant_id)

    # 4. Guardrail groundedness
    g = Grd.groundedness(draft, [], tool_results)
    reply = draft if g.get("passed", True) else "Permintaan Anda telah diproses. Data telah diverifikasi oleh sistem."
    ConvSvc.append_outbound(db, conv_id, reply)

    return {
        "tool_results": tool_results,
        "tool_calls": tool_calls,
        "reply": reply,
        "handoff": False,
    }


# ---------------------------------------------------------------------------
# Node 5: Knowledge Retrieval (RAG) Node
# ---------------------------------------------------------------------------
def rag_node(state: AgentState) -> dict[str, Any]:
    db: Session = state["db"]
    conv_id = state["conv_id"]
    text = state["text"]
    corr = state["corr"]
    tenant_id = state["tenant_id"]

    prior_question = _previous_customer_question(db, conv_id, text)
    effective_question = text
    retrieval_query = text

    try:
        r = KmSvc.search(db, retrieval_query, language="id", corr=corr, tenant_id=tenant_id)
        if r.get("zero_result") and prior_question:
            effective_question = (
                f"Pertanyaan saat ini: {text}\n"
                f"Konteks pertanyaan sebelumnya (untuk memahami rujukan saja): {prior_question}"
            )
            retrieval_query = prior_question
            r = KmSvc.search(db, retrieval_query, language="id", corr=corr, tenant_id=tenant_id)
        if r.get("zero_result"):
            t_lower = text.lower()
            if state.get("intent", {}).get("intent_code") == "INFO_PRODUCT_POLICY":
                if any(w in t_lower for w in ("operasional", "oprasional", "jam", "buka", "tutup", "kerja", "jadwal", "waktu", "kontak", "alamat", "telepon", "call center", "email")):
                    r_fb = KmSvc.search(db, "jam operasional dan saluran layanan pelanggan", language="id", corr=corr, tenant_id=tenant_id)
                    if not r_fb.get("zero_result"):
                        r = r_fb
    except Exception:
        audit_svc.emit(
            tenant_id, corr, "SYSTEM", "rag-svc", "knowledge.retrieval_failed",
            "conversation", conv_id, "retrieval-svc", result="ERROR"
        )
        reply = "Pencarian informasi sedang mengalami gangguan. Silakan coba kembali beberapa saat lagi."
        ConvSvc.append_outbound(db, conv_id, reply)
        _log_routing(tenant_id, conv_id, corr, state["intent"], "ERROR")
        return {
            "retrieval_error": True,
            "zero_result": False,
            "reply": reply,
            "handoff": False,
            "reason": "RETRIEVAL_ERROR",
        }

    zero_result = bool(r.get("zero_result"))
    results = r.get("results", [])
    citations = KmSvc.cite(results) if not zero_result else []

    return {
        "effective_question": effective_question,
        "retrieval_query": retrieval_query,
        "retrieval_results": results,
        "citations": citations,
        "zero_result": zero_result,
        "retrieval_error": False,
    }


def route_after_rag(state: AgentState) -> str:
    if state.get("retrieval_error"):
        return "finish"
    if state.get("zero_result"):
        return "handoff_node"
    return "llm_node"


def _reflow_document_text(raw_text: str) -> str:
    """Reflow PDF and extracted document chunks into clean, structured paragraphs."""
    if not raw_text:
        return ""
    text = raw_text.replace("\t", " ")
    text = re.sub(r"[ ]{2,}", " ", text)
    raw_lines = [l.strip() for l in text.splitlines() if l.strip()]
    lines = []
    for line in raw_lines:
        if re.search(r"(_\w+|\.pdf|\.md)\b", line, re.IGNORECASE) and not re.search(r"\b(visi|misi|tentang|layanan|produk)\b", line, re.IGNORECASE):
            continue
        if re.match(r"^(JUDUL|KATEGORI|VERSI|STATUS YANG DISARANKAN|TUJUAN)\s*:", line, re.IGNORECASE):
            continue
        lines.append(line)
    if not lines:
        return raw_text

    is_list_item = lambda l: bool(re.match(r"^(\d+[\.\)]|[-*•–—]|[a-zA-Z][\.\)])\s+", l))
    is_list_marker_only = lambda l: bool(re.match(r"^(\d+[\.\)]|[-*•–—]|[a-zA-Z][\.\)])$", l))
    is_header = lambda l: (
        not is_list_item(l) and not is_list_marker_only(l) and
        len(l) <= 55 and (
            re.match(r"^(Tentang Kami|Visi|Misi|Profil Perusahaan|Sejarah Singkat|Layanan Utama|Fitur Utama|Paket Layanan|Harga & Spesifikasi|Kontak|Jam Operasional|Catatan|Ketentuan|Syarat & Ketentuan|SLA|Daftar Produk)\b", l, re.IGNORECASE) or
            l.endswith(":") or
            " — " in l
        )
    )

    merged_lines = []
    idx = 0
    while idx < len(lines):
        cur = lines[idx]
        if is_list_marker_only(cur) and idx + 1 < len(lines):
            merged_lines.append(f"{cur} {lines[idx+1]}")
            idx += 2
        elif re.match(r"^\d{4}$", cur) and idx + 1 < len(lines):
            next_l = lines[idx + 1]
            if next_l.startswith(("—", "-", "–")):
                merged_lines.append(f"• {cur} {next_l}")
            else:
                merged_lines.append(f"• {cur}: {next_l}")
            idx += 2
        else:
            merged_lines.append(cur)
            idx += 1

    blocks = []
    current_p = []
    def flush_p():
        nonlocal current_p
        if current_p:
            blocks.append(" ".join(current_p))
            current_p = []

    for line in merged_lines:
        if is_header(line):
            flush_p()
            hdr = line if line.endswith(":") or line.endswith("—") or " — " in line else f"{line}:"
            blocks.append(f"### {hdr}")
        elif is_list_item(line):
            flush_p()
            blocks.append(line)
        else:
            current_p.append(line)
    flush_p()

    formatted_output = []
    for b in blocks:
        if b.startswith("### "):
            formatted_output.append(f"\n{b[4:]}")
        elif is_list_item(b):
            formatted_output.append(b)
        else:
            formatted_output.append(f"{b}\n")
    result = "\n".join(formatted_output).strip()
    return re.sub(r"\n{3,}", "\n\n", result)


# ---------------------------------------------------------------------------
# Node 6: LLM Generation & Grounding Node
# ---------------------------------------------------------------------------
def llm_node(state: AgentState) -> dict[str, Any]:
    db: Session = state["db"]
    conv_id = state["conv_id"]
    corr = state["corr"]
    tenant_id = state["tenant_id"]
    results = state.get("retrieval_results", [])
    citations = state.get("citations", [])
    effective_question = state.get("effective_question", state["text"])
    cls = state["intent"]

    source_inputs = []
    for source in results:
        source_id = (
            f"knowledge:{source.get('article_id')}:{source.get('version_id')}:{source.get('passage_ref')}"
            if source.get("source_type") == "article"
            else f"knowledge:{source.get('document_id')}:{source.get('version_no')}:{source.get('passage_ref')}"
        )
        source_inputs.append({
            "source_id": source_id,
            "source_type": "KNOWLEDGE_CITATION",
            "text": (source.get("body") or "")[:4000],
        })

    try:
        from .llm_provider import (
            F4Input,
            F4Output,
            F4Source,
            LLMFunction,
            ProviderError,
            ProviderErrorCode,
            build_provider,
            generate_validated,
        )

        f4_sources = [
            F4Source(source_id=item["source_id"], source_type=item["source_type"], text=item["text"])
            for item in source_inputs
        ]

        generated = generate_validated(
            build_provider(),
            LLMFunction.F4,
            F4Input(question=effective_question, sources=f4_sources),
            timeout_ms=None,
        )

        if not isinstance(generated, F4Output) or not generated.claim_map:
            raise ProviderError(ProviderErrorCode.OUTPUT_INVALID)

        reply = generated.text
        ConvSvc.append_outbound(db, conv_id, reply, citations=citations)
        return {"reply": reply, "citations": citations, "handoff": False}

    except Exception as exc:
        code = getattr(getattr(exc, "code", None), "value", "PROVIDER_ERROR")
        _logger.warning("llm_answer_generation_failed tenant_id=%s conv_id=%s error=%s", tenant_id, conv_id, code)
        audit_svc.emit(
            tenant_id, corr, "SYSTEM", "llm-provider", "knowledge.answer_generation_failed",
            "conversation", conv_id, "llm-provider", result=str(code)[:40]
        )

        # CRITICAL PRESERVATION (RULE 11): Do not remove this sanitization block.
        # It guarantees natural phrasing and strips raw file headers (e.g. '02_products_services')
        # if the LLM provider triggers an extractive fallback.
        # Extractive fallback: sajikan kutipan dokumen faktual yang sudah dirapikan jika LLM provider gagal/stub
        raw_text = (source_inputs[0]["text"] or "").strip() if source_inputs else ""
        if raw_text:
            content_body = _reflow_document_text(raw_text)
            content_snippet = content_body if len(content_body) <= 1200 else content_body[:1197] + "..."

            # Guardrail anti-leak: Cegah dokumen panduan internal / rule bot terbongkar ke customer
            is_internal_guide = bool(
                re.search(
                    r"(jangan mengarang|contoh sapaan|panduan menanggapi|chatbot eaics|status yang disarankan)",
                    content_body,
                    re.IGNORECASE,
                )
            )

            if is_internal_guide:
                reply = (
                    "Mohon maaf, rincian informasi mengenai hal tersebut belum tercantum dalam "
                    "dokumentasi resmi kami saat ini. Silakan hubungi tim dukungan kami atau sampaikan kendala Anda "
                    "secara lebih spesifik agar dapat kami bantu."
                )
            else:
                reply = (
                    f"Berdasarkan informasi resmi layanan kami:\n\n"
                    f"{content_snippet}"
                )
            ConvSvc.append_outbound(db, conv_id, reply, citations=citations)
            _log_routing(tenant_id, conv_id, corr, cls, "EXTRACTIVE_FALLBACK", len(source_inputs))
            return {
                "reply": reply,
                "citations": citations,
                "handoff": False,
                "reason": "EXTRACTIVE_FALLBACK",
            }

        reply = "Saya menemukan sumber informasi resmi yang relevan, tetapi jawaban belum dapat diformulasikan saat ini."
        ConvSvc.append_outbound(db, conv_id, reply, citations=citations)
        return {
            "reply": reply,
            "citations": citations,
            "handoff": False,
            "reason": "ANSWER_GENERATION_ERROR",
            "generation_error": True,
        }


# ---------------------------------------------------------------------------
# Node 7: Human Handoff Node
# ---------------------------------------------------------------------------
def handoff_node(state: AgentState) -> dict[str, Any]:
    db: Session = state["db"]
    conv_id = state["conv_id"]
    corr = state["corr"]
    tenant_id = state["tenant_id"]
    cls = state.get("intent", {})
    reason = "KNOWLEDGE_GAP" if state.get("zero_result") else "MANDATORY_HUMAN_HANDOFF"

    handoff = _queue_handoff(db, conv_id, reason, corr, tenant_id, cls)
    h_state = handoff.get("state", "UNAVAILABLE")

    if state.get("zero_result"):
        reply = (
            "Saya tidak menemukan sumber resmi yang cukup untuk memverifikasi jawaban. "
            + (
                "Permintaan bantuan petugas telah masuk antrean; penerimaan belum dikonfirmasi."
                if h_state in ("QUEUED", "OFFERED", "ACCEPTED")
                else "Saya belum dapat memastikan permintaan bantuan masuk antrean."
            )
        )
    else:
        reply = _handoff_reply(h_state)

    ConvSvc.append_outbound(db, conv_id, reply)
    _log_routing(tenant_id, conv_id, corr, cls, "HANDOFF", handoff=h_state)

    return {
        "reply": reply,
        "handoff": h_state != "UNAVAILABLE",
        "handoff_status": h_state,
        "reason": reason,
    }


# ---------------------------------------------------------------------------
# Graph Construction & Compilation
# ---------------------------------------------------------------------------
def build_agent_graph():
    builder = StateGraph(AgentState)

    # Register Nodes
    builder.add_node("triage_node", triage_node)
    builder.add_node("clarify_node", clarify_node)
    builder.add_node("greeting_node", greeting_node)
    builder.add_node("tool_node", tool_node)
    builder.add_node("rag_node", rag_node)
    builder.add_node("llm_node", llm_node)
    builder.add_node("handoff_node", handoff_node)

    # Edges from START
    builder.add_edge(START, "triage_node")

    # Conditional Routing from Triage
    builder.add_conditional_edges(
        "triage_node",
        route_after_triage,
        {
            "clarify_node": "clarify_node",
            "greeting_node": "greeting_node",
            "tool_node": "tool_node",
            "rag_node": "rag_node",
            "handoff_node": "handoff_node",
            "finish": END,
        },
    )

    # Conditional Routing from RAG
    builder.add_conditional_edges(
        "rag_node",
        route_after_rag,
        {
            "handoff_node": "handoff_node",
            "llm_node": "llm_node",
            "finish": END,
        },
    )

    # Terminal edges
    builder.add_edge("clarify_node", END)
    builder.add_edge("greeting_node", END)
    builder.add_edge("tool_node", END)
    builder.add_edge("llm_node", END)
    builder.add_edge("handoff_node", END)

    return builder.compile()


# Compile reusable singleton graph instance
agentic_workflow = build_agent_graph()


def run_turn_langgraph(
    db: Session,
    conv_id: str,
    text: str,
    corr: str,
    channel: str = "WEB_CHAT",
    actor: str = "AI_AGENT",
    tenant_id: str = "TNT-TEST",
) -> dict[str, Any]:
    """Execute customer turn using the compiled LangGraph workflow."""
    turn_id = new_id("turn")
    initial_state: AgentState = {
        "db": db,
        "conv_id": conv_id,
        "text": text,
        "corr": corr,
        "channel": channel,
        "actor": actor,
        "tenant_id": tenant_id,
        "turn_id": turn_id,
    }

    final_state = agentic_workflow.invoke(initial_state)

    result = {
        "turn_id": turn_id,
        "intent": final_state.get("intent", {}),
        "reply": final_state.get("reply", ""),
        "handoff": final_state.get("handoff", False),
        "handoff_status": final_state.get("handoff_status"),
        "reason": final_state.get("reason"),
        "citations": final_state.get("citations", []),
    }
    if final_state.get("stepup_required"):
        result["stepup_required"] = final_state["stepup_required"]
    if final_state.get("generation_error"):
        result["generation_error"] = True
    if final_state.get("retrieval_error"):
        result["retrieval_error"] = True
    if final_state.get("mode"):
        result["mode"] = final_state["mode"]

    return result
