# Customer portal: request, tracking, and account first slice

Status: requester-authorized incremental UI scope (2026-10-27); this does not close Unit 06 or Unit 07.

## Current evidence

- The customer routes `/customer/requests/new`, `/customer/requests`, and `/customer/account` exist in `web-workspace/src/App.jsx` but render Unit placeholders.
- Authenticated customers can send a `WEB_CHAT` message through `POST /v1/chat/messages`, list only their conversations through `GET /v1/customer/conversations`, and read their own transcript through `GET /v1/conversations/{id}/read-model`.
- The customer role has `conversation.write` and `conversation.read`, but no `case.create` or `ticket.create`. Existing case create, ownership, CRM outage, customer status, and migration decisions in the Unit 06 draft remain open.
- Conversation messages are immutable (FRD BR-CONV-06) and no delete endpoint exists. Do not add a customer delete action or imply records can be erased.
- No customer profile read/update endpoint or durable editable customer profile was found. The local development session exposes only the signed principal identity.

## Authorized first slice and user-visible semantics

1. **Kirim Permintaan:** provide a validated free-text form and send through the existing authenticated customer chat endpoint. Preserve the idempotency key on retries. Existing BR-CONV-01 may append to an open conversation within 72 hours, so the UI must not promise a separate new conversation. Show the resulting conversation and existing handoff/answer states. Copy must say this creates a service message; it does not claim to create a formal case/ticket or guarantee a human chat session.
2. **Lacak Permintaan:** show only the signed-in customer's own conversations from the existing paginated API, with a customer-friendly allowlisted label for conversation state and last activity. Opening an item routes to the existing customer chat/read-model ownership check. Do not display raw internal status or infer that a case/agent session exists.
3. **Akun:** show only fields available from the verified session (customer actor identifier, role/session state) and use existing logout. Do not expose tenant IDs or invent editable profile/contact data. State clearly that profile editing is not available in this local account implementation.
4. **Riwayat:** add a clear new-conversation path and explain that conversation records are not deletable from the portal. Do not add destructive operations.

## Explicit boundary

This is a useful conversation-based customer request flow, not complaint/case intake. Formal case creation, customer case list/detail, authoritative case status projection, evidence upload, CRM receipt semantics, and human-agent reply sessions remain outside this slice until Unit 06 authorization/assurance and data-contract decisions are approved and implemented. The current requester's instruction authorizes these portal pages and use of existing customer conversation APIs only; it does not grant `case.create`/`ticket.create`, change assurance, create schema, or approve status/CRM policy.

## Acceptance evidence

- Customer-only routes render the scoped components; staff/public principals remain denied by the shared route shell.
- New request sends once through the existing endpoint and appears in the customer's owned conversation list; retry uses the same idempotency key.
- Tracking uses the existing tenant/customer-scoped list and owned transcript route; no raw backend status is rendered.
- Account shows no tenant or secret and logout clears the local development session.
- History offers new conversation and contains no unsupported delete control.
- Empty, loading, error, and responsive states follow existing portal styles.
