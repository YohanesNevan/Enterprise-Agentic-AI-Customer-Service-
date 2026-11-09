# EAICS Repository Instructions

Before implementation, read these files in order:

1. `context/project-overview.md`
2. `context/architecture.md`
3. `context/ui-context.md`
4. `context/code-standards.md`
5. `context/ai-workflow-rules.md`
6. `context/progress-tracker.md`

Inspect the relevant FRD and TRD sections and read `context/audit-report.md` before planning a revision. Read `context/specs/00-build-plan.md` before selecting the next unit, then read that unit's active specification before editing code.

Preserve working features and project conventions. Do not change business behavior, architecture, or authorization assumptions without documenting the decision. Keep context and progress documentation synchronized with approved decisions and verified implementation outcomes.

## Critical Agentic Preservation Rules (DO NOT BREAK):
1. **LangGraph StateGraph Integration**: `app/modules/agent_graph.py` is the official decision loop (`run_turn_langgraph`) invoked by `app/modules/orchestrator.py`. NEVER bypass, remove, or revert LangGraph back to legacy procedural routing.
2. **Knowledge Retrieval (RAG) & Human-like Formatting**: The knowledge answering flow (`rag_node` -> `llm_node`) MUST preserve the clean human-like response formatting and metadata filtering (removing raw chunk codes like `02_products_services`, `.pdf`, `.md`). Never revert to dumping unformatted, raw file contents to the customer.
3. **Complaint & Tracking Service (Units 06 & 07)**: The verified customer complaint submission (`POST /v1/customer/complaints`) and SLA tracking (`GET /v1/customer/complaints`), as well as the dual-tab customer interface in `web-workspace/src/App.jsx`, are working features. Do not overwrite or remove them during subsequent units.
4. **All Changes Must Pass Test Suites**: Any new update must verify regression with `python -m pytest tests/test_agent_graph.py tests/test_customer_complaints.py -v`.
