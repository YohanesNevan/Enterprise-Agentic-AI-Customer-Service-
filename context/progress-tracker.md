# Progress Tracker

## Current phase

Phase 1: security foundation and role-based shell complete; Unit 05 information-conversation slice implemented. Premium UI refresh is applied; authenticated conversation journey and comprehensive accessibility verification remain pending.

## Current goal

Complete and verify the customer conversation journey; production identity remains gated.

## Completed

- Inspected repository, manifests, routes, services, models, tests, and supplied FRD/TRD.
- Completed repository audit, requirements traceability (Unit 01), and the dependency-ordered 17-unit build plan.
- Implemented Unit 02 authenticated principal and backend authorization; see `context/specs/02-authenticated-principal.md`.
- Added signed bearer validation, access/refresh purpose and lifetime checks, one-time refresh rotation via Redis, and configured per-service key/role/scope allowlists.
- Removed caller headers as identity; corrected Knowledge Manager and administrator conversation permissions.
- Scoped reviewed customer resources, conversation/session access, handoffs, approvals, knowledge, QA, analytics, audit reads, and outbox operations by tenant/owner where the existing schema permits.
- Migrated existing API tests to signed test credentials and added security regression tests.
- Completed Unit 03 visible route shell: customer-first public landing, URL-based customer/staff route structure, role-specific navigation from the injected provider session, accessible responsive header, and explicit auth/forbidden/unavailable/unknown states.
- Replaced frontend role/actor header behavior with a fail-closed bearer-token provider boundary; no issuer, login form, or token is fabricated.
- Verified SPA deep-link fallback is configured in `web-workspace/nginx.conf` and `web-workspace/vercel.json`.
- Prepared and implemented Unit 04 after inspecting customer API routes, ownership logic, conversation/message models, tests, and FRD/TRD conversation requirements; details and decisions are in its specification.
- Confirmed the backend already defines the `customer` role and the API test helper can sign test-only customer tokens. A trusted production issuer and customer account provisioning are still absent.
- Found a cross-customer replay risk: provider-message deduplication in `app/modules/conversation.py` is global and returns the prior conversation ID before tenant/owner checks. The Unit 04 spec requires fixing this and adding regression coverage before customer access is exposed.
- Started Vite at `http://127.0.0.1:5173/`; local HTTP GET returned 200 and the application title. This is a launch/HTTP smoke check only; no browser rendering was verified.
- Implemented LangGraph StateGraph agentic decision loop in `app/modules/agent_graph.py` with TriageNode, ClarifyNode, GreetingNode, ToolNode, RAGNode, LLMNode, and HandoffNode. Integrated seamlessly into `orchestrator.run_turn` with automated test suite in `tests/test_agent_graph.py` (4/4 tests passed).
- Completed Unit 06 and Unit 07: Implemented `POST /v1/customer/complaints` and `GET /v1/customer/complaints` in `app/modules/routes_a.py` with strict tenant and customer-owner isolation and SLA calculation. Upgraded customer portal UI (`CustomerRequest` and `CustomerTrack` in `web-workspace/src/App.jsx`) with dual-mode official complaint filing, category selection, confirmation cards, SLA target tracking, and progress status badges. Verified with `tests/test_customer_complaints.py` (2/2 passed) and frontend Vite production build (33 modules transformed).

## Current status

- Unit 03 completed and verified per `context/specs/03-role-navigation-shell.md`.
- Unit 04 local customer login, API, UI integration and regression tests are implemented. Production identity and schema migration remain gated.

## Next tasks

1. Complete Unit 05 authenticated browser journey, keyboard and accessibility verification; responsive visual layouts were reviewed during the 2026-10-16 UI refresh.
2. Implement Unit 06 complaint/ticket ownership APIs and a documented complaint-to-case flow.
3. Implement Unit 08 full handoff context/read model and agent queue workflow; keep handoff package marked incomplete until verified.
4. Integrate trusted production identity issuer/account provisioning before enabling production access.

## Open questions

- Obtain canonical signed FRD v1.0 and signed TRD section 16 token contracts; supplied documents are drafts.
- Confirm the trusted JWT issuer, claim construction, secret distribution, rotation, and customer account lifecycle; specifically whether `sub` equals the internal customer ID or maps through a trusted directory.
- Confirm customer self-read audit policy and legacy message uniqueness/migration repair policy before production schema changes.
- Confirm local/managed/stub LLM selection; `.env.example` currently selects stub.

## Architecture decisions

- Preserve the FastAPI/SQLAlchemy modular monolith and React/Vite SPA.
- Token validation contract is fixed HS256 with configured issuer/audience, signed access (maximum 15 minutes), refresh (maximum 8 hours), Redis one-time refresh `jti`, and per-service keys plus server-configured role/scope allowlists. Claim schema and HS256 are local implementation choices pending signed TRD approval.
- External trusted issuer mints production credentials. A separate opt-in fixed-account development issuer supports local customer UI verification only.
- Caller-supplied identity and assurance headers are ignored. Service permissions are intersected with both the role permission set and the configured service allowlist.
- Public status-reference lookup returns only customer-visible status; `X-Assurance` cannot elevate disclosure.

## Known bugs and limitations

- Trusted issuer, human account provisioning, and initial token issuance are not implemented.
- The SPA's development bearer provider is configured only after successful local sign-in and is memory-only; production protected journeys remain unavailable until issuer/account provisioning is integrated.
- The backend role matrix includes `customer` and signed test tokens exercise customer ownership. A trusted production issuer and customer account-to-actor provisioning remain absent; production customer access is therefore not launchable.
- Staff assignment-level authorization is not modeled; current internal reads use role and tenant boundaries.
- Tenant columns are inconsistent and some boundaries rely on joins; a reviewed schema migration is still needed before claiming production multi-tenant readiness.
- Audit storage remains in-memory and is not durable.
- Notifications and attachment storage paths remain stubs; retrieval remains lexical rather than production vector RAG.

## Verification results

- `python -m compileall -q app tests` passed.
- `python -m pytest -q -p no:cacheprovider` passed: 28 passed. Warnings were emitted by Starlette/httpx and python-jose deprecations.
- Unit 02 refresh rotation/replay was tested with mocked Redis. No live Redis or external identity issuer was used.
- Unit 03: `npm run build` in `web-workspace` passed (Vite 5.4.21; 32 modules transformed). Source inspection confirmed no role/actor identity headers remain. Nginx and Vercel SPA fallback were inspected. No browser-based verification or frontend test framework is configured.

## Session notes

Review `context/specs/04-customer-conversation-history.md` and resolve its explicit decisions before starting implementation. The local UI is available at `http://127.0.0.1:5173/`; only HTTP availability was checked. Do not add a role selector, arbitrary identity headers, or a fake issuer.

## CS Agent conversation handling update (2026-10-27)

- Reused the existing tenant-scoped conversation read model, handoff accept/transfer operations, conversation state machine, case/ticket creation routes, and SLA/outbox behavior.
- Added a human-agent reply operation that persists `HUMAN_AGENT` messages with the authenticated staff actor, and emits an audit event. Replies are allowed only when the latest handoff is accepted by that same actor and the conversation is `ACTIVE_HUMAN`.
- Handoff acceptance now transitions the conversation through the existing state machine to `ACTIVE_HUMAN`. Resolution uses the existing supported `RESOLVED_PENDING_CONFIRMATION` conversation status; no unsupported `CLOSED` or duplicate handoff state was added.
- Added tenant-local conversation validation to case/ticket creation and derive the associated customer from that conversation. Staff mutation routes require a human `cs_agent` or `supervisor` principal and appropriate existing permissions. Assignment-level authorization remains unavailable because the schema has no assignment model.
- Added Staff Workspace reply, acceptance, resolution, and linked case/ticket controls with empty-message validation, loading/error feedback, and transcript refresh. The transcript distinguishes customer, AI, and staff authors.
- Verification: full backend suite passed (161 passed, 1 skipped); frontend workspace source-contract tests passed (5 passed); Vite production build passed (33 modules). No browser interaction test was performed. No schema migration was required.

## Additional local customer account (2026-10-27)

- Added optional `DEV_CUSTOMER_ACCOUNTS` server-side allowlist for multiple fixed local customer accounts while retaining the legacy single-account variables. Role and tenant continue to be server-derived; this does not add production signup or a database account table.
- Configured local username `efrant` with actor `customer-efrant-001` in `tenant-dev-001`; credential is stored only in ignored local `.env`.
- The login failure was caused by an old host Python API process intercepting `127.0.0.1:8000`; after it was stopped, Docker Desktop forwarded host loopback requests from its bridge gateway and the existing strict loopback-only guard rejected them. The dev login now trusts only exact addresses configured in `DEV_AUTH_TRUSTED_CLIENTS` (no forwarded headers or private subnet ranges), and the API port is published on host loopback only.
- Configured the local Docker Desktop gateway `172.18.0.1`, rebuilt and restarted the API, and verified login both directly at `127.0.0.1:8000` and through the Vite proxy at `127.0.0.1:5173`; both returned actor `customer-efrant-001`, role `customer`, tenant `tenant-dev-001`. Login/RBAC regressions passed (4 passed). No browser interaction test was performed.

## Knowledge upload and question routing follow-up (2026-10-27)

- Runtime audit showed the upload pipeline already synchronously extracts, chunks, persists, and marks documents `ready`; current `tenant-dev-001` had 7 READY documents. The live tenant-scoped search for `Apa itu NPB?` returned `01_PROFIL_LAYANAN_NPB.txt` as a document source.
- Root cause for some perceived missed knowledge was the closed intent taxonomy: reverse-form questions such as `NPB itu apa?` were classified `OTHER_UNCLASSIFIED`, and the orchestrator handed them off before retrieval. Intent classification now treats reverse-form and sufficiently long unclassified question-mark inquiries as information requests, while explicit human actions and mandatory fraud/staff-conduct handoffs remain higher priority.
- The API was rebuilt and restarted. Live runtime checks confirmed `NPB itu apa?` classifies as `INFO_PRODUCT_POLICY/ACT` and tenant retrieval returns the uploaded document. Python syntax compilation passed. No customer chat was sent and no browser interaction test was performed.
- Follow-up on the seventh CS greeting document: verified through the authenticated Staff Workspace API and Vite proxy that `07_PANDUAN_SAPAAN_CUSTOMER.txt` is present in `tenant-dev-001`, `ready`, and has six chunks. Strengthened Knowledge UI synchronization to reload the list immediately after upload and whenever the page regains focus/visibility; success feedback now states READY and chunk count. Frontend production build passed (33 modules). Browser interaction was not performed.

## Unit 04 implementation update (2026-10-13)

This update supersedes the earlier “Unit 04 specification prepared; implementation not started” status above.

- **Current phase:** Unit 04 customer conversation and local development authentication implemented; production identity remains an integration gate.
- **Completed:** Added a fixed-account dev-only credential issuer with opt-in flag, startup environment guard, loopback restriction, server-derived customer role/actor/tenant, and normal HS256 bearer validation. Added scoped idempotency ledger, validated customer WEB_CHAT, conversation ID in successful turn result, tenant-safe provider replay collision handling and continuity/reopen queries, customer-owned conversation list and bounded cursor history projection. Connected customer login/chat/history routes to API and added responsive transcript/composer states while preserving shell styling.
- **Verification:** `python -m pytest -q -p no:cacheprovider` passed: 38 passed. `npm.cmd run build` passed (32 modules). Browser automation was unavailable/not run. No browser rendering claim. Local HTTP smoke: Vite `/` and `/customer/login` returned 200; API `/healthz` was unavailable because backend is not running.
- **Local configuration:** Existing root `.env` is development mode and contains a signing key, but issuer/audience and customer account fields are unset; no local login succeeds until the operator fills them. Set `DEV_CUSTOMER_AUTH_ENABLED=true`, unique `DEV_CUSTOMER_USERNAME`, `DEV_CUSTOMER_PASSWORD` (at least 20 chars), `DEV_CUSTOMER_ID`, `DEV_TENANT_ID`, `JWT_ISSUER`, `JWT_AUDIENCE`, and `JWT_SIGNING_KEY` (>=32 chars). In `web-workspace/.env.local`, set `VITE_ENABLE_DEV_CUSTOMER_AUTH=true`. Never enable the backend flag outside development. Start backend with `python -m uvicorn app.main:app --reload --port 8000`; start SPA from `web-workspace` with `npm run dev -- --host 127.0.0.1`.
- **Limitations:** No production identity provider/customer provisioning; local token remains memory-only and signs out on refresh/close; no browser refresh token; durable audit storage absent. The new ORM ledger table is created by local `create_all`; production requires a reviewed migration. Existing message tables were not altered and legacy uniqueness/race handling remains for the migration unit.
- **Next:** Unit 05 customer conversation UI journey completion, browser/responsive/accessibility review, safe retry behavior, and human-handoff continuation. Do not reimplement Unit 04 APIs.

## Local authentication repair and staff preparation (2026-10-13)

- **Diagnosis:** Backend consumes `DEV_CUSTOMER_AUTH_ENABLED`, `DEV_CUSTOMER_USERNAME`, `DEV_CUSTOMER_PASSWORD`, `DEV_CUSTOMER_ID`, `DEV_TENANT_ID`, `JWT_SIGNING_KEY`, `JWT_ISSUER`, and `JWT_AUDIENCE`. The root `.env` already had development customer configuration and issuer/audience values, but its signing key was only 30 characters while the implementation requires at least 32. The customer page remained disabled because the Vite flag `VITE_ENABLE_DEV_CUSTOMER_AUTH` was not configured in `web-workspace/.env.local`.
- **Local fix:** Replaced only the local ignored `.env` signing key with a generated 64-character random value; no secret value was emitted. Added ignored `web-workspace/.env.local` with customer auth enabled and staff auth disabled. Added `**/.env.local` to `.gitignore`. The configured local customer credential is already present and meets the 20-character minimum; it was not printed or changed. Both local auth routes remain guarded for development and loopback clients.
- **Staff preparation:** Added a separate development-only `POST /v1/dev-auth/staff/login`, sourced exclusively from server-side `DEV_STAFF_ACCOUNTS` allowlist JSON and the existing human RBAC role set. It accepts username/password only, compares password in constant time, and issues a normal 15-minute signed bearer token. Added SPA staff-login entry/configuration, disabled by default locally. Existing role permissions govern authorization; management remains unable to read conversation content, and Knowledge Manager is not conflated with admin. No production staff issuer, account lifecycle, MFA, or credentials were added.
- **Verification:** `python -m pytest -q -p no:cacheprovider`: 40 passed (91 dependency deprecation warnings). `npm.cmd run build`: passed, 32 modules transformed. Fresh Vite dev server was restarted and `/customer/login` returned HTTP 200; transformed `/src/api.js` confirms customer feature flag `true`, staff feature flag `false`. Frontend source scan found no caller-controlled role/actor headers. No browser automation was run.
- **Runtime limitation:** `127.0.0.1:5432` and `:6379` were closed, Docker Desktop's Linux engine named pipe was unavailable, and the API could not be established. The production app creates database metadata at import, so live login/conversation persistence and tenant isolation against a running database remain unverified in this environment. SQLite-backed API tests cover token-based creation/history and existing ownership/tenant regression cases. Redis is needed for refresh rotation, not for initial development access-token issue.
- **Current phase:** Unit 04 local customer auth/config repaired; local staff authentication is prepared for explicit testing only. Production identity remains an integration gate.
- **Next:** Unit 05 customer conversation UI journey completion and browser/responsive/accessibility review, then staff/management production identity-provider integration when the approved issuer contract is available. Start PostgreSQL (and Redis when refresh rotation is needed), run the API, then exercise the configured local account in the running SPA.

## Unit 05 information conversation slice (2026-10-13)

- **Root cause:** The deterministic keyword classifier maps no-match text to `OTHER_UNCLASSIFIED` with `HANDOFF`, required by the available FRD draft; the orchestrator returned “Saya hubungkan ke petugas...” but did not create a queue row. A supported fee question matched only generic `biaya` and stayed in clarification. Independently, grounding received citation title with empty passage body, so it could reject a supported amount. `run_turn` makes no LLM call; `LLM_PROVIDER=stub` is not the cause of the repeated response.
- **Implemented:** Added phrase evidence for the seeded international transfer fee article; greetings now return deterministic greeting; retrieval rejects non-published/future/expired current versions; citation metadata includes retrieval score; grounding uses retrieved passage text; required handoffs create/reuse a tenant-scoped queue row before claiming it was queued, report accepted vs queued state, and leave `package_complete=false` until Unit 08; customer history renders persisted citations and chat reports queue state. Updated Unit 05 spec, build plan, architecture and traceability. Fixed a legacy fixed-ID test fixture to permit repeatable suite runs.
- **Requirement IDs:** FR-INT-001/003/004/007, FR-KM-003/004, FR-ORC-001/006/009, FR-WS-001/002, FR-CONV-003, against the supplied draft copies only; canonical signed FRD v1.0 and signed TRD §16 approvals remain unavailable.
- **Verification:** `python -m pytest -q -p no:cacheprovider` — 43 passed, 96 deprecation warnings. `npm.cmd run build` — passed, 32 modules. No browser automation tool was available; no browser check or live LLM inference is claimed.
- **Known limits:** Knowledge remains lexical and synthetic; no real provider invocation; full complaint-to-case/SLA workflow is Unit 06; handoff context package/workspace is incomplete (`package_complete=false`, Unit 08); browser responsive/keyboard verification remains open. FRD/TRD draft status remains an approval limitation.
- **Current unit status:** Unit 05 remains in progress until browser and accessibility checks are performed. Next implementation unit after those checks: Unit 06 — Complaint and ticket ownership APIs.

## LLM provider readiness audit (2026-10-16)

- **Scope/outcome:** Documentation/source audit only, recorded in `context/audit-report.md`. No application code, `.env`, dependency, or provider setting was changed; no secret was inspected and no Gemini request was made.
- **Finding:** The repository has no provider gateway/interface/adapter or provider-specific tests. `.env.example` contains `LLM_PROVIDER=stub`, `LLM_MODEL=stub-1.0`, and blank `LLM_API_KEY`; source code does not consume these values. The deterministic orchestrator currently invokes zero model calls. TRD v0.9 draft §8 defines four constrained logical functions (F1–F4); this is target architecture, not current implementation.
- **Gemini assessment:** Technically feasible after a provider abstraction, server-only key configuration, a reviewed `google-genai` dependency, strict schemas, bounded timeout/error behavior, and regression/contract tests. Stub remains necessary for deterministic offline tests. No live integration was tested or approved. FRD/TRD version and signature conflicts remain open.
- **Specification gap:** Build plan Unit 06 exists, but no active Unit 06 specification file is currently present in `context/specs/`.
- **Verification:** Read-only source searches and PDF inspection completed. Historical Unit 05 verification (43 backend tests passed and Vite build passed) is recorded in its spec and was not rerun. No provider test exists or was run. Unit 05 remains untouched and in progress pending browser/accessibility verification.
- **Next safe step:** Resolve/record the approved FRD/TRD and provider contract decisions, then write/review a dedicated provider specification and tests before implementation. Continue Unit 05 browser/accessibility verification separately; do not implement a Gemini adapter from this audit alone.
## LLM provider contract preparation (2026-10-16)

- **Documents:** Added draft design/test spec at context/specs/llm-provider-contract.md and a source-linked matrix addendum in context/requirements-traceability.md.
- **TRD findings:** Verified §8.1–§8.2 in source PDF p. 43: F1–F4 narrow schemas, 20-second total turn budget, one strict F4 retry for unsupported claims then safe fallback/handoff, and code-owned state/policy/execution. §13.9 defines degraded handling for LLM timeout/error/rate limit; §13.11 calls for stub/fixtures in routine testing and a pinned real model only in selected EVAL/E2E runs. §16 contract signatures remain unconfirmed.
- **Specification status:** Interface, deterministic fixture stub, separate external adapter, configuration questions, Pydantic validation, failure/fallback/logging requirements, F1–F4 constraints, security invariants, and unit/contract/opt-in integration test plans are documented. Details not fully specified by TRD (including claim_map schema, confidence_hint semantics, key setting, and per-call timeout) are explicitly open.
- **Boundary:** Documentation/traceability only. No source code, env files, dependency manifest, provider config, or tests changed. No credential read and no external API request made. Gemini remains an unapproved candidate; no integration is claimed.
- **Approval gates:** FRD v0.9 is draft; TRD v0.9 references FRD v1.0; canonical signed FRD v1.0 and signed TRD §16 approval are still absent/unconfirmed.
- **Next:** Review and approve the provider contract and unresolved schema/configuration choices before implementation. Implement no adapter until that approval is given.

## LLM provider foundation implementation (2026-10-16)

- **Implemented:** Added `app/modules/llm_provider.py` with one structured provider Protocol, four function identifiers only (F1–F4), Pydantic request/response schemas, deterministic fixture stub, stub-only factory, typed safe provider errors, and common output/semantic validation for tool proposals and claim references.
- **Call sites:** No provider call was added to `orchestrator.run_turn`; current runtime still performs zero LLM calls. `BUDGET_LLM = 4` is unchanged. No external adapter, SDK, settings loader, `.env` change, or network transport exists. Stub remains the only constructible provider.
- **Tests:** `python -m pytest tests/test_llm_provider.py -q -p no:cacheprovider`: 29 passed. `python -m pytest -q -p no:cacheprovider`: 72 passed, 96 dependency deprecation warnings. No Gemini/provider connection test was run.
- **Security/regression:** Provider module has no tool executor or access to principal, database, or workflow services. Existing backend suite passed, including auth/RBAC, tenant ownership, idempotency, audit, and workflow regression tests. F3 allowlist and schema validation are local contract checks only; no tool call is made.
- **Limits/open:** F4 semantic grounding still belongs to the existing guardrail and is not wired to a call site; no orchestrator fallback/degraded provider path exists yet. Schemas/entity bounds and config decisions remain subject to FRD/TRD approval. FRD v0.9 draft vs TRD v0.9 reference to FRD v1.0 and unsigned/unconfirmed TRD §16 remain open.
- **Docs synchronized:** `context/specs/llm-provider-contract.md`, `context/requirements-traceability.md`, and `context/architecture.md` now describe the implemented local boundary and its limits. Unit 05 remains untouched; no Unit 06 implementation was started.
- **Next:** Review this foundation and resolve contract decisions before wiring any F1–F4 call sites. Gemini must remain unimplemented until a separate approval.

## Truthful ticket and degraded fallback repair (2026-10-16)

- **Root cause:** The orchestrator degraded branch claimed ticket creation and human follow-up without calling ticket storage or enqueueing a handoff. The card-block response also said a delivery ticket was created although the executed simulator only returned card status.
- **Implemented:** Degraded output and persisted message now use the same honest response, report handoff `NOT_ATTEMPTED`, and do not claim ticket creation or follow-up. Action response wording now requires matching operation evidence (`TEMP_BLOCKED` or `sent is True`); card-block copy no longer asserts a ticket. The separately authorized ticket endpoint continues to return success/status only after its store transaction commits.
- **Tests:** Focused regression tests: 5 passed. `python -m pytest -q -p no:cacheprovider` with isolated temporary SQLite DB: 77 passed, 99 warnings. Warnings: Starlette/httpx TestClient and anyio deprecations, plus python-jose `datetime.utcnow()` deprecation. A prior full-suite run against the shared test DB had one collision on fixed conversation ID `CNV-1`; rerun with a clean isolated DB passed.
- **Boundary:** No auth/RBAC, tenant ownership, approval, queue acceptance, Gemini, Unit 06 workflow, dependency, or env configuration was changed. No external connection was made.

## Gemini provider adapter foundation (2026-10-16)

- Added `GeminiStructuredGenerationProvider` as an isolated implementation of the existing structured provider interface. It is selected only by explicit `LLM_PROVIDER=gemini`; default remains deterministic `stub`, and API-key presence does not change provider selection.
- Pinned `google-genai==2.31.0`. Backend settings use `LLM_MODEL`, `LLM_API_KEY`, and `LLM_TIMEOUT_MS` (default 10000 ms; max 20000 ms). `.env.example` documents names and empty placeholders only. Local `.env` was not read or changed.
- Structured JSON passes the existing F1–F4 Pydantic validators. F3 schema is narrowed to the policy-provided allowlist; no tool executor is exposed. Provider errors map to safe categories without upstream text; SDK retries are disabled.
- Tests: adapter/provider contract tests **48 passed**. Full backend suite **96 passed, 99 warnings** in 12.98 s from an isolated temporary working directory to keep the repository `.env` outside dotenv discovery. Warnings: Starlette/httpx TestClient and AnyIO BlockingPortal deprecations, plus python-jose `datetime.utcnow()` deprecation.
- Boundary: no orchestrator call site was added; runtime LLM calls remain zero and stub remains active default. No SDK installation, API-key test, Gemini request, or external connection. Adapter compatibility with an installed SDK and live behavior remain unverified; tests use a fake client. Conversation fallback, semantic grounding through guardrail, and FRD/TRD approval remain open.

## Gemini diagnostic error mapping refinement (2026-10-16)

- Added safe, additive provider error categories for authentication, access denied, resource not found, connection failure, and provider/server error. Existing categories remain. Adapter uses the installed SDK's `APIError.code`/allowlisted `status` and `httpx` timeout/transport types only; it never stores or emits raw exception details.
- 429/`RESOURCE_EXHAUSTED` maps to `RATE_LIMITED`; the available status does not safely distinguish quota from rate limiting. Unknown errors retain `UNAVAILABLE`.
- Offline tests for SDK `ClientError`/`ServerError`/`APIError`, timeout, connection, status mapping, and sensitive canary redaction: **55 passed**. No live test or external request was run. Orchestrator/default provider/configuration are unchanged.

## Premium frontend UI/UX refresh (2026-10-16)

- **Implemented:** Updated the existing React/Vite shell with a responsive charcoal-green sidebar, collapsible desktop navigation, mobile drawer, warm-paper surfaces, local/system typography, restrained motion, and shared operational styles. Reworked the customer landing and chat empty/loading/error/message presentation. Existing routes, bearer API boundary, auth/session rules, and backend contracts were preserved.
- **Conversation UX:** Starter prompts only populate the composer; citations render only from API responses; queue/acceptance copy remains backend-state driven; 401 returns to login, 403 does not offer retry, and safe resend retains the existing idempotency key. No regeneration feature, fake source, status, analytics, or AI response was added. No LLM runtime call was added.
- **Verification:** `npm.cmd run build` passed (Vite 5.4.21, 32 modules). Local frontend at `http://127.0.0.1:5173/` returned HTTP 200 and was visually inspected in Edge at 1440x1000 and a 390px emulated mobile viewport. Browser interaction checks verified Enter opens the mobile menu and routes to the protected chat/auth gate, Escape closes the menu and restores focus, and desktop collapse works by click. No frontend test framework is installed; authenticated API journey and comprehensive screen-reader checks remain outstanding.
- **Reference limits:** `https://emitra-app.vercel.app/` was inaccessible to the web inspection tool, and `UX for AI week 07 gabungan.pdf` was not present in the repository. Design uses the visual and seven-pattern guidance in the task prompt. FRD v0.9 draft / TRD v0.9 reference to FRD v1.0 and TRD §16 approval status remain unresolved.
- **Files:** `web-workspace/src/App.jsx`, `web-workspace/src/app.css`, `context/ui-context.md`, `context/specs/03-role-navigation-shell.md`, `context/specs/05-customer-information-conversation.md`, and this tracker.
- **Runtime note:** A Vite proxy log showed `ECONNREFUSED` for the development-auth endpoint during the local session. No authenticated API journey was attempted, so backend connectivity remains unverified.

## Customer chat Enter submission fix (2026-10-20)

- **Diagnosis:** `CustomerChat()` used a multiline textarea in a form with an `onSubmit` handler; Enter therefore inserted a newline and did not invoke the send handler. The button already submitted through that handler.
- **Implemented:** Plain Enter now requests native form submission; Shift+Enter and IME composition preserve textarea behavior. A synchronous submission lock prevents repeated Enter/click events from overlapping before React applies the loading state. API path, authentication, conversation ID, idempotency key generation/retry, and styling are unchanged.
- **Verification:** `npm.cmd run build` in `web-workspace` passed (Vite 5.4.21; 32 modules). No frontend interaction test framework is configured. This review did not run browser interaction or inspect a browser console. Edge is installed, but no browser automation harness/authenticated session was available to this process. Enter/Shift+Enter, rapid repeat, button parity, retry, focus, and no-reload behavior remain unverified in a browser.
- **Unit status:** Unit 05 remains IN PROGRESS. Do not mark its browser/accessibility gate complete until the manual checks are recorded.
## Unit 05 gate evidence refresh after Enter-key fix (2026-10-20)

- **Fresh automated checks:** `python -m pytest tests/test_a_skeleton.py -q -p no:cacheprovider` — **11 passed, 27 warnings** (2.16 s), with `LLM_PROVIDER=stub` and a uniquely named SQLite database in the OS temp directory. `npm.cmd run build` from `web-workspace` — **passed**, Vite 5.4.21, 32 modules (659 ms).
- **Coverage boundary:** The backend tests cover deterministic supported-question/citation/history and unknown-intent queued handoff behavior. The frontend build verifies compilation only. No frontend test script or browser automation framework is configured; no authenticated browser session, chat keyboard interaction, console, Network capture, responsive chat journey, or assistive-technology check was run.
- **Current Unit 05 status:** **IN PROGRESS; gate BLOCKED.** Enter/Send behavior, Shift+Enter, blank/repeated submission, UI retry, reload/history, desktop/mobile chat, focus/labels, and accessibility still require browser evidence. Prior 1440px/390px shell inspection and menu keyboard checks do not satisfy these chat checks.
- **Unit 06:** Not started. Continue to wait for Unit 05 browser/accessibility gate evidence and unresolved Unit 06 prerequisite decisions.

## Unit 05 developer-reported browser acceptance (2026-10-20)

- **Reported manual results:** Development login; Enter single-send; Shift+Enter newline; Send button; blank-input rejection; repeated-Enter duplicate prevention; history after reload; supported and unsupported questions; error handling; idempotent retry; desktop chat at 1440 px; mobile chat at 390 px; keyboard controls; visible/logical focus; and zoom/reflow were all reported PASS by the developer.
- **Evidence boundary:** Codex did not execute or observe these manual checks. No screenshots, recording, Network/HAR, console capture, or separate test log was supplied/located for this update. Record these as developer-reported, not Codex-verified. The previous fresh automated result remains 11 backend tests passed and frontend build passed.
- **Still untested:** Screen-reader/basic assistive-technology checks, contrast, and browser console/Network capture. Unit 05 spec/build plan require browser and accessibility verification generally; `context/ui-context.md` explicitly requires contrast testing, so contrast remains a closure item. Screen-reader basics are in the broader Unit 17 release verification and are not separately listed as a Unit 05 acceptance item. Confirm the required contrast target before claiming compliance.
- **Current Unit 05 status:** **IN PROGRESS; BLOCKED FOR CLOSURE pending contrast evidence and reviewer disposition.** This supersedes the earlier readiness note; reported manual outcomes remain developer-reported, and no approval is recorded. Unit 06 implementation remains not started.

## Unit 06 readiness audit (2026-10-20)

- **Unit 05 gate:** manual browser outcomes remain PASS — developer-reported, not Codex-verified. Re-review of `context/ui-context.md` found an explicit contrast-testing rule; contrast was not reported. Unit 05 remains **IN PROGRESS; blocked for closure** pending contrast evidence and reviewer disposition. Screen-reader basics remain untested for the Unit 17 release verification; no approval is inferred.
- **Unit 06 status:** **BLOCKED; implementation not started.** The active `docs/units/UNIT_06_SPEC.md` is a draft with no implementation authorization. D-01–D-10 remain unresolved in the decision log/checklist. Required gates include Unit 05 disposition; official FRD/TRD baseline; approved actor/assurance for customer case creation; migration baseline/rollout; and customer-facing CRM outage/ACK/retry/reconciliation contract.
- **Other stage decisions:** D-05 duplicate matching, D-06 customer status, D-07 audit/timeline retention, D-08 idempotency contract, and Unit 06/07 UI scope must be resolved before their affected schema/service/API/UI stages. No implementation, migration, test, provider, CRM, or banking operation was performed for this readiness audit.
- **Audit report:** `docs/units/UNIT_06_READINESS_AUDIT.md`. Recommendations in it do not constitute mentor, product, security, DB, or operations approval.

## Unit 05 contrast follow-up (2026-10-20)

- **Source review:** Re-inspected active `web-workspace/src/app.css` and `App.jsx`. The contrast changes documented in the Unit 05 audit are already present: secondary text for placeholder/counter, chat-scoped dark focus outline and composer focus ring, explicit disabled/sending palettes. Chat labels, keyboard submit behavior, loading/status/error semantics, and responsive rules remain present. No application source change was necessary.
- **Build:** `npm.cmd run build` from `web-workspace` — **PASS**, Vite 5.4.21, 32 modules, 769 ms. No frontend test script or browser automation framework is configured.
- **Runtime:** Edge headless rendered `/customer/chat` at 1440×1000 and showed the authentication-required panel. Without a customer session, composer/focus/loading/error states were not visible; no keyboard or contrast sampling is claimed.
- **Target note:** Requirements traceability maps draft FRD §17.1 NFR-09 to WCAG 2.1 AA; signed FRD v1.0 remains unavailable. Ratios in the contrast audit use WCAG 2.2 AA as a technical reference, not a separately approved project threshold.
- **Gate:** Unit 05 remains **IN PROGRESS; BLOCKED FOR CLOSURE** pending authenticated chat-state/browser verification and reviewer disposition of the evidence/baseline. Unit 06 remains blocked and not started.

## Unit 06 readiness re-audit (2026-10-20)

- **Requester report:** The requester says they manually tested Unit 05 and consider it okay to continue. Codex did not repeat those tests; no detailed checklist/artifact or reviewer disposition was attached. This authorizes the requested readiness review only and does not mark Unit 05 COMPLETE/APPROVED or authorize Unit 06 source work.
- **Source probe:** Direct `intent.classify()` probe for “Transaksi saya gagal, tetapi saldo saya terpotong.” returned `INFO_ACCOUNT_BALANCE`, confidence 0.7, `CLARIFY`. This is a pure-function probe, not a pytest result; no case was created.
- **Approvals:** D-01–D-10 remain UNRESOLVED in the decision register; approval checklist remains blank. Fresh source findings and per-decision choices/risks/recommendations/approvers are in `docs/units/UNIT_06_READINESS_AUDIT.md`.
- **Test/migration boundary:** No pytest suite or migration ran. Relevant pytest fixtures drop/create tables or remove `eaics_test.db`; tests were not run to protect database contents. No live DB schema was inspected. `git status` could not run because this folder has no discovered `.git` metadata.
- **Unit 06:** **BLOCKED for implementation.** Continue approval/specification work only. No Unit 07 work started.

## Unit 05 current-session verification (2026-10-20)

- **Fresh frontend build:** `npm.cmd run build` in `web-workspace` passed (Vite 5.4.21, 32 modules, 648 ms). No frontend test script or Playwright/Puppeteer/WebDriver harness is configured/installed.
- **Frontend serving:** started Vite with `npm.cmd run dev -- --host 127.0.0.1`; it became ready on port 5173. `GET /customer/login` and `GET /customer/chat` both returned HTTP 200 with the SPA root shell. These GETs do not establish browser rendering, login, or chat behavior.
- **Backend:** `GET http://127.0.0.1:8000/healthz` was unavailable (connection refused). The backend was not started because importing `app/main.py` invokes `Base.metadata.create_all()`; starting it would not be a read-only check.
- **Login access conditions:** `CustomerLogin` displays “Login lokal belum diaktifkan” unless `VITE_ENABLE_DEV_CUSTOMER_AUTH` is enabled; when enabled it calls `/v1/dev-auth/customer/login`. A configured development identity and a running backend are required. The chat route requires a customer session. No credentials/config secrets were read and no login/chat POST was sent.
- **Contrast/source:** re-inspection found the earlier placeholder/counter, focus, disabled, and sending palette fixes still present; no new source defect and no CSS/source edit. Existing calculated ratios remain static, not runtime contrast evidence.
- **Not run in this session:** Enter/Shift+Enter, blank/repeated sends, authenticated history reload, error/retry/fallback/handoff behavior, keyboard focus, 1440 px/390 px browser rendering, dynamic contrast, and assistive technology. The developer-reported manual results elsewhere remain reported results, not Codex-verified results.
- **Environment limitation:** `git status --short` failed because this active project path is not recognized as a Git repository; no clean/dirty status is asserted.
- **Unit 05 status:** remains **IN PROGRESS; BLOCKED FOR CLOSURE**. Required final evidence is a safe authenticated browser run covering the chat journey and specified responsive/keyboard/dynamic states, plus reviewer confirmation/disposition of the contrast baseline and gate evidence. Do not mark COMPLETE/APPROVED on the basis of build/SPA GET/source checks.

## Unit 11 Staff Workspace Knowledge Base access slice (2026-10-27)

- **Role audit:** `app/core/rbac.py` defines human roles `customer`, `cs_agent`, `supervisor`, `complaint_officer`, `knowledge_manager`, `qa_analyst`, `management`, and `admin`; `ai_agent` is service-only. The Staff Workspace navigation includes the seven human roles other than `customer`.
- **Implemented:** Reused the existing Knowledge Manager page for all seven Staff Workspace roles. Added `knowledge.document.ingest` to those roles and enforced it on document upload/retry. Added `knowledge.read` to staff roles missing it. Kept `knowledge.write` restricted to Knowledge Manager article authoring. Customer has no knowledge permission; `ai_agent` retains explicit read access for retrieval but cannot access document management endpoints. Document management endpoints also require a verified human principal, so service tokens cannot inherit staff UI access through a configured role. Staff nav and `/knowledge` route share a role allowlist. Detail view reads the existing tenant-scoped detail endpoint; original files are not served by a customer endpoint.
- **Preserved behavior:** Tenant filters on upload/list/detail/retry/retrieval remain. Ready chunks remain searchable through the same chatbot pipeline. No delete/edit endpoint, new role, login method, or public access was added.
- **Verification:** `tests/test_knowledge_documents.py` — **35 passed**. Full backend suite with process-only `LLM_PROVIDER=stub` for tests and isolated temporary SQLite/upload paths — **139 passed, 1 skipped** (163 existing dependency deprecation warnings). Frontend role/navigation tests — **2 passed**. `npm.cmd run build` — **passed**, 33 modules.
- **Initial full-suite note:** Running with the existing local `LLM_PROVIDER=gemini` produced two unrelated failures in tests that assume a stub default. Re-running with a process-only stub setting passed; `.env` was not changed.
- **Browser boundary:** No authenticated browser session was available; role navigation is covered by the frontend unit test and production build. API access is covered by signed-token tests. Broader Unit 11 knowledge lifecycle requirements remain incomplete.
- **Specification:** `context/specs/11-knowledge-staff-workspace-access.md` records the audit, permission decision, endpoint boundaries, and verification.

## Local Staff Workspace login enabled for Knowledge Base upload (2026-10-27)

- Enabled the existing loopback-only development staff login in ignored local `.env` and enabled the existing Vite staff-login flag in ignored `web-workspace/.env.local`. The local allowlist account uses role `cs_agent` and the same configured development tenant as the local customer account; its credential is not stored in tracked documentation.
- Restarted the local API and Vite dev server. Verified `POST /v1/dev-auth/staff/login` returns the `cs_agent` principal, authenticated `GET /v1/knowledge/documents` returns HTTP 200, `/staff/login` returns HTTP 200, and Vite loads both development auth flags as `true`.
- No document was uploaded during setup; the user will select the actual source document. Development login is still disabled by default in tracked templates and must not be enabled outside `ENVIRONMENT=development`.

## Unit 05/11 dynamic Knowledge RAG chat follow-up (2026-10-27)

- **Root causes confirmed:** the customer chat route called deterministic `orchestrator.run_turn`, which routed generic informational questions such as "Apa itu NPB?" to `OTHER_UNCLASSIFIED/HANDOFF` before retrieval and never called the existing F4 provider. Lexical search counted query words like "apa/itu" and could miss an acronym. The retrieval path also injected sample demo knowledge, including a sample transfer fee, into tenants without articles. Ingestion/retry raised supported extraction errors after setting `failed` but did not commit that state.
- **Changes:** generic information questions enter the existing INQUIRY retrieval path while explicit fraud/safety/staff-conduct handoffs remain first. Lexical tokenization removes interrogative stopwords, improves overlap checks, and continues enforcing authenticated tenant and eligible article/document states. Demo seed data is opt-in with `KNOWLEDGE_SEED_DEMO=true` and no longer silently affects live tenant searches. The existing F4 structured provider is now called from the real customer chat path with retrieved sources and the question; source IDs are validated and every answer sentence must be represented by a source-mapped claim. The Gemini prompt treats source/query as untrusted, prohibits unsupported facts and secret collection. Retrieval/provider failures are distinguished from knowledge gaps. Failed ingest/retry details are committed. Customer UI no longer says direct AI processing is unavailable and still renders stored response/citations.
- **Verification:** full backend `python -m pytest -q -p no:cacheprovider` with isolated SQLite/upload paths, `LLM_PROVIDER=stub`, and demo seeding disabled — **149 passed, 1 skipped** (182 existing warnings). New `tests/test_rag_chat.py` exercises A–J: NPB, failed transfer, unsupported fee/phone, OTP, missing knowledge, tenant isolation, failed PDF, actual chat F4 propagation/persistence, and mandatory fraud handoff. Frontend `npm.cmd run test:access` — **2 passed**. Frontend production build — **passed** (Vite 5.4.21, 33 modules); initial sandbox run hit `spawn EPERM`, then the authorized elevated build succeeded.
- **Limits (superseded by runtime check below):** At implementation time no live Gemini request or browser session was run. Retrieval remains lexical; no vector service or model training was added.

## Knowledge tenant/runtime diagnosis (2026-10-27)

- **Data location confirmed read-only:** PostgreSQL database `eaics` on the Compose PostgreSQL service contains 6 READY documents and 16 chunks for `tenant-dev-001`; another unrelated tenant `TNT-MANUAL` has 1 READY document/1 chunk. The local staff login resolves to role `cs_agent`, tenant `tenant-dev-001`; local customer login resolves to the same tenant. All six original files still exist under `data/uploads`, and the document metadata/chunks are in the same PostgreSQL database. No DB, file, document, or tenant was deleted or changed.
- **Runtime cause:** an old host Uvicorn process (PID 26792, started Oct 2) continued to hold `127.0.0.1:8000`, so local requests hit stale application code/runtime and showed zero documents. That process was stopped. The current host API is running on loopback port 8000 with a process-only database-host override to reach the same Compose PostgreSQL service; `.env` and tenant data were not changed. The Compose API container was stopped to avoid a competing published port. PostgreSQL and Redis remain running.
- **Safe diagnostics:** added hashed/sanitized database identity and environment/provider startup diagnostics; staff login and Knowledge list/upload events report tenant, DB identity, counts by ingest status and outcome; retrieval reports tenant and hit/source counts; chat reports intent/decision and safe provider failure category. No file contents, credentials, API key, raw provider errors, or customer query text are logged.
- **Observed API check:** current host API staff login resolved `tenant-dev-001`; authenticated Knowledge list returned 6 documents, all READY. Customer chat for “Apa itu NPB?” classified as product/policy information, retrieved `01_PROFIL_LAYANAN_NPB.txt`, and preserved that source citation. The response did not become the generic handoff, but returned the controlled `ANSWER_GENERATION_ERROR` because live provider generation failed.
- **Real provider boundary:** actual Gemini runtime attempts did not generate an answer. The host process logged a network `CONNECTION_ERROR`; Docker runtime requests reached Gemini but received model/key access failures (404 for `gemini-2.5-flash`, 403 for a second metadata-available model). Minimal content-generation probes also failed, so this is provider access/configuration rather than missing tenant data, retrieval, prompt, or citations. Do not mark end-to-end RAG complete until a permitted Gemini key/model/network configuration produces a customer answer. No secret was changed or disclosed.
- **Current regression checks:** `tests/test_gemini_provider.py tests/test_llm_provider.py tests/test_rag_chat.py` with isolated SQLite/upload paths and process-only stub — **66 passed, 21 warnings**. Previously verified full backend suite remains **149 passed, 1 skipped**; frontend access tests **2 passed** and production build passed before this runtime-diagnostic follow-up. Browser journey was not run in this follow-up; there is no claim of browser verification.
- **Manual verification after provider access is repaired:** open `http://127.0.0.1:5174/staff/login`, sign in with the configured local staff account, and confirm `/knowledge` shows the six READY documents. Then sign in at `/customer/login`, ask “Apa itu NPB?” in customer chat, and confirm an answer cites `01_PROFIL_LAYANAN_NPB.txt`. At present the latter check is expected to show the controlled provider error until Gemini access/network is fixed.

## Gemini provider runtime diagnosis (2026-10-27)

- **Runtime settings:** application startup loads `.env` in `app/core/db.py` without overriding values already in the process environment. The active local config resolved to `LLM_PROVIDER=gemini`, `LLM_MODEL=gemini-2.5-flash`, `LLM_TIMEOUT_MS=10000`, and a configured `LLM_API_KEY`. Installed SDK is `google-genai==2.31.0`; no custom API base URL is configured, so the adapter uses `https://generativelanguage.googleapis.com` (SDK default). The key value was never printed or changed.
- **Provider probes:** adapter construction passed. A minimal F4 prompt and an F4 prompt with a small synthetic NPB passage both returned `RESOURCE_NOT_FOUND` (HTTP 404, RPC `NOT_FOUND`). Requests with plain text (without response schema) also returned 404 for `gemini-2.5-flash` both with and without the `models/` prefix. Therefore the JSON schema, RAG source, and response parser are not the cause. The same configured key successfully listed 60 models, including `models/gemini-2.5-flash` with `generateContent` advertised. The endpoint/model is discoverable but actual generateContent access remains rejected/not found; available evidence cannot safely distinguish a key/project API entitlement or endpoint restriction from provider-side resource routing. Do not switch model or fabricate fallback output without a successful real generation probe.
- **Actual customer HTTP flow:** a fresh diagnostic customer token in the existing tenant invoked `POST /v1/chat/messages`. Intent classification and retrieval succeeded; the response retained citation to `01_PROFIL_LAYANAN_NPB.txt`, then returned controlled `ANSWER_GENERATION_ERROR`. A previous same-account request hit the preserved `REPEAT_CONTACT` handoff rule before generation. No browser test was performed.
- **Code changes:** Gemini error diagnostics now derive allowlisted reasons from numeric HTTP/RPC status fields only (404 => `MODEL_OR_ENDPOINT_NOT_FOUND`, 403 => `ACCESS_DENIED`, 401 => `CREDENTIAL_REJECTED`, etc.), never raw exception strings. Startup diagnostics now include model name, timeout, fixed SDK endpoint, SDK version and key-configured boolean; never log the key. No provider selection, model, credential, retrieval, tenant, citation, or handoff behavior was changed.
- **Tests/build:** `tests/test_gemini_provider.py tests/test_llm_provider.py tests/test_rag_chat.py` — **70 passed, 21 warnings**; `python -m compileall -q app tests/test_gemini_provider.py` passed; frontend production build passed (Vite 5.4.21, 33 modules). These use deterministic fake provider for automation; actual Gemini generation and actual chat did not pass.
- **Resolution gate / setup:** user/operations must provide a Gemini API key/project with `generateContent` access to an enabled model on the Gemini Developer API, ensure the outbound route to `generativelanguage.googleapis.com` is allowed, set `LLM_API_KEY` in the ignored local `.env` (never paste it into chat/logs), verify `LLM_PROVIDER=gemini` and `LLM_MODEL` against that key, then restart API and repeat the probes. Until the minimal real generation and customer NPB answer both succeed, provider failure remains open and this feature is not complete.

## Gemini runtime model correction and live chat verification (2026-10-27)

- **Model correction:** the configured `gemini-3.1-flash-lite-preview` had been shut down on May 25, 2026. Updated ignored local `.env` only: `LLM_MODEL=gemini-3.1-flash-lite`; `LLM_TIMEOUT_MS=20000` after an observed 10-second timeout and a successful run at the supported 20-second application maximum. `LLM_API_KEY` value was not printed or edited. Official model docs name the stable model as replacement.
- **Small adapter change:** F4 prompt now directs Gemini to copy each `claim_map.claim` verbatim into answer text. This matches local output validation, which requires each answer sentence to be present in the source-mapped claim text. The previous prompt allowed semantic paraphrases that caused safe `OUTPUT_INVALID` rejection.
- **Service state:** PostgreSQL and Redis Compose services are running; host Uvicorn is running on loopback `127.0.0.1:8000` outside the restricted network sandbox so the process can reach Gemini; Vite dev server is running at `127.0.0.1:5173`. `/healthz` and `/staff/login` both returned HTTP 200.
- **Live verification:** Direct adapter generation with the stable model and synthetic passage passed using a 20-second timeout. A real HTTP `POST /v1/chat/messages` with an ephemeral diagnostic customer principal in the configured tenant retrieved the actual `01_PROFIL_LAYANAN_NPB.txt`; Gemini returned a grounded answer (“Nusantara Prima Bank (NPB) adalah tenant rujukan sintetis yang digunakan dalam demonstrasi platform Enterprise Agentic AI Customer Service.”) and the API preserved the source citation. No customer browser session was run.
- **Credential handling:** the requester pasted the API key in chat. It was only read from local `.env` for the authorized API probe and was not output or modified. Treat it as exposed and rotate/revoke it, update local `.env`, then restart Uvicorn.

## Unit 05 customer chat routing consistency follow-up (2026-10-27)

- **Root cause:** `intent.classify()` counted every turn for the same conversation/intent in a process-global `_repeat` map and forced `HANDOFF` at the third hit. It did not distinguish informational requests already answered from unresolved action requests, and unrelated informational turns shared the same counter. A runtime chat record had previously shown `REPEAT_CONTACT` before answer generation. `_queue_handoff()` then reused an existing queue row; when its state was `ACCEPTED`, the customer saw “Petugas telah menerima...” instead of the grounded answer. This occurred before retrieval/LLM, not because Gemini varied its response or the frontend overwrote it.
- **Implemented:** removed frequency-only handoff escalation; added a deterministic handoff reason for explicit refund/reversal execution requests; kept refund policy/eligibility questions on the inquiry/RAG path; kept repeat-contact handoff only for explicit unresolved-repeat language; preserved mandatory fraud/vulnerability/staff-conduct handoff. For a short follow-up such as “Mengapa?”, the system first searches the current message, then uses only the preceding customer question if direct retrieval found no evidence. Added per-turn safe routing diagnostics (intent, decision, reason, retrieval outcome/source count, handoff state) without message text, and removed raw query fragments from retrieval audit IDs.
- **Files:** `app/modules/intent.py`, `app/modules/orchestrator.py`, `app/modules/knowledge.py`, `tests/test_rag_chat.py`, `context/specs/05-customer-information-conversation.md`, and this tracker.
- **Verification:** focused chat/skeleton tests — **24 passed**. Fresh isolated full backend suite — **158 passed, 1 skipped, 192 warnings** (`DATABASE_URL` pointed to a unique temporary SQLite file; `LLM_PROVIDER=stub`; `KNOWLEDGE_SEED_DEMO=false`). Available frontend access test — **2 passed**; production build — **passed**, Vite 5.4.21, 33 modules. The frontend test checks Knowledge navigation roles, not chat UI interactions. No browser test or live Gemini request was performed in this change.

## Customer request, tracking, and account portal first slice (2026-10-27)

- **Implemented:** replaced the customer route placeholders for `/customer/requests/new`, `/customer/requests`, and `/customer/account`. Request submission uses the existing authenticated `POST /v1/chat/messages` endpoint with an idempotency key and navigates to the resulting conversation. Tracking uses the existing customer-owned conversation list and opens the conversation through its read model. The account page shows only the session actor ID/role and existing logout action. Conversation history links to the request form and explains that records cannot be deleted.
- **Scope semantics:** this slice submits service messages and tracks conversations; it does not implement formal complaint cases/tickets or a staff/customer live-reply session. Existing 72-hour conversation continuity can append a submitted message to an existing conversation. UI labels do not expose raw internal status or imply a case/agent session. No backend authorization, database, or role changes were made.
- **Build:** `npm.cmd run build` in `web-workspace` passed (Vite 5.4.21, 33 modules). No authenticated browser journey or API integration test was run. Taste-skill static lint reported 44 FAIL / 27 WARN across the existing shared `App.jsx`/`app.css` design patterns; this is not a clean design lint result and was not treated as a build failure.
- **Remaining workflow:** formal case creation/tracking and the human agent reply session remain gated by the unresolved Unit 06 decisions/specification. Do not mark Unit 06 or the complete customer-to-agent workflow done based on this portal slice.


## Agentic AI Dynamic Slot Extraction & Autonomous CRM Ticket Creation (2026-11-04)

- **Problem:** previous orchestrator tool executions relied on hardcoded static strings (`****4821`, `range: 30d`, `action: TEMP_BLOCK`), lacked dynamic slot extraction from customer utterances, and always responded to transaction disputes with a passive non-committal message (`"Pesan Anda tersimpan dalam percakapan. Saya belum dapat mengonfirmasi pembuatan tiket..."`) without resolving the problem or issuing a ticket.
- **Implemented:**
  1. **Dynamic Slot Extraction (`app/modules/intent.py`):** enhanced `_slots()` to dynamically extract alphanumeric transaction references (`TRX-...`, `REF-...`), card numbers, and currency amounts from conversational Indonesian text. Added dispute keywords (`saldo berkurang`, `saldo kepotong`, `transaksi gagal`) to prevent false-positive balance inquiry clarifications.
  2. **Dynamic Tool Calling (`app/modules/orchestrator.py`):** updated `_need_tool()` and `_exec_tool()` to accept context slots and pass extracted transaction references, card numbers, and accounts into tool invocations.
  3. **Autonomous Dispute Ticket Creation:** when handling transaction disputes (`CMP_TRANSACTION_DISPUTE`), the agent checks transaction status via `transaction_lookup`, observes failure/debit mismatch, and automatically creates an official CRM ticket (`cases.create_ticket()`) with a unique reference number (`T-TKTA-...`).
  4. **Grounding Guardrail Adjustment (`app/modules/guardrail.py`):** updated `groundedness()` to strip trailing sentence punctuation from matched numeric tokens, avoiding false-positive unsupported claim rejections on grounded references at sentence boundaries.
  5. **Universal Login Platform Boundary:** unified login under `UniversalLogin` and `/v1/dev-auth/login` with automatic role-based dispatching (`customer` => Customer Web, `cs_agent` => Agent Workspace, `supervisor` => Supervisor Dashboard, `management` => Analytics). Removed administrative staff links from the public customer portal sidebar.
- **Verification:** verified dynamic extraction, transaction dispute resolution, and auto-ticket issuance via end-to-end Python test; verified dynamic card balance lookup and card blocking; verified frontend production build (`npm.cmd run build` passed in 1.43s, 33 modules).

## CRM Ticket Persistence, Endpoints & Cross-Portal Synchronization (2026-11-04)

- **Problem:** AI-generated dispute tickets were previously held only in-memory, missing collection listing endpoints (`GET /v1/tickets`, `GET /v1/cases`), and not rendered in the Agent Workspace `/agent/cases` or Customer Portal `/customer/requests`. Additionally, balance inquiries output raw ISO timestamps (`2026-11-03T18:42:51.452481+00:00`).
- **Implemented:**
  1. **Database Ticket Persistence (`app/modules/orchestrator.py`):** linked `_compose_action_answer` with `create_ticket_db`, persisting dispute tickets into `TicketRow` (with SLA calculation and CRM outbox enqueueing), associating the customer ID from `ConversationRow`.
  2. **Localized Indonesian Timestamps (`app/modules/orchestrator.py`):** formatted `as_of` timestamp in `_exec_tool` into Indonesian date representation (`"4 November 2026, 01:42 WIB"`), passing strict numeric grounding checks with zero hallucination flags.
  3. **Collection Endpoints (`app/modules/routes_a.py`):** added `GET /v1/tickets` and `GET /v1/cases` with tenant filtering, customer isolation (customers only see own records), and sorting by creation timestamp. Added `PATCH /v1/cases/{cid}` and updated `GET /v1/tickets/{tid}` to return full checksummed customer reference (`short_reference`).
  4. **RBAC Scope Alignment (`app/core/rbac.py`):** added `ticket.read`, `ticket.update`, `ticket.create` to supervisor and complaint officer roles.
  5. **Agent Workspace Live Management UI (`web-workspace/src/App.jsx`):** upgraded `Cases` component (`/agent/cases`) with multi-tab dashboard displaying active tickets and cases tables, status badges, one-click status transitions (`RESOLVED`, `CLOSED`), and quick navigation to conversations.
  6. **Customer Tracking UI (`web-workspace/src/App.jsx`):** upgraded `CustomerTrack` (`/customer/requests`) to fetch and display official dispute tickets alongside conversations with status indicators, creation dates, and direct links to the relevant chat.
- **Verification:** Python compilation passed; frontend Vite production build passed cleanly (`✓ built in 1.21s`, 33 modules transformed). Direct endpoint tests verified tenant isolation and customer scoping.

## Human Handoff Intent Detection & Real-Time Sync Foundation (2026-11-04)

- **Problem:** When customers explicitly requested human assistance (e.g. *"Saya ingin berbicara dengan petugas"*), the intent engine previously classified the turn as generic `OTHER_UNCLASSIFIED` with reason `INTENT_REQUIRES_HANDOFF` rather than the canonical `CUSTOMER_REQUEST`. Furthermore, customer chat had no background polling for staff replies, and accepting an agent queue item required manual copy-pasting of conversation IDs.
- **Implemented:**
  1. **Canonical Human Agent Intent Classification (`app/modules/intent.py`):** added `_human_agent_requested()` matching explicit conversational Indonesian patterns for human agent, operator, or customer service requests, routing directly to `HANDOFF` with reason `CUSTOMER_REQUEST` and confidence 0.95.
  2. **Customer Chat Near Real-Time Polling (`web-workspace/src/App.jsx`):** added background polling (3.5s interval) in `CustomerChat` while a conversation is open, automatically fetching incoming human-agent replies without requiring page refreshes.
  3. **Seamless Agent Queue Acceptance & Navigation (`web-workspace/src/App.jsx`):** updated `Queue`'s `accept(q)` to navigate directly to `/agent/conversations?cid=...`, and updated `Conv` to auto-read `cid` from query parameters and open the conversation context and reply workbench immediately.
- **Verification:** Python compilation passed; pattern unit tests passed; frontend build passed (`✓ built in 1.25s`, 33 modules transformed).

### Unit 08 live handoff verification (2026-11-04)
- Fixed stale handoff: an ACCEPTED handoff whose conversation is no longer ACTIVE_HUMAN/PENDING_HANDOFF is now CLOSED in orchestrator._queue_handoff; a new customer request creates a fresh QUEUED handoff and returns the conversation to ACTIVE_AI.
- Manually verified by user: customer request -> queue -> Terima -> staff reply in /agent/conversations -> reply appears as 'Petugas' in customer chat via 3.5s polling. Resolve step ('Selesaikan penanganan') also verified: status RESOLVED_PENDING_CONFIRMATION, reply box hidden.

