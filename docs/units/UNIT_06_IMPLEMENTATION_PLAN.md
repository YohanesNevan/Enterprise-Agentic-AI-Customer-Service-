# Unit 06 — Implementation Plan

**Status:** pre-implementation proposal; not approved for coding.  
**Scope:** safe deterministic complaint-to-case flow for an authenticated customer. No live Gemini, banking transaction, transfer or reversal is required.  
**Companion documents:** `docs/audit/CURRENT_PROJECT_AUDIT.md`, `docs/units/UNIT_06_SPEC.md`, `context/specs/00-build-plan.md`, FRD/TRD v0.9 working copies.

## 1. Pre-implementation fact check

This section records code evidence, not proposed behavior. Source code is authoritative where older audit notes differ.

| Claim / area | Actual code evidence | Assessment / correction to Unit 06 spec |
|---|---|---|
| Customer chat authentication, ownership and replay | `routes_a.chat_message()` validates `CustomerChatIn`, WEB_CHAT, signed context and conversation `(id, tenant_id, customer_id)`. It hashes the idempotency key into `CustomerRequestRow`, stores a body fingerprint, and replays COMPLETE response. | Reusable. The request ledger commits PROCESSING before orchestration; failures remain FAILED and return 409 on replay. Case write is not atomic with ledger completion. |
| Duplicate conversation ownership check | `routes_a.chat_message()` repeats the same ownership query twice for a supplied conversation id. | Redundant check; not a blocker for behavior, can be cleaned only if in scoped change and covered by tests. |
| Intent selection | `intent.classify()` uses substring keyword scoring. On the exact target phrase, `INFO_ACCOUNT_BALANCE` (“saldo”), `INFO_TRANSACTION_HISTORY` (“transaksi”) and `CMP_SERVICE_FAILURE` (“gagal”) each score 0.70; insertion order puts `INFO_ACCOUNT_BALANCE` first and the near-tie rule sets decision `CLARIFY`. `CMP_TRANSACTION_DISPUTE` does not match this exact phrase. | The current result is deterministically clarification, not complaint/case creation. Unit06 needs either a narrow, tested rule/slot refinement for this exact complaint or keep asking clarification; do not create from current ambiguous result. |
| Complaint orchestration | `orchestrator.run_turn()` handles HANDOFF/CLARIFY/inquiry and allowed tools. `_need_tool()` has no complaint/create-case mapping. | Complaint→case is absent. Gemini is not called. |
| Tool gateway | `tool_gateway.REGISTRY` has `create_case` at AL1/idempotent. `permitted_set()` filters by assurance only (its actor parameter is unused); `evaluate()` checks registry/prohibited tools and AL but does not itself check RBAC role, customer ownership, tenant, or case arguments. It emits in-memory audit. | Gateway alone is not full authorization. Caller must provide trusted principal context and an explicit permission/ownership policy. Do not treat `create_case` registry entry as proof a customer may create a case. |
| RBAC / API case creation | `ROLE_PERMS` gives customer `case.read`, not `case.create`; `ai_agent`, CS and supervisor have create. `/v1/cases` in `main.py` requires `case.create`. Its customer_id assignment branch is unreachable under current customer permissions unless a different trusted role is used. | Customer must not be granted a new permission implicitly. Determine authorized server-side actor/delegation and assurance before coding. |
| Existing case read | `routes_a.case_lookup()` filters tenant then compares customer id for customer role, returning 404 on mismatch; `case.read` is required. It returns only case_id/internal status/customer-visible status. | Safe narrow read is present and test evidence exists; no customer list/detail projection or proper status mapping contract. It still exposes internal `status` to a customer and needs a customer-safe contract before portal reuse. |
| Case request/service | `cases.CreateCaseIn` supports customer_id, category, severity, risk, description, source channel, links and optional idempotency key. `cases.create_case()` stores an in-memory dict. API route instead calls `Store.create_case_db()`. | Do not confuse legacy dict simulator with persistent case service. `CreateCaseIn.idempotency_key` is not used by `Store.create_case_db()`. |
| PostgreSQL case record | `models.CaseRow` includes ID, tenant, nullable customer, origin conversation, unique customer reference, category/subcategory, proposed/confirmed severity, internal/customer status, queue, logged time, reopen count and SLA version. | Missing TRD fields/relations include description, source channel, risk level, created-by provenance, owner ID, durable case timeline/link history, and durable create-idempotency mapping. There is no explicit FK relationship in this model declaration. |
| Case transaction and audit | `store.create_case_db()` adds CaseRow, SlaRecordRow and CrmOutboxRow, commits once, then calls `audit_svc.emit()`. The audit implementation is in-memory. | DB case/SLA/outbox writes are grouped; durable audit/timeline is not in that transaction. Returned response includes data from the saved case but no explicit read-after-write. |
| Severity | `store.create_case_db()` leaves confirmed severity NULL for AI_AGENT HIGH/CRITICAL; legacy `cases.create_case()` does likewise. | Existing rule is useful; add actor/role tests before using it for the chat flow. |
| Customer status mapping | `contracts.vocabularies.CustomerVisibleStatus` has RECEIVED, BEING_INVESTIGATED, WAITING_FOR_YOU, OUTCOME_READY, CLOSED, REOPENED. `cases.INTERNAL_TO_CUSTOMER` maps internal states to those values. | FRD labels are human concepts (Under review, Waiting for customer, etc.); spec’s proposed API constants `UNDER_REVIEW` / `WAITING_FOR_CUSTOMER` are not current enums. Product/API owner should confirm vocabulary; simple technical map can otherwise preserve established enum values. |
| CRM outbox | `models.CrmOutboxRow` has state, attempts, last_error, created_at, sent_at. `outbox.drain()` increments attempts; unavailable leaves PENDING and sets error; available sets SENT without calling a CRM adapter. `worker_outbox.py` polls every 15s and calls internal drain. | No demonstrated CRM ACK, backoff, cap/terminal failure, or reconciliation/human task. “SENT” currently means only simulator flag allowed the local transition. Do not expose it as externally synced. |
| Handoff | `orchestrator._queue_handoff()` persists HandoffRow via QueueSvc and accurately distinguishes queued/accepted; `package_complete=False`. | It is a conversation handoff, not a proven CRM reconciliation task. A persisted handoff is possible, but product/ops must define whether it satisfies CRM recovery work and what queue/reason/SLA apply. |
| Audit / append-only | `core.audit` keeps an in-memory event/hash chain. Case mutations emit after DB commit. No case timeline model was found. | Durable and atomic FR-CASE timeline is absent. Schema/service boundary and event visibility require design; whether global audit belongs in Unit06 is a product/architecture scope decision. |
| Migration | `alembic.ini` points to `alembic`; `alembic/versions/0001_init_b.py` calls `Base.metadata.create_all()` and has a no-op downgrade. `alembic/env.py` is absent. App startup also calls `Base.metadata.create_all()`. | Migration lifecycle is not ready for a safe additive production migration. Before schema coding, decide and verify migration runner/baseline, existing DB state, and deployment procedure. Do not run migration as part of this review. |
| Frontend | `CustomerChat` in `web-workspace/src/App.jsx` posts chat/idempotency key, displays history, but does not render case response. Route map has `/customer/requests/new` and `/customer/requests` as Unit06 placeholders. `package.json` scripts only dev/build/preview; no frontend test runner. | Minimal chat case card/list/detail are feasible; unit/e2e frontend automation needs an approved existing harness or remains manual. Do not add dependency implicitly. |
| Tests | Pytest tests exist for chat idempotency/ownership, security, case severity and outbox. `tests/test_sla_outbox.py` currently treats local PENDING→SENT under simulator toggle as success. | Reuse and extend tests; update the assertion semantics carefully when simulator ACK semantics are approved. Existing test results from past audit are historical, not proof for future changes. |
| Database/cache/provider | PostgreSQL is app default; tests can opt into SQLite. Redis is used for refresh rotation, not durable case workflow. `run_turn()` is deterministic; provider tests do not prove live Gemini. | DB-backed idempotency/outbox can make Redis unnecessary for this flow. Gemini live and Redis availability need not block the deterministic path. |

## 2. Technical decisions / blockers

Options below are alternatives for review. Recommendations do not change policy by themselves.

### 2.1 Authorization and assurance for chat case creation — **approval required**

- **Actual:** customer principal has `case.read` and conversation permissions, no `case.create`; `create_case` tool is AL1. Existing chat route’s trusted context is a customer principal, while orchestrator `run_turn()` gets no principal/role/actor id parameter and defaults actor to `AI_AGENT`. Customer channel session can be AL0. Gateway currently checks assurance, not role-level case permission or ownership.
- **FRD/TRD:** FR-CASE-001 calls for AI to create case via tool layer; auth model says server-side RBAC and assurance apply. Tool proposal is not authorization.
- **Options:** (a) customer direct create permission plus step-up; (b) server-side delegated case-intake service principal with narrowly scoped permission, while preserving customer as owner/provenance and checking signed principal + conversation; (c) require human/customer confirmation before create; (d) leave case creation unavailable until identity assurance reaches existing threshold.
- **Risks:** (a) widens customer write surface; (b) confused-deputy risk if actor/delegation and ownership are not cryptographically/trust-bound; (c) extra friction and can conflict with automatic FRD flow; (d) cannot meet immediate complaint acceptance for AL0 session.
- **Recommendation:** use a dedicated backend case-intake operation, invoked only after trusted principal, tenant/customer/conversation equality checks; authorize using an explicitly scoped service capability through the established gateway/policy and retain original customer as subject. Do not have LLM/AI role invent its own authority. Set its required assurance based on a documented FRD data classification decision. If current rule says AL1, stop with step-up; do not lower AL or mint a customer-facing role implicitly.
- **Approval:** product/security/mentor must approve actor model and assurance. Implementation can then encode the approved rule technically.

### 2.2 Status/reference when CRM simulator is unavailable — **product decision**

- **Actual:** DB case, SLA and outbox are committed locally; `store.create_case_db()` returns local reference and `crm_pending`. `drain()` with unavailable simulator leaves pending. Current worker can mark `SENT` on a boolean without external delivery.
- **FRD/TRD:** FRD p.63 says if CRM simulator unavailable, case is queued and customer told reference will follow; TRD §8.9 permits local reference in degraded mode. These conflict on whether the customer may immediately receive a reference.
- **Options:** (a) local DB is authoritative: return reference after commit, label CRM sync pending; (b) suppress reference until simulator accepts and show provisional receipt; (c) reject acceptance if CRM is down and create no local case (conflicts with outbox requirement).
- **Risks:** (a) customer sees a reference that CRM cannot resolve; (b) avoid mismatch but customer cannot track locally unless provisional status API is defined; (c) loses complaint during outage and contradicts durable outbox pattern.
- **Recommendation:** prefer (a) only if local PostgreSQL case is accepted as authoritative and customer lookup remains local; clearly separate `case_persisted` from `crm_sync_state`. Do not call status “CRM synced”. Resolve the FRD/TRD conflict first.
- **Approval:** product/mentor must choose customer-facing wording and reference semantics; technical implementation follows.

### 2.3 Simulator acknowledgment, retry, reconciliation — **ops/product contract required**

- **Actual:** simulator is a process-local boolean; available drain marks outbox SENT, unavailable drain increments attempts and records a fixed error. There is no retry schedule, terminal state, persisted worker lease, external ACK, or reconciliation task. HandoffRow queues a conversation, package incomplete.
- **FRD/TRD:** FR-CASE-001 requires outbox plus human task on CRM unavailability; TRD §8.6–8.9 requires idempotent retry/failure behavior and reconciliation for side-effect uncertainty.
- **Options:** (a) simulator ACK is a durable accepted response from a test adapter; retry bounded/backoff then create reconciliation task; (b) treat local drain toggle as an explicit simulated ACK only in local test profile, never claim external sync; (c) rely on conversation HandoffRow for human follow-up.
- **Risks:** (a) requires adapter and task schema/worklist; (b) risks test/prod semantics drift; (c) a handoff may not reach CRM operations and is not case-level reconciliation.
- **Recommendation:** define an adapter result contract (`accepted`, stable external operation ID, retryable/permanent error); persist attempt count/next-attempt/last-safe-error and idempotency token; bounded exponential backoff; after exhausted retries create exactly one durable reconciliation task. Keep simulator and production adapter semantics distinct. No production CRM adapter is implied by this plan.
- **Approval:** ops/product must define task owner, SLA, retry cap and customer wording. ACK schema/retry implementation is technical after that.

### 2.4 Dedupe complaint without transaction ID — **product rule required**

- **Actual:** chat request ledger dedupes same key/body only. `Store.create_case_db()` has no duplicate lookup or idempotency. `CaseRow` has unique generated customer reference, not an incident key. FRD relationship supports duplicate/related case links.
- **FRD/TRD:** FR-CASE-001 asks to link an open matching case rather than create duplicate; TRD idempotency key is derived from conversation/intent/tool/version/canonical args/attempt group.
- **Options:** (a) dedupe exact request only; (b) dedupe same customer + conversation + category; (c) require transaction reference/date/amount and dedupe on normalized incident fingerprint; (d) fuzzy semantic match across conversations.
- **Risks:** (a) distinct keys can create duplicate case; (b) multiple incidents in one conversation collapse; (c) requires customer to provide details and protects distinct incidents; (d) false merge, privacy/data leakage, hard-to-reproduce behavior.
- **Recommendation:** first guarantee database-backed idempotency for one logical chat turn. For cross-turn matching, only auto-link on an exact validated transaction reference + tenant/customer/category while target case is open; with no reference, ask a targeted clarifying question or create a separate initial complaint according to approved minimum-field rule. Do not fuzzy merge in first walking skeleton.
- **Approval:** product/mentor must decide whether reference is mandatory and matching rule. Unique constraints/idempotency implementation is technical.

### 2.5 Internal to customer-visible status — **product/API vocabulary approval**

- **Actual:** persisted enum projection is RECEIVED, BEING_INVESTIGATED, WAITING_FOR_YOU, OUTCOME_READY, CLOSED, REOPENED. `INTERNAL_TO_CUSTOMER` maps existing case statuses. Endpoint case lookup returns both internal and customer status.
- **FRD/TRD:** FR-CASE-010 names Received, Under review, Waiting for customer, Outcome ready, Closed, Reopened, and prohibits internal queue/agent details.
- **Options:** (a) retain existing API enums and provide Indonesian display labels; (b) change to FRD-aligned `UNDER_REVIEW`, `WAITING_FOR_CUSTOMER`; (c) versioned projection translating existing persisted values.
- **Risks:** (a) semantic mismatch (`BEING_INVESTIGATED` vs `UNDER_REVIEW`); (b) breaking clients and old rows; (c) extra compatibility mapping complexity.
- **Recommendation:** agree exact API enum with product/API owner, then preserve internal CaseStatus and introduce an explicit tested projection; do not expose internal status in customer endpoint.
- **Approval:** product/API owner approval for terms is needed; implementation mapping is technical.

### 2.6 Durable audit and append-only case timeline — **scope/retention approval required**

- **Actual:** audit service is process memory; case create/status commits before event emission. No CaseTimeline model/table. Hash chain is not durable across restart.
- **FRD/TRD:** FR-CASE-004 requires append-only case timeline for messages, tools, evidence, approval, SLA, escalation, notes/status and actor/correlation; TRD calls for durable audit.
- **Options:** (a) Unit06 adds append-only `case_timeline_entry` transactionally and existing global audit remains non-durable; (b) expand global audit to durable transactional event store; (c) defer timeline to another unit (does not meet case journey audit requirement).
- **Risks:** (a) event duplication/inconsistent global audit; (b) larger cross-cutting migration and writes; (c) audit gap violates requirement and impairs investigations.
- **Recommendation:** add case-specific timeline row atomically with case/outbox/idempotency and every case transition; have a single service writer, immutable API surface and tests. Treat global audit durability as explicit residual risk unless architecture owner assigns it to Unit06. Define retention and redaction before persisting message details.
- **Approval:** product/compliance/architecture must confirm retained fields/retention and Unit scope. Atomic row design is technical after policy.

### 2.7 Chat idempotency to case idempotency — **technical decision after contract**

- **Actual:** `CustomerRequestRow` hashes scoped header and stores response; it marks processing before side effects and complete after orchestrator. Case store ignores `CreateCaseIn.idempotency_key`; tool gateway dedupe is in-memory and keyed by conversation/tool/args, without tool version or durable DB record.
- **FRD/TRD:** chat same-key replay must not duplicate; TRD §8.6 specifies canonical tool operation key. Case, outbox and audit need one logical operation identity.
- **Options:** (a) link chat request row to case and update both in one transaction; (b) add `case_creation_request` unique mapping, transactionally committed with case/outbox/timeline; (c) rely only on current in-memory gateway cache.
- **Risks:** (a) chat orchestration transaction currently commits inbound/outbound at separate points, so broad transaction refactor; (b) adds table/migration but isolates durable contract; (c) restart/concurrency duplicates.
- **Recommendation:** keep existing chat replay contract; pass only its server-derived request identity into the case service. Add a durable unique operation row scoped by tenant/customer/request hash and atomically store case ID/result with case/SLA/outbox/timeline. On replay, return the committed safe response; if request is PROCESSING/ambiguous, return conflict and reconcile rather than run create again.
- **Approval:** architecture owner confirms retention/expiry and exact relationship to request ledger; storage/unique-constraint mechanics are technical.

### 2.8 FRD/TRD baseline and Unit05 dependency — **approval / sequencing decision**

- **Actual:** repo working docs and PDFs are v0.9; audit reports TRD references approved FRD v1.0, but signed v1.0 and TRD approval evidence are absent. Progress tracker says Unit05 remains in progress pending browser/responsive/accessibility verification. Unit05 spec says complaint-to-case is Unit06.
- **FRD/TRD:** Build plan Unit06 depends on Units01–02 and conversation identity; Unit05’s current contract provides deterministic chat/idempotency, but progress gate for selecting next implementation unit says finish browser/a11y verification first.
- **Options:** (a) approve v0.9 as working baseline and proceed while Unit05 verification runs; (b) wait for signed requirements and Unit05 closure; (c) implement only portions not affected by unresolved requirements.
- **Risks:** (a) rework if signed FRD differs; (b) schedule delay; (c) partial design can conceal inconsistent contract.
- **Recommendation:** approve a written working baseline and close the Unit05 verification gate before application coding, or explicitly authorize concurrent Unit06 implementation with limited scope. No Unit06 code should override Unit05 chat behavior.
- **Approval:** product/mentor decides baseline and sequencing; technical team can document deltas and keep implementation additive.

## 3. Pull-request-sized implementation stages

Commands below are proposed future commands, not run in this review. Use isolated test DB as `tests/conftest.py` expects; never point test suite at shared/production DB. Frontend `package.json` has no test/lint script. No test command proves real Gemini/CRM/banking integration.

### A. Contract, authorization and schema decision

- **Tujuan:** close §2 decisions; record approved actor/assurance, status vocabulary, outage behavior, duplicate rule, audit retention, official requirements baseline and Unit05 gate.
- **Files likely:** new/updated `docs/units/UNIT_06_SPEC.md` (decision addendum only after approval), `context/architecture.md`, `context/progress-tracker.md`, possibly `context/requirements-traceability.md`. Do not edit app code.
- **Prasyarat:** product/security/mentor and ops answers; confirmation that Unit05 contract is stable.
- **Acceptance:** each blocker has owner, decision, date/version; no undocumented RBAC/assurance change; API/domain contract states local commit vs CRM ack, retry/task, public statuses, minimum complaint fields and dedupe.
- **Test command:** none (decision/document review). Existing checks can be read-only only.
- **Regression risk:** stale docs or decision notes disagree with v0.9 source documents.
- **Dependencies:** before B–H.

### B. Additive database migration and model

- **Tujuan:** add only approved fields, relationship, durable idempotency and append-only timeline; preserve existing records and reads.
- **Files likely:** `alembic/env.py` (currently absent; setup decision), `alembic/versions/0002_unit06_case_ownership.py`, `app/modules/models.py`, perhaps DB/migration docs.
- **Prasyarat:** A complete; inspect real deployed/test schema and baseline. Decide migration strategy because current 0001 is `create_all()` and downgrade no-op. Use expand/backfill/constraint sequence for nullable legacy fields.
- **Acceptance:** upgrade on clean DB and representative prior schema succeeds; old case rows remain readable; constraints/indexes enforce tenant/reference/idempotency; timeline append-only behavior enforced by service and DB privileges/constraint strategy; rollback/recovery documented (no destructive downgrade assumed).
- **Test command:** `python -m pytest tests/test_unit06_schema.py -q -p no:cacheprovider`; migration smoke on disposable DB with `alembic upgrade head` only after migration runner is fixed and explicitly approved. Do not run against normal `.env` target.
- **Regression risk:** `Base.metadata.create_all()` startup can hide missing migration; SQLite may not model PostgreSQL constraints/concurrency; existing nullable customer cases need backfill policy.
- **Dependencies:** A; required by C/E.

### C. Case service, transaction atomicity and idempotency

- **Tujuan:** establish one persistent case service for validated customer intake/read; create/link case + SLA + outbox + creation ledger + initial timeline atomically; return committed projection.
- **Files likely:** `app/modules/store.py`, `app/modules/models.py`, `app/modules/cases.py` or new `app/modules/case_service.py`, `app/core/ids.py`; tests under `tests/`.
- **Prasyarat:** B schema; A duplicate key, required fields, reference semantics and audit event policy.
- **Acceptance:** same request replay returns same reference and row; conflicting fingerprint returns 409; concurrent same key yields one case; rollback leaves no partial case/SLA/outbox/idempotency/timeline; response derives fields from committed row; severity high/critical confirmation rule retained.
- **Test command:** `python -m pytest tests/test_unit06_case_service.py tests/test_b_skeleton.py -q -p no:cacheprovider`.
- **Regression risk:** existing `Store.create_case_db()` response fields are used by tests/UI; changing transaction ownership could break ticket/case routes; SQLite behavior differs on lock/unique races.
- **Dependencies:** B. Can be reviewed before D and F.

### D. Complaint intent/orchestration through policy gateway

- **Tujuan:** route complaint intent to the approved case-intake service only when classification, ownership, assurance and policy pass; ambiguous input asks clarification.
- **Files likely:** `app/modules/intent.py`, `app/modules/orchestrator.py`, `app/modules/routes_a.py`, `app/modules/tool_gateway.py`, possibly approved narrow RBAC/policy files; tests.
- **Prasyarat:** A actor/assurance authorization decision, C service contract. No Gemini dependency.
- **Acceptance:** exact scenario has deterministic expected complaint or clarification outcome; denied/step-up policy causes zero case writes; case service receives trusted server identity/customer/conversation; no LLM or client body can override tenant/ownership/severity-confirmed; no generic `{ok:true}` executor represents case creation; reply only claims case after service commit.
- **Test command:** `python -m pytest tests/test_unit06_intent_orchestration.py tests/test_a_skeleton.py tests/test_customer_conversations.py -q -p no:cacheprovider`.
- **Regression risk:** existing intent thresholds, handoff, degraded reply and deterministic customer information turns; code currently `_exec_tool()` has generic success fallback.
- **Dependencies:** A and C. Does not depend on E for local-only creation, but response must say if CRM pending.

### E. Outbox, retry, audit and simulator behavior

- **Tujuan:** implement approved simulator ACK contract, bounded retry/backoff and exactly-once reconciliation/handoff record; keep case local state distinct from CRM state; append lifecycle audit events.
- **Files likely:** `app/modules/outbox.py`, `app/worker_outbox.py`, `app/modules/models.py`, `app/modules/store.py`, `app/modules/queue.py` or dedicated reconciliation module, `app/core/audit.py`; tests.
- **Prasyarat:** A defines accepted ACK, retry cap/backoff, terminal behavior, owner/SLA, customer copy and durable audit scope; B schema for timeline/task.
- **Acceptance:** failed/unavailable simulator never marks SENT; duplicate worker delivery does not duplicate case/task; only explicit adapter ACK changes sync state; retry schedule is bounded and persisted; exhaustion creates one task; failure details are safely redacted; timeline/audit matches every state transition.
- **Test command:** `python -m pytest tests/test_unit06_outbox.py tests/test_sla_outbox.py -q -p no:cacheprovider`.
- **Regression risk:** current test assumes boolean toggle can transition PENDING→SENT; internal status endpoints/metrics may count rows differently; worker uses service token scope.
- **Dependencies:** B and A; can proceed parallel to F after contract.

### F. Customer list/detail API and response contract

- **Tujuan:** add safe customer list/detail endpoints; return case result through chat response; preserve internal staff routes.
- **Files likely:** `app/modules/routes_a.py` or customer case router, `app/main.py` router registration, Pydantic schemas, `app/modules/store.py`, `app/core/rbac.py` only if approved, OpenAPI tests.
- **Prasyarat:** A customer projection/status vocabulary; C service. D for chat case response. B schema.
- **Acceptance:** both list/detail derive tenant/customer from verified principal; cross-tenant/customer get generic 404; no internal status/queue/agent/risk/outbox error in response; chat includes only committed/reused reference and customer status; OpenAPI exposes contract/security requirements; pagination is bounded and tenant scoped.
- **Test command:** `python -m pytest tests/test_unit06_case_api.py tests/test_security_auth.py tests/test_customer_conversations.py -q -p no:cacheprovider`.
- **Regression risk:** existing `/v1/cases/{cid}` returns internal `status`; do not silently break staff callers or falsely mark its current projection customer safe.
- **Dependencies:** B, C, A; D for response integration.

### G. Frontend case card and list/detail minimum

- **Tujuan:** show only backend-backed case reference/status in chat; customer can reload list/detail; truthful pending/clarify/error/empty states.
- **Files likely:** `web-workspace/src/App.jsx`, maybe `web-workspace/src/components/CustomerCases.jsx` and style file after inspecting current layout; no dependency change presumed.
- **Prasyarat:** F response contract and approved labels; API available. Decide if minimal tracking is permitted in Unit06 despite build plan Unit07 full UI ownership.
- **Acceptance:** case card appears only from persisted response; navigation reloads from API; no hardcoded record; retry preserves same idempotency key; pending CRM language follows A; other customer ID yields generic not-found; keyboard/loading/empty/error states work.
- **Test command:** `npm.cmd run build` (run from `web-workspace`). No frontend unit/E2E test script is currently configured; browser workflow must be recorded manually unless an approved existing harness is found.
- **Regression risk:** manual history routing, chat notice, request replay and customer/staff route map; avoid conflicting with Unit07 implementation.
- **Dependencies:** F; may be parallelized with E after contract.

### H. Unit, integration, security, API contract and end-to-end tests

- **Tujuan:** prove all acceptance criteria across deterministic backend and browser without live providers or financial side effects.
- **Files likely:** `tests/test_unit06_*.py`, extend `tests/test_customer_conversations.py`, `tests/test_security_auth.py`, `tests/test_sla_outbox.py`; potential browser test only if repo receives approved harness in separate decision; OpenAPI assertions.
- **Prasyarat:** B–G implemented; isolated DB profile. Do not exercise external CRM/network or live Gemini.
- **Acceptance:** cover intent-or-clarify, policy deny/step-up no write, committed reference, list/detail ownership, IDOR 404, idempotency replay/concurrency, rollback, high severity pending confirmation, outbox pending/ack/retry/task, safe customer projection, UI trace from chat response to same DB case.
- **Test commands:** focused `python -m pytest tests/test_unit06_*.py tests/test_customer_conversations.py tests/test_security_auth.py tests/test_sla_outbox.py -q -p no:cacheprovider`; full backend `python -m pytest -q -p no:cacheprovider`; frontend `npm.cmd run build` in `web-workspace`. Existing README also documents `python -m pytest tests/ -v`; prefer isolated no-cache profile used by progress tracker. Browser/E2E command is currently **not available** because no frontend test runner is configured.
- **Regression risk:** shared `eaics_test.db` collisions (audit history documented); environment loader in `app/core/db.py` may read local `.env` on import. Ensure test process explicitly uses isolated disposable DB and stub provider without printing configuration.
- **Dependencies:** all prior steps; H is the evidence gate before calling the unit complete.

## 4. Smallest safe implementation order

Do not implement A–H as one PR. Recommended proof sequence:

1. **A0 — contract gate (no code):** approve trusted case-creation actor/assurance; FRD/TRD baseline; exact target phrase behavior; minimum complaint fields; status enum; local-reference outage rule; simulator ACK/task; dedupe; audit retention; Unit05 sequencing. If unresolved, stop before mutating role/policy/schema.
2. **B1 — schema foundation:** repair/confirm migration runner and additive schema only. Build migration tests against disposable PostgreSQL-compatible environment; do not rely solely on `create_all()`.
3. **C1 — persistent service proof:** unit/integration test direct service create with synthetic customer and conversation, transaction atomicity, durable idempotency and SLA/outbox/timeline. No route/UI yet.
4. **D1 — deterministic chat path:** bind exact user text to complaint or clarification; invoke approved backend service through policy; denied/step-up has zero case writes. No Gemini/live service.
5. **F1 — customer read contract:** add tenant/customer-scoped list/detail, hide internal fields; prove customer A success and customer B/tenant IDOR 404.
6. **D2/F2 — response and replay:** include committed reference/status in chat response; repeat same request key produces one DB case and identical response after retry/restart simulation.
7. **E1 — CRM simulator failure contract:** wire persisted ACK/retry/reconciliation behavior and honest API state. This can be split from local case read, but must precede any claim of CRM synchronization/human follow-up.
8. **G1 — UI minimum:** render committed response, open server-backed case detail/list, test customer isolation in API; build and browser check.
9. **H — full security/regression gate:** focused + full backend suite, frontend build, manual/automated E2E evidence. Update progress docs only with actual outcomes.

**Critical path for requested proof:** A0 → B1 → C1 → D1 → F1 → D2/F2 → G1 → H. E1 is required before describing external CRM state or CRM-failure human follow-up, but a local durable case can be proven without a real CRM connection if the approved customer contract explicitly labels sync pending.

## 5. Five highest blockers before coding

1. **Case creation authorization/assurance:** current customer lacks `case.create`, create tool is AL1, chat orchestrator is not passed a verified principal. Must choose and document a safe delegated actor/policy.
2. **Migration readiness:** missing `alembic/env.py`; current revision uses `create_all()` and no-op downgrade. Need a safe additive migration and baseline plan before adding required case/timeline/idempotency schema.
3. **Outage contract:** FRD/TRD disagree on reference timing; simulator has no real ACK/retry/reconciliation. Need product/ops decision before truthful customer copy/task semantics.
4. **Dedupe rule:** exact chat replay works, but separate request keys/conversations can create duplicate cases; no transaction ID in target message. Need minimum information and matching policy.
5. **Requirement and lifecycle vocabulary:** signed FRD v1.0/TRD approval is unavailable; Unit05 remains in progress; API status constants differ from FRD. Approve working baseline and finish or explicitly sequence Unit05 verification.

Audit durability/retention is an additional blocker for claiming FR-CASE-004 complete, even if local create works.

## 6. Review boundary

This plan does not implement or authorize changes to app source, migration files, RBAC, policy, assurance, dependencies, configuration, `.env`, database data, CRM or banking systems. No tests or migrations were run while preparing it. Product/security/ops approvals listed above are still pending.
