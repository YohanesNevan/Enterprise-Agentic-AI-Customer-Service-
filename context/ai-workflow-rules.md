# AI Workflow Rules

1. Read, in order: `context/project-overview.md`, `context/architecture.md`, `context/ui-context.md`, `context/code-standards.md`, `context/ai-workflow-rules.md`, and `context/progress-tracker.md`.
2. Read relevant FRD/TRD sections and `context/audit-report.md` before planning. Read `context/specs/00-build-plan.md` before selecting a unit, then the active unit specification before changing code.
3. Audit before code changes. Work on one implementation unit at a time and stay within its scope.
4. Treat FRD/TRD as product truth. If a requirement is ambiguous in a way that affects architecture, security, privacy, or business behavior, record it and seek clarification. Use conservative defaults for low-risk details and record assumptions.
5. Do not silently replace architecture, remove business behavior, or weaken authorization. Preserve working features and conventions.
6. Keep documentation synchronized with approved decisions and update the progress tracker after every meaningful unit.
7. Verify only by commands actually executed. Never claim a test/build/runtime check succeeded without observing its result. Report unverified conditions clearly.
8. Do not represent simulated LLM, retrieval, financial, CRM, channel, storage, or notification behavior as live production behavior.
9. Every user-facing action must have a real behavior, an explained disabled state, or an explicit prototype label. Backend authorization and ownership are mandatory even when the UI hides controls.
10. Keep changes focused and reviewable; explain affected boundaries, risks, and verification status.
