# Unit 06 Readiness Audit

**Review date:** 2026-10-20  
**Purpose:** read-only readiness review before Unit 06 implementation.  
**Current decision:** **Unit 06 BLOCKED**.  
**Implementation status:** not started. No source, API, permission, policy, schema, migration, dependency, environment, configuration, or database data was changed. No tests, migration, Gemini, CRM, or banking request was run for this review.

## 1. Executive summary

Unit 05 manual browser results are recorded as **PASS — developer-reported**, not Codex-verified. The current Unit 05 gate is not approved: no reviewer approval is recorded, and the project UI context explicitly says to test color contrast. Contrast was not included in the developer's reported results. Screen-reader/basic assistive-technology checks are also untested; they are explicitly included in Unit 17 release verification, but are not separately enumerated as a Unit 05 acceptance check. Unit 05 remains **IN PROGRESS** and cannot yet be treated as a completed dependency for Unit 06.

A Unit 06 specification exists at `docs/units/UNIT_06_SPEC.md`, but it is marked **Draft for review; no application implementation is authorized**. The implementation plan is a pre-implementation proposal, and all D-01 through D-10 in the decision log remain **UNRESOLVED**. Approval checklist fields remain blank. Unit 06 is therefore **BLOCKED**, not ready to code.

## 2. Evidence classes and sources reviewed

- **Current repository facts:** source and Markdown/PDF files inspected in this review. Static code inspection is not a runtime test.
- **Developer-reported:** browser outcomes supplied by the developer; no independent Codex observation is implied.
- **Prior recorded test evidence:** the previous review record says the focused backend suite passed 11 tests and the frontend build passed. These commands were not rerun in this readiness audit.
- **UNRESOLVED:** no approved decision or sufficient evidence in the repository settles the item.

Reviewed: `docs/units/UNIT_05_GATE_REVIEW.md`; `context/progress-tracker.md`; `context/specs/05-customer-information-conversation.md`; `docs/units/UNIT_06_SPEC.md`; `docs/units/UNIT_06_IMPLEMENTATION_PLAN.md`; `docs/units/UNIT_06_DECISION_LOG.md`; `docs/units/UNIT_06_APPROVAL_CHECKLIST.md`; `context/specs/00-build-plan.md`; `context/specs/01-requirements-traceability.md`; `context/architecture.md`; `context/ui-context.md`; project overview/standards/workflow notes and historical `context/audit-report.md`; the repository FRD/TRD PDF copies; and relevant source in `app/core/rbac.py`, `app/modules/routes_a.py`, `app/modules/intent.py`, `app/modules/orchestrator.py`, `app/modules/cases.py`, `app/modules/store.py`, `app/modules/models.py`, `app/modules/tool_gateway.py`, `app/modules/outbox.py`, `app/main.py`, `alembic/`, and `web-workspace/src/App.jsx`.

## 3. Unit 05 gate

### Developer-reported browser outcomes

The following are **PASS — developer-reported**: development login; Enter sends once; Shift+Enter adds a line; Send button; blank/whitespace rejection; repeated Enter does not duplicate while pending; history after reload; supported and unsupported question behavior; error handling; retry without duplicate; chat at 1440 px desktop and 390 px mobile; keyboard use of primary controls; visible/logical focus; and zoom/reflow.

No screenshot, recording, HAR/Network export, Console capture, or separate run log was supplied or located for this audit. The results remain useful developer attestation, but are not Codex-observed. The previously recorded `tests/test_a_skeleton.py` result (11 passed) and frontend build pass are backend/build evidence only; they do not independently verify browser behavior.

### Required criteria not yet evidenced

| Criterion | Status | Basis |
|---|---|---|
| Color contrast testing for the Unit 05 UI | **NOT TESTED** | `context/ui-context.md` says to pair color with text/icon and test contrast, with implementation values to be confirmed. No contrast result or ratio was reported. Since the Unit 05 gate requires accessibility verification generally, this project UI rule remains an unverified criterion for this UI. No numerical target was found in the active Unit 05 spec; use the project-approved target if recorded, otherwise ask product/mentor to set/confirm it rather than inventing a ratio. |
| Screen-reader/basic assistive-technology check | **NOT TESTED** | No result reported. Build plan Unit 17 includes keyboard/screen-reader basics in release verification and says verification is incremental. It is a remaining release check, but not listed as a standalone Unit 05 acceptance criterion in Unit 05's active spec/build-plan section. |
| Console and Network capture | **NOT TESTED** | Not reported and no capture provided. Useful diagnostic evidence; not separately listed as a Unit 05 acceptance criterion in the active plan. |
| Reviewer disposition/approval of Unit 05 gate | **UNRESOLVED** | The gate document says “ready for review again”; no mentor/product/reviewer acceptance is recorded. Do not label it approved. |

**Unit 05 status:** **IN PROGRESS; BLOCKED FOR CLOSURE pending contrast evidence and reviewer disposition.** The browser journey is reviewable based on the developer's report, but the written project UI rule leaves contrast unverified. Screen-reader testing remains for the broader Unit 17 release verification unless product/mentor explicitly makes it a Unit 05 closure condition. No failure was reported; these items are untested, not failed.

## 4. Unit 06 scope, acceptance, and dependencies

### Active specification and goal

`docs/units/UNIT_06_SPEC.md` is present and is the active Unit 06 specification found in the repository; no `context/specs/06-*` unit spec was found. Its status is draft, not an implementation authorization. The target is an authenticated customer reporting “Transaksi saya gagal, tetapi saldo saya terpotong,” leading to a policy-authorized, PostgreSQL-persisted customer-owned case, an honest backend-derived reference/status, and owner-scoped customer list/detail. It explicitly excludes transfers/reversal, unverified transaction claims, live Gemini, and real CRM/banking calls.

The spec's testable acceptance criteria require, among other things: deterministic complaint intent or targeted clarification; no case on ambiguity or policy denial; durable case/SLA/outbox/timeline state; response reference matching committed data; request replay/concurrency without duplicate case; customer A read and customer B/other tenant 404; ownership fields cannot be forged; HIGH/CRITICAL severity remains proposed until authorized human confirmation; honest outage/retry state and reconciliation where required; allowlisted customer projections; and a UI case reference/list/detail journey backed by API data.

### Current implementation facts (static source inspection)

- `routes_a.chat_message()` authenticates the customer chat, enforces conversation ownership and has a durable chat request ledger/idempotency path. It does not atomically commit a case operation with that ledger.
- `intent.classify()` is deterministic. The Unit 06 decision log's source review records that the target sentence currently produces a clarification tie rather than a proven complaint case intent; no case-create action is implemented in `orchestrator.run_turn()`. This is a static source finding, not a new runtime test.
- `ROLE_PERMS` gives `customer` `case.read`, not `case.create`. `app.main.create_case()` requires `case.create`; its customer-id binding code is reached only after that authorization dependency. The `create_case` tool's AL1 registry entry is not a customer permission grant. The chat orchestrator does not receive verified customer principal context for delegated case creation. No permission/assurance bypass is approved.
- `CaseRow` persists an internal case, tenant/customer (customer nullable today), origin conversation, reference, category/subcategory, severity fields, statuses, queue, logged time, and SLA version. It lacks fields/relations required by the draft contract, including complaint description/provenance, source channel, owner identity, case-conversation linking, timeline and durable case-operation idempotency. `Store.create_case_db()` commits case, SLA and outbox together, then emits the global audit event after commit; global audit is in-memory.
- `GET /v1/cases/{cid}` has customer owner checks but returns internal `status` together with customer-visible status. `/v1/status/{reference}` returns a visible status projection but has no documented AL2 check. No dedicated `/v1/customer/cases` list/detail contract was found.
- `CrmOutboxRow` is persisted with case creation. Worker `drain()` uses process-local `CRM_AVAILABLE`: true marks the local row `SENT`; false increments attempts and leaves it `PENDING` with an error. No explicit simulator ACK payload/ID, external CRM call/receipt, bounded retry/backoff, terminal failure, or CRM reconciliation task is implemented in this path. These states must remain distinct: **case committed in PostgreSQL**, **outbox PENDING/SENT**, **simulator ACK (not currently modeled)**, and **external CRM acceptance (not evidenced)**. `SENT` is not proof of either ACK or CRM receipt.
- Alembic has `alembic.ini` and `versions/0001_init_b.py`, but no `alembic/env.py`; the initial revision calls `Base.metadata.create_all()` and downgrade is a no-op. Startup also calls `create_all()`. No deployment schema baseline or safe migration/rollback procedure is established by this audit. No database was inspected or changed.
- `/customer/requests` and `/customer/requests/new` are route-map entries/placeholders; current `CustomerChat()` does not render a case result. Build plan assigns the full complaint/tracking UI to Unit 07 while Unit 06 draft proposes minimum list/detail UI. This scope conflict requires an explicit decision.
- Redis is described/used for refresh-token rotation, not as case/outbox authority. It is not a case persistence prerequisite when a valid customer principal exists and PostgreSQL is available. Gemini live is not required for this deterministic skeleton; the current chat orchestrator does not call Gemini.

### Dependencies and likely implementation files

Build plan Unit 06 depends on the established identity/conversation foundation (Units 01–04) and proceeds after Unit 05 verification. Implementation reuse candidates are `app/modules/routes_a.py`, `intent.py`, `orchestrator.py`, `tool_gateway.py`, `cases.py`, `store.py`, `models.py`, `outbox.py`, `app/core/rbac.py`, `app/core/audit.py`, `app/main.py`, Alembic setup, `web-workspace/src/App.jsx`, and tests under `tests/`. Likely new work includes a dedicated case service/model migration, customer-scoped case API, transactional timeline/idempotency records, worker semantics, and focused unit/integration/security/API/E2E tests. These are candidates only; the draft spec and UI ownership decision determine final scope.

Unit 07 owns the broader complaint form/tracking journey; Unit 08 owns complete handoff context. A CRM reconciliation task must not be equated with existing conversation `HandoffRow` without an approved owner/queue/SLA contract. No production identity issuer is present; this unit's local synthetic flow can reuse a verified development principal but must not claim production identity readiness.

## 5. Unit 06 readiness and blockers

**Status: BLOCKED.** No implementation is authorized by the active draft, the Unit 05 gate is not accepted, D-01–D-10 are unresolved, and the current source lacks required customer case flow/persistence contracts. Existing recommendations are not decisions.

### Mandatory before any Unit 06 code under current project sequence

| Blocker | Current fact / required decision | Authority and source |
|---|---|---|
| Unit 05 gate and sequencing (D-10) | Unit 05 remains IN PROGRESS and contrast testing is outstanding. No reviewer approval or sequencing exception is recorded. | Mentor/project owner; `context/specs/00-build-plan.md` Unit 05/06; `docs/units/UNIT_06_DECISION_LOG.md` D-10; latest gate review. |
| Official requirement baseline (D-09, P0) | Repository contains v0.9 FRD/TRD working PDFs; TRD refers to FRD v1.0, but canonical signed FRD v1.0/TRD approval is not established. Confirm approved baseline or explicitly approve v0.9 as working baseline and record deviations. | Product/mentor; build plan, audit and D-09. |
| Case creation actor/assurance (D-01, P0) | Customer lacks `case.create`; current orchestrator doesn't bind a verified customer principal into the case operation. Decide delegated service authority vs step-up/confirmation and exact assurance. | Product + security/mentor; RBAC/auth source and D-01. |
| Migration baseline/rollout (D-02, P0) | Migration runner is incomplete and existing schema/backfill/rollback policy is not verified. Decide target baseline, migration owner, rollout/rollback and legacy-row treatment before an additive migration. | DB/architecture owner; `alembic/`, architecture notes and D-02. |
| CRM outage contract (D-03/D-04, P0) | Active spec includes outage semantics. Decide whether a local committed reference is customer-visible while CRM is pending, what a simulator ACK means, retry bounds, and who owns terminal reconciliation task/SLA. | Product/mentor + operations; FRD/TRD conflict, spec §§11, decision log. |

### Must be resolved before the affected implementation stage; some can be scheduled after the initial contract review

| Decision | Stage gate | What must be agreed |
|---|---|---|
| D-05 duplicate complaint without transaction ID (P1) | Before C duplicate matcher/schema constraint | Whether same-request idempotency alone suffices initially, required incident fields, matching scope, and when to clarify/link rather than merge. No fuzzy matching by assumption. Product/mentor approval for behavior; uniqueness mechanics are technical afterward. |
| D-06 customer-visible status vocabulary (P1) | Before F API projection/G labels | Public enum/Indonesian wording and assurance for status lookup; keep internal status hidden. Product/API owner. |
| D-07 audit/timeline content and retention (P1) | Before B schema; before C/E writes | Event fields, customer visibility, append-only guarantees, retained data and ownership between case timeline and global audit. Architecture/product/compliance. |
| D-08 chat-to-case idempotency/retention (P1) | Before B/C schema and transaction design | Key derivation/link to existing chat ledger, replay/concurrency/crash-window behavior, expiry/retention. Architecture owner for retention contract; mechanics can be implemented technically after. |
| Unit 06 vs Unit 07 UI boundary | Before G | Whether Unit 06 includes only a chat case card or also minimum list/detail; build plan assigns full tracking UI to Unit 07. Product/mentor. |

P0 D-03/D-04 may only be deferred from a narrower local-case prototype if product explicitly narrows/approves scope and the customer copy makes no CRM delivery/reconciliation claim. No such scope decision is recorded; the active Unit 06 spec includes those behaviors, so they block full Unit 06 readiness/completion now.

## 6. Review of A–H implementation plan

The A–H split is sensible as a proposal, but not executable as written until the contract and dependencies are approved. Keep A as a no-code decision gate. Run migration-runner/schema-baseline verification before B, not as part of or after an unreviewed migration. Make C transactionally bind case, SLA, outbox, timeline and durable idempotency. Split D intent/clarification tests from the authorized create operation. F must be a customer allowlisted projection, not a reuse of the current `/v1/cases/{cid}` response. E may be developed after shared state/ACK decisions and schema; it is mandatory before claiming CRM outage recovery or reconciliation. G must wait for the Unit 06/07 UI allocation. H includes Unit 05 regression, migration rehearsal, authorization/IDOR, crash-window idempotency, outbox failure and browser evidence.

Suggested gated order: **Unit 05 contrast result + reviewer disposition → A0 human decisions → migration baseline/runner readiness → B schema → C durable case operation → D deterministic intent + gateway/policy → F customer API → D2 replay/response integration → E simulator/outbox/reconciliation (can parallelize with F after common contract, must finish for full CRM claims) → G only after UI scope approval → H verification.** No Gemini-live request, external CRM call, or financial transaction is needed.

## 7. Next safe step

See the current-session re-audit below. Continue at document/decision stage until the Unit 05 gate is dispositioned and the applicable Unit 06 approvals are explicitly recorded. The requester authorized this readiness work and reported Unit 05 manual testing as okay to continue; that report does not itself change the gate, approve D-01–D-10, or authorize application implementation.

## 8. Current-session readiness re-audit (2026-10-20)

### Evidence boundary

- **Inspected now:** active Unit 06 spec/plan/decision log/checklist, this audit, Unit 05 gate, build plan/progress tracker; relevant current source in `app/core/rbac.py`, `app/main.py`, `app/modules/routes_a.py`, `models.py`, `models_a.py`, `intent.py`, `orchestrator.py`, `tool_gateway.py`, `cases.py`, `store.py`, `outbox.py`, `app/core/db.py`, Alembic files, `web-workspace/src/App.jsx`, and relevant test files.
- **Current source findings below are static inspection**, except for the isolated intent-function probe explicitly marked as run. No live database schema/query was inspected. No pytest suite, migration, server startup, external service, banking action, or Gemini request was run.
- **Git:** `git status --short` failed because the active folder has no discoverable `.git` repository. This review cannot report the initial tracked/unstaged change set. No application source, schema, DB data, dependency, auth config, or permission was changed by this review.
- **Prior evidence:** older test/build results quoted elsewhere in this audit remain historical and were not rerun here.

### Fresh source findings

1. **Customer chat and request idempotency:** `routes_a.chat_message()` validates customer text/channel and owned conversation, hashes the scoped `Idempotency-Key` and request body, commits a `PROCESSING` request row before orchestration, replays only a `COMPLETE` response, and returns conflict for non-complete/reused-different requests. On later errors it marks the request `FAILED`. This ledger is not transactionally tied to case creation; no durable case-operation key/relationship is present in the inspected case store. Source: `app/modules/routes_a.py`, `models_a.py`.
2. **Intent probe (actually run, no DB):** `python -c "from app.modules.intent import classify; import json; print(json.dumps(classify('Transaksi saya gagal, tetapi saldo saya terpotong.', 'READINESS-AUDIT-CNV'), ensure_ascii=False))"` returned `INFO_ACCOUNT_BALANCE`, category `INQUIRY`, confidence `0.7`, decision `CLARIFY`. This is a direct pure-function probe, not a pytest suite. Current `orchestrator.run_turn()` has no complaint-to-case mapping in `_need_tool()` and receives no verified principal object; no case create is performed for this result.
3. **Authorization/policy:** current `ROLE_PERMS['customer']` includes `case.read` but not `case.create`; `POST /v1/cases` is guarded by `require_perm('case.create')`. `create_case` is registered AL1, but `permitted_set()` filters by assurance/circuit and does not bind role; `evaluate()` checks registry/prohibited action and assurance, not customer ownership/RBAC. The chat path currently does not invoke this case tool. None of these facts grants customer create authority. Source: `app/core/rbac.py`, `tool_gateway.py`, `main.py`, `orchestrator.py`.
4. **Case persistence and API:** `CaseRow.customer_id` is nullable and the inspected model has no description/source-channel/risk/provenance fields, case-conversation link table, append-only case timeline, or durable case-create idempotency mapping. `Store.create_case_db()` writes case, SLA, and outbox in one DB commit, but does not persist all fields accepted by `CreateCaseIn`; it emits global audit after commit. `GET /v1/cases/{cid}` returns internal `status` as well as customer-visible status. `/v1/status/{reference}` has optional principal scoping but no assurance-level enforcement in the route. No dedicated customer case list/detail route was found. These are source facts; the live DB schema and existing data were not inspected.
5. **Outbox:** current worker uses process-local `CRM_AVAILABLE`; when true it changes local outbox state to `SENT` without an adapter call or CRM receipt. When false it increments attempts and leaves the row pending with a fixed error. No bounded backoff, terminal state, or durable reconciliation task was found. `SENT` therefore proves neither simulator ACK nor external CRM acceptance. Source: `outbox.py`, `models.py`, `worker_outbox.py`.
6. **Migration, UI, tests:** `alembic/env.py` is absent; only `versions/0001_init_b.py` exists, with `create_all()` upgrade and no-op downgrade, and app import runs `Base.metadata.create_all()`. Customer request routes are placeholders and chat does not render a case result. Relevant pytest setup calls `Base.metadata.drop_all/create_all`; `tests/test_sla_outbox.py` removes `./eaics_test.db`. Tests were deliberately not run to honor the no-database-change boundary. Source: `alembic/`, `app/main.py`, `web-workspace/src/App.jsx`, `tests/conftest.py`, `tests/test_customer_conversations.py`, `tests/test_sla_outbox.py`.

### Unit 05 statement and gate

The requester states in this task that they manually tested Unit 05 and consider it okay to continue. **This is requester-reported, not Codex-repeated or independently evidenced:** no specific checklist, date/device details, artifact, or reviewer disposition accompanied the statement. It authorizes this Unit 06 readiness review only. The existing Unit 05 gate and build plan do not record a formal review decision; Unit 05 remains **IN PROGRESS**, not COMPLETE or APPROVED. D-10 sequencing/implementation permission remains unresolved for application-code work.

### Approval audit: D-01 through D-10

The active decision register says all ten decisions are `UNRESOLVED`. The approval checklist has no selected options, decision text, approver, or date. No approval is inferred from recommendations or from the requester's Unit 05 report. Detailed alternatives/recommendations already in `UNIT_06_DECISION_LOG.md` remain proposals. Summary of blockers:

| Decision / gate | Choices on record | Main risk | Recommendation on record (not approval) | Required approver; implementation gate |
|---|---|---|---|---|
| **D-01 P0 — actor/assurance** | Customer `case.create`; narrow delegated service capability; customer step-up/confirmation; human-only; other. | Excess customer privilege or confused deputy; alternatively friction/unavailable intake. | Keep customer role least-privileged; bind verified principal/tenant/customer/conversation and policy decision to backend intake; honor AL1 with step-up. | Product + Security/mentor. Before customer create/service authorization work. |
| **D-02 P0 — migration/schema rollout** | Repair Alembic and add additive migration; continue `create_all()`; defer schema gaps. | Existing DB incompatibility, missing constraints/backfill, unsafe rollback. | Establish baseline/owner/rollout and rehearse additive migration on disposable DB; do not treat `create_all()` as migration evidence. | DB/architecture owner. Before schema/migration stage. |
| **D-03 P0 — reference during CRM outage** | Return committed local reference with sync pending; provisional receipt; reject intake. | Local reference may not resolve in CRM; provisional tracking undefined; rejection can lose complaint. | Treat local DB as source only if product explicitly approves and separates local persistence from CRM state. | Product/mentor. Before response/status contract. |
| **D-04 P0 — ACK/retry/reconciliation** | Explicit adapter ACK + bounded retry/task; local-only simulated state; reuse conversation handoff. | False CRM success or unowned/untracked recovery work. | Define persisted ACK, retry cap/backoff, reconciliation owner/queue/SLA; never equate `SENT` with CRM receipt. | Operations + product. Before outbox claims and Unit 06 completion. |
| **D-05 P1 — duplicate matching/minimum data** | Same-request only; exact transaction reference; same conversation/category; fuzzy match. | Duplicate cases or false merges. | Durable same-request idempotency first; cross-request linking only on approved exact incident key; no fuzzy merge by default. | Product/mentor. Before duplicate matcher/schema constraint. |
| **D-06 P1 — customer status/projection** | Existing enum with labels; FRD-aligned public enum; versioned allowlisted projection. | Internal status leakage, semantic mismatch, breaking clients, or assurance gap. | Keep internal state private; expose a tested projection and settle assurance for reference lookup. | Product/API owner. Before customer API/status labels. |
| **D-07 P1 — audit/timeline/retention** | Case-specific durable timeline; durable global audit in this unit; defer. | Split/inconsistent audit, broad schema scope, or missing append-only history. | Persist case timeline atomically with case/outbox/idempotency; agree fields, visibility, redaction, retention. | Architecture + product/compliance. Before timeline schema or case writes. |
| **D-08 P1 — chat-to-case idempotency** | Link existing chat ledger atomically; add durable operation mapping; use memory cache. | Crash-window/concurrency duplicates or retention/privacy mismatch. | Server-derived scoped operation hash and durable unique mapping in case transaction; replay committed result, reconcile ambiguous state. | Architecture owner for key correlation/retention. Before schema/transaction design. |
| **D-09 P0 — FRD/TRD baseline** | Approve v0.9 working baseline with deviation log; wait for signed baseline; narrowly limit invariant work. | Requirement rework and disputed customer-facing behavior. | Record exact approved baseline/version before behavior/schema work. | Product/mentor. Before contract closure and implementation. |
| **D-10 P1 — Unit 05 sequencing / UI scope** | Close Unit 05 first; explicitly permit parallel backend work; documentation/readiness only now; chat card vs list/detail scope. | Violating build-plan gate or expanding Unit 06 into Unit 07. | Continue readiness/docs only; no application-code exception is recorded. Decide Unit 06 minimum UI boundary. | Mentor/project owner. Before Unit 06 code and UI stage. |

P0 items block implementation under the current full draft scope. P1 decisions block their affected stages and cannot be silently defaulted. The current request authorizes readiness work only; it does not fill or approve the decision checklist.

### Safe dependency-aware implementation order after approvals

1. **A0 — contract gate, no code:** record D-01–D-10 answers, named approvers/date, FRD/TRD baseline, customer promise, and Unit 06/07 boundary.
2. **A1 — migration readiness inspection:** after DB/architecture owner approves an isolated environment, verify schema baseline and migration runner/upgrade path. Do not run migration against the active project DB; coordinate general runner repair with Unit 16.
3. **B — additive schema:** only after D-02/D-07/D-08 and legacy data treatment are settled; add required ownership/provenance, timeline, durable create idempotency, and outbox state constraints.
4. **C — case service proof:** atomically persist case, SLA, outbox, timeline, and operation result; verify rollback, uniqueness, replay, and concurrency on disposable DB.
5. **D1 — intent and policy tests, then authorized orchestration:** prove target phrase/clarification and zero writes on ambiguity/deny/insufficient assurance; wire create only under D-01-approved actor/policy. Never grant customer `case.create` or bypass gateway by inference.
6. **E/F — outbox and customer API:** implement ACK/retry/reconciliation per D-03/D-04; expose an allowlisted owner-scoped projection per D-06. Integrate chat response only from committed case results and approved local/CRM state.
7. **G — minimum Unit 06 UI only if allocated:** render the approved chat result and/or list/detail boundary. Keep Unit 07 form/full tracking work out unless explicitly re-scoped.
8. **H — verification gate:** focused/full backend tests, migration rehearsal, policy/IDOR/crash-window/outbox tests, frontend build, and approved browser journey. Update completion status only from actual results and gate review.

### Work allowed without crossing gates

Continue decision collection, requirements traceability, test-case design, and non-mutating source/schema/migration inspection. Do not change app source, auth/RBAC/policy, schema/migrations, config/dependencies, or DB; do not run tests that drop/create tables; do not make CRM, Gemini, or banking calls. Unit 07 has not started.
