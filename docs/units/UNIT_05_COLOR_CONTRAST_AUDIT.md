# Unit 05 Customer Chat — Source Color Contrast Audit

**Audit date:** 2026-10-20  
**Scope:** source-derived before/after calculation for targeted customer chat color fixes.  
**Result type:** source-derived measurement, not browser/visual verification.  
**Gate:** unchanged; Unit 05 remains **IN PROGRESS** and has not been approved.

## Summary and method

The targeted source fixes raise the placeholder and counter to 5.35:1; focus outline to 8.40:1–9.42:1 and the computed translucent composer focus ring to 4.12:1–4.41:1; and the composer, transcript, message, and starter prompt borders to at least 3.33:1 on their stated surfaces. Disabled Send now uses an explicit readable disabled palette (8.35:1 text contrast) and sending keeps the primary dark background and readable white text. Existing success, error, information, and handoff colors were not changed. These are static calculations; runtime appearance remains unverified.

Ratios were calculated from the literal hex colors in `web-workspace/src/app.css`, substituting current CSS custom property values from `:root`. Calculation uses the WCAG relative-luminance method for sRGB: linearize each channel and calculate `(Llighter + 0.05)/(Ldarker + 0.05)`. Values are rounded to two decimals. Unless a row says otherwise, all chat text is small/normal text and therefore compared to 4.5:1. No 18pt regular / 14pt bold-equivalent large text exemption was applied. The current source does not define a formal project-approved numerical contrast threshold: `context/ui-context.md` says “Target WCAG 2.2 AA where practical” and requires contrast testing, but does not record reviewer approval of a specific standard. The thresholds below are therefore a technical evaluation reference, not a claim of an approved project acceptance standard.

WCAG 2.2 AA references: SC 1.4.3 requires 4.5:1 for normal text and 3:1 for large text; SC 1.4.11 requires 3:1 for visual information needed to identify UI components and states; SC 2.4.7 requires visible keyboard focus. See [W3C Understanding SC 1.4.3](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html), [W3C Understanding SC 1.4.11](https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html), and [W3C Understanding SC 2.4.7](https://www.w3.org/WAI/WCAG22/Understanding/focus-visible).

**PASS** means the calculated pair meets the cited numeric threshold in the stated source scenario. **FAIL** means it does not. **NEEDS RUNTIME VERIFICATION** means composition, actual adjacency, state, browser rendering, or essentiality cannot be settled from static colors alone. **N/A** means that chat state/style is not rendered by the current `CustomerChat()` path or the item has no text pair to measure.

## Color pair results

| UI element / state | Foreground | Background | Ratio | Criterion / status | Source-derived note |
|---|---:|---:|---:|---|---|
| Main page/body copy | `#202A25` | `#F3F1E9` | 13.08:1 | SC 1.4.3, 4.5:1 — **PASS** | Body/root color. |
| Secondary/help text on canvas | `#626D64` | `#F3F1E9` | 4.77:1 | SC 1.4.3 — **PASS** | Includes chat description and footnote in page shell. |
| Secondary text in transcript | `#626D64` | `#FBFAF6` | 5.17:1 | SC 1.4.3 — **PASS** | Timestamps/source label on transcript paper. |
| Conversation reference/byline | `#36463E` | `#FBFAF6` / `#FFFEFA` | 9.56:1 / 9.90:1 | SC 1.4.3 — **PASS** | Text is rendered on transcript/paper or surrounding light surfaces; actual adjacent surface can vary. |
| Service message content | `#34423A` | `#FFFEFA` | 10.48:1 | SC 1.4.3 — **PASS** | Default service message surface. |
| Customer message content | `#34423A` | `#EAF1E9` | 9.19:1 | SC 1.4.3 — **PASS** | Customer bubble. |
| Primary link | `#174E44` | `#F3F1E9` / `#FFFEFA` | 8.40:1 / 9.42:1 | SC 1.4.3 — **PASS** | Global `a` color; backgrounds depend on parent surface. |
| Starter prompt text | `#36463E` | `#FFFEFA` | 9.90:1 | SC 1.4.3 — **PASS** | Prompt button normal state. |
| Starter prompt hover text | `#174E44` | `#F5F8F2` | 8.87:1 | SC 1.4.3 — **PASS** | Hover background/color. |
| Prompt arrow/accent | `#27695D` | `#FFFEFA` | 6.37:1 | SC 1.4.3 — **PASS** | Decorative arrow, adjacent prompt label also carries meaning. |
| Secondary button normal | `#202A25` | `#FFFEFA` | 14.66:1 | SC 1.4.3 — **PASS** | Shared `.btn` base. |
| Secondary button hover | `#174E44` | `#FFFEFA` | 9.42:1 | SC 1.4.3 — **PASS** | Shared `.btn:hover`. |
| Primary Send button normal | `#FFFDF7` | `#174E44` | 9.34:1 | SC 1.4.3 — **PASS** | Chat uses `.btn.primary`. |
| Primary Send button hover | `#FFFFFF` | `#123D34` | 12.05:1 | SC 1.4.3 — **PASS** | Hover state. |
| Primary Send button disabled | `#36463E` | `#E8ECE5` | 8.35:1 | SC 1.4.3 — **PASS (advisory contrast; inactive control exemption)** | Disabled button uses a distinct muted surface without lowering opacity. Border `#77867C` vs fill is 3.20:1. |
| Primary Send button sending/loading | `#FFFDF7` | `#174E44` | 9.34:1 | SC 1.4.3 — **PASS (source calculation)** | Sending state retains dark primary palette at full opacity; white spinner track is alpha-composited at 72% (5.79:1 against primary fill). |
| Composer label | `#36463E` | `#FFFEFA` | 9.90:1 | SC 1.4.3 — **PASS** | Label above textarea. |
| Textarea entered text | `#202A25` | `#FFFEFA` | 14.66:1 | SC 1.4.3 — **PASS** | Transparent textarea over composer surface. |
| Textarea placeholder | Before `#9AA299`; after `#626D64` | `#FFFEFA` | Before 2.60:1; after 5.35:1 | SC 1.4.3 — **PASS (source calculation)** | Placeholder remains text for contrast evaluation. |
| Character count | Before `#8B958B`; after `#626D64` | `#FFFEFA` | Before 3.07:1; after 5.35:1 | SC 1.4.3 — **PASS (source calculation)** | Small text; revised color meets 4.5:1. |
| Composer hint | `#626D64` | `#FFFEFA` | 5.17:1 | SC 1.4.3 — **PASS** | Safety hint. |
| Handoff/info message copy | `#305665` | `#E5EEF0` | 6.74:1 | SC 1.4.3 — **PASS** | Rendered as `.alert.info.chat-notice` when `notice` exists. |
| Handoff history link | `#244C5B` | `#E5EEF0` | 7.89:1 | SC 1.4.3 — **PASS** | Link hover only adds underline. |
| Error/talkback copy | `#763A2E` | `#FBF0E9` | 7.76:1 | SC 1.4.3 — **PASS** | `CustomerChat()` error region. |
| Error mark | `#FFFFFF` | `#A03C32` | 6.59:1 | SC 1.4.3 — **PASS** | Decorative `!` is `aria-hidden`; adjacent error text identifies state. |
| Generic alert error | `#81332B` | `#F7E8E4` | 7.21:1 | SC 1.4.3 — **PASS** | Shared style; not the chat's current `.talkback` error treatment. |
| Generic alert success | `#285D40` | `#E4F0E7` | 6.56:1 | SC 1.4.3 — **PASS** | Style exists globally, but no success alert is rendered in the inspected `CustomerChat()` path. |
| Generic warning badge | `#805215` | `#F5EAD4` | 5.61:1 | SC 1.4.3 — **PASS** | Shared `.b-amber` style; no warning state currently rendered in `CustomerChat()`. |
| Generic info badge | `#315A6C` | `#E5EEF0` | 6.34:1 | SC 1.4.3 — **PASS** | Shared badge style. |
| Generic other badge colors | `#286446` / `#8A3028` / `#174E44` / `#5F6A61` | `#E4F0E7` / `#F7E8E4` / `#E2EEE7` / `#EAEDE7` | 5.97 / 6.95 / 7.97 / 4.77:1 | SC 1.4.3 — **PASS** | Shared green/red/violet/gray badge pairs; not all appear in customer chat. |
| Customer chat focus outline vs surface / canvas | Before `#9BCBBB`; after `#174E44` | `#FFFEFA` / `#F3F1E9` | Before 1.79 / 1.59:1; after 9.42 / 8.40:1 | SC 1.4.11 — **PASS (source calculation)** | Chat-scoped 3px `:focus-visible` outline; global focus color remains unchanged for dark shell/staff surfaces. Composer textarea uses the parent focus ring. |
| Composer focus ring and border | Before `#83AA97` and `rgba(91,145,115,.12)`; after `#174E44` and `rgba(23,78,68,.72)` | `#FFFEFA`, `#F3F1E9`, `#FBFAF6` | Border 9.42:1; composited ring 4.41 / 4.12 / 4.32:1 | SC 1.4.11 — **PASS (source calculation)** | Ring contrast calculated after alpha compositing on the listed solid surfaces; runtime rendering still needs check. |
| Composer outer border | Before `#B9C2B7`; after `#77867C` | `#FFFEFA` | Before 1.82:1; after 3.79:1 | SC 1.4.11 if boundary identifies control — **PASS (source calculation)** | Border strengthened to provide a clear composer boundary. |
| Transcript border | Before `#D8DDD4`; after `#77867C` | `#FBFAF6` | Before 1.32:1; after 3.67:1 | SC 1.4.11 if boundary identifies component — **PASS (source calculation)** | Boundary is now visible at the 3:1 technical threshold. |
| Message bubble border | Before `#D8DDD4` / `#CBDed1`; after `#77867C` | `#FFFEFA` / `#EAF1E9` | After 3.79 / 3.33:1 | SC 1.4.11 where boundary distinguishes message groups — **PASS (source calculation)** | Existing light surfaces/layout remain unchanged. |
| Starter prompt border | Before `#D8DDD4`; after `#77867C` | `#FFFEFA` | Before 1.82:1; after 3.79:1 | SC 1.4.11 if boundary identifies control — **PASS (source calculation)** | Prompt fill is close to transcript surface, so border was strengthened. |
| Composer action divider | `#ECEEE8` | `#FFFEFA` | 1.16:1 | SC 1.4.11 if conveying information — **N/A / verify** | Likely decorative separator, not an independent control. |
| Disabled spinner / loading skeleton | Spinner border `rgba(255,255,255,.72)` / white | Primary fill `#174E44`; skeleton gradient `#E6E9E1` / `#F2F2EC` | Spinner track 5.79:1; animated skeleton has no text pair | SC 1.4.11 where indicator conveys state — **NEEDS RUNTIME VERIFICATION** | Spinner track is mathematically composited; skeleton animates. Verify browser rendering and state visibility. |
| Citation source title | `#174E44` | `#FFFEFA` or `#EAF1E9` | 9.42:1 / 8.40:1 | SC 1.4.3 — **PASS** | Source chip is a `<span>`, not a navigable citation link in current JSX. Runtime citation content/appearance depends on API response. |

## Failures and runtime verification

### Before-change findings now addressed in source

The source pairs listed in the table were revised. Their prior values and updated calculated ratios are shown alongside each other. Disabled Send previously calculated at approximately 2.70:1 under opacity `.52`; inactive controls are exempt from SC 1.4.3, so this was an advisory finding rather than a numeric failure for that criterion.

### Not settled without browser/runtime evidence

- Exact focus indicator appearance with the translucent focus shadow composited against all nearby colors; calculations use listed solid surfaces but do not reveal anti-aliasing, forced-colors behavior, or focus visibility for each control.
- Disabled Send and spinner rendering under browser native control treatment and compositing.
- Loading skeleton's animated gradient and any interaction/contrast changes under hover, focus, reduced motion, or high-contrast/forced-colors modes.
- Citation appearance for actual runtime content and any parent styling returned/selected dynamically.
- Whether thin borders are necessary to identify UI components or are redundant with other visual structure.
- Keyboard focus indicator visibility and component boundary at all supported viewport sizes; this audit did not launch a browser or run visual automation.

Success and warning are **not applicable to the current CustomerChat rendering path**: the shared `.alert.ok` and `.b-amber` colors were measured as reusable styles, but the inspected JSX does not render those states in `CustomerChat()`. The actual handoff/status notice uses the information alert; the actual chat error uses `.talkback`; loading uses skeleton/spinner. No assertion is made about API-provided runtime states beyond these source branches.

## Files examined and changed

Examined:

- `context/ui-context.md`
- `context/progress-tracker.md`
- `docs/units/UNIT_05_GATE_REVIEW.md`
- `docs/units/UNIT_06_READINESS_AUDIT.md`
- `web-workspace/src/app.css`
- `web-workspace/src/App.jsx` (`CustomerChat()`, `CustomerHistory()`, shared badges)

Changed:

- `web-workspace/src/app.css`: placeholder/counter, keyboard focus, focus ring, composer/transcript/message/prompt borders, disabled and sending button colors.
- `web-workspace/src/App.jsx`: conditional `is-sending` class to distinguish in-flight from other disabled states; request and submission logic unchanged.
- `docs/units/UNIT_05_COLOR_CONTRAST_AUDIT.md` and `docs/units/UNIT_05_GATE_REVIEW.md`.
- No API, backend, authentication, policy, database, migration, dependency, environment, progress tracker, or gate status change.

No browser verification was run in this follow-up. These calculations do not claim browser visual conformance. Previous developer-reported Unit 05 outcomes remain developer-reported, not Codex-verified.

## Recommended follow-up (not applied)

1. Confirm with product/reviewer whether WCAG 2.2 AA is the accepted Unit 05/project threshold; `context/ui-context.md` states it as a practical target but records no formal approval.
2. Perform browser-based visual checks for focus, disabled, sending/loading, error/handoff, desktop/mobile, reduced-motion, and forced-colors behavior.
3. Record reviewer disposition in the Unit 05 gate report after browser verification and standard confirmation; do not infer approval from this audit.

## Gate relevance

The source contrast fixes are applied and calculated pairs meet the temporary WCAG 2.2 AA reference in the examined scenarios. This does not change the gate status or establish visual/runtime conformance. Unit 05 remains **IN PROGRESS; BLOCKED FOR CLOSURE** pending browser verification and reviewer disposition. The project target itself should be confirmed by the reviewer; this report does not claim it has been approved.

**Submission decision:** The source measurements are useful for reviewer discussion, but contrast evidence is **not sufficient by itself for approval**. It needs the project's standard confirmed and runtime/browser follow-up for dynamic/focused states.

## Follow-up verification (2026-10-20)

The current `app.css` and `CustomerChat()` markup were re-inspected before any implementation change. The previously recorded remediation is present in the active source: placeholder, composer hint, and character count use `--muted` (`#626D64`); the chat focus outline uses `--brand-strong` (`#174E44`); the composer uses the dark focus border and 72% alpha focus ring; and the disabled/sending button states have explicit palettes. Keyboard handling (`requestSubmit()` for plain Enter, native Shift+Enter/IME), the labelled textarea, `role="status"` handoff/loading states, and `role="alert"` error state remain present. The existing responsive CSS rules remain in place. No CSS or application source change was necessary in this follow-up because the audit fixes were already present.

The existing source-derived calculations above apply to the re-inspected values. They are static measurements, not browser color sampling. A fresh `npm.cmd run build` from `web-workspace` passed on 2026-10-20 (Vite 5.4.21; 32 modules; 769 ms). No frontend test script or browser automation package is configured.

An Edge headless render was attempted at `http://127.0.0.1:5173/customer/chat` with a 1440×1000 viewport. The SPA rendered the customer authentication-required panel because no authenticated customer session was available; the composer, placeholder, counter, focus ring, loading, and error states were therefore not present to inspect in the browser. This confirms the rendered route and authentication gate only. No screenshot was retained, and no keyboard interaction, browser contrast sampling, console review, or chat-state runtime test is claimed.

The source remediation remains present and build-verified. `context/requirements-traceability.md` maps draft FRD §17.1 NFR-09 to a WCAG 2.1 AA design target, while the signed FRD v1.0 is unavailable. The 4.5:1/3:1 figures in this report use WCAG 2.2 AA as a technical reference and do not claim separate reviewer approval of that stricter reference. Reviewer confirmation of the applicable baseline and disposition is still required. Runtime contrast and focus behavior remain unverified. Unit 05 remains **IN PROGRESS; BLOCKED FOR CLOSURE**.

## Current-session verification refresh (2026-10-20)

Re-inspection found the documented CSS remediation still present, including `--muted: #626D64`, chat-scoped focus color `#174E44`, the explicit composer focus ring, and explicit disabled/sending button palettes. No new contrast defect was identified, so no CSS change was made. The previously listed ratio calculations remain source-level calculations only.

`npm.cmd run build` passed (Vite 5.4.21, 32 modules; 648 ms). Vite served `/customer/login` and `/customer/chat` with HTTP 200, but no browser automation harness or frontend test script was available. The frontend response is only the SPA shell; because the backend was not running and no customer session existed, runtime placeholder/counter/focus/disabled/loading/error/handoff states could not be observed. No browser contrast measurement, keyboard interaction, or authenticated flow was run. The project's applicable approved WCAG baseline and reviewer disposition remain outstanding. Unit 05 stays **IN PROGRESS; BLOCKED FOR CLOSURE**.
