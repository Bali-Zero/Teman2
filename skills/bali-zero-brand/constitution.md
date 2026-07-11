# Bali Zero Brand Constitution

> Hard rules. Non-negotiable. The wr2-critic subagent enforces these. Violations = hard fail, route back to layout-composer.
>
> Last revision: 2026-05-08. Owner: Antonello Siano.

---

## Article 1 — Format

1.1 **Aspect ratio**: 1080 × 1350 px (Instagram 4:5 portrait). Hard fail if not.
1.2 **Slide count**: 7-10 per carousel. Below 7 = thin; above 10 = fatigue.
1.3 **Hero image count**: 4-6 per carousel. Cover (slide 1) ALWAYS hero. Closing often hero. Mid-carousel pivot slide often hero.
1.4 **Resolution**: PNG export at 1080×1350, sRGB.

## Article 2 — Palette (closed namespace)

2.1 Colors are referenced by **token name only**, never hex. Token namespace is closed; anything outside fails.

| Token | Hex | Role |
|---|---|---|
| `color.bg.antracite` | `#373D42` | Primary background |
| `color.bg.black` | `#000000` | Secondary background, hero overlay |
| `color.text.white` | `#FFFFFF` | Body text, headlines |
| `color.accent.yellow` | `#F4C430` | Data, sub-headlines, key numbers |
| `color.status.red` | `#C8102E` | Logo, "STOPPED", "CRIMINAL", critical alerts |
| `color.text.muted` | `#9CA3AF` | Sources, captions, footer (rare use) |

2.2 **Banned colors in TEXT zones and UI elements**: green (any shade), blue (any shade), purple (any shade), pastels, beige, brown. Hard fail.
2.3 **Region-aware pixel adherence**:
- **TEXT zones** (heading, body, sub-headline, list items, captions, source footers, status badges): ≥95% of pixels in palette tokens (color.bg.* + color.text.* + color.accent.* + color.status.*). Hard fail.
- **HERO PHOTO zones**: NO palette pixel constraint. Photo can use natural cinematic grading (35mm teal-amber Villeneuve/Deakins). Critic does NOT measure pixel-palette ratio inside hero bounding box.
- **GRADIENT OVERLAY zones**: where text sits over photo, dark gradient `color.overlay.darken-60` (rgba(0,0,0,0.6)) MUST be present at ≥0.6 opacity for legibility — see Article 5.5.
2.4 **Critic enforcement**: critic agent receives the layout JSON which declares for each element its `zone_type` (text | hero-photo | overlay | logo). Palette check applies only to `text` and `logo` zones. Photo bounds are skipped.
2.5 **Reason for region-aware rule**: a hard-blanket palette rule (the prior version) made teal-amber photo grading impossible (teal = blue-green). Region-aware preserves brand visual identity (cinematic photo treatment) without compromising text-zone legibility.

2.6 **Total-black flat-bg restraint** (added 2026-05-09 after Antonello aesthetic critique on QA + statement-bomb slides): pure `#000000` flat background WITHOUT texture/gradient/photo is permitted ONLY when text occupies ≥35% of canvas area visually. Below threshold the slide reads as "placeholder/unfinished" rather than "minimalist editorial". When text is sparse (statement-bomb ≤8 words, qa-dialogue, elegant-close), one of the following MUST be present:
- radial gradient (warm 5% center → black 100% edge), OR
- micro paper-grain texture (rgba opacity ≤2%), OR
- darkened photo backdrop (filter brightness ≤0.5), OR
- Hammurabi-stele backdrop (evidence-carved layout), OR
- antracite `color.bg.antracite` instead of pure black

Lesson: the WR2 reference set's all-black slides worked because they had heavy text mass. New layouts with sparse poetic text need atmospheric reinforcement to avoid reading as Word-doc empty.

## Article 3 — Typography

3.1 **Single family rule**: one geometric sans-serif throughout the carousel. Approved stack:
- Primary: Montserrat 700/800
- Fallback: Inter 700/800
- Secondary fallback: Poppins 700/800
3.2 **Banned font categories** (with one decorative exception): serif (any), script, display, handwritten, monospace (except IBM Plex Mono in source-citation footers — see 3.6). **Exception 3.2.1 — decorative serif at ultra-low opacity**: Cormorant Garamond OR Times New Roman serif allowed for decorative typographic ornaments (giant quote marks, oversized numerals, paragraph-mark glyphs) at opacity ≤8% as background visual flourish only, NEVER for any text the reader is meant to read. Added 2026-05-09 after qa-dialogue layout needed atmospheric quote marks. Use sparingly — max 1 layout family per carousel uses this.
3.3 **Case**: titles UPPERCASE always. Body case per Article 6.1.1 (UPPERCASE ≤35 words OR Title Case ≤50 words, NOT both in same carousel). Sentence case = hard fail in titles.
3.4 **Letter-spacing**: 0.02em titles, 0em body.
3.5 **Hierarchy**: heading must be visually topmost on each slide; body second-topmost. Decorative/source/footer below.
3.6 **Source citations** (rare): IBM Plex Mono 400 11px, `color.text.muted`, bottom-right corner.

## Article 4 — Logo

4.1 `3 ALI ZERO` mark — official PNG asset at `~/.claude/skills/bali-zero-brand/assets/logo.png` (940×940 RGBA: black circle, red `3`, white `ALI ZERO`, ॐ symbol bottom-right). The renderer copies this file into each carousel's `slides/logo.png` and CSS references via `background-image: url('logo.png')` in `_base.css`. Do NOT recreate the logo with text/SVG — always use the asset.
4.2 Position: centered bottom, 60-80px from bottom edge. Diameter:
- **80px** default (most layouts)
- **110px** allowed in `statement-bomb` and `elegant-close` layouts where the canvas is high-negative-space and the small logo would feel orphaned (added 2026-05-09).
- Diameter outside [80, 110] = hard fail.
4.3 Present on **every slide** without exception. Hard fail if missing.
4.4 The logo appears identical on every slide regardless of background color (black-circle wraps any background). NO inversions, NO color modifications, NO transparency adjustments.

## Article 5 — Imagery

5.1 **Style**: editorial 35mm film cinematic. Chiaroscuro lighting. Teal-amber color grading (Villeneuve / Roger Deakins reference). Low saturation outside palette.
5.2 **Cameras (for AI prompts)**: ARRI Alexa Mini LF, Hasselblad X2D, RED V-Raptor, Leica M11.
5.3 **Banned visual content** (anti-cliché, hard fail):
- Palm trees, beaches, infinity pools
- Sunsets / sunrises (unless storm/dramatic)
- Smiling team photos / handshakes / corporate stock
- Boho aesthetic / pastel filters / Instagram-influencer look
- Clipart, vector flat illustrations, icons-as-hero, meme images
- AI-art fingerprints (extra fingers, melted faces, impossible architecture)
5.4 **Faces**: no faces of real people unless verified Bali Zero stockphoto with consent. AI-generated faces must be ambiguous/back-turned/silhouette.
5.5 **Photo overlay**: when photo is hero with text overlay, dark gradient overlay (`color.bg.black` 0.6 opacity, top→bottom) always present on text zone for legibility.

5.6 **Anchor reference cascade** (added 2026-05-08, revised same day): every hero image generation MUST start from the domain anchor at `~/.claude/skills/bali-zero-brand/anchors/<domain>-anchor.jpg` as style reference. Slide 1 inherits domain anchor style; slides 2..N inherit slide-1 style. This guarantees both cross-carousel domain mood consistency and per-carousel internal consistency. Missing domain anchor falls back to pure slide-1 anchor with logged warning. Decision rationale: see `_canonical-anchor-decision.md`.

5.7 **Domain taxonomy (closed set)**: 5 production domains for carousel-ig surface — `visa`, `tax`, `property`, `regulatory` (covers HR/labor/BPJS/Permenaker), `health` (public health, outbreaks). Plus optional `brand` (about Bali Zero itself, rare). Adding a new domain requires constitutional amendment per Article 11. HR was merged into `regulatory` 2026-05-08 because labor/BPJS topics are infrequent and conceptually overlap with regulatory.

5.8 **Image style mode (per slide)**: 9 closed-set modes — `desk-document`, `event-photo`, `architecture-or-texture`, `provocation-photo`, `human-silhouette`, `object-comparison`, `calendar-photo`, `data-visualization`, `cultural-photo`. Each carousel declares dominant + secondary mode (Article 13.4). **Anti-monotone rule — see Article 10.6 for the binding form** (amended 2026-06-05): the old "NO two consecutive same dominant mode" wording here CONTRADICTED Article 13.4's "max 2 back-to-back". Article 10.6 (same-domain 14-day window, must differ in register AND/OR image-mode) SUPERSEDES both and is the law the critic enforces against `topic_type_log`. This clause is now descriptive (declare a dominant mode; vary it); the binding constraint lives in 10.6. `topic_type_log` is live on the production path as of 2026-06-05 (migration 216). Lesson from S11 (2026-05-09): 12 consecutive desk-document carouseli became visually indistinguishable; users perceive the brand as "always the same dark desk".

5.9 **Anchor reference cascade — implementation requirement**: when a domain anchor exists at `~/.claude/skills/bali-zero-brand/anchors/<domain>-anchor.jpg`, the slide-1 image generation MUST pass it as `--reference-image` to Codex `$imagegen` (or equivalent backend reference flag). Slide 2..N hero generations then chain-reference slide-1 of the current carousel. The previous loose interpretation ("include camera anchor in prompt text") is INSUFFICIENT — text-only reference produces drift. Lesson from S11: 12 carouseli with identical text-anchor produced visually identical mood, indicating text reference does NOT propagate style as image-reference does.

5.8.1 **Empirical mode ranking (added 2026-05-12, source: `_empirical-metrics-2026-05-12.md`)**: the 9 image-style modes are NOT equal in IG performance. Based on 7 top-performing past carouseli (@balizero0) ranked by Saves+Shares+Reach:

- **Tier 1 — preferred for COVER slides**:
  - `event-photo` (aerial drone documentary — 37k_villa 47K reach, mangrove 25K reach, traffic 23K reach)
  - `provocation-photo` (ground-level reportage with subject — bali_flood 14K reach, villa_ota 13K reach with 382 saves)
- **Tier 2 — selective use, mid-carousel**:
  - `architecture-or-texture` (weather/atmospheric variant)
  - `cultural-photo` (ONLY if tied to investor implication — pure-cultural without business angle empirically penalized, ref `respect` post)
- **Tier 3 — rare, justified only**:
  - `human-silhouette`, `data-visualization`, `desk-document`, `object-comparison`, `calendar-photo` — context-dependent, not for COVER without specific narrative reason

5.8.2 **Banned visuals — surreal/abstract (added 2026-05-12, empirical)**: hard fail for COVER if image is:
- Surreal Dalí-style figures (melting objects, distorted bodies, dream-state composition) — `cepaka` (lowest performer of the 7)
- Abstract geometric metaphor (shattering locks, exploding blocks, color-block conceptual) — predicted negative based on cepaka pattern
- Pergamena/parchment/wax seal/scroll — template trap S11 already documented + zero presence in top-7 performers
- Painterly/illustrated/anime/cartoon style — not editorial 35mm cinematic per Article 5.1

These bans apply to COVER specifically. Mid-carousel slides MAY use Tier-3 modes for variety, subject to Article 5.8 anti-monotone rule.

5.10 **No silent placeholder reuse (added 2026-05-09 after test-3+test-4 pattern, extended 2026-05-10 after test-6 catch)**: every hero slide MUST declare `image_source` in slides.json with one of two prefixes: `imagegen:<codex_session_id>` (fresh generation) OR `anchor:<filename>` (explicit declared reuse, requires slide-spec `image_strategy: "anchor_reuse"`). Verification rules:

- **5.10.1 hero ≠ anchor** (added 2026-05-09): `image_source: imagegen:*` → sha256 of hero file MUST differ from sha256 of `<domain>-anchor.jpg`. Equal hashes = silent reuse (caught by `cp anchor → hero` shortcut).
- **5.10.2 declared anchor matches** (added 2026-05-09): `image_source: anchor:<file>` → sha256 of hero file MUST equal sha256 of declared anchor file (proves it really is the anchor and not a stale placeholder from a prior carousel directory).
- **5.10.3 hero ≠ hero pairwise** (added 2026-05-10 after test-6 catch): for any two hero slides H_i, H_j (i ≠ j) where both have `image_source: imagegen:*`, sha256(H_i) MUST differ from sha256(H_j). Cause of failure: Codex `$imagegen` occasionally returns the same image for distinct prompts (cache hit / concurrent throttle / prompt similarity). Test-6 (2026-05-10 03:47 WITA) caught this: S3 and S4 ended up with bit-identical 2,064,224-byte JPGs. Without 5.10.3 the carousel would publish two consecutive heroes with the same image. Layout-composer hero-write step + critic Rubric 4 both enforce. On hit: re-trigger imagegen with `--force-fresh` flag and prompt-tweak (add unique salt phrase per slide, e.g., "[slide N variant]" appended); max 2 retries; on third hit, abort hero with `STATUS: imagegen_duplicate_unrecoverable` and surface to user.
- **5.10.4 missing or malformed image_source** = hard fail.

Lesson from test-3 (5 placeholders silently reused), test-4 (slide 1 layout-composer copied tax-anchor.jpg as finished hero in violation of 5.9 → critic R2 retry caught after fresh imagegen), test-6 (Codex returned identical bytes for S3+S4 prompts even with $imagegen explicitly invoked — orchestrator self-detected and called retry, but the formal rule was missing). Fix is sha256 verification at TWO points: layout-composer pre-write check AND critic post-render check. Belt-and-suspenders justified because failure modes are invisible-on-inspection.

## Article 6 — Copy

6.1 **Body length**: **25-50 words per slide** (revised 2026-05-08 from 25-90). Hard fail if outside range. Cover slide exempt (title only). Reason: at body 28-32px Montserrat 700 UPPERCASE in 1080×1350 with hero zone occupying ≥40% of canvas, 50 words is the empirical max before text-zone overflow OR illegibility (Tinker 1955 reading-speed studies confirm UPPERCASE >2 lines at body sizes loses 13-20% reading speed). 90 words was theoretical max; 50 is craft max.
6.1.1 **Body case**: Body Title Case OR UPPERCASE — pick ONE per carousel and stick to it. Mixing cases across slides = soft fail (route to layout-composer). UPPERCASE body REQUIRES body length ≤35 words to remain legible. Title Case body allows full 25-50 range. Recommended default: UPPERCASE for slides with hero (≤35 words) + Title Case for text-only slides (up to 50 words).
6.1.2 **Body lingua-target — two-bucket bilingual lexicon (added 2026-05-09)**: the audience is anglophone expats who already know branded technical terms but NOT every Indonesian operational noun. Brief-interpreter classifies every ID term used in body into one of two buckets:

- **Always-untranslated bucket** — KITAS, KITAP, PT PMA, KBLI, SHGB, hak pakai, KKPR, BATARA, Permenkumham, Coretax, OSS RBA, NPWP, konsultan pajak, PPJK, Wajib Pajak Badan. Use verbatim, NO gloss. Translating these = hard fail.
- **Assist-on-first-use bucket** — DENDA, BUNGA, MAP, MAR, KURANG BAYAR, LAMPIRAN, and similar operational nouns the audience may not recognize. On FIRST occurrence in carousel body (slides 2..N), term must be followed by English assist appositively (parens, em-dash, or comma+gloss). Subsequent uses can drop the gloss. Patterns:
  - "ZERO DENDA (MONTHLY LATE-FILING FEE). ZERO BUNGA (INTEREST ACCRUAL)."
  - "DENDA — THE MONTHLY FEE FOR LATE FILING — IS WAIVED."
  - "FILE THE LAMPIRAN (ATTACHMENT) BY MAY 31."

Hard fail if a non-always-untranslated ID term appears on first use without English assist. Lesson: test-4 S4/S6 accumulated DENDA/BUNGA/MAP/MAR/KURANG BAYAR/LAMPIRAN as raw terms — readable to a tax consultant, opaque to the actual audience. Robotic literalism is not editorial discipline; classy bilingual exposition is.

6.2 **Tone register**: must be one of the seven recognized registers (rituale, analitico, ironico, militante, pedagogico, poetico, tecnico). Mixing 3+ registers in same carousel = hard fail.
6.3 **Numbers concrete always**: `$7B`, `498 hectares`, `Rp 230M/year`, `47 KITAS filed this month`. Vague ("a lot of investment", "many expats") = hard fail.
6.3.1 **Bullet-promise enforcement (added 2026-05-09)**: when heading or subheading announces a count or list (`FOUR FORCES CONVERGED`, `THREE DEADLINES`, `5 RED FLAGS`, `TWO PATHS`), the body MUST deliver exactly that count as a discrete bullet/list/numbered structure (`<ul>`, §-marker A/B/C, list_items array, or numbered lines). Hard fail if N announced ≠ N delivered, or if body is a prose paragraph despite count promise (S6 mappazza pattern). If true count is uncertain at brief time, rewrite the heading to remove the count promise rather than fudge the body. Storyboarder is the primary enforcer; layout-composer flags as `validation_failures`; critic Rubric 3 hard-fails on detection.
6.4 **Regulatory citations verbatim**: `PP 18/2021`, `Permenkumham 22/2023`, `KEP-71/PJ/2026`, `UU No. 26/2007`. Paraphrasing ("a recent law", "new spatial planning regulation") = hard fail.
6.5 **Bilingual lexicon untranslated**: KITAS, KITAP, PT PMA, KBLI, SHGB, hak pakai, KKPR, BATARA, konsultan pajak, PPJK, Permenkumham, NPWP, Coretax, OSS RBA. Acronyms UPPERCASE, bahasa lower (`hak pakai`).
6.6 **Sentence-bomb closings**: closing slide MUST be single-line bold centered statement. NO CTA hard-sell. Specifically banned ("hard-sell"):
- "DM US NOW" / "MESSAGE US"
- "BOOK A FREE CONSULTATION"
- "LIMITED OFFER ENDS [DATE]"
- "TAP / CLICK / SWIPE TO [verb]"
- "SAVE THIS POST" / "SHARE WITH A FRIEND"
- "FOLLOW @balizero0 FOR MORE"
- "👉" or any directional emoji
- "LINK IN BIO" on a slide (acceptable in IG caption only)

6.6.1 **Elegant CTA allowed** (added 2026-05-09, revised same day): a single optional `elegant-close` slide MAY follow statement-bomb (so the carousel ends statement-bomb → elegant-close at slides N-1, N). Elegant-close uses soft consultant language, NOT sales language. Permitted patterns:
- TWO reach lines: email `ZANTARA@BALIZERO.COM` + WhatsApp `+62 821 3107 363` (both = same Bali Zero Zantara front-desk, listing both is informational not pushy)
- A soft conditional invite: "IF YOUR CASE TOUCHES THIS — A 30-MIN CALL CONFIRMS NEXT STEPS." or "WHEN YOU'RE READY — WE'VE WALKED THIS PATH 5,000 TIMES."

Forbidden in elegant-close:
- imperative verbs ("CALL NOW", "BOOK", "CONTACT", "TAP", "CLICK")
- urgency language ("TODAY", "SOON", "DON'T MISS", "ENDS")
- benefit-claim language ("BEST", "FAST", "EASY", "GUARANTEED")
- prices, deadlines, offers, discount codes
- emoji directional arrows
- "FOLLOW @balizero0" / "SAVE THIS POST" / "SHARE WITH A FRIEND"
- trust-marker / credentials line (removed 2026-05-09 — credentials live in IG bio + caption, not on slide; the slide is for contact + invite only)
6.7 **No emoji** in titles or body. Ever.
6.8 **No corporate disclaimer**: "this is not legal advice", "consult a professional", "we are not lawyers" — hard fail. Bali Zero IS the lawyers (konsultan pajak + PPJK registered).

6.9 **Saves-over-Likes optimization (added 2026-05-12, empirical)**: Bali Zero IG carousel KPI is **Saves and Shares**, NOT Likes. Reference dataset: `_empirical-metrics-2026-05-12.md`.

**Top 2 performers** by Save/Like ratio:
- `villa_ota` (Save/Like = **2.20**, Share/Like = **2.69**) — explains a rule (OTA license) with monetary consequence
- `37k_villa` (Save/Like = 1.12, Share/Like = 2.03) — concrete number (37,881) with verdict

**Common structure of S-pattern (Save magnet) carouseli — required**:
1. Cover headline contains a **concrete number, regulation code, OR named scope** (`37,881`, `KEP-71/PJ/2026`, `$7B`, `2 floors / built 7`)
2. Cover sub-headline is **location-specific OR time-specific OR contains categorical verdict** (`KEROBOKAN KELOD`, `AFTER THE SEPTEMBER 10TH FLOODS`, `MANGROVES WON`)
3. Body slides MUST teach: **1 rule + 1 consequence + 1 actionable next step** (or set of N where N matches a count promise per Article 6.3.1)
4. Audience tilt: **investor / business operator > local / cultural tourist**. Pure-cultural content empirically gets 0% Explore push and ≤3% non-follower reach (`respect` post case).

**Hard fail (Article 6.9.fail)** — cover heading + subhead together MUST contain at least ONE of the following six **empirical anchors** (refined 2026-05-12 after Antonello edge-case challenge — pure editorial commentary like `Two Boys. Two Faiths. One Island.` was being wrongly rejected):

1. **Concrete number** — count, percentage, currency, hectares, years (`37,881`, `$7B`, `25%`)
2. **Regulation / code** — verbatim Indonesian regulatory cite (`KEP-71/PJ/2026`, `Permenkumham 22/2023`, `UU 26/2007`)
3. **Specific location** — Indonesian place name or zone (`KEROBOKAN KELOD`, `UBUD`, `BADUNG`, `TUKA TIBUBENENG`, `BALI`, `JAKARTA`)
4. **Categorical verdict** — closed-state outcome (`MANGROVES WON`, `BALI SHUTS DOWN`, `BANS NEW BUILDS`, `RESCINDED`, `WAIVED`)
5. **Editorial contrast / parallelism** — n-tuple parallelism that creates narrative tension (`TWO BOYS. TWO FAITHS. ONE ISLAND.`, `SAME POOL. SAME DESIGN. SAME PROBLEM.`, `PERMIT: 2 FLOORS / BUILT: ALMOST 7`)
6. **Time-specific event** — date, named event, period (`AFTER THE SEPTEMBER 10TH FLOODS`, `DECEMBER 30, 2025`, `Q1 2026`)

A cover is **valid** if the heading+subhead together carry AT LEAST ONE of these six anchors. The `respect` post (`THINGS YOU CAN'T DO IN BALI THAT PEOPLE KEEP DOING`) fails because it contains ZERO of the six — vague generality with no specificity.

**Soft fail (Article 6.9.warn)** — body slides without a single "what should YOU do" thread by slide N-1.

6.10 **Distribution-aware design (added 2026-05-12, empirical)**: top performers in @balizero0 dataset reached audience via **From Home + Other (DM peer-share)**, NOT via Explore algorithm. Implications:
- Design for **share-by-follower** (something a follower wants to forward to a peer)
- NOT for click-bait Explore push (sensationalist hooks underperform — `cepaka` Dalí cover, `respect` cultural-only)
- A good test before publishing: "would a Bali Zero follower send this to their accountant / business partner / lawyer?"

## Article 7 — Forbidden phrases (closed list)

The following phrases are absolutely banned. Soft-match (case-insensitive substring) = hard fail.

- `delve into`
- `landscape` (in metaphorical sense — "regulatory landscape" → use "regulatory perimeter")
- `tapestry`
- `realm`
- `journey` (in the boilerplate sense — "your Bali journey")
- `ecosystem` (in marketing sense)
- `make Bali your home`
- `live the dream`
- `paradise`
- `are you thinking of moving to Bali`
- `your Bali adventure`
- `book now`
- `limited offer`
- `DM us`
- `link in bio` (acceptable only in IG caption, never on slide)
- `swipe to`/`swipe for` (carousel mechanic, not editorial copy)
- `let's dive in`
- `at the end of the day`
- `game-changer`
- `unlock`
- `seamless`
- `synergy`

## Article 8 — Spelling & accuracy

8.1 **Spell-check mandatory** before export. WR2 historical typo log: `DIFEFERENT`, `MIINISTRIES`, `PARLEMENT` (correct: `PARLIAMENT`), `GRANDFATHHERED` (correct: `GRANDFATHERED`).
8.2 **Acronym verification**: every regulatory acronym must be cross-checked against NB-1 (legal) or NB-4 (tax) or NB-5 (property) before export. Hallucinated acronyms = hard fail.
8.3 **Number verification**: any concrete number (currency, hectares, deadlines, percentages) must trace to a source in the brief's `key_facts`. Unsourced numbers = hard fail.

## Article 9 — Layout discipline

9.1 **Layout family pool** (closed set, current revision 2026-05-09):
- `cover-photo`
- `photo-headline-yellow-sub`
- `qa-dialogue` (two voices, two colors)
- `timeline-pinboard`
- `dark-status-list` (status/number enumerations ONLY — e.g. `X: STOPPED`, numeric tiers; for the FACTS-VS-TAKE frame it is DEPRECATED since 2026-05-09, use `evidence-carved`. Generic `FACT`/`OUR TAKE` labels are BANNED, see storyboarder CONTENT-LABEL RULE)
- `evidence-carved` (Hammurabi-backed FACTS frame; replaces dark-status-list for FACTS-VS-TAKE function — added 2026-05-09)
- `three-verdicts` (3 §-marker color-coded outcome blocks over hero photo backdrop — added 2026-05-09 for decision-tree/scenario slides)
- `statement-bomb`
- `elegant-close` (soft CTA slide, follows statement-bomb when carousel needs contact invite — added 2026-05-09)
- `source-citation` (dedicated SOURCES slide N-1 for regulatory/visa/tax/property with slide_count ≥ 7 — added 2026-05-12 per Article 14.3 amendment pending, SOTA pattern #11 from `_external-bench-2026-05.md`)
9.2 **Variety rule**: a single carousel may use at most **5 distinct layout families** (revised 2026-05-08 from 3 → 5 after first production run KEP-71-SPT showed regulatory carousels with FACTS/TAKE frame + Q&A pivot + statement-bomb closing genuinely benefit from 5 families). Soft cap: prefer ≤4 unless the topic warrants high information density (regulatory dossiers, multi-deadline pieces). Avoid Frankenstein patchwork — each family should serve a narrative function, not just visual variety.
9.3 **Cover slide**: always `cover-photo` family. Hard fail otherwise.
9.4 **Frame slide** (slide 3 typically — shifted from slide 2 on 2026-05-12 per Article 14.2 framing-question rule): often `dark-status-list` styled as "FACTS (SOURCED) VS OUR TAKE". Recommended, not mandatory. Slide 2 is now reserved for the framing-question transition per Article 14.2 (SOTA pattern #13). The legacy convention "slide 2 = frame" applied before Article 14.2 was adopted.
9.5 **Closing slide**: always `statement-bomb` family. Hard fail otherwise.

## Article 10 — Process guardrails

10.1 **Critic panel mandatory**: every carousel must pass `wr2-critic` before output. Skip = hard fail at orchestrator level.
10.2 **Human-in-loop on publish**: agent never publishes to Instagram. Damar publishes manually. (Owner-binding decision OB-1, 2026-05-07.)
10.3 **No autonomous skill writes to main**: skill changes go to `_proposed/`. Antonello commits to main weekly.
10.4 **Cost = zero**: only OAuth Claude (subagents), free Gemini CLI, NotebookLM, DeepSeek API ($0.01/q OK). Never use ANTHROPIC_API_KEY, OpenAI API, Vertex AI billed runtime. (CLAUDE.md HARD RULE.)
10.5 **Idempotency of FACTS + STRUCTURE only** (amended 2026-06-04 after WR2 autopsy): re-running the same brief must keep the *verifiable* layer stable — same key numbers, same legal citations, same slide count, same archetype. It must NOT force the *expressive* layer (register, image-style mode, layout family, copy phrasing, hero composition) to be identical. Drift in facts/structure = hard fail; drift in expression is EXPECTED and good. (Prior wording made expressive variety itself a hard fail — that rewarded the monotony this constitution now forbids in 10.6.)

10.6 **Anti-sameness across a domain window** (added 2026-06-04, WR2 autopsy P-3): two carousels published in the SAME domain (visa / tax / company / property / culture) within a 14-day window MUST differ in BOTH (a) dominant register AND (b) image-style mode. Identical register+mode on consecutive same-domain carousels = **hard fail**. This is the positive counterweight to 10.5: facts stay fixed, the telling must vary. Enforced via `topic_type_log` (last-2-published lookup) once that table is live on the production path; until then, the critic asserts it from the running session's prior outputs.

## Article 11 — Amendment process

11.1 Constitution is amended only by Antonello, via git commit to `~/.claude/skills/bali-zero-brand/constitution.md`.
11.2 The reflective loop (weekly cron) may *propose* amendments by writing to `~/.claude/skills/bali-zero-brand/_proposed-amendments/<date>-<slug>.md`. Antonello reviews and merges.
11.3 All amendments must include: rule number, change, rationale (why), date, link to triggering carousel(s).

## Article 13 — Editorial archetypes (closed taxonomy)

13.1 Every carousel belongs to ONE of 8 archetypes. The archetype determines slide_count range, dominant register, layout pool, image style mode. No archetype = no carousel. (Added 2026-05-09 after S11 produced 12 carouseli all in single regulatory-explainer mode — the rest of the taxonomy must be available.)

| Archetype | Slide count | Dominant register | Layout pool | Image style mode |
|---|---|---|---|---|
| `regulatory-explainer` | 8-10 | tecnico + analitico | cover-photo + evidence-carved + photo-headline-yellow-sub + qa-dialogue + statement-bomb | desk-document |
| `news-flash` | 4-6 | analitico + militante | cover-photo + dark-status-list + statement-bomb | event-photo |
| `quote-led` | 6-8 | rituale + poetico | cover-photo + statement-bomb (heavy) | architecture-or-texture |
| `anti-cliche` | 5-7 | ironico + militante | cover-photo + statement-bomb (heavy) + qa-dialogue | provocation-photo |
| `story-driven` | 8-10 | pedagogico + tecnico | cover-photo + photo-headline-yellow-sub + timeline-pinboard | human-silhouette + document |
| `comparison` | 7-9 | analitico + pedagogico | cover-photo + dark-status-list + qa-dialogue + statement-bomb | object-comparison |
| `calendar-tracker` | 6-8 | analitico | cover-photo + timeline-pinboard (dominant) + statement-bomb | calendar-photo |
| `testimonial-data` | 5-7 | rituale + tecnico | cover-photo + dark-status-list (numbers) + statement-bomb | data-visualization |
| `cultural-insight` | 7-9 | poetico + pedagogico | cover-photo + photo-headline-yellow-sub + statement-bomb | cultural-photo |

13.2 **Archetype declaration mandatory** in `slides.json`: top-level `archetype: "<name>"` field. Critic checks slide_count + register + layout pool against archetype rules — out-of-archetype = soft fail.

13.3 **Archetype is a REQUIRED, JUSTIFIED choice — no static default** (amended 2026-06-04, WR2 autopsy P-3): there is NO fallback archetype. The brief-interpreter MUST pick one of the 8 archetypes for THIS topic and record a one-line rationale. Picking `regulatory-explainer` reflexively for every visa/tax/company topic is the documented S11 failure (12 identical carousels) and the cause of the "always the driest register" complaint — it is now disallowed as an unjustified default. Guidance, not a default: breaking-news → news-flash; cultural pieces → cultural-insight; single-statement provocations → anti-cliche; a genuine rules-explainer with no stronger angle MAY still be `regulatory-explainer`, but only with a rationale stating why no other archetype fits better. A missing or rote ("default") rationale = soft fail.

13.4 **Image style modes** (Article 5.8 below):
- `desk-document`: paper/seal/lamp/dark wood (current S11 norm)
- `event-photo`: subject in real environment (street, office, building)
- `architecture-or-texture`: monolithic structure, building edge, stone, fabric — no text or document
- `provocation-photo`: visually surprising element (broken object, contradiction, scale shift)
- `human-silhouette`: anonymous figure, back-turned, no face
- `object-comparison`: 2-3 objects side-by-side
- `calendar-photo`: dates/clock/calendar dominant
- `data-visualization`: chart, graph, ledger, ledger
- `cultural-photo`: ceremony detail, offering, temple gate (close-up, never wide tropical)

Each archetype maps to 1-2 default image modes. Variation enforced: max 2 carouseli back-to-back can use the same image-style mode (avoid the S11 monotone trap where all 12 used desk-document).

## Article 12 — Surfaces (closed taxonomy)

12.1 This brand cortex governs **4 surfaces**. Each surface inherits cross-surface rules (Articles 2, 3, 6.3-6.7, 7, 8) and adds surface-specific rules.

| Surface | Spec location | Aspect / format |
|---|---|---|
| `carousel-ig` | constitution.md Articles 1-11 + layouts/ | 1080×1350 portrait, 7-10 slides, PNG export |
| `internal-print-a4` | `surfaces/internal-print-a4.md` + `surfaces/internal-print-a4/_template.css` | A4 PDF, multi-page, zero-margin print |
| `web-mouth` | `apps/mouth/CLAUDE.md` + `packages/core/styles/bz-tokens.css` | Next.js frontend (separate stack — referenced not maintained here) |
| `email-template` | TBD (open backlog) | Brevo HTML email |

12.2 **Cross-surface mandatory rules** (apply to every surface):
- Article 2 (palette, region-aware enforcement)
- Article 3 (single-family Montserrat)
- Article 6.3 (numbers concrete)
- Article 6.4 (regulatory citations verbatim)
- Article 6.5 (bilingual lexicon untranslated)
- Article 6.6 (no CTA hard-sell on primary editorial content)
- Article 6.7 (no emoji)
- Article 7 (forbidden phrases closed list)
- Article 8 (spelling + acronym verification)

12.3 **Surface-specific overrides allowed only** for typography sizing (e.g., A4 brief uses larger headline scale than 1080×1350) and layout constraints (e.g., A4 brief has cover + interior page distinction; carousel has cover + closing). NEVER override palette tokens, voice rules, forbidden phrases, or regulatory citation discipline.

12.4 **Adding a new surface** requires constitutional amendment (Article 11.1). Proposing in `_proposed-amendments/` is open to any agent; merging requires Antonello git-commit.

## Article 14 — SOTA Adoption Rules (added 2026-05-12, partial merge — subset 14.1/14.2/14.4 approved; 14.3/14.5 deferred)

Bali Zero IG carousel design must remain aligned with global editorial state-of-the-art (`_external-bench-YYYY-MM.md`). The following rules formalise the gap-closing changes adopted after the 2026-05-12 100-cover SOTA audit. Source evidence: `_external-bench-2026-05.md`.

**Status (2026-05-12 Antonello decision)**: 14.1 + 14.2 + 14.4 APPROVED, merged. 14.3 + 14.5 DEFERRED pending smoke test (status preserved in `_proposed-amendments/2026-05-12-five-sota-adoption-rules.md`).

### 14.1 — Swipe indicator on inner slides (APPROVED, SOTA pattern #10)

Slides 2 through N-1 of every carousel MUST contain a `.swipe-indicator` element (yellow dot, bottom-right, 12px, 32px offset from canvas edges). Cover (slide 1) and last slide (N) excluded.

**Rationale**: Carouseli without swipe affordance underperform on completion rate (Hootsuite 2026 benchmark). Yellow dot signals "more inside" without consuming attention. NYT, Axios, Semafor, Quartz adopted this 2024-2025.

**Enforcement**: critic Rubric 5 check 5.6 — soft fail (-5 per missing slide, capped at -20).

**CSS class**: `.swipe-indicator` in `layouts/_base.css`. Variant `.swipe-indicator--arrow` available for archetypes preferring directionality.

### 14.2 — Slide 2 = framing question (APPROVED, SOTA pattern #13)

Slide 2 MUST be a single-sentence framing answering "why this carousel exists for the reader specifically", in question-form OR statement-form. NOT a 3-5 item bullet list.

**Rationale**: The SOTA editorial stack (NYT, Atlantic, Vox, WSJ) treats slide 2 as transition between hook (cover) and evidence (slide 3+). Bali Zero's previous convention skipped this and cost swipe-through rate.

**Format**:
- Question-form (preferred): `Bagaimana ini terjadi?` / `Apa artinya untuk PT PMA kamu?` / `What this means for your PT PMA.`
- Statement-form (when question would sound rhetorical): `Your annual return deadline just shifted by 31 days.`

Body under the framing question: 25-50 words, ONE sentence answering the question. NOT a list.

**Archetype carve-out**: short archetypes (`news-flash` 4-6 slides, `anti-cliche` 5-7 slides) where `slide_count ≤ 5` MAY collapse the framing into the cover sub-headline OR the slide-2 evidence opener. Required for: `regulatory-explainer` (8-10), `quote-led` (6-8), `story-driven` (8-10), `comparison` (7-9), `calendar-tracker` (6-8), `testimonial-data` (5-7), `cultural-insight` (7-9).

**Enforcement**: storyboarder enforces at brief-time; critic Rubric 3 detects 3-5 item bullet list on slide 2 = soft fail; legacy "FACTS VS OUR TAKE" pattern now belongs to slide 3 (Article 9.4 reflects shift).

### 14.4 — Regulation badge top-right on cover (APPROVED, SOTA pattern #3, REVISED 2026-05-13 for WCAG AAA)

When `brief.primary_regulation_code` is non-empty, the cover slide MUST display a `.regulation-badge` (**yellow rounded rect `#F4C430`, black text `#000000`, IBM Plex Mono 16px**) at top-right (32px offset) showing the regulation code verbatim.

When `brief.primary_regulation_code` is empty, the cover MUST NOT display this badge (avoid false-authoritative signal).

**Rationale**: FT, Kontan, Tempo signal "we are citing the primary source" before the body is read. Indonesian regulatory audience reads the code first. Yellow chosen 2026-05-13 after WCAG audit (research/wr2-design-sota/2026-05-13-best-bg-color-editorial-publisher.md) found red-as-text on the dark bg FAILS contrast; yellow passes. Recomputed 2026-07-08 on the corrected antracite `#373D42` (historic value `#373D42` read as blue-grey — palette fix by Zero): yellow `#F4C430` vs bg = 6.70:1 (AA, AAA for the large display text carousels use), white vs bg = 11.0:1 (AAA), muted `#9CA3AF` vs bg = 4.33:1 (large text/captions only), red `#C8102E` vs bg = 1.87:1 (never as text on bg — logo/badge fills only), black text on yellow = 12.79:1 (AAA inside).

**Brand semantics (added 2026-05-13)**: yellow unifies regulation badge with Article 6.9 anchor highlights as the **family color for "verifiable facts"** — numbers, codes, regulations, dates. Red retained for: logo (3 ALI ZERO red glyph on black-circle bg, accessible by construction), red rule dividers (line not text, contrast n/a), and status critical alerts on white background only.

**Enforcement**: critic Rubric 5 check 5.7 — soft fail (-10) if missing when code is set; HARD FAIL if badge text differs from `brief.primary_regulation_code` (citation tampering = Article 6.4 cascade); HARD FAIL if badge uses red `#C8102E` bg on antracite (legacy WCAG-fail pattern).

**CSS class**: `.regulation-badge` in `layouts/_base.css`. Token namespace `regulation_badge` in `tokens.json` (revised 2026-05-13).

### 14.3 — Source-citation slide (DEFERRED, SOTA pattern #11)

Status: deferred pending smoke test + decision after measuring impact of approved rules. Draft preserved at `_proposed-amendments/2026-05-12-five-sota-adoption-rules.md` § 14.3. Layout file `layouts/source-citation.md` exists in repo (ready) but is not constitutionally required until merge.

If a carousel chooses to include `source-citation` layout, it follows the rules in `layouts/source-citation.md`. Critic check 5.5 stays soft-fail-advisory until promotion.

### 14.5 — QR closing for primary source (DEFERRED, SOTA pattern #25)

Status: deferred pending smoke test + server-side QR generator implementation (qrencode/segno integration in renderer). Draft preserved at `_proposed-amendments/2026-05-12-five-sota-adoption-rules.md` § 14.5. CSS class `.qr-closing` exists in `_base.css` (ready) but storyboarder will not populate `primary_source_url` until promotion + QR generator wired.

### 14.6 — Rule promotion process (added 2026-05-12)

Deferred rules (14.3, 14.5) graduate to APPROVED via the standard amendment process (Article 11.1):
1. A/B test on ≥3 carouseli where deferred rule is opt-in active via brief field
2. Measure Save/Like and Share/Like delta vs `_empirical-metrics-2026-05-12.md` baseline after 14 days
3. If delta is positive AND not contradicted by `_external-bench-YYYY-MM.md` next monthly run, propose promotion in `_proposed-amendments/`
4. Antonello git-commit promotes the rule into Article 14 (deferred → approved)
5. Critic Rubric 5 corresponding check upgrades from soft-fail-advisory to soft-fail-enforced

## Article 15 — Banned Type-as-Design Patterns (added 2026-05-13)

The 2026-05-12 SOTA audit (`research/wr2-design-sota/2026-05-12-type-as-design-inner-slides.md`) catalogued 10 type-as-design patterns observed in editorial publishers worldwide. After visual review of 5 mockups (`/tmp/wr2_5patterns_observe_mockup.py`), Antonello rejected the following five patterns on 2026-05-13 with the verdict "gimmick visivi — distraggono dal contenuto utility".

**Banned patterns (hard fail in critic Rubric 5 if present in any slide):**

### 15.1 — Oversize quote marks (`oversize-quote-marks`, was SOTA pattern 3.3)

Decorative quotation glyphs (« » " " " ") set at 200pt+ as background ornament. Banned because: (a) signals "this is a quote" before the reader has decided whether it matters, (b) eats canvas real estate that should carry editorial content, (c) imports lifestyle/luxury magazine convention into a utility/regulatory surface.

If a slide MUST cite a verbatim source quote, use `quote-led` archetype rules (Article 13) with attribution line, NOT decorative quote marks as graphic.

### 15.2 — Diagonal / asymmetric break (`diagonal-asymmetric-break`, was SOTA pattern 3.4)

Slide composition where heading or body is rotated 5°-45° off-axis, or where the canvas is split diagonally by a color block. Banned because: (a) reading at non-horizontal angle reduces comprehension and is partially WCAG-failing on small displays, (b) signals "design school portfolio" not "regulatory authority", (c) breaks the Swiss-grid orderliness that distinguishes Bali Zero from competitor lifestyle pages.

The approved alternative for visual rhythm: `swiss-grid-asymmetry` (Pattern 4 ADOPT — horizontal blocks with varied left-edge alignment but ALL text axis-aligned 0°).

### 15.3 — Solid color block statement (`solid-color-block-statement`, was SOTA pattern 3.5)

Inner slide where 60%+ of canvas is a single solid yellow/red/black field carrying one short statement, no other content. Banned because: (a) duplicates the `statement-bomb` closing layout but in a mid-carousel position where it disrupts the discovery arc, (b) on antracite carouseli, a solid yellow block destroys the cinematic continuity established by hero photos, (c) reads as a sponsored-ad break.

`statement-bomb` is ONLY allowed at the closing slide (Article 9.4) or, per archetype rules (Article 13), as the heavy spine of `quote-led` / `anti-cliche`. Solid color blocks in regulatory-explainer / news-flash / story-driven inner slides = hard fail.

### 15.4 — Color-coded label / pill tag (`color-coded-label-tag`, was SOTA pattern 3.8)

Heading prefixed by a small rounded pill ("NEWS", "ALERT", "EXPLAINER", "DEEP DIVE") in a contrasting bg color. Banned because: (a) competes with the cover-only `.regulation-badge` (Article 14.4) for visual identity, (b) every Bali Zero carousel already has a defined archetype (Article 13) which IS the editorial label — adding a pill is redundant noise, (c) blog-import convention.

The single sanctioned in-slide label is `.regulation-badge` (cover only, when `brief.primary_regulation_code` is set).

### 15.5 — Vertical edge running text (`vertical-edge-running-text`, was SOTA pattern 3.9)

Text rotated 90° running along the left or right edge of the canvas (carousel issue number, date, "READ →" prompt rotated vertically). Banned because: (a) at 1080×1350 IG dimensions, vertical text is ~50-80px wide and below WCAG-readable scale on phone display, (b) bahasa Indonesia and English are horizontal-script languages, vertical setting is a typographic affectation, (c) magazine-import not adapted for thumb-scroll medium.

Carousel metadata (date, issue, source) goes in the standard `source-citation-footer` (bottom-left, horizontal, mono 11pt, defined in `_base.css`).

### 15.6 — Enforcement

Critic Rubric 5 adds checks 5.10 (oversize quote marks), 5.11 (rotation ≠ 0°), 5.12 (solid color ≥60% canvas on inner slide), 5.13 (pill labels), 5.14 (vertical text). Detection: visual inspection by `wr2-critic` (Opus 4.7 vision) on rendered PNG. Each occurrence = soft fail (-15), 2+ banned patterns in same slide = hard fail.

Layout-composer MUST NOT generate HTML/CSS implementing these patterns. If a layout file in `layouts/` accidentally implements one, file it under `_deprecated/` with a leading `_` and remove from `layout_families_used` enumeration in Article 9.2.
