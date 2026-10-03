---
adversarial_review: exempt-mission-process-record # ORACLE-PROD-20260927 process record (spec, progress, freeze or round log) for a code release, not a research deliverable; the reviewed object is the code, whose council and final-gate verdicts are in evidence/2026-09/agent-air-m5-mouth-oracle-prod-0927-d995492b/
---

# FIX-ROUND-2 — exact corrective contract (Dux, 2026-09-27T11:05Z)

Round 1 (FIX-ROUND-1.md) was applied only in part. This round is written from MEASURED computed geometry
(probe `qa/atlas-diag.local.spec.ts`, run on Pro against the qa2 build), not guesses. Fix the named cause;
do not stack another override on top of a rule you did not trace. `R` = `apps/mouth/src/app/(visa-oracle)/visa-oracle`.
BUILD-SPEC §0 still binds, with the exceptions stated here. The ending/OutcomeSheet cleanup is NOT in this
round (separate ENDING round later) — do not touch `OutcomeSheet.tsx`, `VerdictReveal.tsx`, `i18n.ts`.

## A. Measured root causes → required fix (CSS in `R/oracle.css`, atlas section only)

| # | Measured cause | Fix |
|---|---|---|
| A1 | World/permit: the presentation element IS `div.oracle-question` and keeps legacy `max-width:46rem` (736px) → headline, hint, pins, WhyWeAsk positioned against a 736px box; Yes pin lands on Africa, h1 left-aligned. | `.oracle-root.oracle-atlas[data-scene-layout="stage"] .oracle-question{max-width:none;margin:0}`. World box must then equal the stage box (1440×900 at 1440×900 viewport). |
| A2 | World headline/hint are two independent absolutes (`top:26%` and `top:calc(26% + 5cqw)`) → overlap whenever the h1 wraps (ID at 1024/1280 overlaps 736×27). | Desktop ≥701px: `[data-presentation="world"]{display:flex;flex-direction:column;align-items:center;gap:.7cqw;box-sizing:border-box;padding:16.25% 6% 0}` (16.25% of width = 26% of the 1.6-aspect height). Headline + hint `position:static;width:auto;max-width:88cqw;text-align:center`; hint `font-size:max(13px,1.25cqw)`. Choices/back/notsure/WhyWeAsk stay absolute (padding never moves an absolute child's containing block). |
| A3 | World WhyWeAsk container is 515–640px wide, so its box sits under the "No" pill. | World WhyWeAsk: `position:absolute;left:50%;bottom:3.8%;transform:translateX(-50%);width:max-content;max-width:min(44ch,40cqw);display:flex;flex-direction:column-reverse;align-items:center;text-align:center;font-size:13px`; its open panel is a paper card above the trigger (`background:var(--oracle-bg-elevated);padding:10px 14px;border:1px solid var(--atlas-rule);box-shadow:0 8px 24px rgba(0,0,0,.08)`). Back/Not sure stay in the bottom corners (`left/right:3.5%;bottom:3.8%`), `font-size:max(14px,1.1cqw)`, `min-height:44px`. |
| A4 | Entry h1 has `transform:scaleX(1.13)` → its box is 1627px at 1440 (clipped-control failure at every desktop width). The 1.13 scale belongs to the prototype `.globe` map, not to the title. | Delete that declaration from `.oracle-atlas-entry__title` (and the now-pointless `transform:none` in the mobile block). |
| A5 | Entry save block: `top:87%` + `width:max(60%,24rem)` + left-aligned text → overlaps Start by 4–5px (EN/ID 1280/1440) and reads off-centre (x=288). | `.oracle-atlas-save{top:calc(79.2% + 6.2cqw);width:fit-content;max-width:min(88%,640px)}`; label `font-size:max(12px,1cqw)`, small `font-size:max(11px,.86cqw)`. No overlap at 1024×768, 1280×800, 1440×900, EN and ID. |
| A6 | Unchecked checkboxes look checked because `apps/mouth/src/app/globals.css:1077` sets `html{color-scheme:dark}` — native unchecked boxes paint dark. `appearance:auto` alone cannot fix it. | `.oracle-root.oracle-atlas[data-oracle-theme="light"]{color-scheme:light}` and `[data-oracle-theme="dark"]{color-scheme:dark}`. Verify in screenshots: unchecked = empty light box, checked = copper tick. |
| A7 | Branch/hub caption is rendered INSIDE `.oracle-main__content`, which is `position:relative` in landscape → `right:7vw;top:calc(100dvh - 180px)` resolves against the ~610px column and the caption covers the tiles (desktop-en-06). | Markup move in `OracleShell.tsx`: render the `AtlasBranchCaption` block as a direct child of `<main className="oracle-main oracle-atlas-main">` (after `.oracle-main__content`), same conditions. Containing block becomes the full-width main. Keep `pointer-events:none`, keep the ≤1050px hide. |
| A8 | Mobile stage (≤700px) keeps desktop `cqw` type (hint computes to 5px, back tiny) and has no map band: the world map is full-bleed, pins at `calc(270px+…)` measured from the main top although the prototype's 270px includes the 64px header. | See §B. |
| A9 | Mobile watershed: tile labels overflow their tile ("employment", "Retirement", "Something" run into the arrow). | ≤700px: tile `padding:12px 10px;gap:8px;min-height:86px`, glyph `28×28`, label `font-size:17px;line-height:1.15;min-width:0;overflow-wrap:anywhere`, arrow `14px`; ≤360px one column. |
| A10 | Mobile TEMPORARILY_UNAVAILABLE ending: an unnamed `button:` (and at narrow 320 also EN/ID) extends past the viewport. | Find the element with the probe (§D); make it wrap/shrink within the column. Header tools must fit 320px (brand text visually hidden is already done). |

## B. Mobile stage contract (≤700px) — prototype mobile values, header (64px) is OUTSIDE `<main>`

- `.oracle-root.oracle-atlas[data-scene-layout="stage"] .oracle-main__content{position:relative;inset:auto;min-height:780px}` — content now flows; scenery stays the absolute layer behind it.
- Entry: `.oracle-atlas-entry` becomes a flow column (`position:relative;display:flex;flex-direction:column;align-items:center;gap:12px;padding:32px 20px 28px;min-height:780px;box-sizing:border-box`); all its children `position:static;transform:none;top:auto;left:auto;bottom:auto`; title `font-size:min(18cqw,72px)`, subtitle `clamp(18px,6cqw,26px)`, body `15px`/`max-width:34ch`; Start gets `margin-top:auto` (Start 28px text, 48px dot), save block after it (label 12px, small 11px, width 100%). Island art band: `top:156px;height:62.5vw;object-fit:contain` (prototype `.art{top:220px}` minus header). Result: Start+save sit at the bottom, never over the map band, no overlap at 320/390 EN/ID.
- World: stage wordmark `top:20px;font-size:40px`; presentation `padding:76px 20px 0` (flex column as desktop); headline `28px/1.15`, hint `13px`; world map band `top:206px;height:62.5vw;object-fit:contain`; pins `[data-answer="no"]{left:26%;top:calc(206px + 48.3vw)}`, `[data-answer="yes"]{left:78%;top:calc(206px + 41.7vw)}`; pills `14px`, `min-height:44px`, width 150px for "no" and **125px for "yes"** (150px overflows 320 — measured); WhyWeAsk `bottom:134px`; Back/Not sure `bottom:72px`, `left/right:18px`, `16px`.
- Permit: flow column, `position:relative;inset:auto;width:auto;padding:84px 24px 28px`, children static incl. **Back as the last flow item** (measured Back⟷Not-sure collision 58×30 at 320/390); headline 28px (26px ≤350px); options row gap 10px, answers `min-height:64px;font-size:22px`; Not sure/WhyWeAsk trigger get a paper chip background (`background:color-mix(in srgb,var(--oracle-bg-elevated) 92%,transparent);padding:6px 10px;border-radius:6px`) for legibility over art; permit art band `top:221px;bottom:0` (prototype `top:285px` minus header) with a top-fading wash so the heading sits on paper.

## C. Accepted review findings (Sol provisional + Kimi/Qwen) — implement with a focused test each

| id | Source | Change | Test |
|---|---|---|---|
| S1 | Sol 2 | `QuestionScreen` tile group: clear the category preview on group `onBlur` only when `event.relatedTarget` is null or outside the group element; keep mouse-leave clearing; tile→tile focus keeps preview. | tile→tile keeps preview; tile→Not sure / Back clears it. |
| S2 | Sol 3 | Motion control: when OS `prefers-reduced-motion: reduce`, do NOT render the Pause/Resume button (motion is already off); otherwise label switches Pause motion ⇄ Resume motion WITHOUT `aria-pressed`. `data-motion` semantics unchanged. | reduced-motion → no button; normal → no `aria-pressed`, label toggles. |
| S3 | Sol 4 | Save opt-in markup: container `div.oracle-atlas-save`; `<input type=checkbox id aria-describedby=…>`; `<label htmlFor>` with ONLY the short `resumeOptIn` text; the full resume sentence in a visible `<small id=…>` OUTSIDE the label. Same handler/checked state. | exact accessible name === short text; description === sentence; sentence visible. |
| S4 | Sol 1 | Print: final `@media print` block placed AFTER every atlas rule: `.oracle-root.oracle-atlas .oracle-atlas-main,.oracle-root.oracle-atlas[data-scene-layout] .oracle-main__content{width:100%!important;max-width:none!important;padding:0!important;position:static!important}`; header tools, scenery, consult float, route dialog, branch caption hidden. | Pro: `page.emulateMedia({media:"print"})` on the verdict → `.oracle-main__content` width ≥ 90% of viewport, left ≤ 24px; plus a `page.pdf()` artefact saved under /tmp. |
| K1/Q2 | Kimi 1, Qwen 2 | `OracleScenery`: mount the permit art block (paper + depth imgs) only when `scene.id` is `"world"` or `"paper"`; entry loads only the island map + world map. | entry DOM has no `permit-` img src. |
| K2 | Kimi 2 | Preview fan-out: debounce the preview→scene projection in `OracleShell` (presentational state only, 150ms; clear timer on unmount/leave) and in `LandscapeArt` effect cleanup set `img.onload=img.onerror=null; img.src=""`. | fake timers: 5 rapid previews → 1 asset request/projection. |
| K3 | Kimi 3 | `LandscapeArt` onerror keeps the previously shown image (remove `setLoaded(null)`). | failed load keeps prior `img`. |
| K4 | Kimi 4 | World presentation only: render the two options in visual order (no = left, then yes = right) so Tab order matches; labels/handlers unchanged; other presentations keep tree order. | world DOM order no→yes. |
| K5 | Kimi 5 | `AtlasRoute`: handle the native `<dialog>` `cancel` event (`onCancel` → `preventDefault(); requestClose()`), drop the Escape branch from `onKeyDown`; focus return unchanged. | Escape closes once and focus returns to opener. |

Rejected with evidence (no change): Qwen 1 (`useId` colons) — measured `useId()` = `_R_0_` on the repo's React 19.2/19.3, no colon; Qwen 3 (arrival truncated by readiness deps) — arrival only starts when both are already true and they never flip back while the permit art stays mounted, so the re-run cannot happen inside the window; Qwen 4/5 — preserved behaviour / debug attribute, not regressions (coordinator ruling).

## D. Harness and acceptance (Pro only)

Harness `research/.../qa/atlas-qa.local.spec.ts` → copy to Pro mirror `apps/mouth/e2e/`. Its geometry asserts are
`expect.soft` (they collect every screenshot) — soft is NOT a pass: acceptance is **0 failed** tests. You may
refine the clipped-control filter only to skip genuinely visually-hidden nodes (computed `visibility:hidden`,
`opacity:0`, `clip`/`clip-path` rect of 1px sr-only pattern) — never to hide real clipping. Probe
`qa/atlas-diag.local.spec.ts` (copy likewise) prints the containing-block chain; extend it if you need to find A10.

Pro commands (blocking, foreground — never `run_in_background`, never Monitor, never end your turn while
something runs): sync `R/` and `apps/mouth/public/static/visa-oracle/` with the rsync form in BUILD-SPEC §9 /
previous rounds; `npx tsc --noEmit -p .`; `npx vitest run "src/app/(visa-oracle)"`; `npx next build`; restart
`next start --port 3949` (kill only the PID listening on 3949); harness `ATLAS_QA_OUT=/tmp/oracle-prod-0927/qa4`;
PR gate e2e `--grep "page Page\|@offline"` must stay 46/46. Output bounded (`| tail -40`). Never `rm -rf`
(guardrail blocks it) — write new output dirs instead.

Acceptance: harness 0 failed (EN/ID × desktop/mobile/narrow, stage geometry 1024/1280/320, dark, reduced
motion); vitest all green (report files/tests count); tsc 0; gate e2e 46/46; you Read and describe the jpgs
for entry/world/permit at 1440 and 390 EN+ID, watershed 390, caption desktop — pins next to their labels
(no→South America, yes→"Indonesia"), nothing overlapping, checkboxes visibly empty when unchecked.
