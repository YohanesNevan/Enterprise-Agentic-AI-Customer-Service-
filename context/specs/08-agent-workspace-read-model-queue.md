# Unit 08 Specification — Agent Workspace Read Model and Queue

## 1. Context and Planning Basis

- **Authority:** FRD-EAICS-001 (FR-WS-001, FR-WS-002, FR-WS-003), TRD-EAICS-001 (§4.12, §4.13, §16.4), and Mitra Slide Deck (PT Viktori Aksara Teknologi Indonesia / UKDW, Slide 20: *Layanan 3 - Human Handoff Context Package*).
- **Preceding Units:**
  - Unit 02: Authenticated staff principal (`cs_agent`, `supervisor`) with RBAC permissions (`handoff.accept`, `conversation.read`, `conversation.write`).
  - Unit 03: Role-aware navigation shell (`/agent/queue`, `/agent/conversations`).
  - Unit 05: LangGraph Agentic AI decision loop with `_queue_handoff` assembling handoff metadata.

## 2. Problem Statement

1. **Bare Read Model:** Endpoint `GET /v1/workspace/conversations/{conv_id}` currently returns raw conversation messages, basic SLA dates, and bare handoff metadata (`reason_code`, `priority_score`, `state`, `accepted_by`). It lacks the structured **Handoff Context Package** required by TRD §16.4 and Mitra Slide 20.
2. **Missing Executive Context for CS Agents:** Human CS agents opening an escalated conversation are forced to read through hundreds of raw chat lines to understand what the customer wants, what the AI already attempted, and what step needs to be taken next.
3. **Queue List Insufficiency:** Endpoint `GET /v1/workspace/queue` displays queue items without immediate intent summary or customer urgency markers, hindering fast triage.

## 3. Scope and Deliverables

### A. Backend Read Model Enhancement (`app/main.py` & `app/modules/handoff.py`)
- Enhance `GET /v1/workspace/conversations/{conv_id}` to compute and return a structured `handoff_package` object:
  - `customer_summary`: Masked ID, channel, and vulnerability/safety flags.
  - `intent_summary`: Primary classified intent, confidence, category, and sentiment.
  - `narrative`: Synthesized chronology/summary of the customer's grievance.
  - `ai_action_log`: Distinct list of banking tools invoked by the AI during the conversation.
  - `recommended_action`: Actionable next-step guidance for the human agent.
  - `package_complete`: Boolean flag indicating full context package availability.
- Enhance `GET /v1/workspace/queue` to include `intent_code` and `summary_snippet` for operational triage.

### B. Frontend Staff Workspace UI (`web-workspace/src/App.jsx` & `app.css`)
- **Queue Table Enhancement:**
  - Display `Intent` and `Paket Lengkap` status badges.
- **Dedicated Handoff Context Package Card:**
  - Render a prominent, executive summary card at the top of the conversation workbench displaying:
    - Customer Profile & Urgency badge.
    - AI Problem Analysis & Chronology.
    - AI Tools Executed History.
    - Prescribed Next-Step Action for Staff.
  - One-click "Terima Handoff / Accept" and "Selesaikan Percakapan / Resolve" controls with immediate transcript feedback.

## 4. Acceptance Criteria

1. `GET /v1/workspace/conversations/{conv_id}` returns valid `handoff_package` with customer summary, chronology, intent, tools called, and recommended action.
2. Unauthenticated calls or customer-role calls are strictly rejected with 403 Forbidden.
3. Queue items include priority score, wait time, intent code, and package completeness indicator.
4. Staff workspace UI renders the Handoff Context Package Card cleanly, separating factual system state from AI recommendations.
5. All regression tests (`tests/test_agent_graph.py`, `tests/test_customer_complaints.py`) continue to pass 100%.

## 5. Verification

- Automated unit and integration test in `tests/test_workspace_read_model.py`.
- Frontend production build check (`npm run build` in `web-workspace`).
