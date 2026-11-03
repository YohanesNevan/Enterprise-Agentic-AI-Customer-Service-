# Unit 05 — Customer Information Conversation and Truthful Handoff

Status: this information-flow implementation slice is complete; full Unit 05 remains in progress pending browser journey/accessibility verification.

## Source status and scope

The repository contains FRD-EAICS-001 v0.9 draft for mentor review and TRD-EAICS-001 v0.9 draft. The TRD references a frozen FRD v1.0, but no signed FRD v1.0 or signed TRD §16 integration approval was found. This slice uses only behaviors stated unambiguously in the available drafts; it does not claim approved final compliance.

This is the next eligible build-plan unit (Unit 05), dependent on completed Units 03–04. It implements one customer conversation slice: deterministic greeting, a supported informational fee question answered from eligible knowledge with persisted citations, truthful queue state for required handoff, and citation visibility in history. Complaint/case creation and full staff handoff context are explicitly deferred to Units 06 and 08. Until then, generic request/complaint fallback copy must not claim a case or staff follow-up that did not occur.

## Requirement trace

| Requirement | Source | Required behavior | Actor/component | Acceptance evidence |
|---|---|---|---|---|
| FR-INT-001, FR-INT-004 | FRD §6.4, pp. 42–44; TRD §4.5 | Closed taxonomy; `OTHER_UNCLASSIFIED` stays a mandatory human-handoff path; do not guess an unsupported intent. | Customer, intent service, orchestrator | Unknown text remains unclassified and creates a queued handoff; regression test retains mandatory handoff. |
| FR-INT-003 | FRD §6.4, pp. 43–44 | Clarification is bounded and offered when confidence is in the clarification band; known greeting should not be treated as unknown. | Customer, intent service | “Halo” returns a deterministic greeting with no handoff. |
| FR-INT-007 | FRD §6.4, p. 45 | Safety/vulnerability conditions take priority and require human handoff. | Customer, intent/orchestrator/queue | Existing vulnerability test plus persisted queue state for a forced handoff. |
| FR-KM-003 | FRD §6.5, pp. 46–48 | Customer information answers use applicable published/current sources, are grounded and cited; insufficient evidence abstains and may offer handoff. | Customer, retrieval/orchestrator | Fee inquiry returns the seeded published passage, citation article/version/body locator/score, persists it, and passes grounding; section-anchor gap is explicitly open; expired or non-published versions are excluded. |
| FR-KM-004 | FRD §6.5, p. 48 | Customer-facing retrieval excludes internal knowledge. | Customer, knowledge retrieval | Existing access-level filter remains; verify no internal article appears in returned evidence. |
| FR-ORC-001, FR-ORC-006, FR-ORC-009 | FRD §6.8 / §14; TRD §4.8 and §8 | Deterministic workflow and policy, validate evidence/claims, do not assert unperformed actions or unconfirmed handoff. | Orchestrator, guardrail, queue | No LLM tool authority; grounded answer accepted; handoff text reports queued or unavailable and never implies agent acceptance unless queue state confirms it. |
| FR-WS-001, FR-WS-002 | FRD §7.2, pp. 71–74; TRD §4.13 | Handoff work enters a queue with reason/priority and context sufficient for the human workflow. | Orchestrator, queue, agent | Queue row persists with tenant and reason. It is explicitly `package_complete=false`; full context package remains a Unit 08 gap. |
| FR-CONV-003 | FRD §6.2, pp. 31–34; TRD §7.3 | Persist conversation history and expose source provenance to the customer. | Conversation API and customer portal | Persisted outbound message contains citations; customer history renders source title and passage anchor. |

## Existing path and confirmed defects (RAG follow-up, 2026-10-27)

`POST /v1/chat/messages` in `app/modules/routes_a.py` authenticates and persists the inbound message, then calls `orchestrator.run_turn`. The orchestrator used deterministic `intent.classify`; no LLM provider/gateway was invoked. An unknown informational question such as "Apa itu NPB?" became `OTHER_UNCLASSIFIED/HANDOFF` before retrieval. The lexical retriever also counted interrogative words, so single acronym queries could miss their source. Finally, `search()` silently inserted demo articles, including a made-up sample transfer fee, into any tenant without articles. Those defects could respectively bypass RAG, cause weak matching, and introduce unsupported facts.

For a text with no configured keyword, `intent.classify` returns `OTHER_UNCLASSIFIED` and `HANDOFF`; this is the documented mandatory behavior. The orchestrator then returned “Saya hubungkan ke petugas manusia agar dibantu lebih lanjut.” without persisting a `HandoffRow`. Therefore the wording was untruthful. A supported query such as “Berapa biaya transfer internasional?” matched only the broad `biaya` token and was scored into clarification, despite the matching published seed article. Separately, the groundedness call supplied citation titles but empty bodies, so source numbers could be rejected as unsupported. These were independent causes.

## Implementation decisions

- User-requested RAG follow-up wires the existing validated F4 provider contract into the real authenticated customer chat turn. The request includes the question and tenant-scoped retrieved passages; F4 claims must cite supplied source IDs and cover every answer sentence. The Gemini prompt treats both values as untrusted reference data and prohibits unsupported fees, limits, phone numbers, workflow claims, or requests for secrets.
- Generic informational questions are routed to `INFO_PRODUCT_POLICY` for retrieval unless an explicit fraud, staff-conduct, vulnerability, or safety path takes priority. Clearly unclassified non-question text and mandatory handoff paths remain intact.
- Retrieval normalizes punctuation and removes interrogative stopwords, applies minimum overlap/relevance, and returns only published eligible article versions and ready document chunks for the authenticated tenant. Demo seed articles are opt-in via `KNOWLEDGE_SEED_DEMO=true`; production tenants no longer receive invented demo policy implicitly.
- Retrieval errors and provider errors are distinct from a knowledge gap. Provider failure with relevant sources returns a controlled retry message plus citations; it does not claim a handoff. No sufficiently relevant source continues through the existing knowledge-gap handoff policy.
- Ingestion and retry now commit a failed status and safe diagnostic details when extraction raises a supported processing error. Invalid uploads still return the API validation message; failed documents never enter retrieval.

- Retain the closed taxonomy and mandatory handoff for truly unclassified intent. Add phrase evidence for the supported seed article topic; do not lower the global ACT threshold.
- Treat recognized greeting intent as a deterministic conversational response, not a knowledge answer or handoff.
- Retrieval filters published article and version, access level, tenant, language relevance, and both article/version effective and expiry times.
- Citation response and stored message retain article ID, version ID, the actual `body` source locator, and retrieval score. Grounding checks actual retrieved text, not citation metadata alone. The model has no section anchors, so this does not satisfy the FRD's section-anchor requirement; `§1` is not fabricated.
- Required handoff attempts create a tenant-scoped `HandoffRow`; an existing active queue row is reused to avoid another open queue entry. Customer response says request queued only after successful persistence and distinguishes queue state from agent acceptance.
- New handoff rows set `package_complete=false`. The current row contains routing metadata but does not persist the full FR-WS-001 context package; Unit 08 remains responsible for completing the staff read model/context.
- Unsupported request/complaint action fallbacks confirm only that the inbound message is saved in the conversation; they do not claim ticket/case creation or staff follow-up.
- Regression tests use deterministic fake F4 output and do not contact Gemini. When `LLM_PROVIDER=gemini`, actual question text and retrieved passage text are sent to the configured Gemini provider; no live provider request was made in this verification.

## Changed boundaries

- `app/modules/intent.py`: informational question routing while preserving mandatory/safety handoff.
- `app/modules/knowledge.py`: tenant/status/effective-date filtering, normalized lexical ranking, opt-in demo seed data, and persisted extraction failure detail.
- `app/modules/llm_provider.py`, `app/modules/gemini_provider.py`, `app/modules/orchestrator.py`: validated F4 grounding contract connected to the actual customer chat path; provider/retrieval failures are controlled separately from knowledge gaps.
- `web-workspace/src/App.jsx`: removes stale copy claiming live AI inference is unavailable; transcript still renders the persisted answer and citations.
- `tests/test_rag_chat.py`, `tests/test_a_skeleton.py`, and `tests/test_llm_provider.py`: authenticated customer upload-to-chat, tenant isolation, unsupported facts, security, failed ingestion, provider failure, answer persistence, and handoff regressions.

## Verification

- Focused: `python -m pytest tests/test_a_skeleton.py -q -p no:cacheprovider` — 10 passed before adding the version lifecycle and duplicate-queue assertions.
- Full backend: `python -m pytest -q -p no:cacheprovider` — 43 passed, 96 dependency deprecation warnings.
- Frontend: `npm.cmd run build` from `web-workspace` — passed; Vite transformed 32 modules.
- No browser automation or live LLM request is claimed.

## Remaining work / risks

- Full backend suite: 149 passed, 1 skipped. Frontend access tests: 2 passed. Production build: passed after sandbox escalation was needed for esbuild.
- Verify the customer UI in an actual browser at mobile/desktop widths and by keyboard; browser automation was not run in this session so far.
- Complete FR-WS-001 package and agent handoff context in Unit 08; do not mark package complete before then.
- Implement the complaint/case path in Unit 06; current chat classifier does not itself satisfy the FRD complaint case workflow.
- Retrieval remains lexical (no embeddings/vector store were introduced). No live Gemini inference was performed; run the app with configured provider credentials to exercise a real provider response.
- Knowledge article schema has no section/anchor representation; citations identify the stored body field, not an FRD section anchor.
- Draft/version approval and signed integration-contract discrepancies remain unresolved.

## Routing consistency follow-up (2026-10-27)

- **Confirmed root cause:** `intent.classify()` incremented a process-global counter keyed only by `conversation_id:intent_code` and unconditionally changed any intent to `HANDOFF` at count three. It counted informational turns as well as unresolved human-action requests, never reset after an answered question, and did not count message identity. Thus earlier unrelated policy questions in the same conversation could make a later repeated refund-policy question hand off before retrieval/provider generation. A runtime diagnostic had previously observed `REPEAT_CONTACT` before Gemini generation. The handoff helper then reused the conversation's existing queued/offered/accepted handoff row; an accepted row produced the exact “Petugas telah menerima...” response. This was an in-memory routing threshold, not a retrieval score, Gemini response, duplicate idempotency replay, or frontend replacement.
- **Routing fix:** removed frequency-only escalation. A knowledge/informational question now remains an inquiry regardless of the number of prior successful questions. `REPEAT_CONTACT` remains available only when the customer explicitly states that repeated attempts remain unresolved. Explicit refund execution/reversal requests map to `CMP_TRANSACTION_DISPUTE/HANDOFF` with `HUMAN_ACTION_REQUIRED`; questions about refund eligibility remain knowledge inquiries. Fraud, vulnerability, and staff-conduct escalation are preserved.
- **History handling:** the current customer message is searched first. For a short referential follow-up such as “Mengapa?” only, if direct retrieval has no match, retrieval retries using the immediately preceding customer question. The F4 prompt input carries both the current follow-up and that limited prior-question context. Old queued/accepted handoff rows do not replace current-turn retrieval results; genuine new action/fraud requests still follow the handoff policy.
- **Diagnostics/privacy:** each completed turn emits `customer_chat_routing` with tenant/conversation/correlation IDs, intent, decision, routing reason, retrieval outcome/source count, and handoff decision; message text is excluded. Retrieval audit events no longer put the first 40 characters of a customer query in the audit resource ID.
- **Regression coverage:** `tests/test_rag_chat.py` now covers repeated refund-policy inquiry in one conversation, the same question in a fresh conversation, refund eligibility inquiry, “Mengapa?” context, explicit refund execution handoff, and explicit unresolved repeat-contact handoff. Existing provider-error, unsupported-knowledge, fraud, tenant-isolation, and action tests remain.
- **Verification:** isolated full backend suite — **158 passed, 1 skipped** (192 dependency warnings), using SQLite, deterministic stub configuration, and demo knowledge seeding disabled. After the final routing-log and third-repeat assertion, focused chat/skeleton suite — **25 passed** (57 warnings). Frontend available `npm.cmd run test:access` — **2 passed** (these are Knowledge navigation/access tests, not a chat interaction suite). `npm.cmd run build` — **passed**, Vite 5.4.21, 33 modules. No browser run or live Gemini chat was performed for this change.

## Composer Enter-key follow-up (2026-10-20)

- **Diagnosis:** `CustomerChat()` used a multiline `<textarea>` inside a form with only `onSubmit={send}`. Native Enter in a textarea inserts a newline; no composer key handler submitted the form. Clicking the send button already used the correct `send` path.
- **Change:** Plain Enter now calls the form's native `requestSubmit()` path; Shift+Enter and IME composition remain native. The send function has a synchronous ref lock to prevent overlapping submissions before React updates the loading state. Whitespace/disabled states remain guarded, and the form still prevents navigation/reload.
- **Verification:** `npm.cmd run build` in `web-workspace` passed (Vite 5.4.21; 32 modules). No frontend interaction test framework is installed. Browser interaction, browser-console review, retry, duplicate-request, Shift+Enter and focus behavior were not executed in this follow-up; Unit 05 remains in progress until manual/browser verification is recorded.

## Customer conversation UI refresh (2026-10-16)

- The existing customer landing, login presentation, and `/customer/chat` were visually redesigned without changing conversation endpoints, payloads, auth/session handling, or orchestration behavior.
- Empty conversation includes prompt chips that fill (but do not submit) the composer. Loading, API error, citation, and handoff states are rendered from actual UI/API state; a successful queue message still distinguishes queueing from staff acceptance. Resend uses the existing same-text idempotency key; no regenerate action was added.
- Frontend production build passed and the public shell was visually inspected at desktop and a 390px emulated mobile viewport. Keyboard Enter was verified for the mobile menu and protected chat route. Authenticated chat/API journey, broader keyboard coverage, and assistive-technology checks remain pending because the browser environment has no configured trusted session provider and no frontend E2E test framework.
- This refresh does not enable Gemini or add any runtime LLM call. FRD v0.9 draft versus TRD v0.9 reference to FRD v1.0 remains unresolved; the UX reference PDF named in the request was not present in the repository.
