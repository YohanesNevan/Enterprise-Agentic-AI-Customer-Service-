# Architecture

## Existing stack and boundaries

- Python + FastAPI is the HTTP/API boundary. `app/main.py` owns many B routes; `app/modules/routes_a.py` registers A routes on the same application.
- `app/core/` supplies SQLAlchemy engine/session, errors, correlation middleware, audit, RBAC, IDs, and masking.
- `app/modules/` contains domain services and persistence models for conversation, identity simulation, intent, knowledge, orchestration, tools, cases, tickets, handoff, SLA, approval, QA, analytics, and outbox.
- SQLAlchemy models are split between `models_a.py` and `models.py`; PostgreSQL is default, SQLite is opt-in for tests. Alembic currently has one initial migration.
- React 18 + Vite 5 SPA is in `web-workspace/`; the role-aware History API shell and injectable bearer-token provider are in `src/api.js`. Fixed-account local customer login and allowlisted local staff login can each be enabled explicitly for development; both mint 15-minute tokens through the same HS256 principal path and are loopback-only. Tokens remain memory-only in the SPA. These are not production identity providers. Vite proxies API paths to port 8000 and both Nginx/Vercel configurations provide SPA deep-link fallback.
- The SPA keeps route metadata in `src/routes.js`, the role-aware shell in `src/App.jsx`, reusable navigation/UI/form helpers in `src/shared/`, and customer and staff pages in `src/pages/customer/` and `src/pages/workspace/`. Styles are grouped by shell, customer, workspace, knowledge, and chat under `src/styles/`; `src/app.css` imports them in cascade order.
- Docker Compose includes PostgreSQL/pgvector, Redis, MinIO and Mailpit, but source inspection did not establish complete usage of each service.

## Data ownership and persistence

Conversation, session, message, intent, knowledge article/version, tool call/policy decision, case/ticket, SLA, handoff, approval, QA, and outbox SQLAlchemy rows are defined in module model files. Some auth challenges/consents, intent context, workflow deduplication, circuit-breaker/idempotency details, or legacy analytics/case state use module-level memory. Do not rely on in-memory state for multi-process durability. Tenant and customer ownership constraints must be established and enforced in query/service boundaries before customer routes are exposed.

`app/main.py` invokes `Base.metadata.create_all()` at import while Alembic is also present. Unit 04 adds only the new `customer_chat_request` ledger table; it does not add constraints or alter existing message/conversation rows. The local create-all path creates this new table, but a production rollout requires an explicit reviewed migration once the Alembic environment and deployment migration policy are established.

## Authentication and authorization

`app/core/rbac.py` validates bearer JWTs with fixed HS256, configured issuer/audience, required subject/token/tenant claims, and bounded access-token lifetime. Production human access credentials are expected from an external trusted issuer; this repository has no production login/account issuer or staff account store. The opt-in customer route mints a token for one server-configured account. The separate opt-in staff route resolves identity, tenant, and role only from the server-side `DEV_STAFF_ACCOUNTS` JSON allowlist; its request accepts only username/password. Both routes require development mode, are disabled by default, loopback-only, and use constant-time password comparison. Permissions come from the existing RBAC role map. This development mechanism does not implement production staff authentication or account provisioning. Refresh credentials rotate through Redis using one-time `jti` consumption. Service credentials use per-service keys plus server configured role/scope allowlists; effective permissions intersect token scope and the role map. Missing config and invalid credentials fail closed. Caller-provided role, actor, and assurance headers are ignored.

`VerifiedPrincipal` supplies the actor, identity type, tenant, role, permissions, scope, and signed assurance context. Route dependencies deny by default. Customer case/ticket reads and conversation detail/append paths include owner and tenant checks; Unit 04 audit found that provider-message replay lookup and 72-hour continuity/reopen lookup still need tenant/owner-safe correction before customer conversation use. Internal conversation projections, handoff, approval, evidence, tool, ticket, and case operations apply tenant checks. The public status-reference route returns only the customer-visible status projection. The backend role map includes `customer`; no production issuer or customer account provisioning is configured. Knowledge Manager is a distinct role; administrator has no conversation-content permission under FRD RBAC-05.

Knowledge document access uses the verified role map. Human roles in the Staff Workspace (`cs_agent`, `supervisor`, `complaint_officer`, `knowledge_manager`, `qa_analyst`, `management`, and `admin`) have `knowledge.read` and `knowledge.document.ingest`; `knowledge.write` remains limited to Knowledge Manager article authoring. Customer has none of these permissions. The `ai_agent` service retains its existing `knowledge.read` for retrieval but receives no document ingest permission; document list/detail/upload/retry endpoints additionally require a human principal. Upload, detail, list, retry, and retrieval remain tenant-scoped; no endpoint serves original files to customers.

Tenant filters are now applied to the implemented case, ticket, conversation, knowledge, handoff, approval, QA, analytics, audit, and outbox paths; some use joins because their own records have no tenant column. Staff assignment-level access is still not modeled. The schemas also lack a uniform tenant foreign key and migration history, so the joins are a compatibility measure, not a substitute for the approved tenant-schema migration. Audit storage remains in-memory in this skeleton and is not durable. FRD §4.2 remains the permission source of truth.

## API conventions

Existing routes use `/v1/...`, JSON responses, request correlation middleware, and `AppError` envelopes. Many endpoints accept untyped dictionaries and instantiate `SessionLocal` directly. Preserve compatibility while introducing typed request/response validation and consistent database dependency/service boundaries in separately specified units.

## AI orchestration and tools

`routes_a.py` calls `orchestrator.run_turn`; intent and sentiment are deterministic; `knowledge.py` performs tenant-scoped lexical retrieval; `tool_gateway.py` checks registry/policy and records calls; orchestrator tool results and corebank behavior are simulated. The customer information path passes eligible retrieved document chunks and source metadata to the existing F4 structured provider, then validates source references and grounded claims before persisting the response. Greeting remains deterministic; genuine safety/policy handoffs remain ahead of ordinary knowledge answering. Gemini is selected only by explicit runtime configuration; its structured adapter uses the pinned `google-genai` SDK and provider errors are safely categorized. A runtime check on 2026-10-27 confirmed the local `tenant-dev-001` has six READY documents/16 chunks and retrieval returns the NPB source, but actual configured Gemini generation failed (host network error; container model/key access errors). Therefore no successful live customer answer is established yet. `.env.example` defaults to `stub`; no vector service or model training is used. Safe diagnostic logs include hashed DB identity, environment, tenant/status counts and retrieval source counts, without raw secrets, document contents, or query text.

### Provider adapter status update (2026-10-16)

The historical note above that no Gemini adapter exists is superseded: `app/modules/gemini_provider.py` now implements the structured provider interface using the pinned `google-genai` SDK. Provider choice is explicit through `LLM_PROVIDER`; its default stays `stub`, while Gemini requires server-side key/model configuration. The adapter is not imported or called by `orchestrator.run_turn`, does not configure SDK tools, and does not perform policy or workflow actions. Offline fake-client tests cover its contract. No provider request or live compatibility test has been performed; data-processing approval and conversation fallback integration remain open.

**Runtime follow-up (2026-10-27 supersedes the preceding status):** The orchestrator now calls F4 for information inquiries and passes retrieved passages/citations through grounding. Runtime config uses `LLM_PROVIDER=gemini`, `LLM_MODEL=gemini-2.5-flash`, `LLM_TIMEOUT_MS=10000`, SDK `google-genai==2.31.0`, and the SDK default endpoint `https://generativelanguage.googleapis.com`; `LLM_API_KEY` is configured server-side. Adapter initialization and model catalog listing succeed, but both schema and plain-text generation return 404/`NOT_FOUND`, including a real customer HTTP chat after retrieval. Thus the real provider remains unavailable to this runtime; no successful answer is claimed. Startup diagnostics log model, timeout, endpoint, SDK version and key-presence only. Provider diagnostics classify allowlisted HTTP/RPC codes and never log raw upstream messages. A valid key/project with generateContent entitlement and outbound connectivity is still required.

**Successful live Gemini check (2026-10-27 supersedes the preceding failure state):** The preview model was shut down; local ignored `.env` now selects stable `gemini-3.1-flash-lite` and a 20-second timeout. The F4 prompt requires verbatim claim text to satisfy the app's claim-map validator. With Uvicorn running outside the network sandbox, a real customer chat request retrieved `01_PROFIL_LAYANAN_NPB.txt`, received a grounded Gemini answer, and preserved its citation. API health and Vite routes returned HTTP 200. Browser UI interaction was not tested. The pasted key should be rotated; no key value belongs in tracked files, logs, or chat.

## RAG and knowledge

Knowledge article/version rows and search/citation logic exist. A persistent document ingestion/indexing pipeline or vector query path was not established by inspection. pgvector in the compose image is not evidence that vector retrieval is wired. Current citations identify the stored article version and whole `body`; the schema has no section anchor, so section-level citation compliance remains open. Any RAG implementation must follow approved TRD requirements, preserve provenance/citations, and report indexing/publication only after the operation succeeds.

Uploaded PDF, DOCX, and TXT documents use the existing tenant-scoped extraction/chunking pipeline. Ready chunks enter the same lexical retrieval path used by chatbot turns. The Staff Workspace reuses the Knowledge Base screen for every human staff role; document ingestion uses the narrower `knowledge.document.ingest` permission, while article creation continues to require `knowledge.write`.

## Background work and integrations

SLA tick and outbox drain are exposed as internal routes and worker scripts exist. Compose includes Redis/MinIO/Mailpit; actual message broker, object storage, and provider adapters need verification. CRM/corebank/channel behavior is synthetic or simulated in inspected code. Background jobs must be idempotent and durable according to TRD before production claims.

## Logging and audit

Correlation middleware, audit service, masking utility, and audit-trail endpoint exist. Keep correlation IDs through API, tool, workflow, and integration actions. Verify masking, append-only integrity, access to audit data, retention, and tenant scope against FRD/TRD.

## Security invariants

- Authenticate principal before authorization; never trust browser-selected role or actor headers.
- Enforce tenant and customer ownership on backend reads and writes.
- Deny by default and require least privilege for routes and data.
- Do not expose secrets, OTPs, internal notes, or unverified AI output as authoritative customer facts.
- Enforce assurance level, tool allowlists, approval separation, and argument integrity server-side.
- Keep customer data synthetic unless explicitly approved otherwise; audit sensitive actions with correlation IDs.

## Architectural decisions and open items

- Preserve the current modular monolith and stack (README identifies ADR-01); no migration is approved.
- Confirm canonical FRD revision and trace role matrix/API ownership requirements.
- Production customer access remains gated on a trusted issuer, customer provisioning, and an authoritative subject-to-customer/tenant mapping. Local development login does not resolve those production dependencies.
- Decide provider/storage/vector/queue adapters only from TRD a

**Customer routing consistency update (2026-10-27):** the previous process-global repeated-intent counter has been removed because it forced answered informational inquiries into handoff after three turns and could return an earlier handoff's `ACCEPTED` wording instead of evaluating the current turn. Informational questions remain retrieval-first regardless of previous inquiry count. Human-action handoff is explicit for refund/reversal execution; repeat-contact escalation requires an explicit unresolved-repeat signal. Short referential follow-ups search the current message first and consult only the immediately preceding customer question when direct retrieval has no result. Each completed chat turn logs intent, route reason, retrieval outcome/source count, and handoff decision without logging customer text. Full evidence is recorded in `context/specs/05-customer-information-conversation.md`.

