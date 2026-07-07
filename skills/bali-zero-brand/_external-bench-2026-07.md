# External Bench 2026-07 — Bali Zero WR2 Design

**Captured**: 2026-07-06 (first-Monday scheduled run)
**Source universe**: 12 editorial publishers + 3 competitor + 2 trend-report families (Later/Metricool/Socialinsider + Sprout/Buffer 2026)
**Method**: Multi-LLM — Gemini 3.1 Pro (`agy`) 15-account structured ingestion (`/tmp/wr2-external-bench-gemini-2026-07.txt`, 19.6 KB) + WebFetch/WebSearch Tier-3 trend quant + DeepSeek v4-pro pattern extraction (`reasoning_effort` high→medium, 29 patterns) + Claude Opus synthesis serving as the adversarial gate.
**Cost**: ~$0.03 (DeepSeek v4-pro, 2 calls, 22.6k + 21.4k tokens — first call hit `finish_reason=length` at max_tokens=16000 with 12.2k reasoning tokens; re-run at `reasoning_effort=medium` / max_tokens=28000 returned clean 29-pattern JSON). Gemini free OAuth, Claude MAX flat, WebFetch free.
**Adversarial gate (Opus)**: DeepSeek over-adopted (22 ADOPT of 29). Opus synthesis corrected **5 over-adopts** against Article 15 + June institutional memory (bold-swipe-arrows, editorial-kicker-label, monospace-progress-counter, no-social-graphics-minimalism → REJECT; feed-grid-coherence → OBSERVE) and **2 factual errors** (DeepSeek said regulation-badge uses red — it is yellow #F4C430 since the 2026-05-13 WCAG revision; DeepSeek cited Art 14.2 for brand-mark — correct is Art 4). This Opus pass replaces June's separate DeepSeek devil's-advocate call — the generator≠grader separation is preserved (DeepSeek generates, Opus grades).
**Carryover input**: `_external-bench-2026-06.md` (25 patterns: 8 ADOPT / 7 PARTIAL / 3 OBSERVE / 7 REJECT).
**Internal cross-reference**: `_proposed-amendments/2026-06-29-ig-insights.md` (freshest weekly analyst run, N=42 corpus).

---

## Executive summary

The mid-2026 editorial-IG shift catalogued in June (transparency layer + annotated data + polarized length) has **hardened into a documentary-reference convergence in Q3**: the strongest new mechanics all serve the *saveable-reference* motive — dual-language parallel glossaries (@restofworld), swipe-progression checklists (@emerhub, @flado.id), micro-sparklines embedded in copy (@bloomberg, @qz), and official-document textures as evidence backdrops (@propublica, @themarkup). The counter-current is a **motion drift** pushing carouseli toward Reels — cinemagraph loops (@nytimes, @wired) and audiogram waveforms (@financialtimes) — which is a publishing-format decision, not a WR2 static-design rule, and stays OBSERVE.

The decisive fact this month is **convergence between the external SOTA and Bali Zero's own fresh internal evidence**: the 2026-06-29 analyst run shows the **tax domain saving at +78% vs corpus (SL 1.388, N=5)** and the **evidence-carved "prove-e-documenti" format** as the most stable save-driver — i.e. BZ's own audience rewards exactly the *visible-data-and-sources* aesthetic the SOTA is moving toward. The three gap-closing moves: (1) **dual-language-parallel-alignment** — formalize Art 6.2 into a repeatable bold-ID / light-EN glossary block, palette-native and a pure save magnet for the reference audience; (2) **swipable-checklist-progression** — a new document-checklist layout family (visa docs, PT PMA prerequisites) that is the compliance-brand analogue of Emerhub's best device; (3) **micro-sparklines + document-texture** as evidence-carved amplifiers, directly reinforcing the internally-proven winning format. Bali Zero continues to LEAD on palette restraint, single-family Montserrat, and documentary gravitas versus all three regional competitors — and June's flagship find (AI-disclosure Art 14.7) **still awaits Antonello approval on disk** (verified: not in constitution.md or _base.css), so it re-enters as a standing recommendation, not a shipped rule.

---

## Source roll-call

| # | Source (current handle) | Tier | Status | Sample basis |
|---|---|---|---|---|
| 1 | @nytimes | 1 | ingested | type system, cinemagraph, caption box, minimal close |
| 2 | @ft → **@financialtimes** | 1 | ⚠ handle-changed | salmon discipline, quote spine, audiogram, framed assets |
| 3 | @reutersphotos | 1 | ingested | full-bleed photojournalism, panoramic split, BTS video |
| 4 | @wired | 1 | ingested | numbered slides, mono data labels, scanline texture, neon-on-dark |
| 5 | @bloomberg | 1 | ingested | data-hero, micro-sparklines-in-text, yellow accent, slide numbering |
| 6 | @qz | 1 | ingested | progress numbering, hand-drawn annotation, narrow palette |
| 7 | @pudding.cool → **@thepudding** | 1 | ⚠ handle-changed | integrated progress bar, scrollytelling split, methodology close |
| 8 | @restofworld | 1 | ingested | dark-mode + magenta accent, dual-language overlay, numbered |
| 9 | @propublica | 1 | ingested | crimson kicker, redacted-document texture, QR close |
| 10 | @themarkup | 1 | ingested | mono-heavy, privacy-card mockups, progress bar |
| 11 | @drift_official → **@driftmag** | 1 | ⚠ handle-changed | print-magazine layout, paper-grain / page-turn texture |
| 12 | @pentagram → **@pentagramdesign** | 1 | ⚠ handle-changed | kinetic-branding hybrid slides, massive type |
| 13 | @letsmoveindonesia | 2 | ingested | WhatsApp-UI slides, corporate blue/yellow, contact-close |
| 14 | @emerhub_official → **@emerhub** | 2 | ⚠ handle-changed | swipe-progression checklists, process flows, corporate blue |
| 15 | @flado.bali → **@flado.id** | 2 | ⚠ handle-changed | dark-mode checklist, Syne+serif, gold/green accent, WA-close |
| 16 | Later/Metricool/Socialinsider 2026 | 3 | ingested | engagement quant, lifecycle, slide-count |
| 17 | Sprout/Buffer 2026 | 3 | ingested | AI-disclosure enforcement, DM-share weighting, save benchmarks |

**⚠ Six Tier-1/2 handles changed** since the reference universe was last reviewed (FT, Pudding, Drift, Pentagram, Emerhub, Flado). All six accounts are still active under the new handle — logged, NOT silently substituted (per spec §"If a brand's IG handle has changed… log in output file and skip"). **Recommend Antonello update the closed-set handles in `wr2-external-bench.md` at the next annual review.**

**Trend-report quant retained for downstream agents**: carousel engagement 0.55–0.72% (Socialinsider Q1 0.55; Metricool +30.9% YoY to 0.72) — highest of all formats; **9× more saves than single image, 2× saves vs Reels**; +109% engagement vs Reels (Buffer); 3× reach vs single image; **DM sends weighted 3–5× likes**; lifecycle: **76% of views + 75% of interactions in first 72h, day-1 = 44%**, algorithm re-serves high-swipe carouseli 24–48h later; slide sweet-spot **6–13** (drop beyond ~13), max 20; **20% text-overlay max per slide**; AI-disclosure enforcement: **IG flags 94% of undisclosed branded AI content within 24h, repeat violators −31% reach**; proof-slides best at position 7–9; a question on the last slide can double first-hour comment rate; best window Tue–Thu 10:00–12:00 audience-TZ.

---

## 29 patterns extracted — Bali Zero applicability

Decision summary: **9 ADOPT · 8 PARTIAL · 4 OBSERVE · 8 REJECT** — **9 patterns NOT in the June carryover** (anti-stagnation requirement ≥2: exceeded).

### ADOPT (compatible + likely improves Save/Share)

| # | Pattern | Novel | Brands | When it works | Where to wire it in |
|---|---|---|---|---|---|
| 1 | **dual-language-parallel-alignment** ⭐ | **YES** | @restofworld, @flado.id | Every post introducing an Indonesian legal term (NPWP, KITAS, SHM, KBLI) to an expat audience | **NEW layout block**: bold ID term (Montserrat 700) + light EN gloss (Montserrat 300) directly beneath, weight-contrast hierarchy — NO color, NO serif, axis-aligned (Art 3/9 clean). Formalizes Art 6.2 first-occurrence assist into a repeatable *saveable pocket-glossary* device. Directly amplifies the reference-save motive the 2026-06-29 analyst run proves is BZ's strongest driver. |
| 2 | **swipable-checklist-progression** ⭐ | **YES** | @emerhub, @flado.id | Visa document checklists, PT PMA prerequisites, property due-diligence lists | **NEW layout family** `layouts/checklist-progression.md`: static per-slide advance (slide N shows items 1..N ticked), yellow checkmarks (#F4C430 = verifiable-facts family color, Art 2), Montserrat, Swiss-grid. Compliance-brand analogue of Emerhub's best device — a pure save magnet (9× carousel save multiplier). Sibling of process-step-map. **Honesty note**: static carousel cannot truly animate a tick; the device is per-slide state advance, not interactivity — document so critic does not expect motion. |
| 3 | **data-annotation-callouts** | carryover | @wired, @bloomberg, @thepudding, @restofworld | Charts/maps of tax brackets, deadlines, fines, zones | Confirmed from June #2. Yellow pointer to load-bearing datum (Art 2), axis-aligned (Art 9). No naked charts. |
| 4 | **process-step-map** | carryover | @bloomberg, @qz, @restofworld, @emerhub | Regulatory how-to (KITAS flow, PT PMA setup, LKPM filing) | June #3 — layout **NOT yet created on disk** (verified: no `layouts/process-step-map.md`). Re-recommend building it; the tax-domain save win (+78%) makes it higher-priority than in June. |
| 5 | **translucent-caption-pill** | carryover | @nytimes, @financialtimes, @restofworld | One sentence of context over a full-bleed photo | June #4 — `caption-pill` class **NOT yet in `_base.css`** (verified). Re-recommend: antracite ~75% translucent scrim, white/yellow text. NOT an Art 15 pill (legibility scrim ≠ color-coded label). |
| 6 | **ai-disclosure-label** ⭐ | carryover | @nytimes, @financialtimes, @wired (+ Meta/EU enforcement) | Any carousel with an AI-generated hero | June #1 flagship — **NOT shipped** (verified: no Art 14.7 in constitution.md, no label class in _base.css). Enforcement hardened since June (IG flags 94% undisclosed AI in 24h, −31% reach for repeat). Re-enters as standing recommendation pending Antonello. Spec: 7–8pt Montserrat, white ~40% on dark corner, "AI-assisted image / Gambar berbantuan AI". |
| 7 | **swipe-indicator-dot** | carryover | @financialtimes, @wired, @bloomberg | All (slides 2..N-1) | SHIPPED Art 14.1 — confirmed still convention. Defend. |
| 8 | **regulation-badge-top-right** | carryover | @propublica, @themarkup, FT-class | Policy/legal covers with a primary code | SHIPPED Art 14.4 — confirmed. **Yellow #F4C430 / black text** (WCAG AAA, 2026-05-13). DeepSeek's "uses red" was WRONG — corrected. |
| 9 | **brand-mark-corner** | carryover | @financialtimes, @wired, @bloomberg, @qz | All (protects attribution in shared screenshots) | Art 4 — confirmed (DeepSeek mis-cited Art 14.2; corrected). DM-share weighting (3–5×) makes screenshot-durable branding more valuable this month. |

### PARTIAL ADOPT (compatible but needs adaptation)

| # | Pattern | Novel | Why partial |
|---|---|---|---|
| 10 | **scrollytelling-split-screen** | **YES** | @thepudding, @nytimes, @themarkup pin one visual (map/document/chart) on half the canvas while annotations change across slides. Extends June #12 split-image; `layouts/photo-fullbleed-split.md` already exists as a base. Strong for multi-step legal processes (visa flow with a pinned Bali zone-map). **Build cost**: layout-composer must hold a persistent asset with changing overlay across N slides, and must satisfy Art 5.10 sha256-uniqueness (a pinned asset re-used across slides is legitimate here but must be whitelisted so critic does not false-fail it as silent placeholder reuse). A/B before promoting. |
| 11 | **micro-sparklines-in-text** | **YES** | @bloomberg, @qz embed mini trend-charts *inside* body copy (tax-rate shift, fee change) instead of a separate chart slide. Palette-native (yellow sparkline on antracite). Directly amplifies the internally-winning evidence-carved format. **Caveat**: at 1080×1350 phone scale an in-text sparkline risks sub-WCAG legibility — needs a min-height spec and restriction to hard numeric trends only. Specialized extension of #3. |
| 12 | **redacted-document-texture** | **YES** | @propublica, @themarkup layer a semi-transparent official-regulation scan as an evidence backdrop. Kernel is strong for BZ ("this comes from the source") and converges with the evidence-carved winner. **Adaptation**: must be desaturated to greyscale/antracite to stay inside Art 2 (no new colors), used sparingly on key-announcement slides only. Distinct from June's os-window OBSERVE (that was retro-tech skin; this is document-as-evidence). |
| 13 | **slide-numbering** | carryover | June #14 — Reuters/RoW "01/05". Adopt ONLY for 8+ deep-dives; redundant on 4–5 punches. Coordinate to ONE progress device per carousel (dot vs bar vs numbering). |
| 14 | **progress-bar** | carryover | June #9 — thin custom bar (@thepudding, @themarkup) replacing dots. Overlaps shipped Art 14.1 dot. Wire as `_base.css` variant, A/B vs dot — do not silently replace an empirically-grounded shipped device. |
| 15 | **full-bleed-photo-cover** | carryover | June #15 — only when the photo is dark enough to carry yellow/red overlay text (existing `cover-photo` constraint). Pairs with #5 caption-pill. |
| 16 | **per-slide-photo-credit** | carryover | June #13 — BZ heroes are mostly AI-generated, so "photo credit" is wrong; adapt as ONE unified image-attribution corner slot carrying "AI-assisted image" (#6) OR "Photo: X" by source type. |
| 17 | **alt-text-accessibility-note** | carryover | June #11 — adopt at PUBLISHING-checklist level (per-slide alt-text in the Damar handoff), not as a slide-design change. IG weights accessibility for reach. |

### OBSERVE (not clearly beneficial — log for A/B)

| # | Pattern | Novel | Watch for |
|---|---|---|---|
| 18 | **cinemagraph-hybrid-motion** | **YES** | @nytimes, @wired, @pentagramdesign insert subtle documentary loops (drifting light, city traffic) into an otherwise static slide to lift dwell time. **Out of WR2 static-design scope** — it converts a carousel toward a Reels/video asset (publishing-format decision, like June's music-on-carousel flag). If ever tested, motion MUST stay strictly documentary-photoreal (Art 5.8), never surreal. Flag to Antonello as a production-side option, not a design rule. |
| 19 | **audiogram-waveform-overlay** | **YES** | @financialtimes, @propublica overlay an audio waveform on a quote slide. Audio is not native to text-based regulatory advisory; no evidence it lifts saves for law content. No constitutional violation but same motion/publishing-scope caveat as #18. Pure OBSERVE. |
| 20 | **source-citation-tiny** | carryover | June #18 / Art 14.3 DEFERRED — layout `source-citation.md` exists, critic 5.5 soft-advisory, A/B still pending. The evidence-carved save win strengthens the case; re-raise for promotion. |
| 21 | **feed-grid-coherence** | carryover | June #16 — 3-column profile mosaic. DeepSeek re-proposed ADOPT; **downgraded to OBSERVE** (ops cost — WR2 pipeline has no profile-level feed-planning step). Locked palette already gives soft grid coherence for free. Revisit only if a feed-planning step is built. |

### REJECT (incompatible with brand or empirical data)

| # | Pattern | Novel | Why reject |
|---|---|---|---|
| 22 | **tactile-print-texture** | **YES** | @driftmag, @pentagramdesign, @financialtimes paper-grain / page-turn shadows. Ornamental texture contradicts documentary-photoreal (Art 5) and Swiss-grid cleanliness (Art 9); it is the exact luxury/print register BZ rejects. Institutional memory: do not re-propose. |
| 23 | **hand-drawn-sketch-annotations** | **YES** | @qz, @thepudding messy handwritten arrows over clean charts. Off-axis handwriting violates Art 9 (all text 0°) and the informal-doodle register conflicts with regulatory authority. The legitimate need (pointing at a datum) is already served by #3 data-annotation-callouts, axis-aligned and type-set. |
| 24 | **chat-bubble-conversational-ui** | carryover | @letsmoveindonesia, @flado.id, @emerhub faux-WhatsApp/Slack mockups. June #22 REJECT confirmed — not documentary-photoreal (Art 5), imports LMI template-clutter register. **Note**: BZ already has a brand-compliant Q&A device (`layouts/qa-dialogue.md`, SL 1.54 on the villa-compliance post) that delivers the humanized-advice benefit WITHOUT aping a messaging app — that is the sanctioned alternative. |
| 25 | **thin-serif-frames** | carryover | @financialtimes, @qz, @driftmag serif stroke borders. Serif banned outright (Art 3). June #23 confirmed. |
| 26 | **editorial-kicker-label** | carryover | DeepSeek said ADOPT ("part of archetype taxonomy") — **WRONG, corrected to REJECT**. June #19: Art 15.4 HARD-FAIL (color-coded pill/kicker labels banned). The archetype (Art 13) IS the editorial label; an uppercase category pill is redundant chrome. Institutional memory. |
| 27 | **monospace-progress-counter** | carryover | DeepSeek said ADOPT — **corrected to REJECT**. June #21 (DA-corrected): duplicate of slide-numbering + a typography violation (mono restricted to IBM Plex *source footers* only, Art 3 — a nav counter is not a source footer). |
| 28 | **bold-swipe-arrows** | carryover | DeepSeek said ADOPT ("functional navigation") — **corrected to REJECT**. June #24 (DA-corrected): oversized swipe arrows are listicle-pap engagement gimmick and LMI's clutter device; Art 14.1 dot already covers the affordance with restraint. |
| 29 | **no-social-graphics-minimalism** | carryover | DeepSeek said ADOPT — **corrected to REJECT** (of the maximalist "strip all devices" reading). June #25: Pentagram zero-device purity contradicts SHIPPED Art 14.1 dot + 14.4 badge, both empirically grounded. BZ already omits social-overlay chrome (like/share icons) — that part needs no action; the REJECT targets stripping the shipped functional devices. |

---

## Bali Zero gap analysis

1. **The external SOTA and BZ's own fresh data now point the same way — exploit it.** The 2026-06-29 analyst run: tax domain SL 1.388 (+78% vs corpus 0.780, N=5), evidence-carved "prove-e-documenti" the most stable save-driver. The Q3 SOTA convergence (annotation callouts, micro-sparklines, document textures, dual-language reference) is *the same aesthetic*. BZ should lean hard into visible-data-and-sources design — it wins on both baselines simultaneously. This is the strongest, lowest-risk direction of the month.
2. **BZ has no bilingual layout DEVICE, only a copy rule.** Art 6.2 (English assist on first occurrence) is delivered inline; the SOTA (RoW) has turned it into a *structured weight-contrast glossary block* that reads as a saveable pocket-guide. For an expat regulatory audience this is the single highest-leverage new layout — palette-native, zero brand risk. Pattern #1.
3. **Utility content still lacks a checklist device.** June flagged the process-step-map gap; the layout was never built (verified on disk). Q3 adds the checklist sibling (@emerhub/@flado.id) — a document-checklist progression that is a pure save magnet for exactly the visa/PT-PMA/property-DD content BZ sells. Two related layouts (#2 checklist, #4 step-map) remain unbuilt. Priority raised by the tax save win.
4. **June's flagship (AI-disclosure) is still un-shipped while the enforcement risk grew.** Verified: no Art 14.7 on disk. Meanwhile IG now flags 94% of undisclosed branded AI in 24h with −31% reach for repeat violators — a measurable distribution penalty, not just a trust argument. For a compliance brand publishing AI heroes every carousel, this is now a *reach* liability, not only a coherence gap. Re-raise for approval.
5. **A motion drift is coming BZ should consciously decline (for now).** Cinemagraph + audiogram push carouseli toward Reels. BZ's edge is static documentary gravitas + reference-save utility; chasing motion would dilute it and sits outside WR2 static-design scope. Log as OBSERVE and let the publishing side decide, don't bake into the design pipeline.

**Where BZ leads (defend, do not regress)**: locked two-accent palette + single-family Montserrat (the restraint the SOTA keeps converging on); documentary photographic gravitas versus all three regional competitors (LMI WhatsApp-UI clutter, Emerhub corporate flat-illustration, Flado banned dark-luxury serif register); shipped Art 14.1/14.2/14.4 matching the convention set; the `qa-dialogue` device already delivers humanized Q&A without messaging-app mimicry; the six-anchor headline discipline and S-pattern remain uncontradicted by July evidence.

---

## Recommended changes this month

1. **NEW layout — `layouts/term-gloss.md`** (pattern #1, ADOPT ⭐): bold-ID / light-EN weight-contrast bilingual block formalizing Art 6.2. Highest-leverage, zero-risk. Cite: @restofworld dual-language; internal reference-save motive (2026-06-29 tax +78%).
2. **NEW layout — `layouts/checklist-progression.md`** (pattern #2, ADOPT ⭐): per-slide static checklist advance, yellow checkmarks. Cite: @emerhub/@flado.id; carousel 9× save multiplier; document-heavy BZ services.
3. **Build the still-missing June layouts** (patterns #4 step-map, #5 caption-pill): `layouts/process-step-map.md` + `_base.css` `.caption-pill` class — both proposed in June, **verified absent on disk**. Tax-domain save win raises priority.
4. **`_proposed-amendments/` — re-draft Art 14.7 AI-image disclosure** (pattern #6): unchanged spec from June, now with the added enforcement evidence (94%/24h flag, −31% reach). NO auto-merge — Antonello veto stands.
5. **`wr2-layout-composer.md`** (patterns #11, #12): micro-sparklines allowed inside body copy ONLY for hard numeric trends with a min-height legibility floor; redacted-document texture allowed desaturated-to-antracite on key-announcement slides only. Both amplify the evidence-carved winner.
6. **`wr2-critic.md`**: (a) whitelist the scrollytelling pinned-asset (#10) so an intentionally-repeated reference visual is not false-failed under Art 5.10 sha256-uniqueness; (b) re-affirm the REJECT institutional-memory list (#24 chat-bubble, #26 kicker, #27 mono-counter, #28 swipe-arrows) — DeepSeek regurgitated all four as ADOPT this month, so the critic must hold the line.
7. **`wr2-external-bench.md` reference universe**: flag the **6 handle changes** (FT→financialtimes, Pudding→thepudding, Drift→driftmag, Pentagram→pentagramdesign, Emerhub→emerhub, Flado→flado.id) for Antonello to update at annual review.

---

## Carryover from last month

June proposed 7 changes + carried the May-shipped devices. Status **verified on disk 2026-07-06**:

| June recommendation | Status July (verified) |
|---|---|
| Art 14.7 AI-disclosure draft (#1) | 🔴 **NOT shipped** — absent from constitution.md + _base.css. Re-raised (rec #4), enforcement risk now higher. |
| Length-polarization in storyboarder (#10) | 🟡 Not verified merged; June evidence (n=8) still too small — validate against the 42-carousel corpus (2026-06-29 analyst has N=14 in 90d window). |
| `layouts/process-step-map.md` (#3) | 🔴 **NOT created** on disk. Re-raised (rec #3), priority up. |
| `_base.css` caption-pill + progress-bar (#4/#9) | 🔴 **caption-pill NOT in _base.css** (verified). Re-raised (rec #3). |
| Chart annotation-callout soft-fail (#2) | 🟡 Pattern confirmed ADOPT again (#3 this month); enforcement status not verified. |
| Per-slide alt-text (Damar handoff) (#11) | 🟡 Publishing-checklist item, carried as PARTIAL #17. |
| Critic caption-pill vs Art-15 distinction (#6) | 🟡 Carried; add scrollytelling-whitelist (rec #6a) this month. |

**Compare vs weekly analyst amendments** (`2026-06-29-ig-insights.md`): the analyst's top finding — **tax domain +78% SL, evidence-carved/data-and-sources format as the stable save-driver** — independently confirms this month's external direction (annotation/sparkline/document-texture/dual-language reference aesthetics). External SOTA and internal evidence are **not in tension** this cycle; they reinforce. The analyst also flags generic-regulatory (LKPM/OSS without direct impact) as underperforming — consistent with June's S-pattern requirement and this month's push toward concrete, saveable, sourced utility.

**Anti-stagnation check**: **9 of 29** July patterns are NOT in the June list (requirement ≥2, exceeded): dual-language-parallel-alignment, swipable-checklist-progression, scrollytelling-split-screen, micro-sparklines-in-text, redacted-document-texture, cinemagraph-hybrid-motion, audiogram-waveform-overlay, tactile-print-texture, hand-drawn-sketch-annotations. The June flagships (AI-disclosure, length-polarization, annotation-callouts, translucent-pill, process-step-map) all re-confirmed, none falsified by July evidence.

**Era-watch — newly dated/abandoned in 2026** (extend June's table): faux-messaging-UI slides (competitor tell), hand-drawn doodle-on-chart, print-skeuomorph paper texture. BZ structurally avoids all three.

---

## Open questions / verification needed

- [ ] Antonello veto/approval on Art 14.7 AI-disclosure draft (NO auto-merge — 2nd month pending; enforcement risk now quantified).
- [ ] A/B: `term-gloss` bilingual block vs inline Art 6.2 assist (14-day Save/Like delta).
- [ ] A/B: `checklist-progression` layout on a visa/PT-PMA document post vs current bullet delivery.
- [ ] Build the 3 still-missing layouts (term-gloss, checklist-progression, process-step-map) + caption-pill class.
- [ ] Validate length-polarization against the 42-carousel corpus (n=8 → now N=14 in 90d window available).
- [ ] Update the 6 changed handles in `wr2-external-bench.md` reference universe (annual-review item).
- [ ] Motion drift (cinemagraph/audiogram): publishing-side decision — flag to Antonello, keep out of WR2 static-design scope.

---

## Maintenance

- Read by every WR2 carousel run (via `wr2-design-architect` skill load of `bali-zero-brand`) and by `wr2-ig-metrics-analyst` (weekly) + `wr2-critic`.
- Updated MONTHLY by `wr2-external-bench` (1st Monday 07:00 WITA); this edition = the 2026-07-06 scheduled run.
- DUAL-BASELINE companion to `_empirical-metrics-2026-05-12.md` (internal evidence) — this cycle the two baselines converge.
- Antonello has VETO on all ADOPT promotions to constitution Art 14. Propose, never auto-merge.
- Intermediates for audit: `/tmp/wr2-external-bench-gemini-2026-07.txt`, `/tmp/wr2-external-bench-raw-2026-07.json`, `/tmp/deepseek-bench-patterns-2026-07.json`, `/tmp/deepseek-bench-patterns-2026-07-raw.json`.
