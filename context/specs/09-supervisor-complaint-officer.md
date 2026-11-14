# Unit 09 Specification — Supervisor and Complaint Officer Operations

## 1. Context and Planning Basis

- **Authority:** FRD-EAICS-001 (FR-WS-001..003, FR-SLA-005/006, FR-CMP-001..008), TRD-EAICS-001 (§4.12, §4.13, §6.3, §16.4).
- **Preceding Units:**
  - Unit 02: Authenticated staff principal (`supervisor`, `complaint_officer`) with RBAC permissions (`escalation.resolve`, `sla.read`, `sla.override`, `case.read`, `case.update`, `case.close`, `evidence.adjudicate`).
  - Unit 03: Role-aware navigation shell (`/supervisor`, `/complaints`).
  - Unit 06 & 07: Customer complaint submission (`POST /v1/customer/complaints`) and SLA tracking (`GET /v1/customer/complaints`).
  - Unit 08: Agent Workspace Read Model & enriched Handoff Context Package.

## 2. Problem Statement

1. **Missing Complaint Officer Workspace:** Route `/complaints` in `web-workspace` was marked `unit: '09'` with no page implementation. Complaint Officers have no dedicated interface to review customer dispute claims, examine evidence, or adjudicate settlements.
2. **Missing Supervisor Escalation Visibility:** The supervisor shared console lacks an operational view of Level L1 escalations triggered by SLA breaches or repeat contacts. There is no API to query active escalations.
3. **Missing SLA Risk Monitor:** Supervisors cannot view which cases and tickets are currently `AT_RISK` or `BREACHED` across tenants and queues.
4. **Missing Reassignment and Adjudication Operations:** Ticket reassignment and formal dispute adjudication (`evidence.adjudicate`) lack dedicated endpoints and structured audit records.

## 3. Scope and Deliverables

### A. Backend Endpoints (`app/main.py` & `app/modules/`)
1. **Escalations API:**
   - `GET /v1/workspace/escalations`: Returns active escalations filtered by target role (`SUPERVISOR` or `COMPLAINT_OFFICER`) and tenant.
   - `POST /v1/workspace/escalations/{eid}/acknowledge`: Marks escalation acknowledged with staff actor attribution and audit logging.
2. **SLA Risk Monitoring API:**
   - `GET /v1/workspace/sla/records`: Returns SLA records with `state` in `('AT_RISK', 'BREACHED', 'RUNNING')`, computing time elapsed and remaining.
3. **Ticket Reassignment API:**
   - `PATCH /v1/tickets/{tid}/assign`: Allows supervisors and complaint officers to reassign a ticket's `owner_queue` or target agent.
4. **Complaint Adjudication API:**
   - `POST /v1/cases/{cid}/adjudicate`: Allows complaint officers to formally adjudicate customer disputes with decision (`UPHELD`, `REJECTED`, `SETTLED`), compensation amount, and closure notes.

### B. Frontend Workspaces (`web-workspace/src/`)
1. **Dedicated Complaint Officer Workspace (`ComplaintOfficer.jsx`):**
   - Active Complaints Table: Filter by category (`TRANSACTION_DISPUTE`, `SERVICE_FAILURE`, `STAFF_CONDUCT`, `FRAUD_SUSPICION`), SLA deadline, and severity.
   - Dispute Adjudication Panel: Review customer claim chronology, requested evidence, and record formal resolution with customer-facing explanation.
2. **Enhanced Supervisor Operations Workspace (`SupervisorWorkspace.jsx` / `SLA.jsx` / `Cases.jsx`):**
   - Escalation Feed: Real-time list of Level L1 escalated interactions with one-click acknowledge and review.
   - SLA Risk Alert Board: Highlight cases/tickets approaching breach (< 2 hours remaining) and breached SLA records.
   - Staff Reassignment & Approval Integration.

## 4. Acceptance Criteria

1. Only authenticated principals with `supervisor` or `complaint_officer` roles can access `/v1/workspace/escalations` and `/v1/cases/{cid}/adjudicate`.
2. Customer and unauthorized staff roles receive strict 403 Forbidden.
3. Complaint adjudication enforces valid decisions (`UPHELD`, `REJECTED`, `SETTLED`) and records audit events.
4. Supervisor can view active escalations, acknowledge them, and reassign tickets.
5. All regression test suites (`test_agent_graph.py`, `test_customer_complaints.py`, `test_workspace_read_model.py`) pass 100%.

## 5. Verification

- Automated test suite in `tests/test_supervisor_officer.py`.
- Frontend production build check (`npm run build`).
- Frontend workspace test check (`npm run test:workspace`).
