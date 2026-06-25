# External Bench 2026-05 — Bali Zero WR2 Design (SEED)

**Captured**: 2026-05-12
**Source universe**: 100 cover SOTA + 10 inner-slide paragons from 5 buckets
- Bucket A: editorial publishers (35) — NYT, FT, Bloomberg, Reuters, Economist, WSJ, Axios, Vox, Atlantic, Semafor, AP, NewYorker
- Bucket B: data journalism (20) — Pudding, Rest of World, ProPublica, The Markup, Quartz
- Bucket C: photo-led storytelling (15) — Magnum, NatGeo, World Press Photo, AP, Drift
- Bucket D: design studio IG (15) — Pentagram, Wieden+Kennedy, Mother, Sagmeister, Collins, Studio Dumbar
- Bucket E: Indonesia region peer (15) — Kontan, Katadata, Tempo, CNN Indonesia, CNBC Indonesia, Emerhub, Flado, Lets Move Indonesia + 3 legal/tax firm
- Trend reports: Hootsuite 2026, Sprout Social 2026, Metricool 2026, New Engen, Creative Bloq, TrueFuture Media
**Method**: Multi-LLM cascade — Gemini 3.1 Pro (1M context) ingestion + DeepSeek Reasoner (×2: pattern extraction + devil's advocate) + Claude Opus 4.7 synthesis + WebSearch/WebFetch trend grounding
**Cost**: $0.04 (DeepSeek), Gemini free, Claude MAX flat
**Source file**: `~/Desktop/nuzantara/research/wr2-design-sota/2026-05-12-sota-gallery.md` (47 KB, 336 lines, status=draft)
**Devil's advocate gate passed**: DeepSeek Pass 2 — 5 holes found, 3 false positives (prompt-truncation artifacts), 2 real and applied verbatim §9-bis

---

## Executive summary

World-class editorial Instagram in 2025-2026 has converged on a discipline Bali Zero only partially practises: **the SOTA carries ≥1 of six factual anchors (number, code, location, verdict, parallelism, time) in the top 35% of the canvas**. The newsroom stack (NYT, FT, Bloomberg, Reuters, Economist, WSJ) treats the carousel as a 7-10 slide explainer with mandatory slide-2 framing, embedded chart at slide 4-5, pull-quote slide 6, statement-bomb close. Data journalism stack (Pudding, Rest of World, ProPublica, The Markup) elevates the chart to hero and dedicates a separate slide to source citation. Photo-led stack (Magnum, NatGeo) keeps overlay text <15% canvas and uses brand frame instead of explicit logo.

**Bottom line**: Bali Zero's 6-anchor empirical rule (`_empirical-metrics-2026-05-12.md`) is **industry-aligned, not idiosyncratic**. We beat regional peer (Emerhub/Flado/LMI) on photographic gravitas. We lag SOTA on five specific moves (slide-2 framing, swipe indicator, source-citation slide, regulation badge top-right, QR code closing).

---

## 30 patterns extracted — Bali Zero applicability

Decision summary: **22 ADOPT · 6 PARTIAL · 2 OBSERVE · 1 REJECT** (rotated-text-accent, Dalí-adjacent, already empirically penalised in `cepaka` post).

### ADOPT immediately (compatible + likely improves Save/Share)

| # | Pattern | Brands using | When | Where to wire it in |
|---|---|---|---|---|
| 1 | **minimal-headline-hierarchy** | NYT, Atlantic, Economist | Story value carried by single strong headline | constitution Art 3 (already aligned) |
| 2 | **color-block-number-anchor** | Bloomberg, Reuters, Katadata | Data-driven story; number entry point | layout `cover-photo` enhancement |
| 3 | **regulation-badge-top-right** | FT, Kontan, Tempo | Policy/legal news where code is essential | NEW layout slot — propose Art 4.5 |
| 4 | **location-header-subtitle** | Rest of World, CNN Indonesia, Tempo | Geographically specific stories | storyboarder subhead spec |
| 5 | **verdict-single-word** | Axios, Semafor, The Markup | Fast, decisive judgement | Art 6.9 anchor 4 already covers |
| 7 | **time-stamp-left-edge** | AP, Reuters, NYT | Breaking news, live updates | layout enhancement bottom-left yellow timestamp |
| 8 | **monochrome-photo-accent** | New Yorker, Magnum, World Press Photo | High-mood imagery + single colour pop | image-prompt-author tier 1 enhancement |
| 10 | **swipe-indicator-dot** ⭐ | Semafor, Axios, Quartz | Signal carousel-ness, increase swipe-through | NEW — every layout. **Currently missing from Bali Zero.** |
| 11 | **source-citation-tiny** | ProPublica, The Markup, AP | Investigative/data credibility | layout enhancement bottom-left 8pt white |
| 12 | **brand-mark-corner** | NYT, Economist, Bloomberg | Recognition without distraction | Art 4 already aligned (small mark) |
| 13 | **slide-2-framing-question** ⭐ | Atlantic, Vox, WSJ | Transition hook → deeper story | storyboarder NEW rule: slide 2 = "Why this matters" / "Bagaimana ini terjadi?" |
| 14 | **closing-slide-callout** | Reuters, Axios, Quartz | Summary or next-step | Art 6.6.1 elegant-close already covers |
| 15 | **sans-serif-headline** | FT, Semafor, Bloomberg | Clean modern authority | Art 3.1 already canonical (Montserrat) |
| 17 | **white-space-dominant** | Pentagram, Collins, Studio Dumbar | Luxury editorial calm | Art 2.6 total-black restraint already enforces |
| 19 | **caption-below-photo** | NatGeo, Magnum, AP | Photo-driven + explanatory context | layout `photo-headline-yellow-sub` enhancement |
| 21 | **yellow-highlight-keyword** | Bloomberg, Axios, Semafor | Emphasise key term in headline | Art 3 enhancement — formalise one-word yellow |
| 22 | **red-line-divider** | FT, Economist, Kontan | Section separation on inner slides | layout enhancement — thin red `<hr>` |
| 23 | **bullet-point-inner-slide** | Axios, The Markup, Semafor | Listicles or takeaways | Art 6.3.1 bullet-promise already enforces structure |
| 25 | **qr-code-in-closing** ⭐ | NYT, AP, Reuters | Drive to primary source | NEW layout slot — propose for elegant-close. **Currently missing from Bali Zero.** |
| 26 | **type-only-cover** | NYT, Atlantic, Economist | Opinion/analysis where image unnecessary | layout `statement-bomb` already does this |
| 29 | **two-color-palette-restricted** | Kontan, Katadata, Flado | Strong recognition + limited accents | Art 2 already protects |
| 30 | **data-source-footer** ⭐ | ProPublica, The Markup, Bloomberg | Transparency in data journalism | NEW — `Sumber: BPS / DJP / OSS` in 7pt white bottom. **Currently inconsistent.** |

### PARTIAL ADOPT (needs adaptation)

| # | Pattern | Why partial |
|---|---|---|
| 6 | **parallelism-dual-text** | Use only for direct comparisons, never as filler — anchor 5 in Art 6.9 is for this |
| 9 | **data-embed-minimal** | Simplify chart to red/yellow lines on dark; no 3D, no chart-junk |
| 16 | **serif-subhead-credibility** | Use serif only for deck text (pull-quotes), not headline — would conflict with Art 3 single-family rule |
| 20 | **split-screen-two-images** | Only when narrative demands; keep dark bg |
| 24 | **full-bleed-photo-cover** | Only if photo is dark enough to overlay yellow/red text (existing `cover-photo` layout already constrains) |
| 28 | **two-color-palette-restricted** | Already restricted but formalise yellow + red emphasis variation slide-to-slide |

### OBSERVE (not clear it benefits BZ — A/B test)

| # | Pattern | Watch for |
|---|---|---|
| 18 | **gradient-overlay-subtle** | Only if gradient is yellow-to-transparent; avoid surreal — Art 5.8.2 already bans surreal |
| 27 | **animated-element-subtle** | Not for static carousel slides; reconsider if BZ explores Stories format |

### REJECT (incompatible with brand or empirical data)

| # | Pattern | Why reject |
|---|---|---|
| 28 | **rotated-text-accent** | Readability sacrifice incompatible with regulatory/utility brief. Dalí-adjacent — already penalised empirically (`cepaka` 60 likes) |

---

## 15 anti-patterns (era-tagged, Bali Zero compliance)

What the SOTA has moved past. Critical for `wr2-critic` Rubric 5 expansions.

| # | Anti-pattern | Era | BZ avoids? | Action needed |
|---|---|---|---|---|
| 1 | **surreal-dali-collage-cover** | 2018-2021 | ✅ YES | `cepaka` lesson encoded in Art 5.8.2 |
| 2 | **full-gradient-text** | 2019 era | ✅ YES | solid yellow/red on dark enforced |
| 3 | **multiple-font-families** | 2017-2019 | ✅ YES | Art 3.1 single Montserrat family |
| 4 | **poor-contrast-text-over-image** | 2020 era | 🟡 PARTIAL | enforce dark overlay strip behind text on cover-photo layouts |
| 5 | **overcrowded-information** | 2018 era | ✅ YES | ≤1 anchor per cover rule |
| 6 | **left-aligned-everything** | 2019 era | 🟡 PARTIAL | consider centring statement-bomb closer |
| 7 | **no-swipe-indicator** | 2020 era | ❌ NO | **add swipe indicator — cheap win** |
| 8 | **brand-mark-before-content** | 2019 era | ✅ YES | small mark top-left, content starts after |
| 9 | **excessive-data-on-cover** | 2018 era | ✅ YES | charts go inner |
| 10 | **closing-slide-no-cta** | 2021 era | 🟡 PARTIAL | elegant-close pattern (Art 6.6.1) covers but inconsistently applied |
| 11 | **identical-colour-every-slide** | 2020 era | 🟡 PARTIAL | vary yellow/red emphasis slide-to-slide |
| 12 | **text-wrapping-around-images** | 2019 era | ✅ YES | clean rectangular blocks |
| 13 | **auto-play-video-on-cover** | 2021 era | ✅ YES | static carousels only |
| 14 | **vertical-hierarchy-ignored** | 2019 era | ✅ YES | natural top-down hierarchy enforced |
| 15 | **no-source-citation** | 2018 era | 🟡 PARTIAL | **add source slide as standard in regulatory/tax/property carousels** |

---

## Bali Zero gap analysis — 5 things to fix

### Priority 1 (cheap, high-impact)

1. **Swipe-indicator dot or arrow** (pattern #10, anti-pattern #7)
   - Bottom-right yellow dot/arrow signals "more inside"
   - Carousels with no swipe affordance underperform on completion (Hootsuite 2026 data)
   - Add to ALL layouts (`cover-photo`, `photo-headline-yellow-sub`, `statement-bomb`, `evidence-carved`, etc.)
   - Estimated effort: 1 CSS rule per layout (~20 min total)

2. **Slide-2 framing question** (pattern #13)
   - Currently: cover → fact-list slide
   - SOTA: cover → "Why this matters" → fact-list
   - Add `wr2-storyboarder` rule: **slide 2 MUST be a single-sentence framing of "why should YOU care"** in plain language
   - Estimated effort: 1 paragraph in `wr2-storyboarder.md`

3. **Source-citation slide as standard** (pattern #11, anti-pattern #15)
   - Every regulatory/tax/property carousel must end with a dedicated `Sumber:` slide listing: exact regulation, ministry/issuing body, decree number, date
   - ProPublica and The Markup as credibility reference
   - Currently: we cite verbatim in body text, but don't dedicate a slide
   - New layout: `source-citation.md` (needs spec)
   - Estimated effort: 1 new layout file + storyboarder rule

### Priority 2 (medium-impact, requires layout work)

4. **Regulation-badge top-right** (pattern #3)
   - When carousel is about a specific regulation (KEP-71/PJ/2026, Permenkumham 22/2023), place a small red badge top-right with the code
   - Signals "we are citing the primary source" before reader reads body
   - Layout enhancement to `cover-photo` and `evidence-carved`
   - Estimated effort: token + CSS class + storyboarder hint

5. **QR code in closing slide** (pattern #25)
   - Indonesian audiences screenshot, then re-read; QR closes loop to primary source
   - Target: DJP page, OSS portal, BPS dataset, Permenkumham link — NOT Bali Zero own site (avoid hard-sell, Art 6.6 compliance)
   - Bali Zero peers don't do this — would be a differentiator
   - Estimated effort: 1 CSS slot in elegant-close layout + storyboarder rule to require QR URL

---

## 5 things Bali Zero already does well (DEFEND, do not regress)

1. **Six-anchor headline discipline** — number/code/location/verdict/parallelism/time. The 100-cover audit confirms world has converged on the same rule. We are **industry-aligned**, not idiosyncratic.
2. **Restricted two-colour palette** (#F4C430 yellow + #C8102E red on #2C2F38 + black) — matches Kontan/Katadata recognition discipline; protected in Art 2.
3. **No surreal/Dalí/painterly cover** — we have empirical penalty case (`cepaka`, 60 likes). Most peer agencies still trip on this. Art 5.8.2 encodes the ban.
4. **Aerial-drone + ground-documentary image modes** (Tier 1 in `_empirical-metrics-2026-05-12.md`) — matches Reuters/Rest of World/NatGeo/Guardian. Beats Lets Move Indonesia / Emerhub / Flado on photographic gravitas.
5. **Statement-bomb closing** (pattern #26, paragon #6) — already in `layouts/statement-bomb.md`. Empirically validated by `mangrove` post (893 likes, "MANGROVES VS MEGA-PROJECT" closer).

---

## Recommended changes this month

For `wr2-design-architect` orchestrator + downstream agents:

1. **`wr2-storyboarder.md`**: add rule "slide 2 = framing question" (pattern #13)
2. **`wr2-storyboarder.md`**: add rule "regulatory/tax/property carousels MUST end with source-citation slide" (pattern #11)
3. **`wr2-image-prompt-author.md`**: explicit reference to pattern #8 (monochrome-photo-accent) when cover is photo-led
4. **New layout**: `~/.claude/skills/bali-zero-brand/layouts/source-citation.md` (spec needed)
5. **Layout enhancement**: `swipe-indicator` CSS class in `_base.css` (pattern #10)
6. **Layout enhancement**: `regulation-badge` slot in `cover-photo` and `evidence-carved` (pattern #3)
7. **Layout enhancement**: `qr-closing` slot in `elegant-close` (pattern #25)
8. **`wr2-critic.md` Rubric 5**: add check 5.5 — "source citation slide present for regulatory/tax/property domains" (soft fail if missing)
9. **Constitution Article 14 draft** in `_proposed-amendments/`: "Five SOTA adoption rules" (slide-2 framing, source slide, swipe indicator, regulation badge, QR closing)

---

## Open questions / verification needed

From the gallery file §10 checklist:
- [ ] Verify `lex.indonesia` and `baliprivatevilla` are real IG handles (Gemini may have hallucinated — check before adding to monthly bench source list)
- [ ] A/B test pattern #3 (regulation-badge top-right) on next regulatory carousel; measure Save/Like delta 14 days
- [ ] Draft `~/.claude/skills/bali-zero-brand/layouts/source-citation.md` (layout spec to be written by layout-composer with Antonello input)
- [ ] Draft Article 14 amendment in `_proposed-amendments/2026-05-12-five-sota-adoption-rules.md`
- [ ] Decide whether `wr2-external-bench` should run 2026-06-02 (next 1st Monday) with new data, or wait for 90+ days of WR2-published data first

---

## Carryover

This is the SEED file — first run. Next month's `_external-bench-2026-06.md` (auto-generated by `wr2-external-bench` agent, 2026-06-02) will use this as carryover input and add 2+ new patterns NOT in this list.

The agent contract (in `~/.claude/agents/wr2-external-bench.md`) requires that the next monthly run:
- Compare ADOPT decisions from this seed against actual WR2 production runs in May
- Report which ADOPT items shipped, which didn't, and why
- Add ≥2 new patterns NOT in this list (anti-stagnation)
- Re-verify that 22 ADOPT / 6 PARTIAL / 2 OBSERVE / 1 REJECT classifications still hold given new evidence

---

## Maintenance

- This file is **read by every WR2 carousel run** (via `wr2-design-architect` skill load of `bali-zero-brand`)
- Updated MONTHLY by `wr2-external-bench` agent (1st Monday 07:00 WITA)
- DUAL-BASELINE companion to `_empirical-metrics-2026-05-12.md` (internal performance) — together they form the complete Bali Zero design intelligence (internal evidence + external SOTA)
- Antonello has VETO on all ADOPT promotions to constitution Art 14
