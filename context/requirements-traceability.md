# Requirements Traceability

Status: Unit 01 complete as a source and code traceability pass. This is not approval of draft requirements or proof that behavior passes at runtime.  
Documents reviewed: `FRD-EAICS-001` v0.9 draft (148-page PDF) and `TRD-EAICS-001` v0.9 draft (87-page PDF). TRD §1 and its cover say it was issued against FRD v1.0 frozen in Week 4; that signed/frozen FRD v1.0 is absent from this repository. Use the supplied FRD v0.9 as the working baseline and keep the version mismatch open.

## 1. Role, action, and data access baseline

Source: FRD §4.1–4.2, PDF pp. 18–22; TRD §3–4 and §11. FRD matrix uses `F` full, `O` own/assigned records, `M` masked, `A` aggregate only, `R+` read with reason, and `—` no access.

| FRD persona | Documented capabilities and data boundary | Current code evidence | Status / planned units |
|---|---|---|---|
| Customer | Own conversations and records only; personal data requires AL2; sensitive data AL3; status may use valid reference at T1; feedback on own interaction. | `customer` has generic `case.read`/`ticket.read`; no ownership predicate established in lookups; no portal UI. | Ownership unsafe; portal absent. Units 02–07. |
| AI Agent | Per-turn tool set intersects role, session assurance, tool declarations, and policy; may suggest/act only inside this boundary. | `ai_agent` and `tool_gateway.py` exist; deterministic orchestration/simulator results; actor headers are caller-controlled. | Partial prototype. Units 02, 04, 08, 11, 15. |
| Human CS Agent | Assigned/authorized conversations, handoff, responses, limited case/ticket updates, evidence requests, relevant knowledge; no self-approval. | `cs_agent` and queue/conversation/case APIs exist; shared UI, no proven assignment scoping. | Partial. Units 02, 03, 08, 10. |
| Supervisor / Team Lead | Queue/SLA/escalation oversight, reassignment, priority, justified SLA override, high-risk approval within limits, force escalation/reopen; cannot erase audit or self-approve; knowledge publication only if separately authorized. | Broad `supervisor` permissions, approval/analytics/reopen APIs; no distinct operational workspace. | Partial. Units 02, 03, 09–10. |
| Complaint Officer | Own complaint completeness, evidence, classification, justified resolution and root cause. | `complaint_officer` has case/evidence permissions; no distinct workspace or proven assignment scope. | Partial. Units 02, 03, 06, 09. |
| Knowledge Manager | Knowledge lifecycle and publication; no unrelated privileged access. | **No `knowledge_manager` role exists** in `ROLE_PERMS`; knowledge writing is assigned to supervisor/admin. | Role mismatch and lifecycle/UI gaps. Units 02, 03, 11. |
| QA Analyst | Reviews authorized evidence and scores; findings are separate objects; cannot mutate operational records. | QA endpoints/services exist; no dedicated review UI or verified evidence/masking boundaries. | Partial. Units 02, 03, 12. |
| System Administrator | Manages users/roles, tool registry, connectors and configuration; cannot read unmasked conversation/PII, delete audit, or approve business actions. | `admin` has `conversation.read`; no UI; masking/separation not enforced comprehensively. | Concrete permission mismatch. Units 02, 03, 14. |
| Management | Aggregate and anonymized drill-down; no individual case action or raw PII. | `management` has `analytics.read`; source/aggregation boundaries need proof; dashboard is default for all roles. | Partial. Units 02, 03, 13. |

FRD RBAC rules: RBAC-01 audit writes are system-only and append-only; RBAC-02 no self-approval; RBAC-03 AI tools are the intersection of role, assurance, tool requirements and policy; RBAC-04 no customer master updates in MVP; RBAC-05 admin content masking/task separation; RBAC-06 reasoned and audited `R+` reads. The FRD matrix, not current Python permissions, is authoritative.

### Unit 02 verification update

The earlier `Current code evidence` and `Status` cells above are the Unit 01 baseline and are superseded for authentication/authorization findings by `context/specs/02-authenticated-principal.md`. The API now validates signed bearer claims, rejects header identity, scopes reviewed customer resources and tenant operations, limits service permissions by server allowlists, and applies the documented Knowledge Manager/admin separation. `python -m pytest -q -p no:cacheprovider` passed 28 tests. Remaining limits: external issuer/provisioning is absent; assignment-level staff access and durable audit are not implemented; tenant fields are inconsistent and require a reviewed migration.

2026-10-13 follow-up: local development customer sign-in now has a configured frontend flag and a valid local signing key; a separate opt-in staff development allowlist route uses existing RBAC roles. Production customer/staff issuer and account lifecycle remain unavailable. This is not production authentication. See `context/specs/04-customer-conversation-history.md` and `context/progress-tracker.md` for the configuration and verification boundary.

## 2. Functional-domain traceability

Source: FRD §6.1, PDF p. 31; domain specifications §6, pp. 32–91; requirement-to-test links §17.3, pp. 142–144. Status is based on source inspection; no runtime/test success is implied.

| Requirement IDs | FRD domain / source pages | Repository evidence and gap | Planned units |
|---|---|---|---|
| FR-CONV-001…010 | Omnichannel conversation, pp. 32–36 | `conversation.py`, `routes_a.py`: four channel simulators, persistence/read models; customer history UI and complete I-11 contract incomplete; auth/tenant ownership unsafe. | 02, 04–05, 08 |
| FR-AUTH-001…010 | Customer identity/auth, pp. 37–41 | `auth.py` has AL/OTP simulation; challenge/consent/locks partly process-local; API principal is unverified headers. | 02, 04 |
| FR-INT-001…009 | Intent/context/sentiment, pp. 42–45 | `intent.py` deterministic keyword/rules; model evaluation and all requirement details not verified. | 08, 11–12, 15 |
| FR-KM-001…010 | Knowledge/RAG, pp. 46–50 | `knowledge.py` persists article/version and lexical search/citations; ingestion, lifecycle UI and vector retrieval not evidenced. | 11, 15 |
| FR-ORC-001…009 | Agentic orchestration, pp. 51–55 | `orchestrator.py`, guardrails/gateway exist; simulator outputs, limits and full provenance/audit not shown to meet all IDs. | 08, 10, 15 |
| FR-TOOL-001…009 | Enterprise tool/API integration, pp. 55–59 | `tool_gateway.py` policy/idempotency; `corebank.py` simulated; no dedicated registry manager. | 02, 10, 14–15 |
| FR-SVC-001…007 | Inquiry/service request, pp. 60–62 | Workflow/tool routes exist; customer service-request lifecycle incomplete; FRD A-02 specifies simulator integrations. | 04–07, 15 |
| FR-CASE-001…010 | Complaint/case CRM, pp. 63–67 | Case lifecycle rules/API exist; no customer-owned list/detail/submission journey; ownership/root cause completeness needs work. | 02, 06–07, 09, 13 |
| FR-EV-001…007 | Evidence, pp. 67–70 | Evidence request validation exists; quarantine/storage/scanning/upload lifecycle absent; upload-link is a stub. | 06–07, 15 |
| FR-WS-001…009 | Agent workspace/handoff, pp. 71–74 | Queue/handoff APIs/UI exist; B read model comments call itself a stub; full I-11 context and scoped data absent. | 02, 08–09 |
| FR-CP-001…006 | Agent copilot, pp. 75–77 | Suggestion endpoint exists; provenance/grounding and usable suggestion UI not established. | 08, 11–12 |
| FR-SLA-001…008 | SLA/escalation, pp. 77–80 | Business-hour calculation, records/tick/escalation exist; durable schedule and role workflow need verification. | 02, 09, 15–16 |
| FR-QA-001…007 | QA, pp. 81–83 | Sampling/review/finding/summary exist; no dedicated workbench or verified scorecard/consent coverage. | 02, 12 |
| FR-ANA-001…008 | Analytics/root cause, pp. 84–87 | Operational/resolution/handoff/QA/driver-tree exist; metric definitions/source/export/root cause not proven complete. | 09, 13 |
| FR-SEC-001…010 | Security/audit, pp. 87–91 | Header RBAC, correlation/audit/masking/gateway exist; identity, route inventory, audit atomicity, masking and attachment-security gaps remain. | 02, 10, 14–16 |

FRD §17.3 links the ranges to UT/IT/E2E/SEC/EVAL tests; p. 144 says every released FR must have at least one automated test. Existing skeleton tests do not establish full trace-to-test completion.

## 3. Security and data-access requirements

| Requirement | Source | Current observation | Planned work |
|---|---|---|---|
| Human API identity | TRD §11.1, p. 57: JWT access 15 min + refresh 8 h, rotation/revocation via Redis. Service identity: signed, short-lived, scoped tokens per service. | `app/core/rbac.py` does not verify bearer credentials; caller supplies role/actor headers and defaults to `cs_agent`/`agent-1`. | Unit 02. |
| Customer assurance | FRD §10, pp. 110–112: AL0 public, AL1 identified, AL2 verified (OTP), AL3 step-up; operation tier controls disclosure; T4 is request/ticket only until authenticated human approval. | `auth.py` simulates AL/OTP; identity matching is simplified; challenge state partly in memory. | Unit 02 identity boundary; keep customer AL separate in Unit 04. |
| Deny-by-default routes | FR-SEC-001/002, BR-SEC-02, p. 88, NFR-14 p. 141. Only public knowledge search and health are stated exceptions. Every route needs permission and role/class tests. | Many routes use `require_perm`, but principal is unauthenticated; exceptions/permission mapping not fully inventoried; `ticket_lookup` uses `ticket.create`. | Unit 02 inventory, permissions and exhaustive denial tests. |
| Tenant/customer isolation | FRD §4.1.1/§10; TRD §6.1/ADR-13: tenant column on every table and tenant-aware query/repository; customer own-data only. | Some rows have `tenant_id`, others (e.g. messages/session) do not; lookups by ID show no principal/tenant scope. | Units 02–04; schema work coordinated with Unit 16. |
| Separation of duties | RBAC-01…06, pp. 21–22. | Self-approval check exists; role boundaries and reasoned masked reads not comprehensive. | Units 02, 09–10, 12, 14. |
| Audit/correlation | FR-SEC-004/005, p. 89; TRD §12 pp. 64–66. Mutating audit must share transaction or operation fails. | Audit/hash chain and correlation middleware exist; complete transactional coverage is unproven. | Units 02, 09–10, 14–16. |
| Masking | FR-SEC-003/009/010; TRD §11 pp. 57–63. Mask response/log/prompt boundaries; admin content masked; secrets never logged. | `masking.py` exists; route-wide classification and boundary tests not established. | Units 02, 08, 12, 14. |
| AI policy/untrusted input | FR-SEC-006/008 pp. 89–90; FRD §14. Tool set and policy computed outside the model. | Gateway/guardrail exist; full injection suite/evaluation not evidenced. | Units 08, 10–12, 15. |
| Attachment safety | FR-SEC-007 p. 90; TRD §11.5–11.6 pp. 58–59: quarantine, content checks, scan/hash, authorized short-lived download; scanner unavailable means quarantine; file not sent to LLM. | Inbound rejects selected MIME/extension/size only; upload link is a stub; no scanner/storage lifecycle. | Units 06–07, 15. |

## 4. UX requirements and evidence

- **Customer:** FRD §4.1.1 and CONV/AUTH/SVC/CASE/EV; TRD API catalog §7.4/Appendix B lists `/v1/chat/*`, `/v1/attachments`, `/v1/status/{ref}`, `/v1/auth/*`. No portal exists. Status by reference must not expose internal status.
- **Agent:** FR-WS-001…009 and FR-CP-001…006; TRD I-11 is one read projection of transcript, intent, tool calls, citations, assurance per session and linked objects. Current B read model/UI are incomplete.
- **Supervisor/complaint:** FRD §4.1 and CASE/EV/WS/SLA/ORC/SEC; APIs partly exist, separate role workflow does not.
- **Knowledge:** FR-KM-001…010; draft/in-review/expired/archived sources must not answer customer questions; published versions immutable; citations identify article/version/passage. Current retrieval is lexical.
- **QA:** FR-QA-001…007; published scorecard, comments for deductions, findings separate from operational changes. Current APIs exist; no dedicated evidence review UI verified.
- **Management:** FR-ANA-001…008 and FRD §15; metrics publish formula/filter/source and allow source data export; management access is aggregate/anonymized.
- **Admin:** FRD §4.1/§4.2 RBAC-05; config authority does not grant content or business approval. Current `admin` includes `conversation.read`, a concrete discrepancy.

## 5. AI/RAG and integration requirements

- FRD p. 2: product resolves long-lived work, not just FAQs. AI has no direct data access; it reaches data/effects through 15 schema-defined/versioned tools behind external policy.
- FRD §14 and FR-ORC/TOOL/SEC: allowed tool set computed outside model; recommendation, approval and execution are distinct; denied/failed/timed-out calls cannot be described as success; high-risk requests require authenticated human approval.
- FR-KM-001…010 and FRD §6.5, pp. 46–50: version lifecycle, eligible published/unexpired sources, retrieval/citations and no-answer behavior. Current code does not establish vector RAG.
- FRD A-02 §1.2 p. 6: direct bank/CRM/messaging integrations are unavailable; realistic team simulators are in scope. Production external connectors are not missing MVP functionality; label simulator behavior.
- FRD A-03: managed/local LLM availability is an assumption; fallback is local model or classifier + extractive RAG. `.env.example` currently selects `stub`, which must be clear in UX.
- TRD §14.5 pp. 74–75 sequences Week 5 skeleton, Week 6 intent/handoff/workspace, Week 7 OTP/security, Week 8 knowledge/RAG/SLA and later QA/analytics. Current repository has partial walking-skeleton behavior; README calls remaining UI milestones deferred.

## 6. Non-functional and test acceptance

Source: FRD §17.1 pp. 140–141; TRD §13 pp. 67–71 and §14.1 pp. 72–73.

| ID | Target / verification | Consequence |
|---|---|---|
| NFR-01 | First AI response p50 ≤3s, p90 ≤6s on demo hardware | Instrument/measure; source presence is not evidence. |
| NFR-02 | Knowledge retrieval p90 ≤800ms | Measure retrieval path. |
| NFR-03 | Agent workspace p90 ≤2s | Test I-11 read model. |
| NFR-04 | 20 concurrent conversations, 200 messages/min, single node | Load test. |
| NFR-05 | Seed volume: 50 customers, 500 conversations, 300 tickets/cases, 60 articles | Reproducible seed verification. |
| NFR-06 | No unhandled crash in demo; degraded mode on dependency failure | E2E/failure tests. |
| NFR-07 | Allowlisted files, 10MB/file, 50MB/case, max 10/request | Server-side security tests. |
| NFR-08 | 100% handoff context in conversation workspace | Unit 08 usability check. |
| NFR-09 | WCAG 2.1 AA design target: keyboard, contrast, labels, focus | Critical-jouney keyboard + axe/manual. |
| NFR-11/12 | End-to-end correlation and audit each state change | Audit integration verification. |
| NFR-13/14/15 | No secrets/OTP/full account numbers; deny-by-default routes; masking on all surfaces | Secret, role-route and masking suites. |
| NFR-16 | Seed rebuild byte-identical | Run seed/checksum twice. |
| FRD §17.3 | Every released FR has automated test links; UT/IT/E2E/SEC/EVAL | Existing skeleton tests are insufficient evidence. |
| TRD §13.8 | Keyboard-only chat, handoff, approval, QA; axe plus manual review | Include during UI units and release. |

## 7. Approval state and safe defaults

FRD §1.3 pp. 7–8 and §17.6 list open questions with defaults if no decision by Week 4. TRD §16 pp. 79 onward says integration contracts require sign-off by both team leads, advisor, and mentor. No signatures are present in the repository. Do not describe defaults as approved. Safe work assumptions from the documents:

- Synthetic data only; no production data or direct real bank/CRM/messaging integrations (A-01/A-02).
- WhatsApp is simulator-only (A-04); supported channel simulators include web chat, email, contact form, WhatsApp.
- T4 actions create a request/ticket; no money movement, reversal/chargeback, or prohibited tool exists.
- If no managed LLM is available, use the documented local/classifier + extractive fallback; current `stub` mode must be disclosed.
- TRD JWT/service-token details are the target design, not implementation evidence.

Open approvals: canonical signed FRD v1.0; signed TRD §16 contracts (IDs, vocabularies, roles, tool schemas, I-11, audit envelope, errors, assurance); deployment profile and managed/local/stub LLM selection. These do not block designing the route shell, but protected actions cannot rely on frontend role selection.

## Unit 05 information conversation slice update (2026-10-13)

Source caveat: repository FRD-EAICS-001 v0.9 and TRD-EAICS-001 v0.9 are drafts. The TRD references frozen FRD v1.0, but no signed FRD v1.0 or signed TRD §16 integration approval was found. This update records implementation evidence against unambiguous draft requirements and does not represent final approval.

| Requirement ID / source | Required behavior | Actor / component | Existing implementation before this slice | Gap found | Planned/implemented change | Acceptance test | Verification status |
|---|---|---|---|---|---|---|---|
| FR-INT-001, FR-INT-004; FRD §6.4 pp. 42–44; TRD §4.5 | Closed taxonomy; unknown intent is not guessed and must hand off. | Customer; intent + orchestrator | Keyword classifier routes no-match text to `OTHER_UNCLASSIFIED`/HANDOFF. | Handoff reply claimed an agent connection without creating a queue entry. | Keep mandatory unknown-intent policy; persist tenant-scoped queue record, report queued/unavailable; mark package incomplete. | Unknown intent still handoffs; response state and `HandoffRow` agree. | Full backend suite passed. |
| FR-INT-003; FRD §6.4 pp. 43–44 | Clarify uncertain intent; recognized greeting is not unknown. | Customer; intent + orchestrator | “Halo” classified as small talk but fell into generic clarification. | Greeting did not receive an ordinary conversational response. | Deterministic greeting path without handoff; supported fee topic receives phrase evidence without lowering global threshold. | Greeting returns no handoff; fee question maps to information intent. | Focused tests passed. |
| FR-INT-007; FRD §6.4 p. 45 | Vulnerability/safety takes priority and requires handoff. | Customer; intent + queue | Vulnerability classification could force handoff. | Forced handoff was not connected to durable queue state. | Same queue-backed truthful handoff path; vulnerability raises queue priority/flag. | Existing fraud/vulnerability regression plus queue persistence. | Full suite passed; existing vulnerability regression passes. |
| FR-KM-003; FRD §6.5 pp. 46–48 | Use current published eligible sources, ground informational answer, cite source; abstain if evidence absent. | Customer; knowledge/orchestrator | Article status/access/expiry filter and lexical retrieval existed. | Version status/effective/expiry omitted; guardrail received empty evidence body; retrieval score omitted from citation. | Filter version lifecycle; validate against actual retrieved passage; preserve article/version/body locator/score in citation. | Grounded seeded fee response and persisted cited history; expired/draft source excluded. | Full suite passed; includes persisted citation and non-published-version exclusion tests. |
| FR-KM-004; FRD §6.5 p. 48 | Do not expose internal sources to customers. | Customer; knowledge retrieval | Customer access filter allowed PUBLIC/CUSTOMER only. | No new gap found in inspected query. | Preserve existing access predicate. | Existing knowledge access controls; full regression suite pending. | Existing implementation retained; broader verification pending. |
| FR-ORC-001, FR-ORC-006, FR-ORC-009; FRD §6.8/§14; TRD §4.8/§8 | Deterministic workflow; claims grounded; no false action or unconfirmed handoff. | Orchestrator, guardrail, queue | No LLM call in `run_turn`; deterministic services. | Source body was not passed to grounding; handoff copy overstated status. | Supply retrieved bodies, persist queue before claim, distinguish queued from accepted. | API tests assert citation grounding and queue/status truth. | Full backend suite passed. |
| FR-WS-001/002; FRD §7.2 pp. 71–74; TRD §4.13 | Queue handoff with routing metadata/context. | Orchestrator, queue, agent | Queue API/service exists but chat orchestrator did not invoke it. | No queue row on forced handoff; complete context package not implemented. | Create/reuse tenant-scoped row with reason, priority and `package_complete=false`. | Queue row is persisted and no second active queue row is created for same conversation. | Full backend suite passed including queue reuse; full context package remains Unit 08. |
| FR-CONV-003; FRD §6.2 pp. 31–34; TRD §7.3 | History retains chronological messages and source provenance. | Customer portal/read model | Customer history returns message citations; chat rendered them; selected history omitted them. | Customer history did not render persisted source references. | Render citation title and passage reference in selected customer history. | Frontend build plus browser history review. | Frontend build passed; browser review not performed. |

Implementation details and remaining scope: `context/specs/05-customer-information-conversation.md`. Full suite and build pass; Unit 05 remains in progress until browser/accessibility checks complete. Complaint requests still do not create a case/ticket in this slice, and customer-facing fallback explicitly makes no claim that they do. No real LLM inference was used.

## 8. Status and next work

- **Source present, runtime unverified:** portions of conversation, simulated auth, intent, lexical knowledge, orchestration/gateway, cases/tickets/evidence, queue/handoff, SLA/outbox, approvals, QA, analytics.
- **Missing or unsafe after Units 02-03:** external human token issuer/provisioning, exhaustive route/role tests, customer ownership schema completeness, customer workflow APIs, document processing, full I-11, UI accessibility evidence. The customer landing and role route shells exist, but protected workflows remain unavailable until authenticated provider integration and later workflow units.
- **Out of current MVP scope:** live bank/CRM/messaging integrations and real customer data per FRD assumptions.
- **Next:** Unit 04 — customer conversation and history API — follows the completed Unit 03 route-shell foundation.

## Unit 03 implementation update (2026-10-13)

- The public `/` route is now a customer-first service landing page. Customer chat, request creation/tracking, and conversation history have structural routes; unfinished journeys remain explicit placeholders.
- Staff route navigation is distinct for `cs_agent`, `supervisor`, `complaint_officer`, `knowledge_manager`, `qa_analyst`, `management`, and `admin`. AI Agent remains a service identity without human navigation. Administrator navigation does not include conversation content.
- Route presentation reads role only from the injected authenticated session provider. This is not backend authorization; protected API access requires the provider bearer token and the API enforces access.
- The frontend no longer emits caller-controlled role or actor headers. No trusted token issuer/login is implemented, so protected journeys remain unavailable in the default deployment.
- Vite production build passed. Browser-based accessibility/route verification remains outstanding.
- Next: Unit 04 — Customer conversation and history API — as defined in `context/specs/00-build-plan.md`.

## Unit 04 API inspection update (2026-10-13)

- Current `ROLE_PERMS` includes `customer`; prior baseline rows describing its absence are historical Unit 01 evidence. Signed test credentials can exercise the role, but no trusted production issuer/account provisioning maps customer subjects to customer records.
- Existing chat/read APIs and SQLAlchemy models were inspected. A customer history list is missing; the read-model route returns a reduced customer projection but does not yet provide stable pagination or all FR-CONV-003 fields.
- `ConvSvc.ingest` currently performs provider-message deduplication globally before owner/tenant checks and omits tenant filters from 72-hour continuity/reopen lookup. These are security defects to fix and test in Unit 04 before exposing customer conversation access.
- Unit 04 details and implementation gates are recorded in `context/specs/04-customer-conversation-history.md`.

## Unit 04 implementation update (2026-10-13)

- Reproduced the blockers: no initial trusted customer credential issuer existed; channel identify/challenge/verify routes are not application login. Chat persisted input but omitted the conversation ID from the orchestrator response; there was no customer history list and the frontend had no token provider or connected chat flow.
- Added an explicitly opt-in local fixed-customer issuer. It is disabled unless `DEV_CUSTOMER_AUTH_ENABLED=true`, requires `ENVIRONMENT=development`, server-configured credentials/actor/tenant and the existing signing key, is loopback-only, and mints a 15-minute customer access token validated by the normal principal dependency. Startup rejects enabled configuration outside development. The browser keeps the token in memory only.
- Added customer-scoped idempotency, validated WEB_CHAT message input, principal-derived ownership, response conversation ID, tenant-scoped history listing and cursor-paged detail. Non-owner details use 404. Provider-ID collision responses do not disclose another conversation; continuity/reopen now include tenant.
- Added the customer login, chat and conversation-history UI using actual API data and visible loading/error/empty states. No fake AI reply is added; the transcript is loaded from persisted messages after the API turn.
- Added the `customer_chat_request` table to ORM metadata. Existing tables and records were not migrated or altered. Local startup `create_all` handles the new ledger table; production migration setup remains a required follow-up before deployment.
- Verification: backend `python -m pytest -q -p no:cacheprovider` passed (38 passed); frontend `npm.cmd run build` passed (32 modules). No browser automation/visual verification was performed.
- Production issuer, account lifecycle, subject-to-customer/tenant mapping, access-token refresh for browser sessions, durable customer read audit policy, and a reviewed Alembic migration remain open.
## LLM provider contract preparation (2026-10-16)

Source status is unchanged: supplied FRD v0.9 is a draft; TRD v0.9 refers to signed/frozen FRD v1.0 that is not present; TRD §16 integration contract sign-off has not been confirmed. See context/specs/llm-provider-contract.md for the provider boundary, field-level F1–F4 mapping, assumptions, implementation scope, and test results. The local foundation below is implementation evidence, not approval of the provider contract or external provider.

| Requirement/source | Contract mapping | Planned evidence | Status |
|---|---|---|---|
| TRD §8.1, PDF p. 43; §8.2 | Four narrowly scoped functions: F1 intent refinement, F2 bounded clarification, F3 tool argument proposal from externally computed allowlist, F4 sourced answer with claim_map. Workflow state, permission, thresholds, tool availability/execution, approval, case creation, and closure remain code-controlled. | Per-function Pydantic schema/semantic tests; call-site/budget architecture test; orchestrator regression. | Local interface/schema/stub implemented in app/modules/llm_provider.py; focused tests passed (29). No orchestrator call site; runtime LLM calls remain zero. |
| TRD §8.1 F1 | Intent output must use V-1 enum and cannot determine final confidence. | Unknown-enum rejection; verify deterministic classifier/policy owns final confidence and decision. | Enum and finite 0–1 hint implemented; entity keys restricted to current intent slots. Hint does not mutate classifier/workflow. Exact hint/entity semantics still need approval. |
| TRD §8.1 F2 | Output question plus no more than three options; no internal codes. Clarification-attempt cap remains deterministic (§8.2). | Four-option rejection, code leakage rejection, deterministic fallback and max-attempt tests. | Nonempty question, 0–3 nonempty options and internal-code rejection implemented/tested. Orchestrator fallback/attempt-cap integration remains unwired. |
| TRD §8.1 F3; ADR-04; §16.3 | Model proposes one call matching an allowed tool schema; policy computes allowlist before prompt and re-evaluates specific arguments. Model/SDK cannot execute tools. | Out-of-set/malformed/cross-tenant argument rejection; assert executor not invoked. | Validator checks allowed name and matching Pydantic/JSON schema; no tool executor exists in provider module. Registry-wide schemas and policy/orchestrator integration remain unimplemented; signed §16 contract remains open. |
| TRD §8.1 F4; FR-KM-003; FR-ORC-006/009 | Answer text plus claim_map referencing current-turn eligible retrieval/tool evidence; grounding and action-state checks remain after generation. Unsupported output gets one strict retry then safe fallback/handoff (§8.2). | Missing/unknown source rejection; grounding, citation, action-state, fallback and retry-count tests. | Implemented nonempty claim mapping, answer-span check, and source-ID membership check. Full semantic grounding, caller guardrail integration, strict retry and fallback remain unwired; claim_map schema/granularity need approval. |
| TRD §13.9; §16.6 | Provider timeout, upstream error and rate limit enter degraded handling; errors must map to approved safe internal categories. | Timeout/rate-limit/provider failure contract tests and honest degraded response assertions. | Typed timeout/rate-limit/unavailable/config errors tested using fakes; no network timeout/config or orchestrator degraded fallback is implemented. Per-request timeout/retry unresolved; §8.2 total wall budget is 20 s. |
| TRD §13.11; §13.3 | Deterministic tests use stub and fixtures; real pinned model is isolated to explicitly approved EVAL/E2E runs. Provider/schema contract tests must fail on incompatibility. | Offline stub/unit and fake-provider contract suites; separately gated synthetic-only live integration suite. | Offline unit/contract tests implemented and passed (29); real-provider suite not implemented or run. |
| FRD §14, FR-SEC-006/008; TRD §11.5–11.6; §16.7 | Policy remains external to model; untrusted attachments stay out of model context; preserve masking, audit and no-secrets logging. | Adversarial provider regression, attachment-boundary and log canary/redaction tests. | Provider module has no authority/I/O and error text is redacted; backend suite passed (72). Full provider-to-orchestrator adversarial checks await call-site integration. Audit event schema/sign-off and provider data-processing terms unresolved. |

Open decisions: canonical FRD v1.0 and TRD §16 sign-off; provider and pinned model; endpoint/region and data retention; provider/model/key/timeout setting names and secret management; timeout/retry/rate-limit policy; F1/F2/F4 schema details; function enablement/call placement; log/audit events; and authorization for real-provider EVAL/E2E runs. Provider/API credential values are not part of this traceability record.

## Action and degraded response truthfulness (2026-10-16)

Trace: FR-ORC-006/009, FR-CASE-001, FR-WS-001, and TRD §13.9. `orchestrator.run_turn()` no longer says a ticket was created or that a human will help on the degraded branch, which does not create a ticket or enqueue a handoff. Its response and persisted outbound copy now agree and mark handoff `NOT_ATTEMPTED`. Card-block copy requires an actual `TEMP_BLOCKED` result and does not claim a delivery ticket; statement copy requires `sent is True`. The authorized `/v1/tickets` endpoint still reports ticket ID/status only after `Store.create_ticket_db()` commits, and a failed creation returns an error. Regression evidence: five focused tests passed; isolated backend suite passed 77 tests with 99 warnings. Existing queued vs accepted handoff wording remains distinct. This change does not implement Unit 06 or connect an LLM.

## Gemini adapter implementation update (2026-10-16)

| Requirement/source | Contract mapping | Evidence | Status |
|---|---|---|---|
| TRD §8.1–§8.2; provider contract | Isolated structured adapter for F1–F4, preserving interface and deterministic stub. | `app/modules/gemini_provider.py`; fake-client tests; focused suite 48 passed. | SDK `google-genai==2.31.0`, structured output and shared Pydantic validation. Not called by `orchestrator.py`; runtime calls remain zero and stub remains default. |
| TRD §13.9; §8.2 | Bound request time and map provider failures to safe internal errors. | Fake timeout, HTTP 429, network, provider, empty and malformed response tests. | `LLM_TIMEOUT_MS` defaults to 10000 ms and is capped at 20 s; SDK retries disabled. Conversation fallback remains separate because no orchestrator call site exists. |
| TRD §8.1 F3; ADR-04 | Model may propose only a tool in the external policy allowlist and cannot execute it. | Fake tests verify schema narrowing and absence of SDK tool executor. | Adapter has no executor/authorization access; final policy re-evaluation remains backend integration responsibility. |
| TRD §8.1 F4; FR-KM-003 | Preserve source membership/claim map validation; semantic grounding remains guardrail responsibility. | Shared Pydantic validation; guardrail unchanged. | Structural checks are present; no orchestrator/guardrail integration or semantic grounding claim is made. |
| FRD v0.9 / TRD v0.9 §16 | External processing requires approved baseline/data policy. | FRD v0.9 remains draft; signed FRD v1.0 unavailable; §16 approval unconfirmed. | Approval, allowed data, minimization, region/retention and final F1–F4 activation remain open. No live test/request occurred. |

Verification: focused tests **48 passed**; complete backend suite **96 passed, 99 warnings** from an isolated temporary working directory. No SDK installation or live Gemini verification. Provider is selected only by explicit `LLM_PROVIDER=gemini`; key presence alone does not select it. `LLM_MODEL`, `LLM_API_KEY`, and `LLM_TIMEOUT_MS` are read only after explicit selection. `.env.example` contains placeholders; local `.env` was not read or changed.

## Staff Knowledge Base access slice (2026-10-27)

The Knowledge Manager screen and document pipeline now serve the seven human roles registered in `STAFF_ROUTES`: `cs_agent`, `supervisor`, `complaint_officer`, `knowledge_manager`, `qa_analyst`, `management`, and `admin`. Each receives `knowledge.read` and the new least-privilege `knowledge.document.ingest` permission for PDF/DOCX/TXT upload and failed-document retry. `knowledge.write` remains unchanged and limited to Knowledge Manager article authoring. `customer` has no knowledge permission; `ai_agent` keeps its pre-existing explicit `knowledge.read` for retrieval and receives no document ingest permission. Document list/detail/upload/retry also require a human principal, so a configured service token cannot use the staff workspace routes. Existing tenant predicates and the shared chatbot retrieval path are retained. Knowledge API tests passed (35); full backend suite passed (139 passed, 1 skipped); frontend role/navigation tests passed (2); production build passed. See `context/specs/11-knowledge-staff-workspace-access.md` for evidence.

## Gemini error diagnostic refinement (2026-10-16)

Trace: TRD §13.9/§16.6 provider error handling. `ProviderErrorCode` retains existing values and adds safe categories `AUTHENTICATION`, `ACCESS_DENIED`, `RESOURCE_NOT_FOUND`, `CONNECTION_ERROR`, and `PROVIDER_ERROR`. The adapter maps SDK `APIError.code`/allowlisted `.status` and `httpx` transport exception types only; raw message, details, response, headers, URL, and prompt are not propagated. `RESOURCE_EXHAUSTED` remains `RATE_LIMITED` because the SDK status alone cannot distinguish quota from rate limiting; unknown cases remain `UNAVAILABLE`. Tests using SDK error classes and transport exceptions verify categorization and canary redaction. Focused offline provider/adapter tests: **55 passed**. No live request.
