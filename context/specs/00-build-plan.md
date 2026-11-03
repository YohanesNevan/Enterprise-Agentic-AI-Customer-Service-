# EAICS Improvement Build Plan

## Planning basis

**Unit 02 status: COMPLETE for the API authentication/authorization boundary.** See `context/specs/02-authenticated-principal.md`; backend verification passed with 28 tests. External issuer/provisioning, durable audit, staff assignment-level authorization, and tenant-schema consistency remain explicit integration or follow-up limitations.

The plan preserves the existing FastAPI/SQLAlchemy modular monolith and React/Vite SPA. It is based on the source-level audit and repository README, which describes later milestones as deferred. FRD-EAICS-001 and TRD-EAICS-001 remain authoritative; their canonical revision and detailed acceptance criteria must be confirmed before each unit specification is activated. This plan does not claim the entire 235-page PDF requirements set has been traced.

Each unit should get a focused `NN-*.md` active specification before implementation. Units can be reordered only with an architecture decision recorded here and in `context/progress-tracker.md`.

## Unit 01 — Requirements traceability and security decisions — COMPLETE (source audit)

- **Problem:** FRD/TRD versions conflict in metadata; route, role, and workflow implementation coverage is not traced requirement by requirement.
- **Outcome:** FRD/TRD revision-status map, role/action/data matrix, API/workflow traceability matrix, and resolved or explicitly open security decisions.
- **Scope:** Review FRD/TRD sections for roles, authentication, tenant/customer ownership, customer workflows, channel scope, RAG, integrations, NFRs, and deployment phases; inventory current routes and tests against them.
- **Dependencies:** None; audit report.
- **Boundary:** Product requirements and API/security contract.
- **Acceptance criteria:** Every in-scope requirement has an ID, source location, implementation status/evidence, and planned unit; canonical version and identity/ownership assumptions are explicit; conflicts are not silently decided.
- **Verification:** Document review against the actual PDFs and route inventory.
- **Risks/open decisions:** Requirement PDFs may be drafts; material security choices require product/mentor approval.

Completed artifact: `context/requirements-traceability.md`. The supplied PDFs establish the implementation direction but contain no signed approval record; canonical FRD v1.0 remains unresolved.

## Unit 02 — Authenticated principal and backend authorization

- **Problem:** `X-Role` and actor headers are caller-controlled and default to a privileged staff identity; customer/tenant ownership is not established.
- **Outcome:** Implement the document-specified identity boundary: human JWT access (15-minute TTL) and rotating refresh (8-hour TTL) with revocation; short-lived signed, scoped service tokens; customer AL0–AL3 remains separate session assurance; enforce role, permission, tenant, and resource ownership with uniform disclosure behavior.
- **Scope:** Auth dependency, route inventory/permission map, actor attribution from verified principal only, tenant-aware data access, customer ownership, FRD role separation (including `knowledge_manager`), removal of unsafe header defaults, audit hooks, and authorization tests for spoofing/IDOR/role matrix. A UI role selector must never grant identity.
- **Dependencies:** Unit 01 decisions.
- **Boundary:** API middleware/dependencies, core RBAC, data access, tests.
- **Acceptance criteria:** Unauthenticated callers cannot act as a role; human/service credentials are validated and expire/revoke as specified; each route has its approved permission; customer and tenant queries are scoped; actor identity cannot be forged; system administrator cannot read unmasked conversation/PII; management is aggregate-only; self-approval and audit invariants remain enforced.
- **Verification:** Automated API tests for every route class × role, spoofed headers, ownership/tenant IDOR, token expiry/revocation and separation of duties; run existing regression suite.
- **Risks/open decisions:** TRD prescribes JWT/Redis but signed contract §16 is absent. Confirm claim names/key handling and exact uniform unauthorized/not-found mapping while preserving security invariants. Current tables do not all carry tenant IDs; scope a compatible migration.

## Unit 03 — Role navigation and application route shell

- **Problem:** One dashboard-first SPA and client role selector imply access without authenticated route structure.
- **Outcome:** URL-based role-aware shells with customer portal entry and distinct internal navigation; clear forbidden/unknown-route handling.
- **Scope:** Introduce routing only if approved by Unit 01 and use Unit 02 principal; shared layout primitives, responsive navigation, page titles, and route guards for UX.
- **Dependencies:** Units 01–02; UI context. This is the first UI-visible unit after the security foundation and must begin next, rather than waiting for all backend workflows to finish.
- **Boundary:** React application shell and API client.
- **Acceptance criteria:** No role selector grants identity; routes survive refresh/deep link; backend remains authoritative; customer shell is distinct from staff shell; keyboard and mobile navigation work.
- **Verification:** Browser checks at mobile/tablet/desktop plus route/accessibility checks.
- **Risks/open decisions:** Existing API/header demo contract may have external consumers; preserve compatibility only if required.

## Unit 04 — Customer conversation and history API

Detailed specification: `context/specs/04-customer-conversation-history.md` (implemented; production identity remains gated).

- **Problem:** Existing chat ingestion lacked a portal-ready owned history contract, idempotency, complete tenant scoping, and a reliable returned conversation identifier.
- **Outcome:** Authenticated customer conversation create/send/history endpoints scoped to the principal, plus a safe opt-in local login and connected customer chat/history journey.
- **Scope:** API/service contracts, message persistence and ownership, channel policy, validation, idempotency, errors; fixed-account development-only issuer and customer UI integration. No production identity provider.
- **Dependencies:** Units 01-02. The backend defines the `customer` role and signed test credentials. Local portal login is available only through the opt-in fixed-account development issuer; production access remains gated on trusted issuer/account provisioning and subject-to-customer mapping. No legacy uniqueness constraint is added before a data audit and reviewed migration.
- **Boundary:** Conversation API/domain and database.
- **Acceptance criteria:** Customer sees only own conversations; sends and retrieves persisted messages; scoped retries do not duplicate orchestration; local login is opt-in, loopback-only and rejected outside development; AI/handoff/citation fields distinguish provenance. Attachments remain excluded.
- **Verification:** API tests for local credential issuance/rejection, ownership, persistence, handoff, validation, tenant isolation and idempotency; frontend production build.
- **Risks/open decisions:** Production issuer/account mapping, migration lifecycle, customer read-audit policy and supported simulators remain unresolved.

## Unit 05 — Customer portal conversation UI

Status: IN PROGRESS. The first information-conversation slice is implemented; full Unit 05 still requires browser and accessibility verification.

- **Problem:** Unit 04 delivered the basic API-connected composer and history, but the first supported information question can be stuck in clarification, grounded answers can fail validation, and handoff language can claim a connection without a queued handoff.
- **Outcome:** Complete the first traceable information conversation slice with deterministic greeting, published knowledge answer, persisted citation, truthful queued handoff state, and customer-visible source/handoff status.
- **Scope:** Fix supported informational intent mapping; verify article and version eligibility; ground answer against retrieved passage; persist citation provenance; create queue records for mandatory handoff and report queue/acceptance state truthfully; render sources in history. This does not complete browser E2E, complaint/case workflow, full handoff context package, vector RAG, or provider integration.
- **Dependencies:** Units 03–04.
- **Boundary:** React customer portal, deterministic intent/orchestration, knowledge retrieval, conversation history, and handoff queue.
- **Acceptance criteria:** Supported fee inquiry returns a sourced, grounded persisted answer; greeting does not hand off; unknown intent remains mandatory handoff and has a persisted queue row; customer copy never claims agent acceptance without accepted state; history displays persisted citations; no unsupported or expired/draft version is cited.
- **Verification:** API and service tests for intent/retrieval/grounding/persistence/queue state, full backend suite, frontend production build. Browser journey and accessibility checks remain required before marking the entire Unit 05 complete.
- **Risks/open decisions:** Browser E2E remains pending; complaint/case, full handoff package, vector retrieval and provider integration are separate dependencies. FRD v0.9 and TRD v0.9 remain drafts, and signed FRD v1.0 / integration approval is unavailable.
## Unit 06 — Complaint and ticket ownership APIs

- **Problem:** Internal create/lookup routes exist, but customer submission, list, detail, evidence, and feedback ownership contract is incomplete.
- **Outcome:** Customer-scoped complaint/ticket submission and tracking APIs with approved status visibility and durable feedback/evidence references.
- **Scope:** API schemas, service ownership checks, validation, status projection, audit events; only implement attachments if a storage contract is approved.
- **Dependencies:** Units 01–02; conversation identity as required by FRD.
- **Boundary:** Cases/tickets/evidence/feedback APIs and persistence.
- **Acceptance criteria:** Customer can create and list only own records; status hides internal data; actions validate; success reflects persisted outcome; feedback links to eligible interaction.
- **Verification:** API authorization and workflow tests including cross-customer negative cases.
- **Risks/open decisions:** Status disclosure, required fields, evidence retention, and feedback timing require exact FRD rules.

## Unit 07 — Customer complaints and tracking UI

- **Problem:** No customer complaint submission or tracking journey exists.
- **Outcome:** Portal forms and owned case/ticket list/detail with understandable statuses, evidence request response where supported, and feedback.
- **Scope:** Complaint form, validation, confirmation/reference, filters/details, status timeline, feedback; use Unit 06 APIs.
- **Dependencies:** Units 03 and 06.
- **Boundary:** React portal and case/ticket APIs.
- **Acceptance criteria:** Forms persist; list/detail show only customer-visible fields; status and errors are clear; responsive and keyboard operable; unsupported attachment action is explained/disabled.
- **Verification:** End-to-end customer workflow and responsive/accessibility review.
- **Risks/open decisions:** Exact customer-visible status mappings and upload support.

Authorized incremental slice: `context/specs/07-customer-request-tracking-account.md` covers customer request submission as an authenticated service conversation, owned conversation tracking, and read-only local account display. It does not create cases/tickets or complete Unit 06/07; customer case-creation permission and the Unit 06 product/security decisions remain unchanged.

## Unit 08 — Agent workspace read model and queue

- **Problem:** Queue APIs exist, but B conversation read-model comments identify a stub and UI exposes dense data/raw JSON.
- **Outcome:** Agent queue and conversation workbench with customer context, timeline, handoff reason, cases/tickets, SLA, verified facts, AI summary/suggestions, citations, and internal notes as allowed.
- **Scope:** Complete read model and ownership/role filters; operational queue filters/actions; separate verified/generated data; agent UI.
- **Dependencies:** Units 01–02; existing queue and conversation APIs; Unit 03 shell.
- **Boundary:** Queue/conversation API and internal React workspace.
- **Acceptance criteria:** Agent can accept and act on authorized work; context is coherent and provenance clear; SLA and handoff history visible; no customer/internal data leakage; action state persists and reports errors.
- **Verification:** API role tests and agent browser workflow.
- **Risks/open decisions:** Conversation state transitions, note visibility, assignment rules, and summary generation criteria need traceability.

## Unit 09 — Supervisor and complaint officer operations

- **Problem:** Shared console lacks clear escalation, SLA risk, assignment, review, and complaint oversight workspaces.
- **Outcome:** Authorized views/actions for escalation queues, approaching/breached SLA, reassignment, case review/resolution, history, and approvals as requirements specify.
- **Scope:** Server-side query/action permission contracts and focused supervisor/officer screens.
- **Dependencies:** Units 01–03, 06, and 08.
- **Boundary:** Case/SLA/escalation/approval APIs and internal UI.
- **Acceptance criteria:** Actions are server-authorized; roles see only allowed queues/data; all decisions are audited; self-approval remains impossible; deadlines use the defined timezone/calendar.
- **Verification:** Role/action tests and supervisor/officer workflow review.
- **Risks/open decisions:** Role overlap and SLA escalation rules must match FRD.

## Unit 10 — Approval workflow UI and durable execution boundary

- **Problem:** Approval APIs exist but are mixed into the console; approved action execution and lifecycle require verification.
- **Outcome:** Review queue shows immutable arguments/hash, requester, risk, expiry, and decision history; execution occurs only through authorized verified flow.
- **Scope:** API lifecycle audit/fixes, UI request/detail/decision, argument hash comparison, expiry and audit display.
- **Dependencies:** Units 01–02 and 09.
- **Boundary:** Approval service, tool gateway, supervisor UI.
- **Acceptance criteria:** Requester cannot approve own request; unauthorized roles cannot decide; changed arguments fail; granted state does not imply execution unless actual execution succeeds; decisions are audited.
- **Verification:** API security tests and complete approval workflow.
- **Risks/open decisions:** Exact tool risk classes and execution semantics in TRD.

## Unit 11 — Knowledge lifecycle and manager workspace

- **Problem:** Article create/search exists but no complete review/publish/index lifecycle or manager UI; lexical retrieval is not a production RAG pipeline.
- **Outcome:** Requirement-backed knowledge management with versions, review/publication, processing status, retrieval test, and citation provenance; only use approved retrieval architecture.
- **Scope:** Document/article model/API pipeline and manager UI, including truthful processing states.
- **Dependencies:** Units 01–02; decision on storage/vector/provider dependencies.
- **Boundary:** Knowledge API, persistence/indexing/background work, manager UI.
- **Acceptance criteria:** Version/status transitions are enforced; retrieval citations point to actual source/version; publication/indexing claims require success; access is role-scoped; failed processing is visible.
- **Verification:** Ingestion/retrieval tests with citation and permission checks; manager workflow review.
- **Risks/open decisions:** pgvector, file formats, antivirus, embedding model, and human review rules require TRD approval.

Approved implementation slice: `context/specs/11-knowledge-staff-workspace-access.md`. The existing document page is shared by the seven human Staff Workspace roles. They receive `knowledge.read` and `knowledge.document.ingest`; article authoring remains on `knowledge.write` for Knowledge Manager. This slice does not complete the broader knowledge lifecycle or change the lexical retrieval architecture.

## Unit 12 — QA review workspace and evaluation provenance

- **Problem:** QA sample/review/finding APIs exist but no dedicated review workbench and evidence-focused workflow.
- **Outcome:** QA analyst can sample eligible work, score against approved criteria, cite evidence, record findings, and inspect real metrics.
- **Scope:** API contract audit, evaluation provenance, review UI, findings, status and metrics definitions.
- **Dependencies:** Units 01–02 and conversation read model from Unit 08.
- **Boundary:** QA APIs/database and QA UI.
- **Acceptance criteria:** Criteria match FRD; no fabricated score; evidence maps to source conversation; review status is explicit; access is restricted; aggregates define data source/denominator.
- **Verification:** QA workflow and metric derivation checks.
- **Risks/open decisions:** Consent, sampling denominator, reviewer calibration, and evaluation rubric.

## Unit 13 — Management metrics and reporting

- **Problem:** Dashboard exists but can dominate UX and its data definitions/source traceability need to be clear.
- **Outcome:** Management-only overview and reports for actual conversation/case/SLA/handoff/resolution/feedback/AI-handling data where measurable.
- **Scope:** Metric definitions/source endpoints, filters/date windows, empty state, export authorization, compact dashboard UI.
- **Dependencies:** Units 01–02 and relevant persisted workflow units (06, 08–12).
- **Boundary:** Analytics services/APIs and management UI.
- **Acceptance criteria:** Every displayed metric has definition, denominator, time range, and persisted source; no hardcoded live values; role access enforced; export matches filters and permission.
- **Verification:** Metric fixture/aggregation tests and management review.
- **Risks/open decisions:** Required KPI definitions and privacy aggregation thresholds.

## Unit 14 — Administration and audit workspace

- **Problem:** No distinct system administration UI; tool registry and audit actions are not grouped into an authorized administrative experience.
- **Outcome:** Approved role/permission, integration configuration, registry, and audit views with least-privilege actions and secret-safe display.
- **Scope:** Only functions explicitly specified in FRD/TRD; backend management APIs and admin UI separated from service operations.
- **Dependencies:** Units 01–02; integration decisions; Unit 03 shell.
- **Boundary:** Administration APIs/configuration and UI.
- **Acceptance criteria:** Admin actions are server-authorized/audited; secrets never reappear in responses; config changes validate and take effect truthfully; ordinary staff/customer cannot access.
- **Verification:** Role/security tests and configuration workflow.
- **Risks/open decisions:** Whether user provisioning/integration settings are in capstone scope.

## Unit 15 — Durable integrations, storage, and background workers

- **Problem:** Notification/upload/integration paths include stubs or simulators; module-global state and endpoint-triggered workers limit reliability.
- **Outcome:** TRD-approved adapters and durable idempotent jobs for the specific required channels, CRM, notification, storage, and SLA processes.
- **Scope:** Implement only explicitly required providers; retries, failure states, secret configuration, observability, and operations lifecycle.
- **Dependencies:** Units 01–02 and provider decisions; relevant workflows above.
- **Boundary:** Integration adapters, persistence, workers, deployment configuration.
- **Acceptance criteria:** No fake-success response; retries are idempotent; credentials are server-only; operation state is observable; failure/dead-letter handling matches requirements.
- **Verification:** Adapter contract tests and controlled integration verification.
- **Risks/open decisions:** Provider credentials/network access and operational support are external dependencies.

## Unit 16 — Startup, migration, dependency, and observability hardening

- **Problem:** Schema creation runs at import, migration history is minimal, dependencies are unpinned, and readiness/runtime observability need verification.
- **Outcome:** Predictable startup/migration lifecycle, reviewed dependency constraints, and accurate health/readiness/structured operational signals.
- **Scope:** Alembic lifecycle, settings validation, readiness semantics, logging/correlation, deployment profile checks.
- **Dependencies:** Unit 01; coordinate with schema-affecting units before completion.
- **Boundary:** API bootstrap, database migrations, manifests, deployment.
- **Acceptance criteria:** Application startup does not silently mutate schema; migrations upgrade a clean supported DB; readiness reports dependency failures accurately; secrets/settings validate; logs preserve correlation without sensitive data.
- **Verification:** Clean database migration and startup/readiness checks for documented profiles.
- **Risks/open decisions:** Existing local/production databases require compatibility migration plan.

## Unit 17 — End-to-end role, accessibility, and release verification

- **Problem:** No demonstrated end-to-end coverage across customer and staff roles, responsive accessibility, and integration states.
- **Outcome:** Repeatable release verification covering the approved role journeys and core security/business invariants.
- **Scope:** Browser/API journey matrix, keyboard/screen-reader basics, mobile breakpoints, failure modes, and operational smoke checks.
- **Dependencies:** All shipped units; verification is incremental during earlier units.
- **Boundary:** Test suite, CI/release process, application.
- **Acceptance criteria:** Each approved journey passes on supported profile; unauthorized access tests pass; critical business invariants pass; results include reproducible commands and no unverified claims.
- **Verification:** Execute approved CI and release checklist against a clean environment.
- **Risks/open decisions:** Browser tooling, CI platform, and supported browser matrix.

