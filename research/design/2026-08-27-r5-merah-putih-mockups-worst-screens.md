---
date: 2026-08-27
domain: design
client_case: none
round: R5 — mockups (Design Study Loop, Zero mandate 2026-08-27)
sources:
  - R4 identity contract — research/design/2026-08-27-r4-identity-merah-putih-token-spec.md (PR #5078; tokens, contrast law, component contracts, application map, §8 acceptance split)
  - R3 autopsy — research/design/2026-08-27-r3-heuristic-autopsy-defect-inventory-axis-gap.md (PR #5074; the worst-screen selection below is its severity table)
  - Zero's rulings + STANDING pre-confirmation — loop memory project_design_study_loop_garuda_visa_oracle_2026_08_27.md
adversarial_review: codex gpt-5.6-sol xhigh (25) + kimi-k3 (18) + agy gemini-3.1-pro (20) — qwen3.8-max TP1 seat FAILED twice (connection reset, then read timeout on a small payload; the door itself was degraded — recorded honestly)
---

# R5 — Merah Putih mockups on the screens R3 rated worst

**What this round is.** R4 wrote the contract; R5 is the first thing built against it: **ten** static, self-contained HTML mockups implementing the Merah Putih identity on the screens R3's defect inventory rated worst. Per the loop mandate there is NO product code — these files live under `research/design/mockups/r5-merah-putih/` and are design-study artifacts. Per R4 §8, static mockups prove VISUAL claims only; every behavioral claim (focus traversal, aria-live announcement, keyboard, dvh/svh, resumable upload) is R5b's mandate and is not claimed here — the mockups DO carry the static half (focus-visible rules, aria attributes, inputmode) so R5b tests behavior, not markup archaeology.

This file is Rev 2: the first draft went through the four-seat panel (63 findings) and was rebuilt against it — the set grew from six mockups to ten (two panel-forced splits, two panel-forced additions), the shared CSS gained full-coverage focus, 44px shell targets, real shadows, an AA placeholder color and the dark primitives, and the static checker was rewritten because its first version produced presence-only passes (a vacuous check is not a check).

**Foundation.** `_tokens.css` transcribes the R4 token set — grounds, red family, five states, border-input, the dark-floor primitives, typography with the Cormorant 24px floor (h3 and below are Inter 600), radius 12 with a declared nested-radius floor, the 44px house touch floor with ≥8px stacked-CTA clearance, double-ring focus on every interactive element, the non-color-alone error pattern with programmatic association, the WhatsApp card-with-icon component. Every hex is an R4 token; no new color was invented in R5.

## §1 The screen selection (from R3's severity table)

| Mockup | Screen | Defects cured (visual layer) |
|---|---|---|
| M1 | GARUDA VOA landing | **D-G1 (sev 4)** dark-navy → carta+red · D-G9 Q6 floor in landing · full identity header · trust strip per spec |
| M2a | GARUDA question | D-G2 selection never red (ink outline + check, aria-checked) · D-G3 counter law |
| M2b | GARUDA upload | D-G5 custody placeholders · non-color-alone error with `aria-invalid`/`aria-describedby` · real file affordances (Take photo / Choose file) |
| M3 | VO question (overstay) | D-V3 question above the fold · D-V6 why-we-ask BEFORE the field · D-V1 identity header · D-V2 canopy → red per budget · D-V11 branch announcement (context-coherent: «Immigration history — 2 questions») |
| M4a | VO verdict HUMAN_REVIEW — variant A (named) | D-V9 primary action bound to a person + window · opaque-code wa.me · no price on this verdict (C1) |
| M4b | VO verdict HUMAN_REVIEW — variant B (control) | same page, no names — the R6 people-vs-seals test compares M4a vs M4b as whole pages |
| M5 | VO verdict SUPPORTED + payment | exact bundle price at quoted verdict, checkout line and pay CTA — **three renderings, verbatim-identical** (Q6c) · selectable QRIS/VA/cards rails · honest-human module (R4 wants it on every verdict screen) |
| M6 | my.balizero.com tracker | D-M1 / ruling Q-R3.1: copper → carta+red, same shell (D-M2 seam stays a hypothesis — flag carried) |
| M7 | VO landing | the pre-form half of D-V8/Q9 the first draft missed: the floor BEFORE the interview, on VO's own landing |
| M8 | GARUDA error/recovery | D-G4 checkout dead-end gets a recovery route · D-G7's error half: an error state WITH a person, a retry, and a saved-state line scoped to the case code |

M2a/M2b and M4a/M4b are panel-forced splits (one thing per page; one variant per page — two stacked primary CTAs broke the mobile hierarchy). Each file renders at both acceptance viewports (360px — the Indonesian Android floor — and 390px) from the same responsive markup; the artifact shows both side by side.

## §2 Non-obvious choices, per mockup

- **Prices are width-realistic masked numerals**, not placeholders alone and not real numbers: `IDR 1.5XX.XXX` (floor) / `IDR 1.7XX.XXX` (bundle), rendered inside dashed `.ph` markers with the registry key alongside. The panel's objection was right — a bare `{FLOOR_IDR}` proves neither typography nor 360px fit — but transcribing a live price into a study artifact would go stale while looking authoritative (PricingTool is the sole price source, golden rule 11). The masked numeral proves the pattern at true width; the dashed border keeps it honestly fake.
- **M1/M7**: the trust strip prints `PT {PT_LEGAL_NAME} · NPWP {NPWP} · {REGISTRY_LINK}` — all placeholders. The first draft printed an invented PT name; the panel caught it as exactly the invented-fact pattern the placeholder system exists to prevent (one seat proposed a "corrected" spelling — also unverified, also not adopted; the audit owns that string now).
- **M2b**: the error example is a real rejection class (PDF where a photo is required) with the three-channel pattern (wine border + icon + recovery verb) AND the programmatic channel (`aria-invalid`, `aria-describedby`). Custody renders `{CUSTODY_WHO_SEES}` / `{CUSTODY_RETENTION}` as visible dashed markers.
- **M3**: «Your path so far» collapses to a one-line chip; the branch note now announces the section the question actually belongs to («Immigration history — 2 questions. Your total updated from 9 to 11») — the first draft pasted a sponsor-section announcement above an overstay question, a context collision the panel caught. The why-we-ask card states the true consequence (human review, not exclusion) and carries a dated rules line.
- **M4a/M4b**: identical pages except the human module — that is the R6 experiment, isolated. `{FOTO}` avatar and `{NAMED_AGENT}` are registered markers; the SLA line carries `{SLA}` and `{OFFICE_HOURS}` WITA (an unqualified response window at a 2am airport arrival is a false promise).
- **M5**: the price renders three times (verdict, checkout total, pay CTA) and the copy binds them «to the rupiah» (Q6c). Rails are selectable radio pills — QRIS first, VA BCA/Mandiri, then cards. The FX line states only what is true by construction («your bank's FX rate applies») plus `{FX_POLICY}` for the part nobody audited. The bundle never names the PNBP figure (charter guardrail).
- **M6**: the active step is the one red element — a 22px dot; the step LABEL is ink (the first draft had a red label: a `merah` text duty the token table forbids). Timestamps are mono. «Typical wait» is `{IMMIGRATION_WAIT}` — the 3-5-days promise of the first draft was an unaudited fact.
- **M8**: the saved-state line promises only what the case code makes true («your answers up to this step are saved under case code BZ-7Q4K») — recovery, not reassurance-theater.

## §3 Visual acceptance run (R4 §8, static-provable items only)

Machine-checked (`checks.json`, produced by `assemble.py` — both shipped in the mockups directory; every check can go RED and two did during development, caught as parser errors and fixed against the real CSS):

- Cormorant floor 28/24px, h3 = Inter — **pass** · full identity header (wordmark + EN/ID + WhatsApp **entry as a real link**) on all ten — **pass**
- Company identifier + dated rules line on all ten — **pass** · counter on question screens, explicit `n/a` elsewhere (no vacuous true) — **pass**
- IDR containment: every IDR occurrence inside a mono/ph nowrap span — **pass** (m4a/m4b/m8 report `n/a`: no amounts)
- WhatsApp: mentioned ⇒ card or entry present, else `n/a` — **pass** · selection never red, with padding-compensated 2px ink border (no 1px reflow jitter) — **pass**
- Red budget: inline red uses ≤ documented whitelist (M6's 22px dot only) — **pass**; the progress fill and CTAs get red from the shared classes, and no screen paints a red field taller than its CTA
- Focus: the `:focus-visible` block covers `.cta`, `.option`, `.wa-card`, `.wa-entry`, `.lang-toggle span`, links, buttons, inputs — **pass** · `::placeholder` ink-soft (7.64 on white; UA default measured 2.35) — **pass**
- Touch: 44px on options/CTAs/inputs AND shell (lang-toggle 44px, wa-entry 44×44), ≥8px stacked-CTA clearance — **pass**
- Interactive containers carry border-input + shadow (elevated-vs-carta is 1.08) — **pass** · progress track has a real boundary (was 1.22 alone) — **pass**
- Dark primitives present in CSS · reduced-motion honored · buttons/inputs inherit Inter — **pass**
- Guarantee-language scan (never/guarantee/dijamin) — **pass** (the first draft's «never blocks your application» was caught and rewritten)
- Placeholder markers: M1 ×6 · M2a ×2 · M2b ×4 · M3 ×2 · M4a ×7 · M4b ×5 · M5 ×10 · M6 ×7 · M7 ×5 · M8 ×6 — **pass**

**APCA advisory annex** (R4 §8 asked for it; APCA-W3 0.1.9 constants, advisory only — WCAG 2.x stays the binding bar): ink/carta **Lc 97.5** · ink/white 102.9 · ink-soft/carta 81.1 · ink-soft/white 86.5 · merah-action/carta (links) 69.8 · white/merah-action (CTA) −80.6 · state-error/white 80.3 · state-conditional/carta 78.2 · /white 83.7 · state-eligible/white 83.1. All key text pairs clear APCA's ~Lc 60 body-text guidance; the weakest (links at 69.8) is bold-weight in practice.

Eye-checked in this session: question above the fold at 360px for M2a/M3 — the pre-question stack measures ≈195-200px once the branch note wraps to two lines (header ≈47 + progress block ≈104 + chip ≈38; the first draft's "~180px" arithmetic was wrong — the panel recomputed it — but the conclusion holds: the h2 starts well inside the first viewport).

**Not proven here (R5b/R6):** actual fold behavior with dynamic browser toolbars (dvh/svh), aria-live runtime announcements, focus traversal order, keyboard-only completion, upload resumability, FX display correctness, and every psychological claim (the honest-human variants exist as M4a/M4b; whether A beats B is exactly R6's test).

## §4 Placeholder registry (the audited-facts constraint, enumerated)

| Marker | Meaning | Owner / unblock |
|---|---|---|
| `{FLOOR_IDR}` (masked `IDR 1.5XX.XXX`) | lowest bundle in the price list (static catalog floor, Q6) | PricingTool — product lane, outside the loop |
| `{BUNDLE_EXACT}` (masked `IDR 1.7XX.XXX`) | quoted bundle for a SUPPORTED case | PricingTool / quote engine |
| `{PT_LEGAL_NAME}` / `{NPWP}` | the formal company identifier pair on every screen | corporate registry audit — never typed from memory |
| `{REGISTRY_LINK}` | public registry destination for the identifier | R1 UNKNOWN 7: no verification path audited — until it exists, no «verify» language |
| `{NAMED_AGENT}` / `{FOTO}` | the person (and photo) bound to the case | Zero roster decision (Legge 5) |
| `{SLA}` / `{OFFICE_HOURS}` | response window + hours (WITA) | Zero operational commitment (Legge 5) — never shipped by design |
| `{CUSTODY_WHO_SEES}` / `{CUSTODY_RETENTION}` | passport-photo custody facts | ops audit that does not exist yet (R1) — ENG/ops prerequisite |
| `{APPLY_MINUTES}` | honest completion-time claim (M1) | measured from real funnel data, not asserted |
| `{IMMIGRATION_WAIT}` | typical office wait (M6) | measured from case history, not asserted |
| `{FX_POLICY}` | what we add on FX, if anything (M5) | finance decision + audit |

## §5 Copy decisions declared

1. **Bundle-only pricing copy** (Mohan split-under-total NOT adopted): Q7 ruled bundle; M5 shows one number plus the honest FX sentence. The split stays available to a future ruling.
2. **The date form** is `27 Aug 2026` everywhere a date renders — the unambiguous form; the dated rules line (organ P4) now appears on ALL ten screens, including question screens making regulatory claims.
3. **Case codes** (`BZ-7Q4K`, `BZ-3M8A`) are opaque, mono, and the wa.me sub-line says so out loud.
4. **No guarantee language**: «asking doesn't decide your case — you stay in control» replaced the first draft's «never blocks your application».

## §6 What this round deliberately does not do — declared, each with a reason

- **No home mockup**: the band exception is real but home was not among R3's worst screens.
- **No dark-mode mockups — DECLARED DEVIATION**: R4 assigned the full dark system to R5. This round ships the dark PRIMITIVES in `_tokens.css` but defers dark component mockups to R5b, where focus/keyboard behavior can be proven together with the dark set; a static dark screen would only re-prove ratios already in the R4 pair list. Veto point: if Zero wants a static dark screen in R5, M3-dark is the candidate.
- **D-V5 (nationality predictive search) and D-V12 (DOB necessity)**: behavior and question-tree content respectively — R5b's mandate; a static mockup would fake both. The ENG lane (PR #5077) already shipped the CountryPicker search itself.
- **No KBLI/tax/property** (NON-CONFORMING debt, no deadline — Legge 5).
- **Nesting-law amendment proposed to R4**: «inner radius = outer − padding» yields negative radii for realistic paddings; the CSS uses a declared floor (`--radius-nested: 8px` = max(8, outer−padding)) — R4 should absorb this amendment at the next touch.
- **`.ph` markers are meta-markup of the mockup**, exempt from the product shape law (their 4px radius and dashed border are the honesty flag, not a product component).

## §7 Adversarial review

Seats and counts: **codex gpt-5.6-sol xhigh 25** (13 HIGH — all 25 applied; the price finding applied as masked numerals rather than live prices) · **kimi-k3 18** (17 applied, 1 partial: the `.ph` radius stays, declared exempt; kimi's recomputation calibrated against R4's pair list exactly) · **agy gemini-3.1-pro 20** (19 applied, 1 rejected: «Visa on Arrival» keeps its proper-noun capitals — sentence case governs the sentence, not the noun) · **qwen3.8-max TP1 seat FAILED** — connection reset, then a read timeout on a small payload at retry; the door itself was degraded (the same probe cycle showed codex/kimi seat timeouts earlier today). Recorded honestly: zero findings ingested. Per-finding dispositions ship in the artifact's R5 `adversarial.json`.

The panel materially changed the round: +2 mockups (M7, M8), 2 splits (M2a/b, M4a/b), a rewritten checker whose passes can fail, an APCA annex, three unaudited facts caught in copy (PT name, wait days, apply minutes) and one banned guarantee phrase. Generator≠grader earned its cost here.

## §8 Ruling declarations (adopted under the standing pre-confirmation, async veto open)

1. **Honest-human default = Variant A (named)** (M4a), with B (M4b) as the operational fallback when no person can be bound to the case. Alternative: B as default. Adopted: A — R1's surviving evidence leans person-over-seal; R6's test can still overturn this (the declaration sets the default, not the verdict).
2. **Bundle-only pricing copy** — see §5.1. Alternative: split under a bold total.
3. **The tracker's active step is red** (M6): one 22px dot, label in ink. Alternative: ink dot (zero red outside CTAs). Adopted: red-active dot — progress is one of red's two ruled duties and the tracker step IS progress; the panel's separate point (red on the LABEL) was a real duty violation and is gone.

## §Meta

R5 is where the contract meets a viewport — and where the panel met the mockups' own honesty devices. The first draft failed its own standard three times (an invented PT name, an invented wait time, a guarantee phrase) while shipping dashed placeholders everywhere else; the checker that was supposed to catch drift produced passes that could not fail. Both lessons are now structural: every fact in copy is either dated, masked, or a registered marker — and every check in `checks.json` has a way to go red.

## §Solo-operatore

Reproducible alone: open any mockup at 360/390px; `python3 assemble.py` (shipped WITH the mockups, alongside `checks.json` and the `.body.html` sources) re-runs every static check and the APCA annex from the same directory; every token traces to the R4 spec file; the placeholder registry (§4) names who unblocks each marker. The four-seat log with per-finding dispositions is in the artifact's R5 section.
