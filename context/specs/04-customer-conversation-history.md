# Unit 04 — Customer Conversation and History API

Status: implementation completed for the local customer workflow; local configuration repair and staff development-auth preparation are recorded in the 2026-10-13 progress entry. No browser-based verification is implied.

## Objective

Provide a safe, authenticated customer conversation API using the existing FastAPI, SQLAlchemy, conversation service, and orchestration flow. A customer can start or continue a conversation and retrieve only their own conversation list and customer-safe history. Preserve existing staff and channel-adapter contracts except where a demonstrated ownership or replay defect requires a compatible correction.

## Repository and requirement evidence

### Requirements source

- FRD-EAICS-001 is version 0.9 and marked draft for mentor review (PDF p. 1 and document-control section). Treat it as the repository's current product source while retaining that approval caveat.
- FRD §6.2, pp. 31–34: FR-CONV-001 unified conversation identity; FR-CONV-002 identity resolution; FR-CONV-003 chronological history and stable cursor pagination; FR-CONV-004 attachment handling; FR-CONV-005 channel delivery; FR-CONV-006 channel continuity. Relevant rules include BR-CONV-01 (72-hour continuity default), BR-CONV-03 (one customer or unidentified handle per conversation), BR-CONV-05 (immutable conversation ID), and BR-CONV-06 (messages are immutable).
- FRD §5.2, p. 24: cross-channel continuity occurs only after identity resolution; ambiguous identity must not merge conversations.
- TRD §6, pp. 29–31: tenant-bound entities, conversation/customer relationship, channel sessions, immutable sequenced messages, and unique `(channel, provider_message_id)` deduplication constraint.
- TRD §7.3, p. 40: `GET /v1/conversations/{id}/read-model` is the documented cross-team workspace projection; it is not an adequate customer list contract by itself.
- API identity remains Unit 02's signed JWT principal. The code's `ROLE_PERMS` currently **does include** `customer` with conversation read/write permissions. This corrects the stale statement in prior Unit 03 notes that the role was missing.

### Existing implementation inspected

- `app/core/rbac.py`: validates signed bearer access credentials, maps `sub` to `actor_id`, permits the `customer` role, and provides `conversation.read` / `conversation.write`. Unit tests sign customer credentials with `tests/auth_helpers.py`; this is test-only, not a production issuer.
- `app/modules/routes_a.py`: `POST /v1/channels/{channel}/inbound` and `POST /v1/chat/messages` accept untyped `dict` bodies and use the verified actor as customer identity for customer principals. A first chat message creates a conversation; a request with `conversation_id` appends to it, then invokes `Orc.run_turn`. The route discards the ingest result's `conversation_id`, and current orchestrator responses do not consistently return it, so a new customer client cannot reliably continue the first-created conversation.
- `GET /v1/conversations/{conv_id}/read-model` checks tenant and customer ownership and returns a narrower customer projection. There is no customer-owned conversation list endpoint. The staff read model is separate at `GET /v1/workspace/conversations/{conv_id}` and explicitly denies customer principals.
- `app/modules/conversation.py`: performs 72-hour continuity, seven-day reopen, message persistence, and provider-message replay lookup. It currently checks `provider_message_id` globally before tenant, channel, and owner checks, then returns the prior `conversation_id`; a different customer reusing a provider ID can learn another conversation ID and the chat route may pass that ID to the orchestrator. Its continuity and reopen queries filter by `customer_id` but omit `tenant_id`, so matching customer IDs across tenants can be linked. Fix both defects before customer endpoints are considered safe.
- `app/modules/models_a.py`: `ConversationRow` has nullable `customer_id`, `claimed_customer_id`, tenant/channel/status/timestamps; there is no customer account table or FK that validates an issuer subject-to-customer mapping. `ChannelSessionRow` has no tenant column; `MessageRow` has sequence, author, content, citations, and indexed `provider_message_id`, but no unique `(channel, provider_message_id)` or `(conversation_id, sequence_no)` constraint. `MessageRow` lacks a request-idempotency record. Several model fields have Python defaults, not database `NOT NULL` constraints.
- `tests/test_security_auth.py` covers missing/invalid credentials, customer ownership on read/append, and signed customer roles. `tests/test_a_skeleton.py` covers channel continuity and provider-ID duplicate replay for staff/service callers. There is no regression test for provider-ID collision across customers, customer listing, stable pagination, or a retried browser send.
- `app/core/errors.py` defines the application error envelope/status mapping. FastAPI request-model validation defaults need explicit integration with that convention if Pydantic request schemas are introduced.

## Identity and authorization boundary

- Every customer API operation requires a valid signed access bearer token, `role=customer`, a trusted `sub` equal to the customer actor ID, and the validated tenant claim. Missing/invalid credentials return 401; authenticated non-customer roles receive 403 for customer-only operations.
- Never accept `customer_id`, `claimed_customer_id`, `from_handle`, `author_id`, `author_type`, tenant, assurance level, or channel-session identity as proof of ownership from a customer request. Derive actor and tenant from the verified principal. Reject or ignore non-contract fields consistently; never let them override principal values.
- Every detail, history, append, list, replay, and idempotency lookup must bind both tenant and actor/customer ID. Use the existing not-found convention for cross-customer IDs to avoid confirming resource existence.
- The customer role exists, but there is no trusted production identity issuer, account provisioning, or approved customer claim lifecycle in this repository. API tests use signed test helpers. Production customer sign-in remains disabled until the issuer guarantees that `sub` maps to the persisted customer ID in the correct tenant. A later explicit task authorized a constrained, opt-in local fixed-account login; it cannot accept self-asserted IDs or roles.
- Channel assurance is per `ChannelSessionRow`, not per conversation or API JWT. Do not copy AL values from request bodies or carry assurance between channels. AL/step-up behavior remains owned by the existing auth/orchestrator services; Unit 04 must not infer successful business identity verification from a customer JWT alone.

## Scope and API contract

### Included

1. Preserve `POST /v1/chat/messages` as the customer send/start operation. Validate channel and message fields; allow an optional existing conversation ID only after principal ownership checks. New conversations are owned by the authenticated actor. Customer HTTP requests use `WEB_CHAT`; email/contact-form/WhatsApp simulator traffic stays on the trusted adapter/service path rather than allowing the browser to claim another channel.
2. Add the proposed `GET /v1/customer/conversations` route (FRD specifies the own-history behavior but not this URL) to list only conversations where `(tenant_id, customer_id)` match the principal. Return customer-safe summary fields only, newest activity first, with bounded page size and a stable continuation cursor.
3. Extend/retain `GET /v1/conversations/{conversation_id}/read-model` for a customer-safe detail/history projection. Preserve the existing path and its staff contract. Customer messages are ordered consistently by `(occurred_at, sequence_no)`; return message ID, channel, direction, author type, content, language, timestamp, and valid customer-visible citations. Never return tool arguments/results, internal flags, customer directory data, internal notes, raw channel-session assurance/auth events, or staff-only linked-object details.
4. Support stable cursor pagination for customer history when it exceeds the page bound. Cursor contents are untrusted input and must be validated; the query remains constrained by tenant and owner regardless of cursor fields. Do not regress current staff read-model behavior or exceed the documented output boundary.
5. Scope continuity and reopen searches to both authenticated tenant and customer; a customer ID match in another tenant must never attach/reopen a conversation.
6. Make provider-message deduplication tenant/channel-safe and non-disclosing. A replay belonging to the same owner returns an idempotent response; a duplicate identifier associated with another tenant/customer must not return that conversation's ID or be passed to orchestration.
7. Return the created/continued `conversation_id` with each successful chat turn so the client can continue and retrieve the same resource. Make append and response behavior transactional enough that a persisted inbound message cannot silently be processed twice after a retry. Return the existing application's structured success/error responses and only claim AI/handoff/citation outcomes that were actually persisted or returned by the orchestrator.

### Proposed wire shapes for Unit 05 integration

These shapes are additions to the current code, not claims about existing endpoints. Keep existing A/B and channel-adapter response contracts compatible.

- `POST /v1/chat/messages`: JSON request contains required `text`; optional `conversation_id`; optional `channel` only if omitted/defaulted to `WEB_CHAT` (customer browser requests with any other channel are rejected). Proposed `Idempotency-Key` header is required for new/retried customer turns after the decision below. The customer schema does not accept identity, tenant, author, session, assurance, provider-message ID, attachment, or tool fields. Preserve the existing schema and behavior for trusted staff/service callers.
- Successful response preserves all existing top-level orchestrator result fields and adds `conversation_id` (an additive response change). Keep `turn_id`, intent/reply, citations, handoff/clarification/degraded indicators as emitted; do not synthesize a reply or success flag. Same-key customer replay returns the stored successful result and does not rerun the turn.
- `GET /v1/customer/conversations?limit=...&cursor=...` returns `{ "items": [{ "conversation_id", "status", "language", "origin_channel", "current_channel", "created_at", "last_activity_at" }], "next_cursor": "..." | null }`. Do not include message bodies or internal conversation fields in list summaries. Proposed default limit 20 and maximum 50 require confirmation.
- `GET /v1/conversations/{conversation_id}/read-model?limit=...&cursor=...` retains the existing `conversation` and `messages` top-level keys for customers and adds `next_cursor`. Customer `conversation` fields are limited to `conversation_id`, `status`, and `language`. Each customer message includes `message_id`, `sequence_no`, `channel`, `direction`, `author_type`, `content`, `language`, `occurred_at`, and customer-visible `citations`; omit `author_id`, `tool_call_ids`, staff-only events, and internal metadata. Proposed default history page size 50 and maximum 100 require confirmation. Omitted pagination parameters should preserve the current response behavior where safe, or be introduced compatibly for existing clients.
- The list cursor uses the deterministic `(last_activity_at, conversation_id)` ordering; message history cursor uses `(occurred_at, sequence_no)`. Cursor encoding is opaque to clients, validated server-side, and never substitutes for tenant/owner filters.

### Explicitly excluded

- Building or configuring the external identity provider, customer account lifecycle, or production customer credentials. A fixed-account, opt-in local-only login was added under the explicit follow-up task authorization.
- Complaint/ticket portal journeys (Units 06–07), attachments/storage, outbound email/WhatsApp delivery, streaming, or redesign of AI/RAG policy.
- Changes to staff workspace projections except compatible security fixes proven necessary by regression tests.

## Validation and error behavior

- Use typed request/response schemas at the customer boundary. Require non-empty text and enforce length/channel constraints only where the signed FRD/TRD or an existing contract gives a value; otherwise record the proposed maximum for owner approval before coding.
- Validate conversation ID format, channel enum, cursor format, page size bounds, and any idempotency header. Reject unsupported customer fields so identity/author/tenant spoof attempts cannot be mistaken for data.
- Use the existing error envelope and HTTP conventions: unauthenticated 401, forbidden 403, malformed/invalid input 400 (or documented validation status if the API-wide convention is explicitly updated), nonexistent or non-owned conversation 404, idempotency-key payload mismatch 409, rate limit 429, and transient upstream/unavailable errors 502/503. Do not leak SQL errors, tokens, raw identifiers, or another customer's existence.
- Preserve correlation IDs and audit required human history reads per the approved FRD R+ semantics; audit data must not include raw message content or credentials. Whether customer self-reads need a separate audit event is an open policy decision below.

## Idempotency and persistence decision

FRD/TRD require provider-event deduplication, and the approved build plan also calls for duplicate request protection. The repository has only `provider_message_id`; it has no browser request key, request ledger, or constraint. Do not treat a client-generated key as a provider ID.

**Implemented decision:** customer `POST /v1/chat/messages` requires an `Idempotency-Key`; the server stores only a SHA-256-derived key scoped by `(tenant_id, actor_id)`, a canonical body fingerprint, processing state, and completed response. Same key + same fingerprint returns the completed response without rerunning orchestration; changed content returns 409. A pending/failed record returns 409 rather than risking duplicate effects. Raw keys and message content are not copied into the ledger. Provider adapter deduplication remains a separate channel/provider-ID behavior.

No unique constraint was added to the legacy message table: the existing local database contents could not be safely audited against the deployment database and the repository's Alembic environment is incomplete. Reads use `(sequence_no, message_id)` keyset ordering; the remaining write-race/legacy-duplicate constraint requires the separately planned migration unit. Provider-ID collisions are tenant/channel checked and non-disclosing in service code.

## Frontend integration requirements

- The customer shell now connects `/customer/chat` and `/customer/conversations` to the customer send/list/detail APIs. Local sign-in is exposed only when the SPA's development flag is set; the API independently checks its own opt-in and server configuration.
- The SPA keeps the access token in memory, clears it on 401, and never stores it in URLs or browser storage. It retains a failed draft's idempotency key for retrying identical text; editing the text starts a new request key.
- The SPA must not store bearer tokens in URLs, logs, or conversation records; no customer identity is read from local storage or caller role headers.
- Local Vite at `http://127.0.0.1:5173/` has been started and returned HTTP 200 with the application title. This was a server/HTTP smoke check only; no browser rendering or visual inspection was performed.

## Acceptance criteria

1. Missing, malformed, expired, wrong-audience, and wrong-role credentials fail closed; no default customer principal exists.
2. A signed test customer can send a valid first message; its conversation and inbound/outbound history persist with the principal actor as owner.
3. The send response always includes the persisted conversation ID, including first-message creation and safe same-owner replay.
4. A customer can list and retrieve only their own tenant-scoped conversations; another customer's and another tenant's IDs return the safe not-found response.
5. A customer cannot append to another customer's conversation, alter owner/tenant/author/channel-session/assurance fields, or access staff-only read-model fields.
6. Continuity and reopen never link across tenants, even if the customer ID matches.
7. Reusing a provider message ID for the same scoped event does not create another message; collisions across owners/tenants reveal no IDs and cause no orchestration side effect.
8. Repeating a customer request with the same confirmed idempotency key and body does not create an extra inbound/outbound turn or repeat tool execution; reuse with changed content returns 409.
9. History order and pagination are stable, bounded, and tenant/owner scoped; citations are only the persisted customer-visible references.
10. Invalid body, channel, cursor, oversized content, empty content, and invalid idempotency key return the documented error envelope without persistence side effects.
11. Existing legitimate channel-adapter and staff read-model tests continue to pass; schema migration handles existing data safely and fails closed on unresolved uniqueness conflicts.
12. API and frontend tests verify the opt-in local fixed-customer login and never configure it outside development; production login remains explicitly unimplemented.

## Verification plan

- Focused pytest coverage for the criteria above, including cross-customer replay/idempotency and orchestration call counts.
- Existing full backend suite, migration upgrade test on a clean database, and migration conflict test with duplicate fixtures.
- Inspect serialized customer responses for prohibited fields and compare tenant/owner query filters for every read/replay path.
- Keep the local UI available for review; browser verification is a separate, explicitly reported check and is not a Unit 04 API test substitute.

## Dependencies, risks, and decisions

### Can implement with current dependencies

- Unit 02 principal and `customer` permission set are implemented. Signed test credentials are available; production token minting is not required to write server-side behavior and automated tests.
- Existing SQLAlchemy entities, conversation service, orchestration service, and Alembic are present. The unit can remain in the current modular monolith.

### Must be resolved before enabling live customer access

- Trusted issuer, tenant assignment, customer provisioning, immutable subject-to-customer mapping, key rotation, browser adapter, and logout/refresh lifecycle.
- Whether issuer `sub` is exactly the internal customer ID or requires a trusted directory mapping. Never assume from the role claim alone.

### Resolved implementation decisions / remaining gates

- Local decisions for this implementation: 4,000 character message ceiling; 20/50 customer-list page size default/max; 50/100 message-history default/max; text-only WEB_CHAT; existing `AppError` envelope (400 invalid, 401 unauthenticated, 403 forbidden, 404 non-owned/missing, 409 idempotency conflict). These are implementation defaults because draft FRD/TRD do not settle exact API limits.
- No separate audit event was added for customer self-reads; FRD's human R+ audit rule does not establish a customer self-read requirement. This remains a product/security policy decision.
- Production migration must be planned after duplicate-data inspection; no existing row is deleted or modified by this unit.

## Implementation decision record

- Local login route: `POST /v1/dev-auth/customer/login`. Disabled by default. It requires `ENVIRONMENT=development`, `DEV_CUSTOMER_AUTH_ENABLED=true`, one server-configured username/password (password minimum 20 characters), fixed `DEV_CUSTOMER_ID` and `DEV_TENANT_ID`, and a valid configured signing key. It accepts no role, actor, or tenant choice from the request; credentials are not returned. Startup fails if the feature flag is true outside development; requests are limited to loopback clients. Tokens are 15-minute HS256 access tokens validated by the ordinary `get_principal` path. The SPA memory provider loses the session on refresh/close. This is development-only, not production login.
- Staff development authentication preparation: `POST /v1/dev-auth/staff/login` is a separate loopback-only route, disabled unless `DEV_STAFF_AUTH_ENABLED=true` in development. `DEV_STAFF_ACCOUNTS` is a server-side JSON object mapping usernames to `{actor_id, tenant_id, role, password}`. Only username/password are accepted as credentials; identity and role are read from the allowlist. Roles are restricted to the existing human role map excluding customer; permissions are derived by the normal principal/RBAC path. Passwords require at least 20 characters and comparison is constant-time. This is local development support, not a production issuer, staff account lifecycle, or MFA. No staff credentials are committed or enabled by default.
- Local configuration repair (2026-10-13): the configured customer backend values and issuer/audience were present, but the signing key was below the implementation's 32-character minimum; it was replaced in ignored root `.env` with a generated 64-character random value. The UI's disabled message was caused by missing `VITE_ENABLE_DEV_CUSTOMER_AUTH` in `web-workspace/.env.local`; this local ignored file now enables customer login and leaves staff login disabled. The Vite-transformed `src/api.js` confirmed those effective flags. Do not copy local secrets into this specification or `.env.example`.
- Verification limitation: PostgreSQL and Redis were not listening and Docker Desktop's engine was unavailable. The SQLite-backed test suite passed, including the authenticated login-to-conversation-to-history path and ownership/tenant regressions, but live API startup and actual browser login/persistence were not verified. Redis is required for refresh rotation; PostgreSQL is required for application runtime persistence.
- Conversation API: customer `POST /v1/chat/messages`, `GET /v1/customer/conversations`, and customer-safe `GET /v1/conversations/{id}/read-model` with bounded cursors. Chat requires idempotency key, only accepts WEB_CHAT, and derives owner/tenant from the principal. The response contains the actual orchestrator result plus the conversation ID; stored history is fetched after send, so failed requests are not shown as delivered.
- Fixed provider replay lookup to enforce channel and tenant and deny collisions without revealing another conversation. Continuity and reopen searches now include tenant.
- Customer principals are denied direct `/v1/channels/{channel}/inbound` adapter access; customer web turns must use validated, idempotent `/v1/chat/messages`.
- `customer_chat_request` is introduced in SQLAlchemy metadata. The repository's development `create_all` creates it on startup; a reviewed production migration remains required. Legacy message uniqueness constraints were intentionally not introduced without data and migration-policy review.
- Frontend implements login, chat send/transcript, paged conversation list/history, loading/error/empty states, and logout. It uses existing tokens via the existing bearer-provider boundary.
- Runtime limitations: no approved production identity issuer/account provisioning; no authenticated browser token refresh, durable audit storage, or document migration environment. The local UI and APIs are not browser-E2E verified by this work.
- Verification executed: `python -m pytest -q -p no:cacheprovider` — 38 passed; `npm.cmd run build` — passed (32 modules). Local HTTP smoke returned 200 for Vite `/` and `/customer/login`; `/healthz` on port 8000 was unavailable. No browser automation was run.

## Unit boundary and affected files

Implemented touchpoints: `app/modules/routes_a.py`, `app/modules/conversation.py`, `app/modules/models_a.py`, `app/core/dev_auth.py`, `app/main.py`, `web-workspace/src/api.js`, `web-workspace/src/App.jsx`, `web-workspace/src/app.css`, `tests/test_customer_conversations.py`, `.env.example`, and `web-workspace/.env.example`. No legacy-data migration was added; see the migration risk above.

Dependencies in `context/specs/00-build-plan.md` remain Units 01–02. The earlier note that the `customer` role is missing is corrected: the role exists. Issuer/account provisioning is a production integration gate, not a reason to weaken or bypass the API contract.
