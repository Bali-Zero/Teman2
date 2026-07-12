---
date: 2026-06-30
domain: operations
client_case: WR2-pipeline
partial: true   # DeepSeek tier unavailable (insufficient balance); named editorial-account lengths UNVERIFIED
sources:
  - https://www.socialinsider.io/blog/instagram-carousel/
  - https://yougov.com/articles/31680-carousel-posts-using-all-10-slides-instagram-have-
  - https://www.socialinsider.io/social-media-benchmarks/instagram
  - https://buffer.com/resources/instagram-algorithms/
  - https://carouselli.com/blog/instagram-carousel-engagement
  - https://www.trymypost.com/blog/instagram-carousel-algorithm-2026-guide
  - https://creatorflow.so/blog/instagram-carousel-posts-guide/
  - https://postnitro.ai/blog/post/carousel-copywriting-framework
  - internal:skills/bali-zero-brand/_external-bench-2026-06.md
  - internal:skills/bali-zero-brand/_empirical-metrics-2026-05-12.md
  - internal:skills/bali-zero-brand/_proposed-amendments/2026-06-29-ig-insights.md
  - internal:skills/bali-zero-brand/_proposed-amendments/2026-06-23-ig-insights.md
  - internal:skills/bali-zero-brand/past/  (64 archived carousels, slides_count=7 on all)
  - internal:scripts/wr2_draft_generator.py
---

# WR2 Variable-Length Carousel: The Number, The Criterion, and Length x Design

**Date**: 2026-06-30 · **Domain**: operations · **Author**: deep-researcher (Antonello/Bali Zero) · **Status**: draft · **Client case**: WR2-pipeline

## Question

How should a variable-length carousel actually work — both the NUMBER of slides and the CRITERION for choosing that number, plus how length interacts with design? Ground every claim in real, factual data. This feeds a decision about the WR2 draft-generator, which currently lets an LLM "pick the count the story needs" inside a guard, with three conflicting bounds in the codebase: prompt says 6-8, code accepts 6-11, internal docs said 5-13.

## TL;DR (recommended rule)

- **Number**: `N = clamp(5, 10, 2 + body_slides)` where `body_slides = 1 per distinct claim/beat, floor 3`. Hard cap **10**, hard floor **5**. Resolve the 6-8 / 6-11 / 5-13 conflict to a single guard: **5 <= N <= 10**.
- **Criterion**: per-beat, branched by story type — **punch (single regulation change) = 5-6**, **deep-dive (process / multi-claim) = 9-10**, and **abandon the "standard 7" default** (it sits in the empirical engagement trough; engagement dips after slide 3 and only recovers from slide 8 — Socialinsider). Decide the band from a `distinct_claims` integer, not a fixed house number.
- **Design**: no more than 2 consecutive text-only slides; cover + closer are fixed overhead (hero cover, statement-bomb closer); the closer needs an explicit 2-line-safe spec because the current statement-bomb family has a documented logo/2-line failure mode.

## Key citations (verbatim)

- **Socialinsider 2024** (~3M carousels, 22M+ posts, via YouGov writeup): "2-slide carousel posts have an engagement rate of 1.9%, dropping to 1.7% among 4-slide posts, with figures rising with each subsequent increase, reaching over 2% for posts with 10 slides... engagement dropping off after three slides, though picking up again at 8 slides and above." Only ~6.8% of carousels use all 10.
- **Mosseri (Jan 2025), reported**: the three most important IG ranking signals across surfaces are "watch time, sends per reach (DM shares), and likes per reach." For carousels specifically, swipe-through and completion are repeatedly named the #1-#2 carousel-level signals (target ~65% swipe-to-slide-2, ~55% completion; ~80% completion on a 10-slide deck "significantly boosts distribution to the Explore page").
- **Completion cliff (carouselli / trymypost, aggregator-tier)**: "posts exceeding 12 slides seeing a 40% drop-off in completion rates" unless serialized narrative.
- **Re-serving (Buffer / multiple)**: when a follower does not swipe to the end, IG "treats those unseen slides as new content" and re-shows the carousel later, picking up at the first unseen slide — more slides = more re-engagement surface, conditional on early slides earning the swipe.
- **Internal `_external-bench-2026-06.md`** (Bali Zero, 2026-06-11): "carousel length is polarizing (FT 4-5-slide data punches vs Reuters 12-15-slide essays; the generic 7-slide middle is fading)"; storyboarder gap "#5 Length strategy is undifferentiated. BZ defaults to 6-8 slides — the fading middle... Storyboarder currently has no length-selection rule at all."
- **WR2 code (`wr2_draft_generator.py`)**: docstring line 2/6 "6-11 English slides ... Slide count is FLEXIBLE (6-11)"; prompt line 154 "produce the 6-8 slide structure (flexible: pick the count the story needs)". The two disagree in the same file — this is the bug.

## Findings

### Axis 1 — THE NUMBER (how many slides)

**Platform engagement data (well-attributed).** The load-bearing primary-grade dataset is the **Socialinsider 2024 study** (~3M carousels from 22M+ Instagram posts). It is the only source in this pass that gives an engagement-rate-by-slide-count curve with a sample size. The curve is **non-monotonic / U-shaped**: 2 slides = 1.9%, 4 slides = 1.7% (the trough), then it climbs and **peaks at 10 slides (>2.0%)**. Engagement "drops off after three slides, picking up again at slide 8 and above." Carousels as a format average 1.92% engagement vs 1.74% images / 1.45% video; mixed image+video carousels hit 2.33%. Only ~6.8% of carousels actually use all 10 slides, so the highest-engagement band is the least-used — an exploitable gap.

Caveat on that curve: the Socialinsider study era had a **10-slide cap**; Instagram later raised the limit to 20. So "peaks at 10" was "peaks at the maximum allowed at the time," and we cannot treat 10 as a proven global optimum above the old cap — only as "more is better up to the cap, with the early-slide trough." Socialinsider's current blog phrases the carousel-specific claim conservatively: "carousels with more than 10 slides get increased reach" and "8-10 slides highest engagement."

**Completion / swipe-depth as ranking signal.** Multiple 2025-2026 sources converge: completion is a top-2 carousel ranking input. Reported targets: **65%+ swipe-to-slide-2, 55%+ full completion**; ~80% completion on a 10-slide deck boosts Explore distribution. The friction point is between **slides 1-3** — without a cue (counter, cliffhanger), completion "drops sharply after slide 3." Past **12 slides, completion drops ~40%** unless the content is a serialized narrative. The **re-serving** mechanic (IG re-shows unseen slides as new content) means more slides = more re-engagement surface, but only pays off if the first 2-3 slides earn the initial swipe — otherwise the long tail is never seen.

**DISAGREEMENT surfaced (important).** Several aggregator blogs cite "reach peaks at slide 13, 6-13 sweet spot, 37.8% reach." On verification, **that 37.8%/slide-13 figure is Socialinsider's Instagram *Stories* data, NOT carousels** — the blogs conflate the two formats. Resolution: discard the slide-13 peak for carousels; it does not describe the format we ship. This also means the internal-docs "5-13" range was likely seeded by this conflation. Trusting the carousel-specific Socialinsider figure (peak at 10) over the Stories-contaminated aggregator figure (13).

**Editorial / journalism accounts — UNVERIFIED.** The user asked specifically for observed carousel lengths of NYT, Bloomberg Originals, The Pudding, Reuters, Vox, The Economist, Wired, Rest of World. **I could NOT verify any specific account's typical carousel length via live web search today** — search returned profile links and generic best-practice blogs, not slide-count observations, and the platform does not expose per-post slide counts to search. The ONLY editorial-account length figures available are second-hand from our own `_external-bench-2026-06.md` (FT 4-5-slide punches; Reuters 12-15-slide photo essays), which was produced by our Gemini+Opus ingestion on 2026-06-11 and which I cannot independently re-confirm now. **Treat "FT 4-5 / Reuters 12-15" as a single internal observation, not as verified ground truth.** Everything else about named editorial accounts is UNVERIFIED — not fabricated here.

### Axis 2 — THE CRITERION (how to decide the number per story)

**Documented editorial frameworks.** The dominant rule across copywriting/editorial sources is **"1 idea per slide"** (prevents cognitive overload, keeps the deck skimmable). The narrative arc that recurs is **hook -> context -> turn/insight -> payoff -> CTA** (5 beats), often expressed as **AIDA** (Attention on slide 1, Interest on slides 2-4, Desire/Detail, Action on the last slide) or the compressed **Hook -> Value -> CTA**. None of these prescribe a fixed length; they prescribe a *minimum* (enough slides to complete the arc) and a structure (one beat per slide). This is exactly a **per-beat criterion**, which is what WR2 should encode.

**How strong teams decide length = hybrid (beats x density), branched by story type.** The editorial pattern is not "fixed house format" and not "pure density" — it's **a minimum arc, then +1 slide per distinct claim, capped by the completion cliff**. The polarization our external bench observed (short punch vs long essay) is the same idea: a single-claim story hits the arc minimum and stops; a multi-claim process story adds a slide per step until it nears the cap.

**Translated into an implementable rule (the deliverable).** `body_slides = number of distinct claims/beats the story carries, floored at 3` (so cover + 3 body + closer = 5 = the arc minimum). `N = 2 + body_slides`, clamped to [5, 10]. Branch the *target band* by story type so the drafter polarizes instead of defaulting to the trough:
- **punch** (single regulation change, one consequence): **5-6 slides**
- **standard** (a rule + its mechanism + 1-2 consequences): **7-8** is permitted but is NOT the default — only when claims genuinely land there
- **deep-dive** (multi-step process: KITAS flow, PT PMA setup, multi-clause tax change): **9-10 slides**

### Axis 3 — LENGTH x DESIGN interaction

**Rhythm: text-only runs are the real risk.** The completion data says the danger zone is slides 1-3 and the long flat middle. A run of 3+ pure text slides in the middle is where swipe-depth dies. **Rule: no more than 2 consecutive text-only slides**; break a long text run with a hero or a distinct layout (dark-status-list, evidence-carved, process-step-map). This is consistent with WR2's current "be STINGY with heroes, cover is always hero, usually only 1-3 mid heroes" instruction — the constraint should be *anti-monotony of consecutive text*, not a fixed hero count.

**Hero:text ratio — UNVERIFIED externally.** I found NO external dataset on optimal hero:text composition ratio. Gemini's independent review flagged my draft "1:2 to 1:3" ratio as unsubstantiated, and it is right. Treat hero:text as a **design-judgment heuristic, not a data claim**: roughly 1 hero per 2-3 text/data slides keeps rhythm without making the deck a slideshow, but this is editorial taste, not measured. WR2's existing "filler hero is worse than no hero" rule is the better-grounded constraint and should govern.

**Table-of-contents / "N-part" framing on longer carousels — supported.** For 9-10 slide deep-dives, an explicit position cue ("Slide 1 of 8" / numbered step map) is reported to reduce abandonment by setting a length expectation, and Reuters-style "1/8" numbering is in our external bench as PARTIAL-ADOPT *for 8+ slide carousels only* (redundant on 5-6 punches). So: **add a progress/numbering cue when N >= 8; omit it on punches.**

**The closer slide (specific defect).** WR2's closing family is **statement-bomb** (constitution Art 9.5 hard-fails if the closer uses any other family): "Max 2 visual lines bold centered statement. NO body. NO CTA," statement 3-15 words UPPERCASE, with `auto_shrink` 72px -> 56px -> 48px. An optional **elegant-close** may FOLLOW statement-bomb for operational topics (soft IF/WHEN invite + one reach channel + optional primary-source QR). The documented failure modes that match the reported defect:
1. **`2026-06-04-statement-bomb-absolute-occlusion`**: when `is_hero_image=true` but no image exists, the placeholder hero div (black, full-viewport, absolute) **occludes the text-zone underneath** — the page renders ~all-black with only the logo visible. Latent until the no-hero path is exercised.
2. **`cover-photo.md` logo/headline collision** (same class of bug on the cover): the logo was being "read as a third word of the last headline line," fixed by raising the safe-zone to 270px. A 2-line closer headline that runs tall has the same logo-collision geometry.
3. **`editorial-text.md`**: "Body length over ~110 words overflows the centered stack toward the logo" — the logo gets pushed/overlapped when text is tall.

So the closer defect is **geometric, not content**: a tall (2-line) statement + a fixed-position logo + absolute stacking = logo gets dropped, occluded, or read as text. **The closer spec must guarantee a reserved logo safe-zone below the statement that survives the 2-line + auto-shrink path, and the render must assert the logo zone is present and unoccluded (vision-sweep, per the occlusion lesson's check #3).**

## Bali Zero's OWN data (factual, internal)

**The decisive internal caveat: we have ZERO length variance to learn from.** All **64 archived carousels** in `skills/bali-zero-brand/past/` are **exactly 7 slides** (`slides_count: 7` in every `metadata.json`; all imported from one "WR2 Automation standard.zip"). Both weekly ig-insights files independently confirm it: 2026-06-29 — "`slide_count` NULL on all backfill posts. Cannot compute per-slide analysis"; 2026-06-23 — "Lunghezza dei testi, numero di immagini per post: non registrati (la tabella `carousel_runs` e' vuota)." **Therefore Bali Zero cannot internally correlate length with engagement. Any length recommendation here is externally-grounded, not internally-validated. This is the single most important honesty point in the dossier.**

What our data DOES tell us (domain/tone/layout, N=42 published with metrics, small-N caveat throughout):
- **Domain dominates, not length**: tax carousels save best (SL +78% vs corpus, N=5, HIGH); regulatory announcement-only worst (SL -46%, N=13, HIGH); health forwards best but N=2.
- **Tone**: militante = many likes, few saves; rituale spikes virally on identity topics (GCI 3,043 likes) but fails systematically on regulatory.
- **Layout**: dark-status-list = forwards (ShL 1.33); evidence-carved = saves (SL +60% in 90d, N=4). statement-bomb = highest raw likes, lowest consistent utility (except property news-flash).
- **The S-pattern (rule + consequence + action)** is the load-bearing content rule across every internal finding — and it maps cleanly onto the per-beat length criterion: each S-pattern element is a beat, each beat is a slide.

Implication for length: our internal evidence says **the body slides must each carry one S-pattern beat with a named consequence**; it is silent on how many. So length should be driven by *how many real S-pattern beats the story has* (Axis 2 criterion), which is the only length rule consistent with what our audience actually rewards (saves on consequence-bearing utility content).

## Numerical analysis

**Note**: the DeepSeek Reasoner tier was **unavailable this run (API returned "Insufficient Balance")**, so the numeric derivation below was done by the synthesis tier (Claude) transparently rather than outsourced; it is simple integer logic, not a long numeric chain, so this is auditable in-line. An independent cross-check was run via Gemini 3.1 Pro (`agy`), whose corrections are folded in.

Derivation of MIN/MAX:
- Fixed overhead = 2 slides: **cover (always hero, = the hook beat)** + **closer (statement-bomb, = the CTA/payoff beat)**. The cover and closer DOUBLE as arc beats; they are not extra.
- A complete arc = 5 beats (hook, context, turn, payoff, CTA). Cover covers hook; closer covers CTA. Remaining beats (context, turn, payoff) = 3 body slides minimum. So **arc minimum N = 2 + 3 = 5**.
- Per-claim increment: each additional distinct claim/beat = +1 body slide. `N = 2 + max(3, distinct_claims)`.
- **MAX = 10**: it captures the Socialinsider >2.0% engagement peak (slide 10) AND stays clear of the ~40% completion cliff past slide 12. Going to 11 (current code ceiling) gains no proven engagement (the peak is 10, and 11-12 is flat-to-declining toward the cliff) while moving toward the cliff — so **drop 11**.
- **MIN = 5**, not 6: the arc minimum is mathematically 5 (2 overhead + 3 body). My first draft used MIN 6 while also proposing a "punch = 5" band — Gemini correctly flagged this as a self-contradiction. Resolving to MIN 5 removes it.

Gemini's verdict (verbatim summary): MAX 10 "validated"; MIN 6 "flawed — contradicts your own punch=5 band"; the "standard 7-8 band directly contradicts the evidence... forces output into the statistical trough"; cleanest rule `N = max(5, min(10, 2_overhead + distinct_claims))`; "abandon the standard 7 concept entirely to respect the U-shaped engagement curve."

Final guard: **`N = clamp(5, 10, 2 + max(3, distinct_claims))`** with story-type target bands punch 5-6 / deep-dive 9-10, and "standard 7-8" permitted only when claim-count genuinely lands there (never as a default).

## What this means for the WR2 drafter (implementable specifics)

- **Single guard**: `5 <= N <= 10`. Replace the three conflicting bounds (6-8 prompt / 6-11 code / 5-13 docs) with this everywhere in `wr2_draft_generator.py`.
- **Count formula**: `N = 2 + max(3, distinct_claims)`, where `distinct_claims` = the number of separable S-pattern beats (each a rule, a consequence, an action, or a piece of evidence). Cover = hook beat; closer = CTA beat; they are inside the 2-overhead, not extra.
- **Story-type bands** (prompt instruction to the drafter):
  - punch / single regulation change -> target 5-6
  - deep-dive / multi-step process or multi-clause change -> target 9-10
  - 7-8 allowed ONLY when claim-count genuinely lands there; never the default. Instruct explicitly: "7 is the empirical engagement trough — do not pick it for convenience."
- **Hero:text** (judgment heuristic, not data): ~1 hero per 2-3 text/data slides; never >2 consecutive text-only slides; a filler hero is worse than no hero (keep existing WR2 stinginess rule).
- **Progress cue**: number the slides ("N of M" / step map) only when N >= 8; omit on 5-6.
- **Closer spec**: statement-bomb, <=2 visual lines, auto-shrink 72->56->48px; reserve a logo safe-zone BELOW the statement that holds through the 2-line + shrunk path; render-time assert the logo zone is present and unoccluded (extend the absolute-occlusion vision-sweep). elegant-close only follows statement-bomb on operational topics.

## Disagreements / open questions

- **Slide-13 peak**: aggregator blogs say carousels peak at slide 13 (37.8% reach). Verified this is **Stories data mis-attributed to carousels**. Resolution: carousel peak = 10 (Socialinsider), discard 13. The internal-docs "5-13" range likely inherited this error.
- **10 as a true optimum vs a cap artifact**: Socialinsider's "peak at 10" was measured when 10 was the max allowed. Post-20-slide-cap, we do not know if 11-14 outperforms 10. Open. We cap at 10 conservatively (completion cliff at 12 argues against testing high anyway).
- **FT 4-5 / Reuters 12-15 editorial lengths**: single internal observation (our 2026-06-11 bench), NOT independently verified today. Do not cite as external ground truth.
- **Hero:text ratio**: no external data exists. Treated as judgment heuristic.
- **Our own length effect**: UNMEASURABLE until the pipeline backfills `slide_count` + `ig_save_count` into `carousel_runs` (currently empty). The whole length recommendation is externally-grounded only.

## Checklist for action

- [ ] **Fix the guard inconsistency in `scripts/wr2_draft_generator.py`**: make code, prompt, and docstring all say **5 <= N <= 10** (drop 11; raise floor from 6 to 5 to allow the punch band; delete the 5-13 doc reference). Single source of truth for the bound.
- [ ] **Add a story-type length branch to the drafter prompt**: punch (single regulation change) = 5-6; deep-dive (multi-step process/multi-claim) = 9-10; explicitly tell the LLM NOT to default to 7 ("the 7-slide middle is the empirical engagement trough — polarize by claim count").
- [ ] **Encode the per-beat formula in the prompt**: `body slides = 1 per distinct claim/beat (each carrying one S-pattern element: rule | consequence | action), minimum 3 body slides; cover = hook, closer = CTA.`
- [ ] **Closer-slide hardening**: add a render-time assertion that the logo zone exists, is below the statement safe-zone, and is unoccluded after the 2-line + auto-shrink path (extend the `2026-06-04-statement-bomb-absolute-occlusion` vision-sweep check to the production closer; reserve logo safe-zone the way cover-photo.md does at 270px).
- [ ] **Anti-monotony design rule**: storyboarder/critic flag any run of >2 consecutive text-only slides; require a hero or distinct layout to break it.
- [ ] **Progress cue gating**: add slide-numbering / "N of M" only when N >= 8; omit on 5-6 punches.
- [ ] **Instrument length for future learning**: backfill `slide_count` (and `ig_save_count`/`ig_share_count`) into `carousel_runs` so the next ig-insights run can finally test length x engagement on OUR audience (currently impossible).

## Sources

1. Socialinsider 2024 carousel study (~3M carousels / 22M+ posts) — engagement-by-slide-count curve, peak at 10, U-shape, 6.8% use-all-10. Via https://www.socialinsider.io/blog/instagram-carousel/ and YouGov writeup https://yougov.com/articles/31680-carousel-posts-using-all-10-slides-instagram-have- (fetched 2026-06-30).
2. Socialinsider 2026 IG benchmarks — carousel reach 3.32%, engagement 0.55%, format comparison. https://www.socialinsider.io/social-media-benchmarks/instagram (fetched 2026-06-30).
3. Buffer / aggregator — re-serving unseen slides as new content; Mosseri Jan-2025 ranking signals (watch time, sends/reach, likes/reach). https://buffer.com/resources/instagram-algorithms/ + creatorflow/dataslayer writeups (fetched 2026-06-30).
4. carouselli / trymypost — completion drops after slide 3, recovers 8+, ~40% drop-off past 12, 65/55/80% targets, "Slide 1 of N" reduces abandonment. https://carouselli.com/blog/instagram-carousel-engagement , https://www.trymypost.com/blog/instagram-carousel-algorithm-2026-guide (fetched 2026-06-30; aggregator-tier, not primary).
5. postnitro / AIDA + 1-idea-per-slide + hook-context-payoff-CTA editorial frameworks. https://postnitro.ai/blog/post/carousel-copywriting-framework (fetched 2026-06-30).
6. Internal `skills/bali-zero-brand/_external-bench-2026-06.md` (2026-06-11) — length polarization, FT 4-5 / Reuters 12-15 (UNVERIFIED), trend sweet-spot 8-10, dip-after-3/recover-8, storyboarder length gap.
7. Internal `_empirical-metrics-2026-05-12.md` + ig-insights `2026-06-29` / `2026-06-23` — domain/tone/layout findings; confirmation that slide_count is NULL on all posts.
8. Internal `skills/bali-zero-brand/past/` — 64 archived carousels, ALL slides_count=7 (zero length variance).
9. Internal `scripts/wr2_draft_generator.py` (lines 2,6,154) — the 6-11 vs 6-8 guard inconsistency; `layouts/statement-bomb.md`, `layouts/elegant-close.md`, `_lessons/2026-06-04-statement-bomb-absolute-occlusion.md` — closer spec + defect.
10. Gemini 3.1 Pro (`agy`) independent review 2026-06-30 — MAX 10 validated, MIN 6 flawed, "standard 7" overreach flagged, cleanest rule `N=max(5,min(10,2+distinct_claims))`. Full output: scratchpad/gemini_out.txt.
11. DeepSeek Reasoner numeric tier — UNAVAILABLE 2026-06-30 (API "Insufficient Balance"); numeric derivation done by synthesis tier in-line instead.
