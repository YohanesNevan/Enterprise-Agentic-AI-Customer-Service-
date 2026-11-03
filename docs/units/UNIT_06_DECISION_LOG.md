# Unit 06 — Pre-implementation Decision Log

**Review status:** open; no decision in this document is an approval to implement.  
**Created:** 2026-10-20  
**Scope:** reconcile `UNIT_06_SPEC.md`, `UNIT_06_IMPLEMENTATION_PLAN.md`, current source, current project audit, FRD/TRD working copies, architecture notes, and build plan. No app, policy, schema, database, or integration changes were made.

### Status meanings

- **UNRESOLVED** — no authorized decision/evidence settles the matter.
- **Recommendation** — proposed direction only; it is not the selected decision.
- **Decision authority** — developer means an implementation detail within approved contracts; product/security/mentor means approval is needed before changing customer/business/security behavior.

## 1. Current evidence and corrections to prior documents

Source code was checked again for this review. Where historical audit text conflicts with source, this log records the source behavior and preserves the conflict for follow-up.

| Topic | Current source evidence | Document reconciliation |
|---|---|---|
| Chat principal and idempotency | `app/modules/routes_a.py`, `chat_message()` validates customer chat, checks supplied conversation against principal tenant/customer, hashes the idempotency header, fingerprints request body, persists a `CustomerRequestRow` as PROCESSING, then executes conversation/orchestration and stores response as COMPLETE. A same-key changed body conflicts; a completed request replays. Case creation is not linked atomically to this ledger. | Claims in the spec/plan about the existing chat boundary are supported. The PROCESSING ledger and case DB transaction are separate commits, so exact key replay helps but does not alone solve recovery after a case commit and before the response ledger completes. |
| Exact complaint intent | `app/modules/intent.py`, `_score()` and `classify()`: the target phrase hits `INFO_ACCOUNT_BALANCE` (`saldo`), `INFO_TRANSACTION_HISTORY` (`transaksi`), and `CMP_SERVICE_FAILURE` (`gagal`) at 0.70 each. Stable sort retains taxonomy insertion order; near-tie selects `CLARIFY`. The target phrase does not hit `CMP_TRANSACTION_DISPUTE`. | Verified statically from current rules. This is not a measured runtime/test result. No case can be justified from the current classification without clarification or an approved, tested deterministic refinement. |
| Complaint orchestration | `app/modules/orchestrator.py`, `run_turn()` and `_need_tool()`: clarification returns before action; no complaint case-create path is mapped. `_exec_tool()` has a generic `{ok: true}` fallback, which cannot prove a case was created. | Spec/plan correctly say chat complaint-to-case is absent. A future case path must call a real backend case service and use its committed result; the generic executor must not be used as evidence. |
| Customer case-create authorization | `app/core/rbac.py`, `ROLE_PERMS`: customer has `case.read` but not `case.create`. `app/main.py`, `create_case()` requires `case.create`; its customer-id binding branch is behind this permission. `app/modules/tool_gateway.py`, `REGISTRY`, lists `create_case` at AL1; `permitted_set()` filters by assurance, and `evaluate()` enforces tool registry/prohibited/AL but does not perform role permission, tenant, ownership, or business-argument validation itself. `orchestrator.run_turn()` receives no verified customer principal and defaults actor to `AI_AGENT`. | Authorization blocker is current, not merely historical. The registry is not a grant of RBAC permission. No role/assurance/delegation change is approved here. |
| Case read routes | `routes_a.py`, `case_lookup()` for `GET /v1/cases/{cid}` filters tenant and, for customer role, compares `customer_id`, returning 404 on mismatch. Its JSON includes both internal `status` and `customer_visible_status`. `status_page()` for `GET /v1/status/{reference}` fetches by reference first, then returns only `UNKNOWN` on tenant/customer mismatch, otherwise customer-visible status. It has no AL2 check in current handler. | Existing protected case detail has an ownership predicate but leaks internal status field to customer callers. Public/reference lookup avoids returning the mismatched row’s status, but query is not scoped at fetch and the documented AL2 detail rule in `context/specs/02-authenticated-principal.md` is not enforced by this route. Do not describe either route as a complete approved customer case contract. |
| Persistence and case schema | `app/modules/models.py`, `CaseRow`, has case/tenant/customer/origin conversation/reference/category/subcategory/severity/status/customer projection/queue/logged time/reopen/SLA version. Customer is nullable. It lacks description, source channel, risk, created-by, owner ID and case timeline/relationship/idempotency entities described in TRD. `SlaRecordRow` and `CrmOutboxRow` exist. | The case field-gap statements in spec/plan are broadly supported. Field-level migration design still depends on approved baseline and legacy-row backfill. |
| Case transaction and audit | `app/modules/store.py`, `create_case_db()` adds CaseRow, SlaRecordRow and CrmOutboxRow then commits. It calls `audit_svc.emit()` after commit and returns the local reference/status; no actual reload is performed. `app/core/audit.py` stores records and hash heads in process memory. | PostgreSQL case persistence and outbox enqueue are distinct from durable audit. A later audit exception cannot roll back the already committed case. No durable append-only case timeline model is present in `models.py`. |
| CRM outbox state | `app/modules/outbox.py`, `drain()`: if `CRM_AVAILABLE` is true, increments attempts and sets local row state `SENT`/sent_at; otherwise increments attempts, sets `last_error`, leaves state PENDING. `app/worker_outbox.py` polls internal drain every 15 seconds. No CRM adapter call, response payload, ACK ID, retry schedule, maximum attempts, dead-letter state, or reconciliation task appears in this path. | **Four distinct facts:** (1) case persistence: `CaseRow` is committed in PostgreSQL by `create_case_db()`; (2) outbox status: local `CrmOutboxRow.state` is PENDING or SENT; (3) simulator ACK: no explicit ACK contract/record exists—the boolean only selects a branch; (4) external CRM acceptance: not established by this code. Never equate SENT with ACK or external CRM receipt. |
| Handoff relation | `app/modules/orchestrator.py`, `_queue_handoff()`, can create/reuse `HandoffRow` using queue service; the record currently has `package_complete=False`. | This is a conversation handoff queue, not evidence of a CRM-specific reconciliation task, operator ownership, or CRM retry resolution. |
| Migration setup | `alembic.ini` sets `script_location=alembic`; `alembic/versions/0001_init_b.py` calls `Base.metadata.create_all()` and has no-op downgrade; `alembic/env.py` is absent. App startup also calls `Base.metadata.create_all()` as reported in current audit. | The migration readiness blocker is supported. This review did not invoke Alembic or inspect/alter database state. A migration procedure, existing schema baseline, and safe deployment/backfill plan remain undecided. |
| Frontend scope | `web-workspace/src/App.jsx`, `CustomerChat()`, posts `/v1/chat/messages` with an idempotency key and reloads conversation history. It does not render a case response. `/customer/requests` and `/customer/requests/new` are route-map placeholders. `web-workspace/package.json` declares build/dev/preview only, no frontend test script. | Spec/plan description is supported. Full form/tracking UI belongs to Unit 07 in `context/specs/00-build-plan.md`; minimum case card/detail scope for Unit06 needs a sequencing/scope decision. |
| FRD/TRD authority | Repository has FRD and TRD PDF copies described in the audit as v0.9 drafts; TRD references an approved FRD v1.0, but no signed FRD v1.0 or TRD approval evidence is established by available project docs. `context/specs/00-build-plan.md` says canonical FRD v1.0 remains unresolved. | The unsigned baseline is a live governance blocker. Requirement statements cited in the Unit06 spec are working references, not confirmed approved acceptance criteria. |
| Unit05 gate | `context/specs/00-build-plan.md` says Unit05 is IN PROGRESS and requires browser/accessibility verification before marking complete; `context/progress-tracker.md` says next implementation unit after those checks is Unit06. | The gate is explicit in project plan. Whether Unit06 implementation may begin concurrently is not approved in the documents reviewed. No browser/accessibility verification was conducted in this review. |

### FRD/TRD working requirements in scope

- **FR-CASE-001 / BR-CASE-09, FRD v0.9 p.63:** complaint case via tool layer, service-assigned reference/status/queue, avoid duplicate open matching case, outage outbox and human task, AI HIGH/CRITICAL not finally confirmed without human confirmation.
- **FR-CASE-002…005, FRD v0.9 pp.64–65:** classification/ownership, append-only case timeline, conversation-case links and duplicate/related-case relations.
- **FR-CASE-006, p.65:** no AI financial recovery execution.
- **FR-CASE-010, p.67:** customer status projection and suppression of internal status/queue/agent details.
- **TRD v0.9 §6.3.6–6.3.9, pp.33–34:** case/timeline/outbox data design; **§8.6–8.9, around pp.45–46:** idempotency, retry/degraded CRM behavior.
- **Important conflict:** FRD p.63 describes reference following recovery; TRD §8.9 describes issuing a local reference. Exact external page text remains subject to signed/canonical approval.

## 2. Decision register

All decisions below remain **UNRESOLVED**. Recommendations are not official project decisions.

### D-01 — Authority and assurance for case creation from customer chat — **UNRESOLVED / P0**

- **Current condition:** Customer role has `case.read` but no `case.create`; create tool says AL1; current chat orchestrator lacks the signed principal context needed to prove delegated subject/tenant and assurance. Existing gateway does not replace RBAC/ownership validation.
- **Options and consequences:**
  1. Grant customer `case.create` at approved assurance: simple route authorization, but expands customer write permission and conflicts with current role map until explicitly approved.
  2. Add a narrowly scoped server-side intake capability/service actor: keeps customer role least-privileged, but creates confused-deputy risk unless original principal, tenant, conversation, on-behalf-of, policy decision and case subject are bound and audited.
  3. Require customer step-up/confirmation before intake: uses existing assurance concept, but friction and current OTP challenge/delivery is only simulated/in-memory.
  4. Require human agent to create: safe boundary, but no immediate autonomous customer case registration.
- **Recommendation:** do not change permissions or lower AL. After policy owner approval, pass verified principal context into a dedicated backend intake service, validate owner/tenant/conversation, and authorize through an explicit scoped policy capability. Preserve customer as case owner and actor provenance. If approved rule requires AL1, return the established step-up result and do not create at AL0.
- **Decision authority:** product/security/mentor approval required for actor/delegation semantics and required assurance; developer may implement only after approval.
- **Dependencies:** Must resolve before D stage and any customer create API; precedes B/C contract finalization and E2E acceptance.

### D-02 — Migration readiness and schema rollout — **UNRESOLVED / P0**

- **Current condition:** Alembic environment missing; initial revision is `create_all()`; downgrade no-op; app startup also creates metadata. No migration was run and current DB schema was not inspected.
- **Options and consequences:**
  1. Repair Alembic environment/baseline and add additive revision: standard versioned path, but requires a verified baseline and clean/disposable DB rehearsal.
  2. Keep startup `create_all()` and mutate model: fast for new local DBs, does not upgrade existing deployments or safely add constraints/backfills.
  3. Defer schema changes and fit requirements into existing columns: avoids migration risk, but cannot satisfy description/provenance/timeline/durable idempotency requirements.
- **Recommendation:** use an additive versioned migration only after a migration owner confirms target DB baseline and deployment/rollback strategy; test clean and representative prior schema in disposable databases. Never rely on `create_all()` as migration evidence. Define nullable/backfill treatment for existing cases before NOT NULL constraints.
- **Decision authority:** migration mechanics can be technical; baseline/deployment window and treatment of existing data require architecture/DB owner approval.
- **Dependencies:** before B implementation; prerequisite for C, E timeline/outbox additions, F/G API contract.

### D-03 — Local reference/status while CRM is unavailable — **UNRESOLVED / P0**

- **Current condition:** PostgreSQL case and local reference are committed before outbox drain. `crm_pending` is returned based on process-local flag. There is no external CRM acceptance evidence.
- **Options and consequences:**
  1. Return local reference after PostgreSQL commit, show local case received and CRM sync pending: supports customer tracking during outage, but reference may not resolve in external CRM.
  2. Return provisional receipt and withhold final reference until simulator acceptance: aligns FRD wording, but requires a provisional tracking identifier and explicit local/external states.
  3. Refuse case creation during CRM outage: simple customer semantics, but contradicts local durable outbox intent and risks losing complaint.
- **Recommendation:** prefer treating local PostgreSQL case as authoritative for the EAICS customer tracking API once committed, and return the local reference with a separate `crm_delivery_state=PENDING` only if product approves that authority. Never describe an outbox state as CRM acceptance. If FRD’s “reference follows” is authoritative, define provisional ID and local status contract first.
- **Decision authority:** product/mentor approval required because it changes customer promise and source-of-truth semantics.
- **Dependencies:** settle in A/contract before C/F/G response wording; D-04 simulator ACK semantics also required before claiming delivery status.

### D-04 — Simulator ACK, retry and CRM reconciliation task — **UNRESOLVED / P0**

- **Current condition:** boolean `CRM_AVAILABLE` controls local drain branch; true marks `SENT` without adapter ACK. No retry backoff/cap/FAILED/dead letter/task is implemented. Handoff queue is not CRM reconciliation.
- **Options and consequences:**
  1. A simulator adapter returns explicit accepted/retryable/permanent result plus operation ID; persist ACK and bounded retries; after exhaustion write one reconciliation task. Accurate and testable, requires state/schema/worker and operations queue contract.
  2. Preserve local-only simulator: define boolean as test fixture only and rename customer-facing state to `SIMULATED_ACCEPTED`; no external delivery claim, but it does not fulfill production adapter requirements.
  3. Reuse `HandoffRow`: smaller change, but conversation handoff may not assign CRM repair to right staff or provide reconciliation SLA.
- **Recommendation:** define separate states for local case persistence, outbox delivery attempts, simulator ACK, and external CRM receipt. A success transition should require an explicit adapter response; local boolean can only control a test adapter result. Persist idempotent retry schedule and a unique reconciliation task after bounded failures. Do not treat a generic handoff as reconciliation without an approved queue/SLA contract.
- **Decision authority:** product/ops must approve ACK meaning, retry cap, task owner/queue/SLA and customer message; implementation details thereafter are technical.
- **Dependencies:** D-03; schema decision D-02; must pass before Unit06 is considered complete against FR-CASE-001, though can be developed parallel to D/F after shared contract.

### D-05 — Duplicate matching without transaction ID — **UNRESOLVED / P1**

- **Current condition:** chat ledger protects same key+body; case service does not dedupe; no incident key is stored. The scenario supplies no transaction reference.
- **Options and consequences:**
  1. Dedupe only the same durable chat request: safe and explainable, but new keys can create separate cases for same incident.
  2. Require transaction reference and match exact normalized reference + tenant/customer/category + open status: lower false-merge risk, but requires more customer input and policy on reference data.
  3. Match same conversation + category: simple, but may merge multiple different failed transactions in one conversation.
  4. Fuzzy matching on text/category/time: may reduce duplicates but risks merging unrelated incidents and is hard to audit.
- **Recommendation:** in initial walking skeleton, guarantee durable idempotency for the same request. For cross-request reuse, auto-link only on an exact validated incident key; without one, ask for minimum reference/clarification or keep separate complaint according to the approved intake rule. Avoid fuzzy matching.
- **Decision authority:** product/mentor approval required for minimum fields and what counts as “open matching case”; unique key/constraint mechanics are technical.
- **Dependencies:** choose before C duplicate-service and schema constraints; tests in H.

### D-06 — Customer-visible status vocabulary and API exposure — **UNRESOLVED / P1**

- **Current condition:** `CustomerVisibleStatus` values are `RECEIVED`, `BEING_INVESTIGATED`, `WAITING_FOR_YOU`, `OUTCOME_READY`, `CLOSED`, `REOPENED`. FRD concepts say Received, Under review, Waiting for customer, Outcome ready, Closed, Reopened. `GET /v1/cases/{cid}` exposes internal `status` alongside customer status. `GET /v1/status/{reference}` returns only visible status on matching owner/tenant, but lacks documented AL2 check.
- **Options and consequences:**
  1. Keep existing API enums and define approved Indonesian labels: minimal migration, but semantic mismatch to FRD labels remains.
  2. Adopt FRD-aligned API enum values with explicit compatibility/versioning: closest to requirements, but may break existing clients/rows.
  3. Keep persisted enum and build a new versioned customer projection: avoids internal state leakage while preserving staff contracts, adds API mapping.
- **Recommendation:** keep internal status private; expose a dedicated, allowlisted customer projection with explicit mapping and tests. Obtain product/API confirmation whether existing enum values are accepted labels or whether new public values/versioning are required. Resolve AL2 rule for reference detail instead of silently relying on current route.
- **Decision authority:** product/API owner approves customer wording and assurance disclosure; implementation map is technical once approved.
- **Dependencies:** before F response schema and G labels; D-01 assurance and A baseline also apply.

### D-07 — Durable audit and append-only case timeline — **UNRESOLVED / P1**

- **Current condition:** global `audit.emit()` is in-memory and invoked after case commit; no `case_timeline_entry` SQLAlchemy model/table was found. FRD/TRD require case timeline and durable audit.
- **Options and consequences:**
  1. Add case timeline transactionally with case/outbox/idempotency and case lifecycle changes; keep global audit limitation explicit. Narrow, supports FR-CASE timeline but creates two audit surfaces.
  2. Implement durable global audit within Unit06: one durable source of truth, but broad cross-cutting impact and migration/test scope.
  3. Defer persistence to later audit unit: reduces current scope, but Unit06 cannot claim FR-CASE-004/audit acceptance complete.
- **Recommendation:** add append-only case timeline event writes atomically with case changes and outbox state changes, with actor/provenance/correlation and customer visibility flag; do not put raw credentials or unnecessary customer text in event payload. Leave global audit durability as explicit blocker/residual requirement unless architecture owner assigns it here.
- **Decision authority:** architecture/product/compliance approves scope, retained content and retention; developer can implement schema/service invariants afterward.
- **Dependencies:** retention/privacy decision before B schema; write contract before C/E; acceptance in H.

### D-08 — Chat-to-case idempotency contract — **UNRESOLVED / P1**

- **Current condition:** `CustomerRequestRow` state/response is durable (for configured DB), but request ledger and case service commit separately. Tool gateway dedupe is process memory keyed from conversation/tool/args and does not persist tool version or operation state. `CreateCaseIn.idempotency_key` is unused by DB store.
- **Options and consequences:**
  1. Link case ID/result to existing customer request ledger and coordinate atomic commit: fewer tables but requires restructuring current chat transaction and message commits.
  2. Add durable case-create operation mapping with unique scoped hash; keep chat ledger as replay API and atomically persist operation+case+SLA+outbox+timeline: robust boundary, adds model/migration.
  3. Use current in-memory gateway cache: smallest but unsafe across process restart/concurrency.
- **Recommendation:** use server-derived request identity (never raw header) and durable unique operation mapping in the same DB transaction as case/outbox/timeline; on a post-commit/pre-response retry, resolve the prior case; on ambiguous PROCESSING state, do not create a second case.
- **Decision authority:** architecture owner decides request-key retention/expiry and correlation with TRD canonical tool key; uniqueness/transaction details are technical.
- **Dependencies:** define with D-05 before B/C; acceptance in H.

### D-09 — Official FRD/TRD baseline — **UNRESOLVED / P0**

- **Current condition:** only draft v0.9 PDFs and documents reflecting them are confirmed in repository. TRD references signed FRD v1.0, but that signed copy and TRD approval are not established. Build plan itself records this as open.
- **Options and consequences:**
  1. Approve v0.9 as temporary implementation baseline with a documented deviation process: enables work, risks rework.
  2. Wait for signed canonical FRD v1.0 and approved TRD: highest traceability, delays code.
  3. Implement only clearly invariant infrastructure while holding customer behavior/status/outage decisions: may reduce idle time, but schema is requirement-dependent and migration is expensive to revise.
- **Recommendation:** request mentor/product confirmation of a working baseline and record exact version before implementation. Avoid irreversible/business-facing schema or status decisions while baseline unresolved.
- **Decision authority:** product/mentor approval required.
- **Dependencies:** before A contract closure and B–G scope lock.

### D-10 — Unit05 gate and Unit06 overlap — **UNRESOLVED / P1**

- **Current condition:** build plan and progress tracker say Unit05 remains IN PROGRESS until browser/accessibility verification, with Unit06 next after those checks. Unit05’s technical conversation API has tests/build evidence historically, but this review did not rerun or perform browser/accessibility checks.
- **Options and consequences:**
  1. Finish Unit05 verification first: respects project sequence and gives stable UI base, delays Unit06 coding.
  2. Authorize parallel Unit06 backend work while Unit05 browser checks run: improves schedule, but risks touching shared `App.jsx`/chat contract and conflicts with build-plan gate.
  3. Allow documentation/DB design only now; defer all code until Unit05 gate: low risk, no implementation overlap.
- **Recommendation:** keep Unit06 in decision/specification stage; complete Unit05 browser/accessibility gate before app-code work unless mentor explicitly approves parallel backend work. Avoid concurrent customer UI edits to `App.jsx`.
- **Decision authority:** mentor/project owner approves sequencing exception; browser/a11y execution is a technical verification task.
- **Dependencies:** before any Unit06 code; frontend stage G additionally depends on F and approved Unit06 scope.

## 3. Review of A0–H implementation order

The implementation plan is directionally sound in keeping A as a no-code contract gate and splitting schema, service, orchestration, API, UI, and tests. Its ordering should be tightened as follows:

1. **A0 must include D-01 through D-10**, with explicit decision owners and approved baseline. No role/policy/assurance or customer-facing behavior changes while any P0 remains UNRESOLVED.
2. **B cannot simply start after a verbal “schema decision”:** first verify/repair migration runner and inspect schema baseline in an approved disposable environment. This remains a gate even if app code is parallelized.
3. **C must not precede authorization contract in A.** Service-only tests can be designed, but its accepted actor fields, audit provenance and idempotency key are determined by D-01/D-07/D-08.
4. **D and F need a clearer split:** add complaint intent/clarification and policy denial tests before create path; only wire persistent create after C. Customer read projection in F can be developed after C and D-06; the existing `/v1/cases/{cid}` is not a compliant substitute because it returns internal `status`.
5. **E may run in parallel with F after B and decisions D-03/D-04/D-07**, but it must be complete before claiming CRM outage recovery/human task acceptance or closing FR-CASE-001. It need not block a narrowly stated local-PostgreSQL-only proof if customer copy says CRM delivery is unverified/pending and that behavior is approved.
6. **D2/F2 replay test needs a crash-window test:** persist case successfully, simulate failure before request ledger COMPLETE, retry same key and prove lookup/replay rather than duplicate. Existing customer ledger returns conflict for FAILED/PROCESSING and does not by itself reconcile this window.
7. **G is a scope gate:** build plan places full customer complaints/tracking UI in Unit07. Unit06 can add a minimal chat case card only after explicit scope approval; list/detail UI should either be assigned to Unit07 or approved as a minimal Unit06 dependency. Do not silently expand Unit06.
8. **H is the final completion gate, not merely after all code:** include migration rehearsal, security tests, browser/accessibility verification, Unit05 regression, and the E outbox requirements if Unit06 claims the full FRD case-outage flow. Historical test results are not evidence for current changes.

### Recommended gated sequence

**A0 decisions → Unit05 verification or approved sequencing exception → migration runner/baseline check → B additive schema → C durable case operation → D intent/authorization flow → F safe customer API → D2/F2 atomic/replay integration → E outbox/ACK/reconciliation (parallel after schema, mandatory before full FR-CASE-001 closure) → approved G UI scope → H full verification.**

For the smallest proof, use synthetic data and deterministic rules; no Gemini live call, CRM external call, or banking operation is needed. A local case commit, outbox PENDING, simulator acceptance and external CRM receipt must remain separate observable states.

## 4. Outstanding approvals summary

| Priority | Items that still need approval |
|---|---|
| P0 | D-01 creation actor/assurance; D-02 migration baseline/deployment ownership; D-03 outage reference semantics; D-04 simulator ACK/retry/reconciliation operations; D-09 official FRD/TRD baseline. |
| P1 | D-05 duplicate rule/minimum fields; D-06 public status and assurance; D-07 timeline/audit retention scope; D-08 idempotency retention/operation contract; D-10 Unit05 sequencing and Unit06 UI boundary. |

No approval is inferred from this review or from prior audit/spec recommendations.

## 5. Review boundary

This review created only this Markdown decision log. No source code, permission, policy, assurance rule, schema/migration, dependency, configuration, `.env`, or database data was changed. No migration, test, Gemini, CRM, or banking request was run.

## Current-session approval status (2026-10-20)

The requester authorized a Unit 06 readiness re-audit and reported that they manually tested Unit 05 and consider it okay to continue. This is requester-reported progress only; it contains no explicit answer to D-01–D-10 and no named approver/date or attached Unit 05 evidence. It authorizes the readiness stage, not application implementation or a sequencing exception. **D-01 through D-10 remain UNRESOLVED; no approval checklist fields were filled or inferred.** See the current-session addendum in `UNIT_06_READINESS_AUDIT.md` for fresh source findings, the pure-function intent probe, and the gated implementation order.
