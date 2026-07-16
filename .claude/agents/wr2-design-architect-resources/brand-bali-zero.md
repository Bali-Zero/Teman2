# Bali Zero Brand Profile

> Source: extracted from codebase 2026-05-08. Maintained authoritative for the WR2 Design Architect agent. Update when brand evolves.

---

## 1. Visual Identity

### Palette

Source: `packages/core/tokens/primitives.css` + `themes/dark.css`

| Token                   | Hex       | Role                                    |
| ----------------------- | --------- | --------------------------------------- |
| `--color-gold-500`      | `#f59e0b` | Primary brand gold                      |
| `--color-gold-300`      | `#ffc666` | Warm accent                             |
| `--color-red-500`       | `#ff2d4c` | Visa funnel identity / urgency          |
| `--color-neutral-950`   | `#09090b` | Near-black base                         |
| `--color-black`         | `#040406` | True black                              |
| `--accent-warm`         | `#d4845a` | Editorial copper                        |
| `--accent-sand`         | `#d4b483` | Editorial sand                          |
| `--accent-gold-muted`   | `#c9a96e` | Muted editorial gold                    |
| `--surface-base` (dark) | `#121016` | Warm graphite (3% red-violet undertone) |

### Typography

- **Display/UI**: `Inter`
- **Long-form editorial**: `Cormorant Garamond`
- **Mono**: `IBM Plex Mono`
- **Brand tagline (homepage)**: `Arial Black / Impact / Franklin Gothic Heavy` — uppercase, weight 900, 0.06em letter-spacing

### Carousel hero photo style (BRAND_SUFFIX, scripts/wr2_image_generator.py:145-162)

> "Editorial photography, shot on 35mm film, subtle film grain, chiaroscuro lighting, low-key exposure, desaturated muted palette of deep charcoals and warm ochre accents. Minimalist composition with vast negative space. No human faces visible — silhouettes or objects only. Photorealistic. CRITICAL ASPECT RATIO: 4:5 portrait, 1080x1350 pixels, full-bleed, no border, no whitespace on any side."

### Article cover photo style (apps/bali-intel-scraper/scripts/bz_image_style.py)

5 non-negotiable pillars (16:9, distinct from carousel 4:5):

1. **Cinematic realism** — film frame look, never "AI art plastic"
2. **Teal-amber color grading** (Denis Villeneuve / Roger Deakins palette) — teal/cyan in shadows, amber/gold in highlights
3. **Serious surreal anachronism** — e.g. Einstein in batik, zero visual irony
4. **Monumental scale + golden hour (80%) / moody overcast (20% crisis)**
5. **Tonal dualism** — warm/golden for opportunity, cold/shadow/surveillance for risk

**Cameras**: ARRI Alexa Mini LF, Hasselblad X2D, RED V-Raptor, DJI Inspire 3
**Lenses**: 24mm wide, 35mm environmental portrait, 50mm f/1.4, 85mm f/1.4, 90-120mm macro

### Anti-cliché (ANTI_CLICHE_SUFFIX)

> "Strictly NO palm trees, NO laptops on beaches, NO digital nomad cliches, NO infinity pools, NO neon lights. NO Balinese temples, religious offerings, or traditional dancers. NO AI-art fingerprints: no hyperrealistic faces, no glowing edges, no fantasy elements."

Plus: no handshakes, no generic passports.

### Logo

- `apps/mouth/public/assets/logo/logo_zan.png` — primary
- `apps/mouth/public/assets/logo/zantara-lotus.png` — Zantara AI persona
- `apps/mouth/public/assets/logo/balizeromap.svg` — map variant
- Brand glyph: Om-circle "ॐ" inside the "O" of "ZERO"
- Tagline: **"Your 3ali, from ZerΩ"**

---

## 2. Editorial Voice

### Tone registers (7 valid)

Italian slug, English content. Source: `wr2_draft_generator.py:47-54, 140-148`

| Slug         | Definition                                              | Default use                     |
| ------------ | ------------------------------------------------------- | ------------------------------- |
| `rituale`    | Symbolic events, cultural anniversaries, turning points | Cultural regulation cycles      |
| `analitico`  | Data, numbers, systems                                  | Tax, visa, regulation (default) |
| `ironico`    | Obvious contradictions, bureaucratic absurdity          | When rules are self-defeating   |
| `militante`  | Injustices toward expats / foreign investors            | Enforcement overreach           |
| `pedagogico` | Step-by-step breakdown of complex systems               | How-to compliance               |
| `poetico`    | Stories of people, life transitions                     | Personal visa/life stories      |
| `tecnico`    | Pure procedures, checklists, mechanics                  | KBLI, OSS, notarial steps       |

**FORBIDDEN tones (legacy WR1)**: `cinico`, `istituzionale_severo`.

### Style benchmarks named in code

- "stile Wired magazine"
- "stile Bloomberg photography"
- Audience reading: The Economist (clarity), Bloomberg (show don't tell), Morning Brew + Finimize (5-minute respect)
- Voice positioning: **"L'Insider Intelligente"** — experienced legal advisor having coffee with a client

### 8 storytelling directives (wr2_draft_generator.py:174-258)

1. **Body is a STORY, not a citation.** Open with a hook (person, moment, contradiction, stake). Citations go at the END as `[Source: <law>]`.
2. **Body target ~50-70 words, hard cap 280 characters.** Cut citation before cutting story.
3. **Headline is the HOOK, not the topic title.** "Sham Investor KITAS: The Clock Is Ticking" yes. "Field Inspections Are Legal" no. Magazine cover line, not Wikipedia heading.
4. **Citations: ONE law per slide maximum.** Legal briefs are forbidden.
5. **Each slide answers ONE question or lands ONE punch.** If body contains "and" twice, stack — split or cut.
6. **Forbidden body openings**: "Permenkumham [N]/[year]", "PP No. [N] Tahun [year]", "Article [N]", "Section [N]", any "[Law] requires/authorises/states that..."
7. **"Take" slides (slide 2, slide 11)**: open with a short UPPERCASE editorial-stance kicker (≤3 words — THE UPSHOT / THE VERDICT / THE BOTTOM LINE / WHERE THIS LANDS / THE STAKES / THE SIGNAL / BETWEEN THE LINES / WHAT CHANGES NOW, or coin one in-register), then continue in first-person editorial voice, never third-party legal summary. Pick per carousel; never repeat the previous carousel's choice; NEVER "OUR TAKE"/"OUR READ"/"OUR VIEW" (retired single-example anchors — see evidence-carved.md "## take_label variants" for the full doctrine).
8. **Slide 11 closer**: SHORT, DIRECT, action-oriented. Two sentences max. Ends with Bali Zero CTA.

### Forbidden phrases

`apps/bali-intel-scraper/docs/BALIZERO_STYLE_GUIDE.md:430-450`

"Delve into", "landscape", "tapestry", "paradigm shift", "it's important to note that", "at the end of the day", "game-changer", "revolutionary", "In today's rapidly changing world", "leverage / synergy / ecosystem", generic AI filler.

Also forbidden legalese: "pursuant to" → use "according to"; "shall be required to" → use "must".

### Headline patterns (BALIZERO_STYLE_GUIDE.md:409-425)

- `[Benefit/Risk]: [What] for [Who]` — "Save 40%: New Tax Deductions for Expats with PT PMA"
- `[Number] things to know about [Topic]`
- `[Topic]: What changes [When]`
- `Why [counterintuitive fact]`
- `[Question everyone asks]`
- `[Breaking]: [Immediate impact]`
- Real examples from blog: "Bali Property 2026: Who's Really Buying and What Could Go Wrong", "The Art of Strategic Patience: Navigating Indonesia's KBLI 2025 Transition Without Getting Burned"

### Article body structure ("The Executive Brief")

`BALIZERO_STYLE_GUIDE.md:118-206`

1. **HEADLINE** (benefit/risk driven, max 12 words)
2. **30-SECOND BRIEF** (4 bullets: what, who, when, risk level)
3. **THE FACTS** (pure journalism, 200-300 words, no opinion)
4. **THE BALI ZERO TAKE** ("What they don't tell you...", 150-200 words, first-person "We at Bali Zero")
5. **NEXT STEPS** (segmented by reader profile, actionable)
6. **RESOURCES** (full doc link + consultation CTA)

---

## 3. Topic Universe

### Domain verticals + scoring weights

`apps/bali-intel-scraper/config/quality_gate.yaml:145-153`

| Topic            | Score weight  | Primary keywords                                                      |
| ---------------- | ------------- | --------------------------------------------------------------------- |
| **visa**         | 1.0 (highest) | KITAS, KITAP, VOA, b211, golden visa, second home, digital nomad visa |
| **immigration**  | 1.0           | deportasi, razia, overstay, wna, kanim                                |
| **company**      | 0.90          | PT PMA, NIB, OSS, KBLI, BKPM, perizinan berusaha                      |
| **employment**   | 0.90          | TKA, RPTKA, IMTA, work permit                                         |
| **tax**          | 0.85          | pajak, NPWP, PPh, SPT, Coretax, DJP                                   |
| **property**     | 0.80          | HGB, HakPakai, SHM, PBG, villa, apartment                             |
| **bali_economy** | 0.70          | Ngurah Rai, UMKM Bali, pariwisata                                     |

### Liveness tiers

`apps/bali-intel-scraper/scripts/claude_cli_enricher.py:72-94`

- **breaking** (≥80): specific peraturan + date in last 48h + concrete named event + official figure released
- **developing** (40-79): partial signals
- **evergreen** (<40): routine guides — reference material, NOT news

Quality gate: auto-publish ≥0.70, queue 0.40-0.69, archive <0.40.

### Mood classification (aspiration vs crisis)

`apps/bali-intel-scraper/scripts/bz_image_style.py:65-124`

**Crisis triggers** (cold teal, surveillance light): deportat, arrest, raid, fine, penalt, mandatory, deadline, coretax, wajib, oversupply, crash, bubble. **Crisis wins ties** — brand risk of warm light on bad news.

**Aspiration triggers** (warm amber, golden hour): opportun, invest, growth, launch, paradise, dream, freedom, digital nomad, luxury living, thrive, boom.

### Audience definition

International expats, foreign investors, digital nomads, retirees — primarily English-speaking, from ~50 countries. Age 35-55, entrepreneur/freelancer/active retiree, living in or planning Bali move. Hates bureaucracy. Primary question: **"What does this mean for ME?"**

**NOT for**: Italian-only domestic audience, tourist content, generic lifestyle without regulatory angle.

### Indonesian terms NEVER translated

KITAS, KITAP, VITAS, NPWP, PPh, SPT, PT PMA, NIB, OSS, HGB, SHM, Imigrasi, Kemenkeu, DJP, BKPM, KBLI, PPAT, BPN.

---

## 4. Channels and Tone

| Channel   | Stack                      | Tone                                       |
| --------- | -------------------------- | ------------------------------------------ |
| WhatsApp  | Gemini 3 Flash + RAG       | Empathetic, conversational, client-facing  |
| Telegram  | Opus 4.6 + SOUL.md         | Deep, strategic, owner-facing intelligence |
| Instagram | Fly.io (carousel pipeline) | Editorial, visual, Wired/Bloomberg style   |
| Web Chat  | Fly.io                     | Full RAG context, structured               |

### Email rule (hardcoded)

Always `from=zantara@balizero.com` / display name `Zantara`. Never `notifications@`, `nuzantara@`. Via Brevo `/api/notifications/send-email` + `X-API-Key: zantara-secret-2024`.

### Language protocol

- Client-facing (all channels): **English primary**
- Bahasa Indonesia for Indonesian nationals or in-country regulatory content
- Team internal (`@balizero.com` except `zero@`): **Bahasa Indonesia default**
- **Italian**: personal market slice only, never the default
- Code, commits, docs: **English always**
- Indonesian regulatory terms: **always original (never translated)**
- Never mix Italian and English in the same artifact

---

## 5. Carousel Patterns

### Structure (11-slide non-negotiable)

`scripts/wr2_draft_generator.py:151-258`

- **Slide 1**: Cover — always `is_cover: true`, `is_hero_image: true`
- **Slide 2**: editorial-stance kicker (THE UPSHOT / THE VERDICT / THE BOTTOM LINE / etc. — never "OUR READ"/"OUR TAKE") + first-person take, `is_hero_image: false`
- **Slides 3-10**: story body (8 slides) — typography-only layout, `is_hero_image: false`
- **Slide 11**: CTA closer "What This Means For You" — two sentences max, `is_hero_image: true`
- **Exactly 4 `is_hero_image: true` total**: slides 1, 11 + 2 mid-carousel narrative turning points

### Hero image layout

Full-bleed 4:5 portrait 1080x1350px. No border, no whitespace, no letterboxing. Non-hero slides: clean text-on-color with brand typography, no image background.

### Text constraints

- **Headline**: max 60 characters
- **Body**: max 280 characters (Canva text box hard cap)
- Mid-slides: ONE question per slide, no stacking

### Reference design quality target

5 reference PDFs in `~/Downloads/WR2 Automation standard*.pdf` show:

- Yellow accent on key-data (numbers, laws, dates)
- **Bold key-words** within paragraph body (not whole body bold)
- Photo overlay with dark gradient on hero slides
- Q&A dialogue layouts ("X said / Y replied" two-column)
- Timeline pinboard layouts (calendar collage + bullet list)
- Quote-punch layouts (solid color + centered large quote)
- 5-6 hero per 9-11 slides (NOT just 4 — when narrative demands more visual punch)

### Canva integration

- Master template: `DAHE6lx1lf8` (12 pages — 11 used + 1 buffer)
- Slides rendered via Canva MCP cloud connector (claude.ai Canva)
- Asset storage: Tigris bucket `nuzantara-warroom-images.fly.storage.tigris.dev`
- Carousel folder: `FAHEwkTYduI`

---

## 6. Concrete Brand Assertions (rules for the design agent)

These are non-negotiable. Every produced design MUST satisfy all 15.

1. **Aspect ratio is 4:5 portrait, 1080x1350px, full-bleed.** No border, no whitespace, no letterboxing. Validated by VLM.
2. **Body text per slide hard-caps at 280 characters.** Canva text boxes are fixed. Cut citation before cutting story.
3. **Headline max 60 characters.** Magazine cover line, not Wikipedia heading. Urgency and stakes in every headline.
4. **Exactly 11 slides per carousel.** Slide 1 = cover hero, Slide 11 = CTA hero. Exactly 4 hero images total (or 5-6 when narrative justifies — see reference quality target).
5. **No human faces visible in hero images.** Silhouettes or objects only.
6. **Photo style is 35mm film editorial, not AI art.** Film grain, chiaroscuro, desaturated charcoal-ochre palette for carousel. Teal-amber Villeneuve/Deakins grading for article covers.
7. **Zero Bali tourist clichés.** No palm trees, no infinity pools, no neon, no Balinese temples/offerings/dancers, no laptops on beaches, no handshakes, no passport close-ups.
8. **Crisis content gets cold teal / surveillance aesthetic.** Aspiration content gets warm amber / golden hour. Mood is auto-classified before prompting.
9. **Tone register is always ONE of the 7 valid Italian slugs.** Slug for backend validation; content in English.
10. **Body opens with a person, a stake, a date with consequence, or a question.** Never with a law number, article reference, or "Section N". Law cited at end if needed — ONE law per slide max.
11. **Slide 2 and Slide 11 use first-person editorial voice**, opened by a short UPPERCASE editorial-stance kicker (THE UPSHOT / THE VERDICT / THE BOTTOM LINE / WHERE THIS LANDS / THE STAKES / THE SIGNAL / BETWEEN THE LINES / WHAT CHANGES NOW — pick per carousel, never repeat the previous one; NEVER "OUR TAKE"/"OUR READ"/"OUR VIEW"). Never third-party legal summary on these slides.
12. **Slide 11 CTA is two sentences max** and ends with "Bali Zero — Link in bio for a consultation."
13. **Primary brand gold is `#f59e0b` (gold-500).** Dark base is `#121016` (warm graphite, 3% red-violet undertone). Red `#ff2d4c` signals urgency. Never use generic gray.
14. **Fonts: Inter for display/UI, Cormorant Garamond for long-form editorial.** Brand tagline: Arial Black / Impact at weight 900, 0.06em letter-spacing.
15. **"stile Wired magazine" + "stile Bloomberg photography"** are the two style anchors. Internalize as shorthand for the entire visual grammar.

---

## 7. Source Files (for the agent to read)

- `scripts/wr2_image_generator.py` — BRAND_SUFFIX, ANTI_CLICHE_SUFFIX, GEMINI_PROMPT_PREFIX, VLM validation
- `scripts/wr2_draft_generator.py` — VALID_TONES, BRAND_SUFFIX, SYSTEM_INSTRUCTIONS (full schema + 8 directives), `_build_enriched_brief`
- `apps/bali-intel-scraper/scripts/bz_image_style.py` — 5 visual pillars, mood classifier, camera/lens selector, crisis vs aspiration light specs
- `apps/bali-intel-scraper/docs/BALIZERO_STYLE_GUIDE.md` — brand voice, headline patterns, forbidden phrases, article structure
- `apps/bali-intel-scraper/config/quality_gate.yaml` — topic universe, BZ keywords, scoring weights, source tiers
- `packages/core/tokens/primitives.css` + `themes/dark.css` + `semantic.css` — color palette, typography, spacing, semantic tokens
- `apps/mouth/src/app/globals.css` — brand entrance CSS, gold border accent
- `apps/mouth/public/static/` — Midjourney reference hero images (mood classification examples)
- `~/Downloads/WR2 Automation standard*.pdf` — 5 reference carousels (quality target for design agent)
