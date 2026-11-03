# Unit 01: Requirements Traceability and Security Decisions

## Goal

Create a reviewable map from the supplied FRD/TRD requirements to current source evidence, gaps, planned build units, and explicit unresolved approvals. Establish the security contract that later UI/API units must follow.

## Design

Use the supplied Indonesian requirements as authoritative product language. Cite PDF section/page and requirement IDs; distinguish source requirement from implementation evidence. The supplied FRD is v0.9 marked draft; the supplied TRD is v0.9 marked draft and says it was issued against FRD v1.0 frozen in Week 4. Do not claim a signed/approved FRD v1.0 is present. Treat the supplied PDFs as the working baseline while retaining the version conflict as an approval item.

## Implementation

### Requirements matrix

Create `context/requirements-traceability.md` with all functional domains and requirement-ID ranges from FRD §6.1, source page ranges, audited implementation evidence, current status, and planned build units. Include FRD §4.1–4.2 role/data/action matrix, FRD §10 assurance tiers, FRD §14 AI guardrails, FRD §15 metrics, FRD §17.1 NFRs and §17.3 test links, plus TRD architecture/security/data/API/test/milestone references.

### Security decisions

Record the document-specified contract: human JWT access/refresh identity and scoped signed service tokens (TRD §11.1); customer assurance AL0–AL3 (FRD §10, TRD §11.1); per-endpoint deny-by-default authorization and route inventory tests (FRD FR-SEC-001/002; BR-SEC-02; NFR-14); customer/tenant/resource scoping (FRD §4.1.1, §10; TRD §6.1/ADR-13); separation of duties (RBAC-01…06); audit and masking invariants. Distinguish specified target from current implementation.

### Plan and audit synchronization

Update `context/audit-report.md` when new PDF evidence changes earlier assumptions. Update Unit 02 in `context/specs/00-build-plan.md` with the document-backed security contract and keep Unit 03 immediately after it as the first UI-visible unit. Update `context/progress-tracker.md` with evidence, results, and next work.

## Dependencies

- Existing audit and six context files.
- Supplied FRD and TRD PDFs.
- Current API route, role map, model, and UI source.

## Verify when done

- [ ] All 15 FRD functional domains and ID ranges from §6.1 appear in the traceability matrix.
- [ ] Role matrix includes all nine FRD personas and action/data boundaries, including restricted administrator and aggregate-only management.
- [ ] Material security requirements link to source and current code evidence/status.
- [ ] Planned units link to the gaps they address; source-version mismatch is not silently treated as approved.
- [ ] Unit 02 specifies the documented identity/authz/tenant contract; Unit 03 remains the next UI-visible unit.
- [ ] Audit, plan, and tracker agree on findings and next work.
- [ ] Verification claims describe only reviews and commands actually performed.
