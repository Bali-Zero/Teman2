---
adversarial_review: exempt-mission-process-record # ORACLE-PROD-20260927 process record (spec, progress, freeze or round log) for a code release, not a research deliverable; the reviewed object is the code, whose council and final-gate verdicts are in evidence/2026-09/agent-air-m5-mouth-oracle-prod-0927-d995492b/
---

# DELTA-ROUND — final-gate BLOCK on 3710a230 (successor Dux, Opus 5.5 xhigh)

Source of the round: fresh Opus 5.5 final gate `BLOCK` on `3710a230` (code `f38cbf46`), three findings, reproduced
empirically by the coordinator's Sol probe on the exact Mini build (`/tmp/oracle-prod-0927-print-probe/report.md`).
One writer (Sonnet 5), one finite delta, owned files only: `OutcomeSheet.tsx`, `oracle.css`, `OracleShell.tsx` and their
focused tests. Engine, reducer, privacy, consent, i18n content, assets, dependencies and backend unchanged.

## F1 (HIGH) — print/PDF drops the content of default-closed disclosures
- Cause: a closed `<details>` hides its content through the UA details-content slot; `display:block` on children does
  nothing (Sol: closed-state PDF had zero occurrences of the fixture law title, publisher, freshness, support sentence).
- Fix: `OutcomeSheet` opens its own closed `details.oracle-candidate__why` / `details.oracle-outcome__legal` on
  `beforeprint` and closes on `afterprint` only the ones it opened (visitor-opened disclosures stay open); the dead
  `> *:not(summary)` print rule is replaced by a `::details-content` print override for event-less print paths.
- Acceptance: PDF text of a default-closed verdict contains the fixture law title, publisher, source-specific
  effective/observed dates line, freshness and support sentence; disclosures are closed again after `afterprint`; a
  visitor-opened disclosure is still open afterwards.

## F3 (LOW) — Pause did not suppress the verdict ViewTransition
- Fix: `revealVerdict` gates on the effective `motion` flag (`!reducedMotion && !motionPaused`).
- Acceptance: Pause pressed → 0 `document.startViewTransition` calls on confirm → verdict; not paused → 1; OS reduce → 0.

## F2 (MEDIUM) — route dialog pinned top-left: correction of the first fix (depth 1, spec written here)
First fix removed `position: relative` from `.oracle-atlas-route`. Sol's independent probe on the corrected build
(3949) still saw rect `x0,y0`. Dux diagnostic on the same build (`/tmp/oracle-prod-0927/dux3-diag/diag-{1280,390}.json`
on Mini), opener clicked with a DOM `click()` so Playwright's auto-scroll cannot interfere:

| Viewport | scrollY before → after open | computed position | computed margin | rect x,y |
|---|---|---|---|---|
| 1280×720 | 1377 → 1377 | fixed | 0px | 0, 0 |
| 390×844 | 1782 → 1782 | fixed | 0px | 0, 0 |

- Measured cause: Tailwind v4 preflight (`@import "tailwindcss"` in `apps/mouth/src/app/globals.css`; its `*` reset sets
  `margin: 0`) overrides the UA modal-dialog `margin: auto`, so the fixed, `inset: 0` dialog sits at the viewport's top-left.
  The prototype (Vite, no preflight) kept the UA margin.
- Scroll: native `showModal()` preserves scroll once the dialog is fixed. The earlier `1377 → 0` came from Playwright's
  `locator.click()` scrolling the off-screen opener into view (the header's "Your route" button sits at y≈−1360 on a
  scrolled verdict: the header is `position: sticky` inside a shorter container). No scroll workaround is added; the
  header's stickiness is pre-existing presentation and out of this delta.
- Correction: restate `margin: auto` on `.oracle-atlas-route` (the modal `<dialog>`); nothing else.
- Acceptance, desktop 1280×720 and mobile 390×844, verdict page scrolled to the bottom, opener clicked via DOM `click()`:
  1. `scrollY` unchanged (±1) after opening; `:modal` true; computed `position` = `fixed`.
  2. Centred in the viewport: `|x − (vw − w)/2| ≤ 1` and, when `h < vh`, `|y − (vh − h)/2| ≤ 1`; rect fully inside the viewport.
  3. The close button's rect is inside the dialog's rect, top-right quadrant.
  4. Escape closes the dialog and focus returns to the opener.
  Plus a real `locator.click()` case at `scrollY = 0` (same centring assertions) so the user-visible path is covered.

## Result — code candidate `f7c9d7ee954eb0824db587ab73646c09538f8f45`
- Delta vs `3710a230`: 5 files, +257 / −12 (`oracle.css`, `OutcomeSheet.tsx`, `OracleShell.tsx`, `OutcomeSheet.test.tsx`,
  `OracleShell.atlas.test.tsx`). Freeze: `CODE_FROZEN.md` v3, `/tmp/oracle-prod-0927-DELTA_FROZEN.json`.
- New unit tests: three for F1 (open on beforeprint / close on afterprint; visitor-opened disclosure stays open;
  listeners removed on unmount), two for F3 (Pause → 0 ViewTransition calls; not paused → 1).
- Exact-SHA run3 on Mini (`/tmp/oracle-prod-0927/sha-f7c9d7ee…-run3-dux3/SUMMARY.txt`, CI-parity env exported before the
  build): `npm run build` rc 0 (Next.js 16.3.4 webpack); `tsc` 0 errors; Vitest 50 files / 1329 tests; delta proof
  12 / 12; atlas harness 34 / 34; PR e2e gate 134 passed, 1 skipped (existing opt-in `BZ_VISUAL_GALLERY`), 0 failed.
- Delta proof (`e2e/oracle-delta-proof.local.spec.ts`, gitignored; copies in `/tmp/oracle-prod-0927-final-gate-2/proofs/`):
  - F1: default-closed verdict PDF text (pdftotext) carries `Official immigration regulation`, `Directorate General of
    Immigration`, `Current`, the support sentence and the source line `Effective 3 August 2026 at 12:00 · observed 3 August
    2026 at 12:00` (plus the separate assessment line); both disclosures are closed again afterwards; a visitor-opened
    Legal references stays open while Why this fits closes. In this Chromium `page.pdf()` and the real Print button both
    fire `beforeprint`/`afterprint`; with `emulateMedia("print")` (zero print events) the `::details-content` rule alone
    makes both disclosures' content visible (`checkVisibility()` true).
  - F2 (DOM click after scrolling to the bottom): 1280×720 scroll 1377 → 1377, `position: fixed`, rect 310, 43.203,
    660 × 633.594; 390×844 scroll 1782 → 1782, rect 19, 50.641, 352 × 742.719; close button inside the top-right; Escape
    closes and focus returns to the opener. Real `locator.click()` at scroll 0: same rects.
  - F3: Pause → 0 calls; not paused → 1; OS reduced motion → 0.
- Informational, not gated, out of scope: after Escape on a scrolled page, returning focus to the opener scrolls the page
  to the header, because the header is sticky only inside its own container (pre-existing). Full-page atlas screenshots
  show the fixed dialog and backdrop within the first viewport only; that is how full-page capture renders fixed layers.
  The viewport-sized F2 screenshots are the placement evidence.

## Reviews of the delta
- Coordinator's Sol probe on the first delta build: F1 and F3 PASS, F2 BLOCK (margin). This produced the depth-1
  correction above (`/tmp/oracle-prod-0927-print-probe-fixed/report.md`). The original BLOCK probe stays in
  `/tmp/oracle-prod-0927-print-probe/`.
- Delta panel on frozen `f7c9d7ee`: **Kimi PASS** (15:00:41Z) and **Qwen PASS** (15:00:52Z)
  (`/tmp/oracle-prod-0927-council/delta-final-{kimi,qwen}.md` + receipts, same packet sha256 `70ca44b2…`).
  - Non-blocking notes, not changed: if `afterprint` never fires, the disclosures stay open on screen. That fails
    toward disclosure.
  - A second `beforeprint` without an `afterprint` in between would forget the first batch. Same fail-open direction.
  - `::details-content` is a Chromium fallback only; the JS path is primary.
- Sol final delta review: independent read-only probe against the exact run3 build on Mini port 3950. Its verdict is
  relayed by the coordinator.
- Fresh Opus 5.5 xhigh final gate 2: coordinator-commissioned on the docs-only candidate that carries this file.
