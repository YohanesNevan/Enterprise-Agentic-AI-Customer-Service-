# Unit 11 implementation slice — Staff Knowledge Workspace access

Status: implemented and verified per the user-approved feature brief. The broader Unit 11 lifecycle remains in progress.

## Audit findings before implementation

- Human roles in `app/core/rbac.py`: `customer`, `cs_agent`, `supervisor`, `complaint_officer`, `knowledge_manager`, `qa_analyst`, `admin`, and `management`. `ai_agent` is a service role, not a human Staff Workspace role.
- `web-workspace/src/App.jsx` has staff navigation for seven human roles: `cs_agent`, `supervisor`, `complaint_officer`, `knowledge_manager`, `qa_analyst`, `management`, and `admin`. The `/knowledge` route and menu were previously limited to `knowledge_manager`.
- Identity is a verified signed bearer principal. Frontend staff login is a local development flow backed by a server-side `DEV_STAFF_ACCOUNTS` allowlist. Caller-supplied role/permission headers are not identity and are ignored by the API.
- `knowledge.read` currently protects document list/detail and search; `knowledge.write` protects article creation, document upload, and retry. Customer has neither permission. Tenant IDs are taken from the verified principal for uploads and filtered for list/detail/retry/retrieval.
- The existing document pipeline accepts PDF, DOCX, and TXT, persists tenant-owned document metadata/chunks, exposes processing status, and contributes ready chunks to the same lexical retrieval path used by chatbot turns. The original file has no customer download endpoint.
- No detailed Unit 11 specification existed. The draft FRD §4.2 permission model and FR-KM-001/003/004/009 (FRD v0.9, especially pp. 21 and 46–49) and TRD §4.6 / knowledge retrieval sections were reviewed alongside the repository audit and build plan. Draft status and existing lexical retrieval limitations remain unchanged.

## Decisions and boundary

- Reuse the current Knowledge Manager page and document pipeline; expose that page to every role currently registered in Staff Workspace: `cs_agent`, `supervisor`, `complaint_officer`, `knowledge_manager`, `qa_analyst`, `management`, `admin`.
- Grant those seven roles `knowledge.read` and a narrowly scoped `knowledge.document.ingest` permission for document upload and retry. Preserve `knowledge.write` for Knowledge Manager article authoring only. Do not grant document ingestion to `customer` or service role `ai_agent`; do not add any edit/delete permission or endpoint.
- Backend dependencies remain authoritative and require a verified human principal. `GET /v1/knowledge/documents` and `GET /v1/knowledge/documents/{document_id}` require `knowledge.read`; `POST /v1/knowledge/documents/upload` and `POST /v1/knowledge/documents/{document_id}/retry` require `knowledge.document.ingest`. These document-workspace routes do not accept service tokens, even when a service role has matching scopes. `GET /v1/knowledge/search` remains available to the existing AI service permission for retrieval. All database operations continue to use the verified principal's tenant. No browser role or permission value is accepted as authorization.
- Frontend route audience and navigation use an explicit staff-role allowlist for user experience only; API permission checks remain mandatory.
- Detail view calls the existing tenant-scoped detail endpoint. The view shows metadata and error status only, never serves the original file to customers.
- Customer chat remains on its existing route and shared retrieval/orchestration path. Ready uploaded document chunks remain tenant-scoped retrieval evidence.

## Verification requirements

- Backend role matrix: each allowed staff role reads documents and uploads; customer is denied document list/detail/upload/retry; service role `ai_agent` is not given upload permission; article authoring remains restricted to existing `knowledge.write`; cross-tenant reads/retries remain hidden.
- Retrieval: a Staff Workspace role uploads a document and the existing chat turn returns its citation.
- Frontend role matrix: every Staff Workspace role gets a Knowledge Base navigation link and route audience; `customer`, `ai_agent`, and unknown roles do not.
- Run the existing knowledge tests and backend suite against a fresh temporary SQLite database and temporary upload directory, plus the frontend access tests and production build. Do not use the repository's existing test DB or local upload directory.

## Verified results (2026-10-27)

- Knowledge API tests: **35 passed**.
- Full backend suite with process-only `LLM_PROVIDER=stub`, a fresh temporary SQLite DB, and a temporary upload directory: **139 passed, 1 skipped** (163 existing dependency deprecation warnings). The first full-suite run used the local Gemini setting and had two unrelated provider-default failures; no `.env` setting was changed.
- Frontend role/navigation tests: **2 passed**. Production build: **passed**, Vite transformed 33 modules.
- Coverage includes every allowed role uploading/listing/opening document detail; staff retry; customer denial for read/upload/retry and forged `X-Role`; service-token denial from document management endpoints while preserving AI search/retrieval permission; article-authoring separation; tenant-isolated list/detail/retry; and a chat turn citing a document uploaded by a customer-service agent.
- No live customer or authenticated browser session was used. Frontend route authorization was checked by the role/navigation unit test and production build; backend remains authoritative.
