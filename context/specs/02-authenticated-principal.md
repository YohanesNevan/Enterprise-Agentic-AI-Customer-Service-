# Unit 02: Authenticated Principal and Backend Authorization

Status: implementation and backend verification complete; external identity provisioning remains an integration dependency.

## Goal

Replace trust in caller-provided role/actor/assurance headers with a server-verified bearer principal. Enforce the existing FRD permission boundaries and customer ownership on the inspected resource APIs, and prove spoofed identity and invalid-token requests fail.

## Design and verified contract

- TRD §11.1 (p. 57): human JWT access token lifetime 15 minutes; refresh token lifetime 8 hours, rotation/revocation state in Redis; service tokens are signed, short-lived, scoped, and use a key per service. The TRD does not specify JWT claim names, an issuer integration, or a token-issuance endpoint. No user/account model or JWT verifier exists in source.
- Use the already declared TRD libraries `python-jose[cryptography]` and `redis` by making them available in the local requirements set; do not add an identity provider or password/account database.
- Document the application validation contract: issuer and audience from environment; fixed HS256 algorithm; required `sub`, `iss`, `aud`, `iat`, `exp`, `jti`, `tenant_id`, `role`, and `token_use`; access lifetime ≤900 seconds. Service token uses a service ID selected from a server-configured per-service key map and a `scope` array intersected with the server role permission set; max lifetime 300 seconds. Refresh token lifetime ≤28,800 seconds; consume each refresh `jti` once using Redis `SET NX` with expiry and rotate on success.
- A trusted identity issuer must mint initial human access/refresh tokens with the configured signing key. This unit does not invent a login/password flow. Missing keys or refresh-store outage fail closed; no fallback to headers or privileged defaults.
- Permission source is FRD §4.2 pp. 20–22. Add the documented `knowledge_manager` role with only existing knowledge permissions; remove conversation content access from `admin` per RBAC-05. Other route permissions remain constrained by the current FRD matrix and explicit route use.
- Keep the unauthenticated status-reference route as the documented T1 exception, but return only generic customer-visible status and never trust `X-Assurance`. Other protected routes require a valid access/service token.

## Implementation

### Principal and token validation

Add a typed authenticated principal and bearer dependencies under `app/core/`. Derive actor ID from verified `sub` (or configured `service_id` for service tokens), actor type from token type/role, tenant from signed claims, and effective permissions from the server role map; service permissions are the intersection with token scopes. Ignore legacy `X-Role`, `X-Actor-Type`, `X-Actor-Id`, and `X-Assurance` values.

### API enforcement and ownership

Apply the principal dependency to protected endpoints, secure readiness metadata, correct ticket lookup to `ticket.read`, enforce customer/tenant predicates for case, ticket, and conversation reads, prevent a caller-supplied agent ID from changing queue ownership, and prevent identity/tenant claims in request bodies from overriding the principal. For customer chat, bind the customer identity from the verified principal. Keep status-reference output coarse for unauthenticated callers and allow authenticated detail only for the matching customer at AL2+.

### Existing role policy

Apply the two confirmed FRD mismatches: `knowledge_manager` is a distinct role; `admin` has no conversation-content read. Do not give Knowledge Manager permissions to admin or supervisor as a workaround. Keep human/service role claims allowlisted and intersect service scopes with role permissions.

### Regression tests and compatibility

Add token test helpers that sign test credentials directly; migrate existing API tests from role headers to bearer tokens. Test missing/invalid/expired/wrong-purpose tokens, role and actor header spoofing, service-scope intersection, customer cross-resource reads, customer-visible status, admin content denial, Knowledge Manager allowed/other role denied, request-body actor spoofing, and normal authorized workflows. Update worker clients to use scoped service tokens or fail clearly when service credentials are absent.

## Dependencies

- `python-jose[cryptography]` (already declared in `requirements-full.txt`; JWT validation and signing).
- `redis` (already declared in `requirements-full.txt`; one-time refresh-token rotation/revocation state).

## Verify when done

- [x] No protected route accepts caller-provided role/actor/assurance headers as identity.
- [x] No credential or configuration absence falls back to a privileged identity.
- [x] Access/refresh token signature, issuer, audience, purpose, required claims, expiry, and maximum lifetime are checked.
- [x] Service tokens use per-service keys and cannot exceed configured service role/scope allowlists or role permissions.
- [x] Refresh tokens rotate once; replay is rejected; Redis outage fails closed.
- [x] Customer case/ticket/conversation data is scoped to signed subject and tenant; status reference never returns internal status.
- [x] Queue acceptance actor is principal-derived; body/header spoofing tests fail safely.
- [x] Admin cannot read conversation content; Knowledge Manager can perform knowledge write operations only.
- [x] Existing authorized workflow tests pass after migration to signed test tokens.
- [x] Token values are not included in authentication error responses; tests exercise only opaque bearer values.
- [x] `python -m compileall -q app tests` and `python -m pytest -q -p no:cacheprovider` passed (28 tests).

## Risks and unresolved integration

- No issuer or user provisioning/account lifecycle exists in the repository. Initial token issuance remains an external trusted integration; its actual issuer, secret distribution, and claim-construction contract must be configured before a deployment can authenticate users.
- Existing DB entities do not all contain tenant IDs; several queries use joins to tenant-bearing parents. Staff assignment-level data access remains unmodeled and requires a later schema/workflow decision.
- TRD §16 contract approval is absent; claim names and fixed HS256 are this implementation contract, not a claim that external partners have signed it.
