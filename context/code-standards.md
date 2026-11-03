# Code Standards

These standards describe the current Python/FastAPI/SQLAlchemy and React/Vite JavaScript stack; they do not authorize a framework migration.

## Organization and naming

- Python modules/functions/variables use `snake_case`; classes use `PascalCase`; constants use `UPPER_SNAKE_CASE`.
- Keep HTTP route registration, domain policy, and database persistence responsibilities explicit. Avoid adding unrelated behavior to `app/main.py` or `routes_a.py`.
- React components use `PascalCase`; hooks use `use...`; JavaScript variables/functions use `camelCase`.
- Group frontend components and page modules by shared responsibility; keep API transport logic in the existing API boundary rather than duplicating fetch/header construction.

## Types, validation, and APIs

- Use Pydantic request/response models for new or materially changed API contracts; validate lengths, enums, and required fields at the boundary.
- Preserve existing `/v1` paths and error envelope unless a documented compatibility decision approves change.
- Return explicit status/error feedback. Never encode a failed external operation as a successful queued result.
- Keep authorization and resource ownership checks in backend services/query boundaries, not only in UI visibility.
- Resolve protected-request identity only through `VerifiedPrincipal` from `app/core/rbac.py`. Do not trust caller role/actor headers. Apply both permission and tenant/owner predicates; client-supplied IDs do not establish ownership.
- Keep human signing, issuer, audience, service-key, service-role, and service-scope settings in environment configuration. Never log bearer tokens or copy secrets into tracked files.
- Frontend is currently JavaScript/JSX. Do not claim TypeScript checking; validate API payload assumptions and handle loading, empty, success, and error states.

## Database and errors

- Use SQLAlchemy sessions with bounded lifetime and explicit transaction boundaries. Do not add persistent module-global state for shared workflow data.
- Migrations belong in Alembic and must be forward-compatible; assess the existing `create_all` startup path before changing schema lifecycle.
- Map expected domain failures to the existing `AppError` contract; avoid leaking stack traces, credentials, or sensitive payloads.
- Log/trace with correlation IDs and mask sensitive values. Do not log OTPs, tokens, full payment credentials, or unnecessary customer data.

## UI and styling

- Use semantic HTML, labels, visible keyboard focus, accessible names, and consistent status language.
- Use `context/ui-context.md` tokens for colors, spacing, typography, and interaction states. Avoid page-specific inline styles when a reusable pattern exists.
- Shared components should have one behavior and one visual contract. Tables are preferred for dense operational records; chat uses a readable chronological timeline.
- Every control must work, be intentionally disabled with an explanation, or be identified as a prototype.

## Dependencies and verification

- Reuse installed dependencies. Add a package only when an implementation unit identifies a concrete need and records it.
- Avoid unreviewed dependency upgrades; Python requirement pins are currently incomplete.
- Follow existing pytest/FastAPI TestClient conventions for backend changes and the existing Vite build for frontend packaging. Add or run tests only as required by the active task authorization; report actual results without inference.
- Keep docs and progress tracker synchronized with approved decisions and completed verification.
