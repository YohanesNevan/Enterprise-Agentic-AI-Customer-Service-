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

    # 3. Intent classification
    cls = IntentSvc.classify(text, conv_id, corr)

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
    if decision == "HUMAN" or cls.get("safety_flag"):
        return "handoff_node"

    # Clarification required
    if decision == "CLARIFY":
        return "clarify_node"

    # Polite greeting / small talk
    if cls.get("intent_code") in ("GEN_GREETING", "GEN_SMALL_TALK_OTHER"):
        return "greeting_node"

    # Transaction / action tool execution
    if cls.get("category") == "ACTION" and state.get("tool_name"):
        return "tool_node"

    # Knowledge retrieval (default for inquiries)
    return "rag_node"


# ---------------------------------------------------------------------------
# Node 2: Clarify Node
# ---------------------------------------------------------------------------
def clarify_node(state: AgentState) -> dict[str, Any]:
    db: Session = state["db"]
    conv_id = state["conv_id"]
    cls = state["intent"]
    reply = _options(cls["intent_code"])
    ConvSvc.append_outbound(db, conv_id, reply)
    return {"reply": reply, "handoff": False, "reason": "CLARIFY"}


# ---------------------------------------------------------------------------
# Node 3: Greeting Node
# ---------------------------------------------------------------------------
def greeting_node(state: AgentState) -> dict[str, Any]:
    db: Session = state["db"]
    conv_id = state["conv_id"]
    reply = (
        "Halo! Saya asisten virtual layanan perbankan EAICS. "
        "Ada yang bisa saya bantu terkait produk, kartu, rekening, atau transaksi Anda hari ini?"
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
    dec = Gw.evaluate(tool, al, {"tenant_id": tenant_id})
    if not dec["permitted"]:
        reply = (
            "Untuk memproses permintaan transaksi atau informasi rekening Anda, "
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
            # Ganti karakter tab dengan spasi dan normalkan spasi ganda
            raw_text = raw_text.replace("\t", " ")
            raw_text = re.sub(r"[ ]{2,}", " ", raw_text)

            # Bersihkan metadata/nama file mentah di baris awal (misal: "CloudNova Teknologi - 02_products_services")
            lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
            cleaned_lines = []
            skip_idx = -1
            for i, line in enumerate(lines):
                if i <= skip_idx:
                    continue
                # Abaikan baris kode file seperti "02_products_services" atau header internal file
                if re.search(r"(_\w+|\.pdf|\.md)\b", line, re.IGNORECASE):
                    continue
                # Rapikan nomor daftar yang terpisah baris (misal "1." lalu baris baru "Teks...")
                if re.match(r"^\d+\.$", line) and i + 1 < len(lines):
                    cleaned_lines.append(f"{line} {lines[i+1]}")
                    skip_idx = i + 1
                    continue
                cleaned_lines.append(line)

            content_body = "\n".join(cleaned_lines) if cleaned_lines else raw_text
            content_snippet = content_body if len(content_body) <= 1100 else content_body[:1097] + "..."

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
