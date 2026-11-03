# Repository Audit

Audit date: 2026-10-13  
Scope: repository inspection before application changes. No application source was modified for this audit.  
Evidence labels: **Confirmed** means directly visible in checked-in files; **Unverified** means implementation behavior still needs runtime or broader requirement review.

## 1. Executive summary

**Confirmed:** EAICS is a Python/FastAPI modular monolith with SQLAlchemy persistence, a React/Vite single-page workspace, a set of API modules covering conversation, simulated authentication, intent, knowledge, tools, cases, handoff, SLA, QA, approvals, and analytics, plus a small test suite. The backend has meaningful skeleton workflows and several policy controls. The frontend, however, is an internal operations console, not the complete role-based product: it has one navigation, an editable role selector backed by request headers, no customer portal journey, and no route-level navigation or authenticated identity boundary.

Several features present in screens or APIs are explicitly prototype-level: notification returns a fixed stub ID, authentication state includes in-memory challenge/consent data, knowledge retrieval is keyword based, AI orchestration uses deterministic intent and simulated tool results, and the B workspace read model calls itself a stub. The repo contains both FRD and TRD PDFs (FRD v0.9 draft; TRD v0.9 draft, while TRD text calls FRD v1.0 the source of truth); detailed requirement traceability remains a prerequisite to implementation.

No broad refactor is justified yet. Preserve the modular monolith, workflow/business rules, current React/Vite setup, and useful tests; first establish verified authorization and customer data scoping, then build workflows in small, specified units.

## 2. Existing technology stack

| Area | Confirmed implementation |
|---|---|
| API | Python, FastAPI, Pydantic, SQLAlchemy; `requirements.txt` is unpinned and includes `psycopg[binary]`. |
| Database | PostgreSQL configured as default in `app/core/db.py`; SQLite is explicitly selected for tests. `alembic/versions/0001_init_b.py` calls metadata `create_all`; downgrade is intentionally a no-op. Two ignored SQLite files are present locally. |
| Frontend | React 18 and Vite 5, JavaScript/JSX (not TypeScript); only React/ReactDOM runtime dependencies. No UI component library is installed. |
| Deployment | Docker Compose for Postgres/pgvector, Redis, MinIO, Mailpit, API; separate cloud compose and deployment guidance. |
| Tests/tools | pytest, FastAPI TestClient, smoke script, UI contract script. Existing tests cover selected A/B skeleton contracts. |
| Integrations | Simulated core banking/CRM and local tool gateway; `.env.example` selects an LLM stub. No verified external provider integration. |

The local `.env` exists and is excluded by `.gitignore`; its contents were not read or reproduced. No repository `.git` directory was found, so working-tree status and history could not be inspected.

## 3. Current application structure

- `app/main.py`: FastAPI application, B routes, health/readiness, CORS, exception mapping, schema creation at import.
- `app/core/`: database setup, RBAC header dependency, audit, correlation IDs, error envelopes, masking, identifiers.
- `app/contracts/`: vocabulary enums/contracts.
- `app/modules/`: conversation/auth/intent/knowledge/orchestration/tool gateway/corebank simulator; cases/tickets/evidence/handoff/queue/SLA/escalation/approval/QA/analytics/outbox.
- `app/modules/routes_a.py`: registers conversation and A-owned API routes into the shared app.
- `alembic/`: one initial migration.
- `web-workspace/src/App.jsx`: role selector and conditional page rendering for dashboard, queue, conversation, cases, approvals, QA, analytics, SLA/outbox, and audit.
- `web-workspace/src/api.js`, `app.css`: API request helper and global styling.
- `tests/`: skeleton and queue/SLA tests; `scripts/`: smoke and contract utilities.
- `synthetic/`: deterministic data runner. `context/` did not exist at audit start.

## 4. Existing features that work (source-level evidence)

“Work” here means an implementation and corresponding test or concrete backend path exists; the audit did not run the app or tests.

- Case/ticket creation, case close checklist, reopen, evidence request, SLA calculation, handoff packaging, approval request/decision, queue enqueue/accept/transfer, analytics, QA sample/review/finding, audit trail, and operational endpoints are defined in `app/main.py`.
- Conversation channel ingestion accepts `WEB_CHAT`, `EMAIL`, `CONTACT_FORM`, and `WHATSAPP_SIM`; it rejects selected executable/oversized attachments (`app/modules/routes_a.py`).
- Intent/sentiment/vulnerability classification, knowledge article search/citation, tool policy evaluation, and deterministic orchestration are implemented as Python modules.
- RBAC denies unknown roles/permissions, and tests demonstrate selected policy cases: high severity confirmation, close checklist, evidence validation, SLA weekend handling, incomplete handoff, and self-approval prevention.
- Frontend pages call live API endpoints and show operational errors/empty states in selected workflows; Vite proxies `/v1`, `/internal`, health, and readiness.

## 5. Incomplete or broken features

- Customer portal journey is absent: the current `NAV` and page state in `web-workspace/src/App.jsx` are internal operations pages. No customer sign-in, customer conversation history, customer ticket list/detail, complaint submission journey, or feedback UI is present.
- The UI's “Peran” dropdown changes `X-Role`/actor values via `api.js`; this is a demo role switch, not authentication. It can select `customer`, `admin`, or any listed role in the browser.
- No distinct Knowledge Manager or System Administration workspace is exposed in navigation; knowledge create/search and tool registry routes exist in the backend. Supervisor/complaint officer experiences are not clearly separated from the shared console.
- No API for customer-owned case/ticket listing is evident in inspected route registrations. `/v1/status/{reference}` is unauthenticated and returns coarse status when not AL2; its reference/access design needs requirement and threat review.
- `app/main.py` notification endpoint returns `NTF-stub` and `QUEUED` without an outbox operation. `app/modules/routes_a.py` upload-link returns a path but does not implement object storage or upload processing.
- The `/v1/workspace/conversations/{conv_id}` route in `app/main.py` has a source comment identifying its read model as a stub for A's transcript/intent/tool contract, despite querying some related tables.
- Some UI data is rendered as raw JSON, including copilot suggestions and tool-call details, which is not a finished operational workflow. Empty states and role-specific states vary.
- Production run state, endpoints, and browser behavior were not verified. Test execution was not performed.

## 6. UI/UX problems

- One global operations navigation makes management analytics the default landing page and gives customer users no customer-centered entry point.
- Role selection is presented as if it were an application capability; there is no authentication boundary, route policy, user identity, or sign-out flow in the inspected SPA.
- The SPA uses local component state for page switching rather than URL routes; refresh/deep links and browser history are not represented by the UI structure.
- `App.jsx` is a large file containing navigation, shared components, data fetching, forms, and many pages. The global CSS and inline styles produce inconsistent token use and make responsive behavior harder to maintain.
- Visual hierarchy leans on cards and a large dashboard hero. Raw JSON dumps and dense operational forms are not optimized for scanability or customer understanding.
- No consistent design-system documentation, component library, or evident common loading/error/success contract across all actions. Accessibility and mobile behavior have not been verified.
- Some tables use clickable rows plus nested action buttons; keyboard semantics and focus behavior need review.

## 7. Architecture and code-quality problems

- FastAPI routes are split between `main.py` and a route-registration function, but service, persistence, and HTTP concerns are mixed in route handlers; request payloads are often untyped `dict`.
- `app/main.py` calls `Base.metadata.create_all()` during import, while Alembic is present; this blurs production schema lifecycle and makes application startup side-effectful.
- `app/core/db.py` contains a hand-written dotenv loader and eager database connectivity during module import for non-SQLite configurations.
- Both persistent database services and legacy in-memory stores appear in the repository (`analytics_copilot.py`, `cases.py` and workflows). Audit should identify active imports and remove/retire only with an explicit compatibility decision.
- Migration history is only one initial file, with `downgrade()` intentionally empty. Dependency versions in manifests are mostly unbounded.
- The frontend has no router, type checking, or component-level file boundaries; API calls are coupled to selected role headers.
- There is no `.git` metadata in the inspected project root; change history and existing local modifications cannot be assessed.

## 8. AI Agent and RAG gaps

- Intent and sentiment are implemented as deterministic keyword/scoring logic (`app/modules/intent.py`), not a connected model inference pipeline.
- Orchestration is deterministic and the tool result helper returns fixed simulated data in `app/modules/orchestrator.py`; the CRM/corebank modules are simulators. This is appropriate for a synthetic prototype but must not be labeled production AI or live integration.
- Knowledge retrieval in `app/modules/knowledge.py` is source-level lexical matching; no vector embedding/index or ingestion pipeline is evident in inspected modules despite pgvector in the deployment image and full requirements.
- Article/document lifecycle, version review/publish, ingestion status, retrieval evaluation, and source quality workflow are not represented as a complete manager UI. Confirm exact FRD/TRD requirements before specifying these.
- Tool registry and policy gateway exist, with prohibited tool checks, assurance-level step-up, idempotency, and audit hooks. The inspected route gates registry read with `tool.invoke`; a dedicated registry-management route/action was not established.
- AI summaries/suggestions need explicit provenance and human verification affordances. Existing copilot output must be checked in its service before being shown as factual.
- Authentication challenge records, consent list, counters/locks, intent context, and idempotency state include module-level in-memory structures. These do not provide durable multi-worker behavior.

## 9. Security and authorization risks

- **Critical confirmed design risk:** `app/core/rbac.py` trusts `X-Role`, `X-Actor-Type`, and `X-Actor-Id` request headers; defaults include `cs_agent` and `agent-1`. There is no verified cryptographic identity/session validation at the dependency boundary. Any reachable caller may claim a privileged role unless an external trusted gateway supplies and protects these headers. The browser role picker demonstrates the same trust boundary.
- Customer permissions include generic `case.read` and `ticket.read`; inspected case/ticket lookup routes filter by ID but no tenant/customer ownership check is visible in those lookup handlers. Cross-customer access risk must be resolved before enabling customer UI.
- `/v1/status/{reference}` lacks a permission dependency; whether an unguessable reference is intended authorization is unresolved and needs review against FRD security requirements.
- Route permission mismatches should be audited: `ticket_lookup` uses `ticket.create` for read; evidence upload-link uses `evidence.request`; supervisor and complaint officer capabilities differ.
- `X-Actor-Id` directly influences approval attribution. Self-approval is checked, but identity provenance is not established at the API boundary.
- `.env.example` uses demo credentials and placeholder secrets; ensure deploy guidance requires unique secrets. CORS is opt-in and credential-free, which is safer by default, but deployment configuration needs review.
- Attachment validation is extension/MIME/size based at inbound metadata level; actual upload/storage scanning is absent from inspected route code.
- Audit has append-only/hash-chain intent and masking utilities; tamper verification, retention, tenant scoping, and secret/PII masking coverage require review.
- No authorization penetration tests were observed for IDOR, role-header spoofing, tenant isolation, or customer resource ownership.

## 10. Testing and reliability gaps

- Tests are useful but small: selected workflow contract tests and queue/SLA/outbox tests, without demonstrated role matrix/API ownership tests, frontend tests, browser accessibility checks, or integration verification against real PostgreSQL/Redis/MinIO.
- No tests were run during this audit, per the instruction not to add or run tests unless requested. Existing cache artifacts are not evidence of current passing status.
- No CI configuration was found in the non-dependency file inventory. Runtime logs in the root are empty; that does not establish successful startup.
- In-memory stores and module-level locks/state create process-restart and multi-worker consistency risks.
- Health and readiness endpoints exist; readiness reports database status and outbox count, but readiness currently returns a payload even when DB is down rather than an observed failure status.
- No verified observability/export pipeline, retry policy for external integrations, or persistent background worker lifecycle was established from inspected deployment and source files.

## 11. Requirements not yet implemented or not verified

The repository contains FRD-EAICS-001 v0.9 draft and TRD-EAICS-001 v0.9 draft PDFs. README calls its implementation a walking skeleton and explicitly defers weeks 6–13 functions. FRD/TRD remain authoritative; this list is a gap map, not a substitute for a full requirement-by-requirement matrix.

- Customer portal/authenticated customer experience and customer-owned conversation/ticket history.
- Production authentication and backend-enforced customer data ownership/tenant scoping.
- Full operational workspaces for agent, supervisor/complaint officer, knowledge manager, QA analyst, management, and system administrator.
- Real attachment/object-storage lifecycle and verified document processing.
- Persistent authentication/consent/challenge state and documented identity channel integration.
- Production RAG ingestion/embedding/retrieval and its evaluation/citation lifecycle, if required by the final TRD.
- Real LLM/provider integration and model/prompt governance; current `.env.example` selects stub.
- Durable external channel/CRM/notification adapters and background processing; current integrations are simulated or stubbed.
- Remaining QA sampling/evaluation, SLA scheduling/worker behavior, outbox delivery, operational approval UI, and management driver-tree scope noted as future milestones in README.
- Route-level authorization/ownership proof for every role and resource.

## 12. Existing code to preserve

- Modular monolith and current Python/FastAPI + SQLAlchemy/PostgreSQL architecture (TRD ADR-01 noted in README).
- Frozen vocabularies and business rules around case severity confirmation, closure checklist, evidence validation, incomplete handoff defect recording, self-approval, argument hash, SLA working hours, and correlated audit trail.
- Existing A/B API boundaries and service modules where behavior is verified against FRD/TRD.
- Correlation IDs, structured error envelope, audit/masking utilities, schema-defined tool gateway, and current synthetic-data convention.
- React/Vite client and existing workflow APIs; improve in place unless requirement analysis establishes a concrete architectural need.
- Existing tests as regression contracts; extend only when implementing a specified unit.

## 13. Prioritized recommendations

1. Build a traceability matrix from FRD/TRD roles, workflows, API contracts, and security requirements; resolve document version conflict (FRD v0.9 cover vs TRD reference to FRD v1.0).
2. Resolve identity and authorization trust: replace caller-controlled role headers with a documented authenticated principal or trusted gateway contract, then enforce customer/tenant ownership in backend query/service boundaries.
3. Define role routes/actions/data access and implement customer service API journeys only after authorization is sound.
4. Establish shared UI structure and design tokens; separate customer portal from internal role navigation while reusing components where appropriate.
5. Complete agent workbench read model and human handoff operations against the real conversation data and verified provenance.
6. Deliver complaint/supervisor workflows and approval permissions, then knowledge management and QA workspaces based on requirement traceability.
7. Distinguish prototype adapters from live integration; implement durable notification, storage, retrieval, and provider adapters only as specified and configured.
8. Improve migrations/configuration/startup lifecycle and pin/version dependencies as a focused reliability unit.
9. Add authorization, ownership, workflow, frontend, accessibility, and integration verification alongside each implementation unit.
10. Keep management metrics sourced from real persisted observations, with definitions and empty states; retire no metric until its source and consumers are understood.

## Unit 02 implementation addendum (2026-10-13)

Source review confirmed `app/core/rbac.py` accepted caller-controlled `X-Role`, `X-Actor-Type`, and `X-Actor-Id` with `cs_agent`/`agent-1` defaults. The registered protected routes depended on that check. `app/modules/routes_a.py` also trusted `X-Assurance` on `/v1/status/{reference}` and used `ticket.create` for ticket reads. `app/main.py` allowed body `agent_id` to choose the handoff acceptance actor. These paths now use a verified bearer principal; status returns only customer-visible status, ticket lookup uses `ticket.read`, and the actor comes from the principal.

The API implements configured issuer/audience, fixed HS256, bounded access/refresh lifetimes, Redis one-time refresh rotation, and per-service keys with server-side role/scope allowlists. Missing credentials fail closed. FRD RBAC-05 is applied by removing conversation content access from `admin`; `knowledge_manager` is a distinct least-privilege role. Tests cover invalid/expired/wrong-purpose credentials, header spoofing, resource ownership/tenant boundaries, service scope, refresh replay, role separation, status disclosure, and actor attribution. Backend compile and test checks passed (28 tests).

Not implemented: trusted issuer/account provisioning and initial human credential issuance; live Redis verification; durable audit persistence; staff assignment-level access. Some tenant relationships use joins because existing tables do not carry a common tenant key. The frontend still sends legacy role headers and cannot yet use protected API routes; Unit 03 client integration requires a configured token provider for authenticated journeys.

## 14. Risks, assumptions, unresolved questions

- **Assumption:** current data and named bank are synthetic, as README and PDF covers state. Confirm that no real customer data is loaded before demos/deployment.
- **Unresolved:** FRD cover says v0.9 draft while TRD identifies FRD v1.0 as its source of truth; confirm canonical approved revision.
- **Unresolved:** identity provider/session/token model and whether a trusted edge proxy is intended to inject role headers.
- **Unresolved:** customer account registration, recovery, MFA/assurance levels, and supported customer channels per approved requirements.
- **Unresolved:** tenant model and customer identity linkage across channels; current rows include tenant IDs in some entities, but enforcement was not established.
- **Unresolved:** whether pgvector, Redis, MinIO, and Mailpit are required runtime dependencies in this capstone phase or deployment-only target components.
- **Unresolved:** approved external LLM, CRM, channel, notification, and object-storage providers; current simulator/stub paths must remain clearly labeled until decided.
- **Limitation:** requirements PDFs could not be fully searched in this audit session; the PDF library extraction attempt was too slow. Detailed role/feature acceptance must be confirmed from the source documents before implementation specs are activated.
- **Limitation:** no Git metadata, application startup, test, or browser run was verified in this audit. Source-level findings are not runtime claims.

## Audit addendum — FRD/TRD traceability pass (2026-10-13)

The FRD and TRD were subsequently reviewed for role/RBAC, functional-domain ranges, security, authentication tiers, AI guardrails, metrics, NFR, test and milestone sections. Page-level mapping is in [requirements-traceability.md](requirements-traceability.md). This evidence sharpens the initial findings:

- FRD §4.2 defines nine personas, including Knowledge Manager; current `app/core/rbac.py` does not define `knowledge_manager`.
- FRD RBAC-05 says System Administrator must not see unmasked conversation content/PII, while current `admin` permissions include `conversation.read`.
- TRD §11.1 specifies human JWT access/refresh tokens and short-lived signed scoped service tokens; header-based `require_perm` is not an implementation of that identity contract.
- FRD §10 defines customer assurance AL0–AL3 and operation tiers. This is separate from staff/service identity and role authorization.
- FRD A-02 explicitly places bank/CRM/messaging integrations behind team-built simulators. Live external connectors are therefore not a missing MVP feature. A-03 assumes a managed/local LLM; `.env.example` selects `stub`, which must be communicated clearly.
- TRD §6.1/ADR-13 requires tenant-aware repository queries; FRD §4.1.1 restricts customers to their own data. Current schema/query evidence is incomplete for this invariant.
- FRD §17.1 provides measurable NFRs, including WCAG 2.1 AA target, route authorization, correlation/audit, masking, seed reproducibility and workspace performance.

The original statement that the PDFs could not be fully searched is superseded for these cited sections. The signed FRD v1.0 and signed TRD §16 integration contract are still absent; their approval status remains unresolved.

## LLM provider readiness audit (2026-10-16)

This addendum records a source/documentation audit only. Application code, `.env`, dependency manifests, and active provider configuration were not changed. No API key or other secret was inspected, no request was sent to Gemini, and no live integration test was performed.

### Findings from the repository

- No LLM gateway, provider interface/protocol, adapter, or provider-specific test was found under `app/` or `tests/`. `app/modules/orchestrator.py` defines `BUDGET_LLM = 4`, but a source scan shows no inference client or call from `run_turn` (or another application module). That budget constant is not a gateway or proof that four calls occur.
- The only tracked configuration references found for `LLM_PROVIDER`, `LLM_MODEL`, and `LLM_API_KEY` are `.env.example:25-27`, set to `stub`, `stub-1.0`, and blank respectively. No application code reads these names. The ignored local `.env` was deliberately not inspected. No `GEMINI_API_KEY`, `GOOGLE_API_KEY`, Gemini SDK import, or `google-genai` dependency reference exists in the scanned repository (dependency caches excluded).
- Actual behavior in `app/modules/orchestrator.py`: intent comes from deterministic `intent.classify`; clarification choices are built by `_options`; the tool candidate comes from `_need_tool`, is checked against `tool_gateway.permitted_set` and re-evaluated by policy, and execution routes through the local simulator `_exec_tool`; informational text is assembled by `_compose_answer` / `_compose_action_answer`. `app/modules/guardrail.py` checks injection patterns, grounding, output policy, and action-state consistency after draft construction. None of these are provider adapters.
- TRD v0.9 draft §8.1, PDF p. 43, defines **four allowed/narrow model functions**: F1 intent refinement, F2 clarification composition (maximum three options), F3 tool argument composition from a policy-computed permitted set, and F4 answer composition from retrieved passages and current-turn tool results with `{text, claim_map[]}`. §8.2 describes their orchestration. The current runtime invokes none of F1–F4. This is a target architecture, not evidence of four current call sites. The code's `BUDGET_LLM = 4` is consistent with the draft budget but not connected to inference.
- Provider timeout, retry, provider-error mapping, provider-specific logging/metrics, and strict LLM response-schema validation are not implemented. Existing tool timeout metadata and general correlation/audit utilities do not establish LLM timeout/error behavior. Current tests exercise deterministic orchestration and knowledge/handoff behavior; there are no provider contract, malformed model response, timeout, or live-provider tests.

### Gemini feasibility and minimum future change

Gemini can technically fit behind a provider abstraction, but no such abstraction exists to extend. A minimal implementation must first define a narrow internal interface for structured generation, retain the current deterministic stub as the default and test implementation, and add a server-side Gemini adapter behind that interface. Route every model invocation through the same gateway and preserve the TRD's maximum four logical functions; do not add new model call sites. F1–F4 must validate against explicit Pydantic schemas and the existing intent/tool enums, option cap, allowed tool set, claim references, and retrieved evidence. Rejected, missing, malformed, or timed-out outputs must use a safe deterministic fallback/clarification/handoff path.

Potential Gemini configuration (not applied): preserve `LLM_PROVIDER` (`stub` or an approved Gemini identifier) and `LLM_MODEL`; replace the generic key setting with a documented server-only `GEMINI_API_KEY` (or explicitly map `LLM_API_KEY` into the adapter without logging it). The official Google AI documentation currently supports the Python `google-genai` SDK, environment-based key loading, and constrained JSON/Pydantic structured output. If selected, add a reviewed, pinned `google-genai` dependency to the appropriate requirements profile and set an explicit bounded SDK timeout. No Google SDK/provider feature should be enabled by default in deterministic CI, and untrusted attachments must not be placed in model context.

Required tests before live verification: provider-interface contract tests with deterministic stub; schema acceptance/rejection tests per enabled F function; F3 out-of-set tool and argument tampering tests proving policy is authoritative; F4 claim-map grounding/citation validation tests; provider timeout, quota/auth/network error, malformed/empty response, and secret-safe logging tests; orchestration regression tests proving no extra call points and preserving handoff/auth/idempotency/tenant boundaries. Live Gemini smoke testing should be a separately approved, opt-in integration check and must not be reported as performed by this audit.

### Requirements blockers and audit limits

- FRD v0.9 remains a draft while TRD v0.9 references frozen FRD v1.0; neither that discrepancy nor the missing signed TRD §16 integration approval is resolved here. The model/provider choice is still an open decision in the traceability record. Gemini must not be treated as approved merely because the API is technically usable.
- LLM output cannot grant authorization, define final confidence/thresholds, change workflow state, create or execute tools, or override the policy-computed allowlist. Informational answers must continue to cite eligible published knowledge and pass grounding/claim-map validation. No model-generated claim may imply an unexecuted tool or unaccepted handoff.
- Unit 06 has a build-plan entry for complaint/ticket APIs, but no active Unit 06 specification file is present in `context/specs/`. Do not select or implement that unit from the build plan alone; prepare/read its active spec when it exists. This audit does not resume or repeat Unit 05 implementation.
- Existing repository verification evidence remains historical: Unit 05 spec reports backend suite 43 passed and Vite build passed, with browser/accessibility verification pending. These commands were not rerun for this read-only audit. Provider-specific tests do not exist and no Gemini test was run.

Official Gemini references checked for feasibility (not used to make a provider approval decision): [Python SDK and getting started](https://ai.google.dev/gemini-api/docs/get-started?authuser=3&lang=python), [API key configuration](https://ai.google.dev/gemini-api/docs/api-key?hl=en), [structured output](https://ai.google.dev/gemini-api/docs/generate-content/structured-output?hl=en), [SDK timeout guidance](https://ai.google.dev/gemini-api/docs/generate-content/long-decode?hl=en).

## LLM provider foundation implementation addendum (2026-10-16)

The previous readiness audit's finding that no provider abstraction or provider tests existed describes the pre-implementation baseline. `app/modules/llm_provider.py` now contains the local structured-generation Protocol, four F1–F4 Pydantic input/output contracts, typed safe errors, fixture-keyed deterministic stub, stub-only provider factory, and a common validation boundary. `tests/test_llm_provider.py` adds offline unit/contract coverage.

The provider contract is still not connected to `orchestrator.run_turn`; current application execution remains deterministic and issues zero LLM calls. `.env.example` still names `stub`, but application code does not load that setting. No external adapter, Gemini SDK, network transport, live-provider test, or key configuration was added. Backend verification passed: focused provider tests 29 passed; full suite 72 passed with 96 existing dependency deprecation warnings. Contract details and unimplemented limits are recorded in `context/specs/llm-provider-contract.md` and `context/requirements-traceability.md`. FRD/TRD approval blockers remain unresolved.

## Gemini API readiness review (2026-10-16)

### Ringkasan

Fondasi kontrak offline tersedia, tetapi integrasi Gemini **belum siap diaktifkan**. Aplikasi tidak membuat panggilan LLM; factory hanya menerima `stub`; tidak ada adapter, transport, pembacaan konfigurasi provider, timeout jaringan, retry, atau jalur degraded yang terhubung ke provider. Ini adalah hasil audit kode saat ini, bukan klaim bahwa Gemini telah tersedia atau diuji. Batas desain TRD adalah empat fungsi logis F1–F4; kode runtime sekarang memiliki nol pemanggilan. `BUDGET_LLM = 4` adalah konstanta saja dan belum membatasi jumlah panggilan runtime.

### Matriks kesiapan berbasis implementasi

| Area | Status | Bukti dan batas yang ditemukan |
|---|---|---|
| Interface generasi terstruktur | PERLU PERBAIKAN | `app/modules/llm_provider.py`: `StructuredGenerationProvider.generate(function, payload, timeout_ms)` dan `generate_validated()` memisahkan generasi mentah dari validasi bersama. Bentuknya dapat diimplementasikan adapter, tetapi `generate()` saat ini menerima model input umum dan memulangkan `object`; adapter baru harus tetap memakai validator bersama dan tidak boleh meneruskan output mentah. |
| Stub offline dan factory | SIAP | `DeterministicStubProvider.generate()` memilih fixture berdasar fungsi dan hash payload; fixture disalin sebelum dikembalikan dan fixture yang hilang menghasilkan `NO_FIXTURE`. `build_provider()` hanya mengizinkan `stub`; tidak ada jaringan atau fallback menebak. Aplikasi belum memanggil factory ini. |
| Pemilihan provider/konfigurasi | BELUM DITERAPKAN | `build_provider()` tidak membaca konfigurasi; nilai selain `stub` ditolak sebagai `CONFIGURATION`. Pencarian kode pada `app/`, `tests/`, dan manifest dependency tidak menemukan penggunaan `LLM_PROVIDER`, `LLM_MODEL`, `LLM_API_KEY`, Gemini, `google-genai`, atau `BaseSettings` untuk provider. Karena `.env` tidak dibaca, nilai lokalnya tidak diaudit. Nama variabel, model, key server-side, secret manager, dan timeout belum diputuskan. |
| Skema F1–F4 Pydantic | PERLU PERBAIKAN | `F1Input/F1Output`, `F2Input/F2Output`, `F3Input/F3Output`, `F4Input/F4Output` dan model pendukung di `app/modules/llm_provider.py` menggunakan strict model dan menolak field ekstra. Bentuk internal jelas untuk stub/fake, tetapi F1 entity mengambil slot yang sekarang ada di `_slots`, detail skema dan makna beberapa field bukan kontrak Gemini yang disahkan. TRD tidak menyediakan JSON Schema lengkap; kontrak TRD §16.3 juga belum dikonfirmasi. |
| Respons kosong/skema/intent/opsi | SIAP (batas lokal) | `_model_validate()` memetakan respons kosong dan output invalid ke kode error aman; `F1Output` memakai `IntentCode`; validator F2 mewajibkan question tidak kosong, maksimum tiga opsi dan menolak kode intent internal. Tidak ada pemanggil orchestrator atau fallback runtime yang memakai error tersebut. |
| Tool allowlist dan argumen | PERLU PERBAIKAN | `generate_validated()` menolak nama tool di luar `F3Input.permitted_tools`, mewajibkan schema map dan allowlist sama, lalu memvalidasi argumen terhadap model Pydantic yang diberikan. Ini hanya batas kontrak provider; adapter belum terhubung ke `Gw.permitted_set()` atau `Gw.evaluate()`, dan validasi tersebut tidak membuktikan argumen faktual berasal dari konteks. Executor tetap berada pada orchestrator. |
| Claim map dan grounding | PERLU PERBAIKAN | `F4Output`/`ClaimMapItem` dan `generate_validated()` memastikan daftar source tidak kosong, ID ada dalam input, claim muncul sebagai rentang teks jawaban, dan jawaban tidak tanpa claim map. Ini pemeriksaan struktural, bukan bukti entailment/grounding semantik. `Grd.groundedness()` saat ini memeriksa angka dan sebagian kata faktual terhadap kutipan/tool result; guardrail ini belum menerima keluaran F4 karena tidak ada call site. |
| Timeout, rate limit, jaringan, retry, fallback | BELUM DITERAPKAN | `generate_validated()` mengubah `TimeoutError`, exception umum, dan `ProviderError` menjadi kategori terkontrol tanpa teks upstream. Stub hanya memeriksa `timeout_ms` positif; ia tidak melakukan timeout. Tidak ada transport, error mapper Gemini, retry, timeout budget runtime, atau fallback provider di `orchestrator.run_turn()`. TRD §8.2 meminta satu retry F4 untuk unsupported output; interaksi retry itu dengan anggaran empat panggilan perlu keputusan. |
| Kerahasiaan error/log | PERLU PERBAIKAN | `ProviderError` hanya membawa kode; exception provider generik tidak di-chain; tes mengecek canary pada `str(error)`/`caplog`. Modul provider sendiri tidak mencatat prompt/output. Belum ada uji redaksi pada SDK/HTTP logger atau integrasi; input F1/F3/F4 tetap dapat berisi data sensitif jika kelak dikirim. |
| Otorisasi dan eksekusi tool | SIAP sebagai batas kode saat ini | Interface tidak menerima principal/policy/executor dan tidak menjalankan tool. `orchestrator.run_turn()` menghitung `Gw.permitted_set(al)`, memeriksa izin, memanggil `Gw.evaluate()` lalu baru `_exec_tool()`. Integrasi harus mempertahankan urutan itu dan mengulang evaluasi policy untuk argumen hasil F3. |
| Batas pemanggilan LLM | PERLU PERBAIKAN | `LLMFunction` hanya berisi F1–F4 dan tes AST memastikan belum ada call site. `BUDGET_LLM=4` di `orchestrator.py` tidak didecrement atau dicek. Belum ada runtime counter/deadline di gateway, sehingga konstanta tidak menjamin batas empat pemanggilan. |

### Alur aktual dan titik integrasi yang disarankan

`routes_a.chat_message()` memvalidasi sesi dan permission `conversation.write`, menyimpan pesan inbound/idempotency, lalu memanggil `orchestrator.run_turn()`. Orchestrator mengecek assurance session; menjalankan classifier `IntentSvc.classify()` dan memperbarui konteks; mendeteksi injeksi; memproses HANDOFF/CLARIFY/greeting; menghitung allowlist policy; memetakan tool lewat `_need_tool()`; mengecek policy dan idempotency sebelum `_exec_tool()`; mengambil knowledge untuk INQUIRY; merangkai jawaban lokal lewat `_compose_answer()`/`_compose_action_answer()`; lalu menjalankan `groundedness()`, `output_policy()`, dan `action_state_check()` sebelum menyimpan outbound/audit. Kode provider tidak terlibat dalam alur tersebut.

| Fungsi | Titik yang dapat dievaluasi untuk integrasi | Guardrail yang harus tetap di kode |
|---|---|---|
| F1 intent | Setelah classifier deterministik membentuk kandidat dan sebelum keputusan final, hanya untuk kasus yang membutuhkan penyempurnaan. Implementasi sekarang `classify()` sekaligus mengeluarkan `decision`; pemisahan kandidat dari keputusan memerlukan desain eksplisit. | Handoff wajib, intent rentan, confidence final, threshold, injeksi, dan decision ditentukan kode. F1 tidak boleh menaikkan hak/assurance atau membatalkan handoff. |
| F2 klarifikasi | Hanya cabang `decision == CLARIFY`, sebelum teks dikirim dan selama batas percobaan klarifikasi belum tercapai. | Maksimal tiga opsi dari kontrak fungsi; batas dua percobaan/akhir HANDOFF §8.2 tetap dihitung backend. Jika gagal gunakan `_options()` deterministik. |
| F3 argumen tool | Hanya jika workflow kode sudah memutuskan tool memang diperlukan; setelah `permitted_set()` dihitung, kirim schema tool yang diizinkan, lalu validasi dan panggil kembali `Gw.evaluate()` atas proposal sebelum executor. | Model tidak memilih kebutuhan aksi, tidak memilih tool di luar allowlist, tidak mengeksekusi tool, dan tidak memutuskan approval/STEP_UP. Jika gagal/ditolak, jangan eksekusi dan gunakan jalur aman yang disahkan. |
| F4 jawaban | Setelah retrieval eligible dan hasil tool giliran ini tersedia, hanya untuk jawaban yang membutuhkan komposisi. | Input hanya sumber yang sudah lolos tenant/access/version checks dan hasil tool nyata. Pertahankan `groundedness`, citation, `output_policy`, serta `action_state_check`; status tiket/aksi/handoff tidak boleh dikarang. Fallback harus deterministik dan berbasis bukti, atau abstain/handoff. |

Fungsi tidak perlu dipanggil otomatis pada setiap giliran: greeting, handoff paksa, step-up, jawaban deterministik yang memadai, knowledge gap, dan mode degraded dapat tetap berjalan tanpa LLM. Rancangan runtime perlu satu gateway yang menghitung panggilan fisik per giliran dan menolak panggilan kelima serta menghormati sisa budget 20 detik. Retry F4 §8.2 juga harus mengonsumsi budget; apakah retry itu termasuk empat call perlu diputuskan, bukan diasumsikan.

### Konfigurasi, data, dan risiko

Tidak ada konfigurasi provider yang dikonsumsi kode. Manifest lokal `requirements.txt` tidak mencantumkan SDK Google; belum ada alasan untuk memilih profil dependency atau versi sebelum kontrak dan versi Python/runtime deployment disepakati. Jika disetujui, konfigurasi harus dibaca backend melalui satu settings boundary; default tetap stub, provider eksternal harus opt-in, key hanya server-side, dan konfigurasi tidak lengkap harus gagal tertutup. Timeout transport wajib dibatasi oleh sisa budget per giliran. Kebijakan retry rate-limit/network belum ditetapkan. Jangan menentukan diam-diam apakah mempertahankan `LLM_API_KEY` atau memakai `GEMINI_API_KEY`, atau model/version pin.

Potensi data keluar bergantung fungsi: F1 mengirim pesan pengguna dan konteks singkat; F2 kandidat intent (dan mungkin konteks jika kelak ditambah); F3 konteks dan argumen berpotensi memuat referensi rekening/transaksi, 4 digit kartu, email/kanal, serta ID kasus; F4 mengirim kutipan knowledge internal yang eligible serta hasil tool terkini. Pseudonym/tenant context juga berisiko ikut terbawa melalui payload. Lampiran/bukti tidak boleh ditambahkan ke konteks sesuai TRD §11.5–§11.6. Sebelum provider eksternal diaktifkan, pemilik sistem harus menyetujui minimisasi dan masking per fungsi, data yang diizinkan, region pemrosesan, retensi/penghapusan, penggunaan untuk pelatihan, DPA/ketentuan provider, pemberitahuan/consent bila diwajibkan, serta logging dan audit. Jangan pernah mengirim JWT, kredensial, key, data lintas-tenant, prompt internal, atau payload tool yang tidak dibutuhkan.

Ada temuan perilaku lama yang relevan untuk pengamanan fallback: cabang `DEGRADED` di `orchestrator.run_turn()` memanggil `append_outbound()` dengan teks “Tiket dibuat dan petugas akan membantu” tanpa membuat tiket/queue di cabang itu, lalu mengembalikan `reply: "degraded"`. Ini bertentangan dengan kewajiban fallback jujur dan anti-klaim tindakan TRD §13.9. Juga, pemeriksaan `action_state_check()` menerima boolean `has_executed` untuk setiap tool result, sehingga audit integrasi perlu membuktikan klaim spesifik sesuai hasil tool, bukan sekadar ada hasil tool apa pun. Temuan dicatat saja; tidak diperbaiki pada audit ini.

### Strategi tes yang dibutuhkan

1. **Unit offline:** validasi skema F1–F4, output kosong/malformed, enum, tiga opsi, field ekstra, claim map/source, timeout argument, error mapping dan redaksi tanpa jaringan. Tes provider saat ini di `tests/test_llm_provider.py` mencakup stub/fake untuk kasus utama tersebut; belum ada adapter atau transport nyata.
2. **Kontrak stub/fake:** jalankan contoh kontrak identik untuk setiap fungsi terhadap stub dan fake; pastikan hasil Pydantic/error stabil, fixture sintetis deterministik, dan tidak ada akses jaringan/key. Tes existing juga memeriksa factory menolak `gemini` dan ketiadaan call site.
3. **Integrasi Gemini opt-in (belum ada/jangan dijalankan pada audit ini):** hanya setelah persetujuan, flag eksplisit, key dari secret store/backend, model pinned, input sintetis tanpa PII, kuota/biaya dibatasi, dan environment terisolasi. Memeriksa structured response, timeout, rate-limit, unavailable, serta pemetaan error. Jangan jalankan di suite default.
4. **Orchestrator/fallback:** uji setiap call site kondisional, batas runtime maksimum empat panggilan termasuk retry, deadline, provider fail pada F1/F2/F3/F4, fallback deterministik, dan abstain/handoff tanpa klaim tak berdasar. Buktikan F3 tidak pernah mengeksekusi proposal yang gagal schema/allowlist/re-evaluasi policy.
5. **Regresi keamanan/workflow:** auth/RBAC, tenant ownership dan minimisasi payload, idempotency/replay, audit, guardrail/citation, output policy, status workflow, tool/ticket result, queue/handoff truth. Uji bahwa keluaran model tidak mengubah status dan klaim hanya cocok dengan ledger/result yang sebenarnya.

Tes kode tidak dijalankan dalam audit ini; hasil historis 29 tes provider dan 72 suite backend pada addendum sebelumnya bukan hasil eksekusi audit ini. Tidak ada tes yang menggunakan key, tes live, atau request eksternal.

### Ketidaksesuaian dan keputusan terbuka

- FRD-EAICS-001 v0.9 yang tersedia berstatus draft; TRD-EAICS-001 v0.9 mengacu pada FRD v1.0 yang disahkan, tetapi salinan FRD v1.0 bertanda tangan tidak ditemukan di repository.
- Persetujuan kontrak integrasi TRD §16, termasuk tanda tangan gate yang disyaratkan, belum dapat diverifikasi dari dokumen repository. Referensi §16.3/§16.6/§16.7 belum merupakan persetujuan implementasi.
- Belum ada keputusan final fungsi F1–F4 mana yang diaktifkan, call placement, skema final, model/provider, data yang boleh keluar, masking, retensi/region, retry, audit event, atau persetujuan live EVAL/E2E.
- Tidak ada adapter Gemini, dependency `google-genai`, konfigurasi aktif, call site, atau hasil tes provider eksternal. Tidak ada koneksi eksternal dan tidak ada rahasia dibaca/dicetak.

### Urutan implementasi terkecil yang aman

1. Sahkan FRD/TRD baseline dan kontrak TRD §16; putuskan enablement F1–F4, skema, privasi/data processing, provider/model, config/secret, timeout/retry, dan audit.
2. Sebelum wiring, tetapkan dan uji kebijakan degraded/fallback yang jujur, termasuk koreksi terotorisasi terhadap klaim “tiket dibuat” yang saat ini ada pada cabang degraded.
3. Tambahkan runtime call-budget/deadline yang benar-benar menghitung setiap request (termasuk retry) dan tes batas maksimal empat; jangan menambah call site sebelum mekanisme ini teruji.
4. Implementasikan settings boundary server-side dan adapter terpisah setelah dependency/model disetujui; stub tetap default dan semua tes default offline.
5. Integrasikan fungsi satu per satu pada titik yang disetujui, dimulai dari jalur dengan risiko paling rendah; pertahankan policy/tool gateway dan guardrail existing, lalu jalankan suite regresi.
6. Tambahkan tes Gemini opt-in menggunakan data sintetis hanya setelah persetujuan operasional; jangan menyebut integrasi live terverifikasi sebelum tes itu benar-benar dijalankan.

File yang diperiksa untuk review ini: `AGENTS.md`; `context/specs/llm-provider-contract.md`, `context/requirements-traceability.md`, `context/architecture.md`, `context/progress-tracker.md`, `context/audit-report.md`, `context/specs/00-build-plan.md`, `context/project-overview.md`; FRD/TRD PDFs; `app/modules/llm_provider.py`, `orchestrator.py`, `guardrail.py`, `tool_gateway.py`, `intent.py`, `routes_a.py`; `tests/test_llm_provider.py` dan daftar tes terkait; `requirements.txt`. Audit ini hanya menambahkan bagian di atas pada `context/audit-report.md`; kode aplikasi, tes, dependency, konfigurasi, dan environment tidak diubah. `.env` tidak dibaca; tidak ada rahasia dicetak; tidak ada tes dijalankan atau koneksi eksternal dibuat.

## Perbaikan klaim tiket dan fallback degraded (2026-10-16)

Audit lanjutan memverifikasi dua jalur klaim tiket tanpa bukti: cabang `DEGRADED` menyatakan tiket dibuat/human follow-up tanpa menulis tiket atau queue row; dan `_compose_action_answer()` menyatakan tiket pengiriman kartu dibuat setelah tool `card_status_update`, yang hanya menghasilkan status kartu. Cabang degraded juga menyimpan teks berbeda dari field `reply` dan menandai handoff true tanpa enqueue.

Perbaikan pada `app/modules/orchestrator.py` menyelaraskan respons tersimpan dan respons API, menyatakan status tiket/antrean belum dapat dikonfirmasi, serta menggunakan `handoff_status=NOT_ATTEMPTED` dan `handoff=false`. Copy tindakan kartu kini memerlukan hasil `TEMP_BLOCKED`, tidak mengklaim tiket; rekening koran memerlukan `sent is True`; hasil gagal/absen menghasilkan copy yang tidak mengklaim sukses. Jalur ticket API yang sudah ada tetap melalui permission `ticket.create` dan `Store.create_ticket_db`; respons sukses hanya diberikan sesudah commit dengan `ticket_id` dan status `OPEN`. Jika service gagal, route mengembalikan error tanpa klaim keberhasilan. Copy QUEUED tetap membedakan antrean dari ACCEPTED.

Tes baru di `tests/test_customer_conversations.py` dan `tests/test_b_skeleton.py` mencakup degraded tanpa ticket/queue, konsistensi teks outbound, bukti sukses/gagal aksi, copy QUEUED vs ACCEPTED, create ticket berhasil/persisted, dan create ticket gagal tanpa ID/status sukses. Hasil aktual: lima tes fokus lulus; suite backend terisolasi lulus **77 passed, 99 warnings**. Run suite pertama pada DB test bersama gagal satu tes karena percakapan fixture `CNV-1` sudah tersimpan dari run sebelumnya; rerun memakai DB SQLite sementara yang bersih lulus. Warning adalah deprecation `Starlette TestClient` dengan httpx, `anyio BlockingPortal`, dan `python-jose datetime.utcnow()`.

Tidak ada perubahan auth/RBAC, ownership tenant, policy/approval, Gemini/provider, dependency, atau `.env`; tidak ada request eksternal. Catatan proses: pengujian mengimpor aplikasi yang memiliki `_load_dotenv()` otomatis di `app/core/db.py`. File `.env` tidak dibuka secara manual oleh audit dan tidak ada nilainya ditampilkan; loader aplikasi mungkin membaca entri lokal sebagai efek samping import selama pytest. Hindari menyatakan bahwa proses pytest sama sekali tidak pernah membaca file tersebut.

## Gemini adapter foundation update (2026-10-16)

The earlier audit finding that no adapter existed is superseded by this update. `app/modules/gemini_provider.py` now implements the existing structured F1–F4 provider interface. `app/modules/llm_provider.py` selects it only with explicit `LLM_PROVIDER=gemini`; default remains `stub`, and an API key alone never selects Gemini. The adapter is neither imported nor called by the orchestrator, so runtime still makes zero LLM calls.

`requirements.txt` pins `google-genai==2.31.0`. The adapter requests constrained JSON, validates input/output through existing Pydantic contract schemas, bounds `LLM_TIMEOUT_MS` (default 10000 ms; max 20000 ms), disables SDK retries, and maps provider errors without exposing upstream exception text. F3 output schema is restricted to the supplied policy allowlist; the adapter has no tool executor. F4 structural source/claim checks do not establish semantic grounding; guardrail integration remains required. No conversation fallback is active because no orchestrator integration exists.

Offline fake-client evidence: `tests/test_gemini_provider.py` with `tests/test_llm_provider.py`: **48 passed**. Full backend suite: **96 passed, 99 warnings** (12.98 s), run from an isolated temporary working directory. Warnings were deprecations from Starlette/httpx TestClient, AnyIO BlockingPortal, and python-jose `datetime.utcnow()`. The SDK was not installed and no API-key test, Gemini request, or external connection was made. Local `.env` was not read or changed; `.env.example` contains configuration names/placeholders only.

Remaining decisions: canonical signed FRD v1.0 and TRD §16 approval; external data processing, minimization, region/retention; approved F1–F4 enablement; SDK/live compatibility; and subsequent call-site integration with actual call-budget enforcement, guardrail grounding, and deterministic truthful fallback. This adapter is not end-to-end Gemini integration.

## Gemini safe error mapping update (2026-10-16)

The earlier diagnostic categorized the live failure as `UNAVAILABLE` but retained no upstream cause. The adapter now maps SDK `google.genai.errors.APIError` using only its numeric `code` and fixed allowlisted `status` value, and maps `httpx.TimeoutException`/`TransportError` by type. New additive `ProviderErrorCode` values are `AUTHENTICATION`, `ACCESS_DENIED`, `RESOURCE_NOT_FOUND`, `CONNECTION_ERROR`, and `PROVIDER_ERROR`; prior values and generic `UNAVAILABLE` fallback remain. HTTP 401, 403, 404, 429, 408/504, 400, and 5xx are distinguishable; corresponding allowlisted RPC statuses are handled as well. 429/`RESOURCE_EXHAUSTED` remains one `RATE_LIMITED` category because the SDK status alone does not prove whether quota or rate limiting caused it. A 404 is reported generically as resource-not-found, not asserted to be model-specific.

No message, details, response body, auth header, URL, or prompt is copied into `ProviderError` or logs. Offline tests construct the installed SDK's `ClientError`, `ServerError`, and `APIError`, plus `httpx` transport errors, and verify safe categories and absence of secret canaries. Focused suite: **55 passed**. No live test/request, orchestrator change, `.env` access, or configuration change occurred.
