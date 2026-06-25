# External Bench 2026-06 — Bali Zero WR2 Design

**Captured**: 2026-06-11 (manual completion of interrupted 2026-06 monthly run)
**Source universe**: 12 editorial publishers + 3 competitor + 2 trend report families (Later/Sprout/Metricool 2026)
**Method**: Multi-LLM — Gemini 3.1 Pro + Opus structured ingestion (Tier 1, `/tmp/wr2-external-bench-raw-2026-06.json`) + DeepSeek v4-pro pattern extraction ×2 (extraction + devil's advocate) + Claude Opus synthesis
**Cost**: ~$0.015 (DeepSeek v4-pro, ~30k tokens across 3 calls), Gemini free OAuth, Claude MAX flat
**Devil's advocate gate passed**: DeepSeek pass 2 — 2 corrections found and applied (monospace-progress-counter → REJECT as duplicate of slide-numbering; bold-swipe-arrows → REJECT as engagement gimmick). Note: first DA call returned empty (max_tokens=3000 fully consumed by reasoning tokens) — fixed to 16000 and re-run.
**Carryover input**: `_external-bench-2026-05.md` (seed, 30 patterns: 22 ADOPT / 6 PARTIAL / 2 OBSERVE / 1 REJECT)

---

## Executive summary

The dominant mid-2026 shift is a **transparency layer on top of editorial design**: AI-image disclosure labels (Wired-pioneered, now pushed by Meta's AI-label rollout, the EU AI Act, and the #1 consumer demand in Sprout 2026 — 56% encounter AI content frequently), per-slide attribution, and accessibility/alt-text as a discoverability lever. Mechanically, progress devices are evolving (custom thin **bars replacing dots** — @qz, @restofworld), carousel length is **polarizing** (FT 4-5-slide data punches vs Reuters 12-15-slide essays; the generic 7-slide middle is fading), and **annotated** data callouts have replaced naked charts (@pudding, @themarkup, @propublica).

Bali Zero is structurally well-placed: the locked palette/single-family typography is exactly the restraint discipline the SOTA converged on, the three shipped Art 14 devices (swipe dot, slide-2 framing, regulation badge) match the convention set, and documentary-photographic gravitas still beats all three regional competitors. The three moves that close the gap this month: (1) **AI-image disclosure label** — for a compliance brand, disclosing AI assets is a brand-coherent trust play, and the constitution currently has NO rule for it (Art 5.4 covers faces only); (2) **process-step-map** inner-slide family for utility content (the Save/Like S-pattern engine); (3) **translucent caption pill** on full-bleed photos — it directly closes the "poor-contrast text-over-image" PARTIAL gap flagged in May.

---

## Source roll-call

| # | Source | Tier | Status | Sample basis |
|---|---|---|---|---|
| 1 | @nytimes | 1 | ingested | recent-post conventions (type system, kicker, progress bar, close) |
| 2 | @ft | 1 | ingested | data-punch format, FT-pink discipline, chart palette |
| 3 | @reutersphotos | 1 | ingested | photo-essay mechanics, caption pill, numbering, credits |
| 4 | @wired | 1 | ingested | AI-disclosure label, mono counter, neon-on-dark |
| 5 | @bloomberg | 1 | ingested | data-hero, source credits, yellow-accent close |
| 6 | @qz | 1 | ingested | progress line, exec-summary slide 2 |
| 7 | @pudding.cool | 1 | ingested | annotation arrows, methodology slide |
| 8 | @restofworld | 1 | ingested | geographic kicker, contrast progress bar |
| 9 | @propublica | 1 | ingested | 2026 redesign, evidence annotation, red kicker |
| 10 | @themarkup | 1 | ingested | OS-window/terminal aesthetic, screenshot-as-evidence |
| 11 | @drift_official | 1 | ingested | B2B massive type, chat bubbles, conversational CTA |
| 12 | @pentagram | 1 | ingested | zero-device minimalism, white space |
| 13 | @letsmoveindonesia | 2 | ingested | split-screen template, contact-heavy close |
| 14 | @emerhub_official | 2 | ingested | process step map, flat illustration |
| 15 | @flado.bali | 2 | ingested | beach register (BZ-banned), serif frames |
| 16 | Later/Metricool 2026 trends | 3 | ingested | engagement quant, slide mechanics, max-20 slides |
| 17 | Sprout Social 2026 | 3 | ingested | AI-disclosure demand, DM-share weighting 3-5x |

Trend-report quant retained for downstream agents: carousel avg engagement 1.92% (vs Reels 0.50%, static 0.45%); +114% conversion vs single image; 1.4x reach; DM shares weighted 3-5x likes; sweet spot 8-10 slides with engagement dip after slide 3 and recovery slide 8+; 1080x1350 portrait; max 20 slides.

---

## 25 patterns extracted — Bali Zero applicability

Decision summary: **8 ADOPT · 7 PARTIAL · 3 OBSERVE · 7 REJECT** — 19 patterns NOT in the May carryover (anti-stagnation requirement ≥2: exceeded).

### ADOPT (compatible + likely improves Save/Share)

| # | Pattern | Novel | Brands using | When | Where to wire it in |
|---|---|---|---|---|---|
| 1 | **ai-disclosure-label** ⭐ | YES | Wired (+ Meta/EU AI Act pressure) | Any carousel with AI-generated hero | NEW constitution article (propose Art 14.7): low-contrast corner label "AI-assisted image", 7-8pt Montserrat white ~40% on dark. Constitution currently silent (Art 5.4 covers faces only). Brand-coherent: a compliance brand discloses. |
| 2 | **data-annotation-callouts** | YES | Pudding, The Markup, ProPublica | Data/chart inner slides (tax rates, deadlines, fines) | layout-composer chart slides: yellow/red restrained pointers to the load-bearing data point. Extends May's data-embed-minimal PARTIAL. No naked charts. |
| 3 | **process-step-map** ⭐ | YES | Emerhub | Regulatory how-to (KITAS flow, PT PMA setup, LKPM filing) | NEW inner-slide layout family: numbered step progression, yellow/red on dark, Montserrat. Direct S-pattern (rule→consequence→action) amplifier — the Save/Like engine per `_empirical-metrics`. Competitor's best device; take it. |
| 4 | **translucent-caption-pill** ⭐ | YES | Reuters Photos | Caption text over full-bleed photo | `_base.css`: antracite ~75% translucent rounded rect behind captions. Closes May anti-pattern #4 ("poor contrast text-over-image", PARTIAL). NOT an Art 15 violation: the ban targets color-coded kicker/label pills, not legibility scrims — document the distinction for wr2-critic to avoid a false hard-fail. |
| 5 | **slide-2-framing** | carryover | NYT, FT, Quartz, Drift | All | SHIPPED (Art 14.2) — confirmed still SOTA-dominant. Defend. |
| 6 | **regulation-badge-top-right** | carryover | FT-class + regional | Policy/legal stories | SHIPPED (Art 14.4, WCAG AAA revision 2026-05-13) — confirmed. Defend. |
| 7 | **swipe-indicator-dot** | carryover | FT, Quartz | All | SHIPPED (Art 14.1) — confirmed, but see progress-bar PARTIAL below: 2026 trend is bars over dots; A/B before replacing. |
| 8 | **brand-mark-corner** | carryover | NYT, Reuters, Rest of World | All | Already aligned (Art 4). Confirmed. |

### PARTIAL ADOPT (compatible but needs adaptation)

| # | Pattern | Novel | Why partial |
|---|---|---|---|
| 9 | **progress-bar** | YES | 2026 convention: thin custom bar (top/bottom) replacing dots (@qz, @restofworld, NYT). Compatible (thin yellow bar on black) but OVERLAPS shipped Art 14.1 dot. Wire as `_base.css` variant and A/B vs the dot — do not silently replace a shipped, empirically-grounded device. |
| 10 | **carousel-length-polarization** | YES | FT 4-5 punch vs Reuters 12-15 essay; 7-middle fading. Adopt as storyboarder PRINCIPLE: single-regulation-change → 4-5 slide punch; process deep-dive → 8-12 (trend sweet spot 8-10, recovery after slide 8). Small internal sample (n=8) — validate against incoming metrics before hard rule. |
| 11 | **alt-text-accessibility-note** | YES | BZ design side is already WCAG AAA (brand pillar). The 2026 lever is alt-text as discoverability. Adopt at PUBLISHING checklist level (per-slide alt text in the Damar handoff), not as a slide-design change. |
| 12 | **split-image-across-slide** | YES | Seamless image continuation across slide 1→2 border (replaces cartoon hand-swipe). Strong with Tier 1 aerial-drone heroes (panoramic). Needs layout-composer 2160px split-canvas support AND must coexist with Art 14.2 slide-2 framing text. Photo-led covers only. |
| 13 | **per-slide-photo-credit** | YES | Reuters/NYT device, but BZ heroes are mostly AI-generated — "photo credit" is wrong for them. Adapt as a UNIFIED image-attribution corner slot: carries "AI-assisted image" (pattern #1) OR "Photo: X" depending on source type. One slot, two payloads. |
| 14 | **slide-numbering** | YES | Reuters "1/8". Montserrat numerals fine. Adopt ONLY for deep-dive carousels (8+ slides) where position clarity matters; redundant on 4-5 punches. Coordinate with progress-device family (dot vs bar vs numbering — pick ONE per carousel). |
| 15 | **full-bleed-photo-cover** | carryover | May classification retained: only when photo is dark enough to carry yellow/red overlay text (existing `cover-photo` constraint). Pairs with #4 translucent-caption-pill for the caption layer. |

### OBSERVE (not clear it benefits BZ — log for A/B)

| # | Pattern | Novel | Watch for |
|---|---|---|---|
| 16 | **feed-grid-coherence** | YES | Profile-level 3-column panorama/gradient interlock. Locked palette already gives BZ soft grid coherence for free; FULL interlocking would constrain every cover design and requires profile-level planning the WR2 pipeline doesn't do. Revisit if/when a feed-planning step exists. (Downgraded from DeepSeek ADOPT — ops cost, not design incompatibility.) |
| 17 | **os-window-borders** | YES | The Markup terminal/OS-window aesthetic. Register clash with BZ documentary-photographic gravitas (Tier 1 empirical). The legitimate kernel is **screenshot-as-evidence** — OSS/Coretax portal screenshots framed minimally for process walkthroughs. Observe that kernel only; never the whole retro-tech skin. (Downgraded from DeepSeek ADOPT — palette-renderable ≠ brand-compatible.) |
| 18 | **source-citation-tiny** | carryover | Art 14.3 DEFERRED status unchanged — layout exists, critic check 5.5 soft-fail-advisory, A/B still pending per 14.6. |

### REJECT (incompatible with brand or empirical data)

| # | Pattern | Novel | Why reject |
|---|---|---|---|
| 19 | **editorial-kicker-label** | YES | NYT/FT/Bloomberg/ProPublica uppercase kicker (INVESTIGATION/OPINION). Art 15 HARD-FAIL: color-coded pill/kicker labels banned. The SOTA does it; we structurally cannot — institutional memory, do not re-propose. |
| 20 | **geographic-kicker-label** | YES | Rest of World "JAKARTA, INDONESIA" kicker. Same Art 15 ban. The legitimate location-signal need is already served by May's ADOPT location-header-subtitle (subhead, not kicker). |
| 21 | **monospace-progress-counter** | YES | DA-corrected: duplicate of slide-numbering with a typography violation on top (mono restricted to IBM Plex source footers, Art 3.2). |
| 22 | **chat-bubble-graphics** | YES | Drift B2B SaaS conversational device, adjacent to "DM us" hard-sell culture (empirically penalized register). Palette-renderable but brand-register incompatible with documentary gravitas. (Overrides DeepSeek ADOPT.) |
| 23 | **thin-serif-frames** | YES | Flado lifestyle device. Serif banned (Art 3.2); beach/luxury register is the exact BZ REJECT register. |
| 24 | **bold-swipe-arrows** | YES | DA-corrected: oversized swipe arrows are listicle-pap engagement gimmick; also LetsMoveIndonesia's clutter device (yellow arrows everywhere). Art 14.1 dot already covers the affordance with restraint. |
| 25 | **no-social-graphics-minimalism** | YES | Pentagram zero-device purity. Directly contradicts SHIPPED Art 14.1 (swipe dot) + 14.4 (regulation badge), both empirically grounded. Pentagram's portfolio context ≠ regulatory editorial utility. (Overrides DeepSeek ADOPT.) |

---

## Bali Zero gap analysis

1. **AI-disclosure is a regulatory wave BZ is not riding — and it's OUR lane.** Meta AI-labels + EU AI Act transparency + #1 consumer demand (Sprout 2026). BZ publishes AI-generated heroes on every carousel with zero disclosure, and the constitution has no rule (Art 5.4 governs face ambiguity only). A compliance brand that self-discloses converts a legal trend into a trust signal. Cheapest high-coherence win this month.
2. **Utility content lacks a process visualization device.** The S-pattern (rule→consequence→action) drives BZ's best Save/Like performers (villa_ota 2.20, 37k_villa 1.12) but is delivered as text bullets. Emerhub — otherwise weaker on every axis — beats BZ on step-map clarity. Pattern #3 closes it.
3. **Caption contrast on photo slides is still the open May wound.** Anti-pattern #4 (poor-contrast text-over-image) was PARTIAL in May and nothing shipped. The Reuters translucent pill (#4) is the precise fix, palette-native.
4. **Progress device is one generation behind.** BZ shipped the dot (Art 14.1) exactly as the SOTA moved to custom thin bars (@qz, @restofworld convention now). Not urgent — the dot works — but A/B the bar variant before the gap widens.
5. **Length strategy is undifferentiated.** BZ defaults to 6-8 slides — the fading middle. Trend data says polarize: 4-5 punch or 8-12 deep-dive (engagement dips after slide 3, recovers slide 8+). Storyboarder currently has no length-selection rule at all.

**Where BZ leads (defend, do not regress)**: locked two-accent palette + single-family Montserrat (the restraint the SOTA converged on); documentary photographic gravitas vs all 3 regional competitors (LMI template clutter, Emerhub flat illustration, Flado banned beach register); shipped Art 14.1/14.2/14.4 matching the SOTA convention set; six-anchor headline discipline (May verdict: industry-aligned) still uncontradicted by June evidence.

---

## Recommended changes this month

1. **Constitution `_proposed-amendments/`**: draft Art 14.7 — AI-image disclosure label (pattern #1). Spec: corner placement, 7-8pt Montserrat, white ~40% opacity on dark, text "AI-assisted image" / "Gambar berbantuan AI". Unify with the image-attribution slot (pattern #13) so one corner slot carries AI-disclosure or photo credit.
2. **`wr2-storyboarder.md`**: add length-polarization rule (pattern #10) — single-change story → 4-5 slides; process deep-dive → 8-12; never default to 7.
3. **New layout family**: `layouts/process-step-map.md` (pattern #3) — numbered step progression for regulatory how-to inner slides.
4. **`_base.css`**: `caption-pill` class (pattern #4, antracite ~75% translucent) + `progress-bar` variant (pattern #9, thin yellow, A/B-gated vs Art 14.1 dot).
5. **`wr2-layout-composer.md`**: chart slides MUST carry ≥1 annotation callout to the load-bearing data point (pattern #2); naked charts are a soft-fail.
6. **`wr2-critic.md`**: (a) add the caption-pill vs Art 15 pill-ban distinction so the legibility scrim is not false-failed; (b) note kicker-label REJECT (#19/#20) as institutional memory — any storyboard proposing an uppercase category label above the headline is an Art 15 hard-fail.
7. **Publishing checklist (Damar handoff)**: per-slide alt-text field (pattern #11).

---

## Carryover from last month

May seed (first run) proposed 5 priority moves. Status verified on disk 2026-06-11:

| May recommendation | Status June |
|---|---|
| Swipe-indicator dot (P1.1) | ✅ SHIPPED — Art 14.1 approved |
| Slide-2 framing question (P1.2) | ✅ SHIPPED — Art 14.2 approved (frame-list moved to slide 3) |
| Source-citation slide (P1.3) | 🟡 DEFERRED — Art 14.3, layout exists, critic 5.5 soft-advisory, A/B pending |
| Regulation-badge top-right (P2.4) | ✅ SHIPPED — Art 14.4 approved, WCAG AAA revision 2026-05-13 |
| QR code in closing (P2.5) | 🟡 DEFERRED — Art 14.5, CSS ready, needs server-side QR generator + A/B |

3 of 5 shipped within one cycle; the 2 deferred items remain valid (June evidence does not contradict them — re-confirmed source-citation-tiny as OBSERVE pending the Art 14.3 A/B). May's single REJECT (rotated-text-accent) stands — now reinforced by the Art 15 diagonal/rotated ban. No May ADOPT was falsified by June evidence.

**Anti-stagnation check**: 19 of 25 June patterns are NOT in the May list (requirement: ≥2). The genuinely-new 2026 conventions (AI-disclosure, length polarization, annotation callouts, split-image, feed-grid coherence, alt-text, per-slide repurposing analytics) all enter the bench for the first time.

**Era-watch — newly dated/abandoned in 2026** (extend May's anti-pattern table): Canva gradient blobs; cartoon hand-swipe animation; generic corporate stock (handshakes); heavy drop-shadows; un-annotated charts. BZ avoids all five today; "un-annotated charts" becomes enforceable via recommendation #5.

---

## Open questions / verification needed

- [ ] A/B: progress-bar variant vs Art 14.1 dot (14-day Save/Like + completion delta)
- [ ] Antonello veto/approval on Art 14.7 AI-disclosure draft (NO auto-merge — propose only)
- [ ] Validate length-polarization against next 8+ published carousels (internal n=8 too small for a hard rule)
- [ ] Per-slide insight analytics (IG rollout pending): when available, wire top-slide → standalone-post repurposing into wr2-ig-metrics-analyst
- [ ] Music-on-carousel (pushes into Reels feed): OBSERVE-class, publishing-side decision, out of WR2 design scope — flag to Antonello

---

## Maintenance

- This file is **read by every WR2 carousel run** (via `wr2-design-architect` skill load of `bali-zero-brand`) and by `wr2-ig-metrics-analyst` (weekly) + `wr2-critic`
- Updated MONTHLY by `wr2-external-bench` agent (1st Monday 07:00 WITA); this edition completed manually 2026-06-11 after the cron run died post-DeepSeek-launch
- DUAL-BASELINE companion to `_empirical-metrics-2026-05-12.md` (internal evidence + external SOTA)
- Antonello has VETO on all ADOPT promotions to constitution Art 14
- Intermediates for audit: `/tmp/wr2-external-bench-raw-2026-06.json`, `/tmp/deepseek-bench-patterns-2026-06.json`, `/tmp/deepseek-bench-da-2026-06.json`
