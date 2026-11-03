# Unit 03: Role Navigation and Application Route Shells

Status: completed; implementation and build verified on 2026-10-13.

## Problem

The React/Vite SPA uses one dashboard-first page, button-driven local state, and a role selector that sends caller-controlled identity headers. It has no URL routes, no customer landing experience, and no authenticated session/token-provider boundary.

## Outcome

Deliver a customer-first public shell and URL-based customer/staff route groups with role-specific navigation. Reuse existing operational components where their role permits. The API client sends bearer credentials only when a trusted token provider is configured; no fake login or role-based identity is added.

## Scope

- Replace local page switching with a small History API router using existing React (no router dependency).
- Add customer portal landing, chat, request submission/tracking, conversation history, and account route structures. Unsupported workflows show clearly labeled future-unit/authentication states, not fabricated functionality.
- Add distinct staff navigation for CS agents, supervisors, complaint officers, Knowledge Managers, QA analysts, management, and administrators. AI agent is a backend service identity, not an interactive human workspace role.
- Keep the existing queue, conversation, case/ticket, approval, QA, analytics, SLA, and audit components and expose only relevant routes per role.
- Replace role-header API identity with an injectable bearer-token provider contract. Treat provider principal as navigation UX state only; backend remains authorization authority. No provider is configured by default.
- Add accessible unknown-route, unauthenticated, forbidden, loading, and unavailable states. Make navigation responsive and keyboard operable.
- Update UI context and progress/traceability documentation for concrete design and route decisions.

## Dependencies

- Units 01 and 02; React 18/Vite 5 and existing CSS.
- Trusted human issuer and account provisioning are not present; UI must disclose that integration boundary and avoid protected API calls without a token.

## Affected boundary

`web-workspace/src/App.jsx`, `api.js`, `app.css`, React entry point if needed, UI context, and this specification/progress documentation.

## Acceptance criteria

- `/` opens a customer-first service portal with clear, usable customer actions.
- Customer and staff shells have distinct navigation and responsive layout.
- URL navigation, browser back/forward, refresh, unknown routes, unauthenticated routes, and forbidden role routes behave predictably.
- Role navigation comes only from the configured authentication provider session; no role picker or legacy identity header establishes access.
- Protected API calls require a bearer token; missing credentials produce a clear auth-required error; 401/403 handling does not retry-loop or expose tokens.
- Unsupported customer/role workflows are clearly labeled and do not claim backend completion.
- Existing business pages remain buildable and use the shared shell.
- Build succeeds; route/API-client behavior is verified with available checks. Browser verification is recorded only if an actual browser is available.

## Verification

- `npm run build` in `web-workspace`.
- Add focused API-client/router tests only if a test framework exists; otherwise verify route manifest and build, and use a running browser if tooling is available.
- Inspect source to confirm no request emits `X-Role`, `X-Actor-Type`, or `X-Actor-Id`.

### Results

- `npm run build` in `web-workspace`: passed with Vite 5.4.21; 32 modules transformed.
- Source search across `web-workspace/src` found no role/actor identity header names or legacy role registry.
- Nginx `try_files` and Vercel catch-all rewrite both support direct SPA routes and refresh.
- No frontend test framework or browser automation is configured; no browser run is claimed.
- Provider absence is represented explicitly. Protected pages remain inaccessible until a trusted provider supplies a session and signed access token; no identity issuer is part of this unit.

### Visual shell refresh (2026-10-16)

- Reworked the existing customer/staff shell presentation into a charcoal-green rail, warm paper workspace, local typography, responsive menu drawer, and desktop collapse control. Routes, route manifest, session-derived navigation, bearer-token boundary, and backend authorization are unchanged.
- Updated the public landing and shared operational primitives. No new UI or animation dependency was introduced and no remote font is loaded.
- `npm.cmd run build` passed after the refresh. The running Vite app returned HTTP 200 and was visually inspected in headless Edge at 1440px desktop and a 390px emulated mobile viewport. Keyboard Enter was verified for opening the mobile menu and navigating to the protected chat route; Escape closes the drawer and restores focus; desktop collapse was verified by browser click. Full route-by-route keyboard/screen-reader and authenticated staff journeys remain unverified; screenshots are not full E2E/accessibility sign-off.
- Reference site `https://emitra-app.vercel.app/` was inaccessible through the available web inspection tool. The separate `UX for AI week 07 gabungan.pdf` was not found in the repository, so the redesign uses the visual directions and seven pattern names supplied in the task, not claims about inspected reference details.

### Delivered routes

- Customer: `/`, `/customer/chat`, `/customer/requests/new`, `/customer/requests`, `/customer/conversations`, `/customer/account` (structural placeholder).
- CS agent: `/agent/queue`, `/agent/conversations`, `/agent/cases`.
- Supervisor: `/supervisor`, `/supervisor/queue`, `/supervisor/cases`, `/supervisor/approvals`, `/supervisor/sla`, `/supervisor/audit`.
- Complaint officer: `/complaints`; Knowledge Manager: `/knowledge`; QA analyst: `/qa`; management: `/management`; administrator: `/admin`.
- `/` is public; all other routes require an injected session and matching presentation role. Backend permissions remain authoritative.

## Risks and open decisions

- The external identity provider must define its browser adapter and trusted principal/session lifecycle before protected pages can call the API.
- The backend role matrix includes `customer`, and API tests mint signed test credentials for that role. There is no trusted production issuer or customer account provisioning, so protected customer UX remains unavailable in the default deployment.
- Existing Vercel/Nginx hosting must preserve SPA fallback for deep links; verify current deployment configuration.
- Existing operational components expose prototype actions/raw JSON from earlier units. This shell does not complete or redesign those workflows.
