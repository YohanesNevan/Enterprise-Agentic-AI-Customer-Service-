# UI Context and Design System

Status: applied to the Unit 03 route shell. Tokens below are implemented in `web-workspace/src/app.css`; later unit work should extend these values instead of introducing competing tokens.

## Principles

- Customer and staff journeys are first-class; the internal analytics dashboard is not the application's universal home.
- Put the next useful action and current status before explanatory decoration.
- Show verified customer facts separately from AI summaries, suggestions, retrieved source text, and internal notes.
- Prefer readable lists/tables for operational work and a focused timeline for conversations. Reserve cards for grouped content, not every data point.
- Use plain language, explicit outcomes, and contextual empty/loading/error/success feedback.
- Only render data/actions authorized for the authenticated role and resource.

## Semantic color tokens

Suggested neutral palette: `canvas #F5F7FA`, `surface #FFFFFF`, `surface-muted #EEF2F6`, `text-primary #17212B`, `text-secondary #526171`, `border #D7DEE7`, `brand #155EEF`, `brand-strong #1249B8`. Status: `success #16794B`, `warning #9A5B00`, `danger #B42318`, `info #175CD3`. Always pair color with text/icon and test contrast; confirm values in implementation.

## Typography and spacing

- Use the existing system font stack unless repository review establishes a bundled typeface.
- Type scale: 12, 14, 16, 20, 24, 30 px; body default 16 px, dense table minimum 14 px, line height 1.45–1.6.
- Spacing scale: 4, 8, 12, 16, 24, 32, 40, 48 px. Use 8 px rhythm for common layouts.
- Radius: 4 px controls, 8 px panels, 12 px dialogs. Use subtle borders; elevation only for overlays and meaningful layering.

## Layout and navigation

- Shared internal shell: role-appropriate navigation, page title, concise context, main content. Customer-facing entry should feel like a service portal and not inherit admin navigation.
- Desktop: content max width around 1440 px; operational queue/detail can use a resizable two-pane layout. Avoid fixed widths that force horizontal page scrolling.
- Tablet: collapse secondary panels and allow contextual drawers. Mobile: single-column, compact navigation, full-width forms/actions, horizontally scrollable data tables with clear affordance.
- Use real URL routes for pages when introduced so refresh, deep links, browser history, and unauthorized route states behave predictably.

## Actions and forms

- Primary button: one per decision area; secondary actions are neutral; destructive actions require explicit confirmation and reason where specified.
- Button heights 40 px standard, 32 px compact. Preserve visible focus and disabled-state explanation.
- Place labels above inputs; associate errors with controls; validate on submit and preserve entered data on recoverable failure.
- Use dialogs for bounded confirmation, drawers for contextual detail, and pages for substantial workflows. Provide cancel/close and keyboard behavior.

## Tables, filters, and status

- Use semantic table headers, sortable/filterable controls only when implemented, clear result count, useful empty state, and pagination when server data requires it.
- Status badge colors follow semantic tokens; badge text carries meaning. Use consistent vocabulary from `app/contracts/vocabularies.py` and FRD.
- SLA displays include deadline, time context, and at-risk/breached explanation; never imply live countdown without current data.

## Chat and AI assistance

- Chronological messages with author and timestamp; distinguish customer, human agent, and AI visually and in accessible text.
- Show citations as source title/version and navigable details when supported. A suggestion is labeled “AI suggestion” and requires human action; an internal summary is labeled as generated and may be corrected.
- Handoff state/reason and customer next steps must be clear. Do not show internal notes or protected context to customers.

## Feedback and states

- Loading: preserve layout and announce meaningful pending work to assistive technology.
- Empty: explain why no records appear and provide a relevant authorized action.
- Error: use plain language, retain form input, offer retry when safe, and show correlation reference for support when appropriate.
- Success: identify what actually persisted or was queued; only claim external delivery after confirmed delivery state.
- Notifications must not rely on color alone and should be keyboard/screen-reader accessible.

## Accessibility and icons

- Target WCAG 2.2 AA where practical: contrast, keyboard operation, focus visibility, semantic landmarks, labels, error association, reduced motion, and responsive zoom.
- Use the existing text/Unicode icon conventions only where legible; prefer one consistent accessible icon set if a later unit demonstrates a need. Icons are decorative when adjacent text fully describes the action.

## Component conventions

- Reuse existing React and CSS approach; no UI framework is currently installed. Establish shared buttons, fields, badges, alerts, empty/loading states, table, and conversation components before duplicating page-specific styles.
- Avoid decorative gradients, large dashboard hero regions, excessive shadows, unexplained raw JSON, and controls with no behavior.

## Premium service workspace refresh (2026-10-16)

The current implementation extends the route shell with an editorial EAICS identity while preserving the React/Vite and History API structure:

- Main canvas uses warm paper and a deep charcoal-green navigation rail; mineral green marks primary actions. Amber remains reserved for pending/warning states, with separate success, information, and error surfaces.
- Typography uses local system sans-serif for controls/body and a Georgia editorial serif for display headings. No hosted font or UI dependency is required.
- Desktop navigation is a persistent rail with an accessible collapsed state. At mobile widths it becomes a focus-visible slide-in navigation with a close scrim; the page remains a single-column reading flow.
- Customer landing uses one prominent conversation path, a small number of linked service routes, and an explicit authentication note. It does not show fabricated service availability or activity metrics.
- Conversation starts with prompt chips that only populate the composer; they never send by themselves. Pending retrieval uses a skeleton, source chips appear only for citations returned by the API, handoff status text keeps queued and accepted distinct, and API errors include a recovery message.
- Safe resend remains bound to the existing idempotency key. A 401 points back to login and a 403 does not offer a retry. No regeneration control is shown because the conversation API has no regeneration contract.
- Motion is limited to short entrances, hover/focus feedback, and actual loading states; `prefers-reduced-motion` disables the animation/transitions.

LLM UX mapping is intentionally contract-bound: suggestions/prompt entry, talk-back errors, and available next routes are represented in the current portal. The API does not provide a structured restatement, regeneration/tweak, or explicit next-step contract, so the UI does not fabricate those capabilities. FRD v0.9 remains draft, TRD v0.9 refers to approved FRD v1.0, and the supplied `UX for AI week 07 gabungan.pdf` was not present in the repository during this refresh; listed UX patterns were taken from the task prompt, not from an inspected PDF.

## Unit 03 shell decisions

- `/` is a public, customer-first service landing page. Customer actions route to `/customer/chat`, `/customer/requests/new`, `/customer/requests`, and `/customer/conversations`; unavailable workflows identify their future unit and never fabricate records.
- Staff routes use a shared header and content frame with a route manifest and navigation derived from the injected authenticated session principal. The manifest is only a presentation boundary; backend authorization remains authoritative.
- The identity provider integration uses the exported `configureAuthProvider` contract in `src/api.js`. It supplies `getSession()` (including a verified principal for navigation) and `getAccessToken()`; no provider is configured by default. The application has no login form or token issuer.
- Protected API requests require bearer credentials from that provider. No role or actor headers are sent. 401 and 403 responses have separate user-facing states and are not retried.
- Implemented shell tokens: canvas `#F5F7FA`, surface `#FFFFFF`, primary text `#192B3A`, secondary text `#526575`, border `#DCE4E9`, brand `#176B65`, brand soft `#E0F1EF`. Standard radius is 10px; surfaces use a subtle border and low elevation.
- Desktop uses a centered content width up to 1120px and inline navigation. At 900px navigation becomes a keyboard-operable menu; at 600px customer actions become one column. Main landmarks, skip link, focus-visible outlines, and `aria-current` active links are required.
- Staff navigation is explicitly scoped: CS agent, supervisor, complaint officer, Knowledge Manager, QA analyst, management, and administrator each have separate route lists. AI Agent is a backend service identity with no interactive staff navigation. Administrator navigation contains no conversation content route.
