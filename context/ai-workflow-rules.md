# AI Workflow Rules

1. Read, in order: `context/project-overview.md`, `context/architecture.md`, `context/ui-context.md`, `context/code-standards.md`, `context/ai-workflow-rules.md`, and `context/progress-tracker.md`.
2. Read relevant FRD/TRD sections and `context/audit-report.md` before planning. Read `context/specs/00-build-plan.md` before selecting a unit, then the active unit specification before changing code.
3. Audit before code changes. Work on one implementation unit at a time and stay within its scope.
4. Treat FRD/TRD as product truth. If a requirement is ambiguous in a way that affects architecture, security, privacy, or business behavior, record it and seek clarification. Use conservative defaults for low-risk details and record assumptions.
5. Do not silently replace architecture, remove business behavior, or weaken authorization. Preserve working features and conventions.
6. Keep documentation synchronized with approved decisions and update the progress tracker after every meaningful unit.
7. Verify only by commands actually executed. Never claim a test/build/runtime check succeeded without observing its result. Report unverified conditions clearly.
8. Do not represent simulated LLM, retrieval, financial, CRM, channel, storage, or notification behavior as live production behavior.
9. Every user-facing action must have a real behavior, an explained disabled state, or an explicit prototype label. Backend authorization and ownership are mandatory even when the UI hides controls.
10. Keep changes focused and reviewable; explain affected boundaries, risks, and verification status.
11. **Agentic Workflow & RAG Preservation**:
    - `app/modules/agent_graph.py` implements the verified LangGraph `StateGraph` for conversation turn orchestration. Do not disable or alter its core node transitions (`triage_node`, `greeting_node`, `clarify_node`, `tool_node`, `rag_node`, `llm_node`, `handoff_node`) without explicit architectural mandate.
    - Preserved text sanitization in `llm_node`: Keep the raw document metadata striping and natural conversational response formulation active so the customer never receives raw markdown/PDF file headers.
    - Customer complaint APIs (`POST/GET /v1/customer/complaints`) and frontend dual-tab tracking in `web-workspace/src/App.jsx` must remain fully operational. Always run `pytest tests/test_agent_graph.py tests/test_customer_complaints.py` before completing a task.
