---
name: bali-zero-brand
description: Bali Zero brand cortex — palette tokens, typography, voice registers, taboo phrases, layout families, past-carousel reference. Loaded by wr2-design-architect at start of every carousel run. Progressive disclosure: this entry point is small; deep resources (constitution, tokens, voice examples, layouts) are loaded only when needed.
---

# Bali Zero Brand Cortex

This skill is the brand DNA file the WR2 design agent consumes. It is structured for progressive disclosure: this entry document orients the agent; the deep files are loaded on demand.

## Surfaces (closed taxonomy — see constitution Art. 12)

This skill governs 4 brand surfaces. Load surface-specific spec when working on that surface; cross-surface rules (palette, typography family, voice forbidden-phrases) apply always.

| Surface | Spec | When to load |
|---|---|---|
| **carousel-ig** (1080×1350 IG) | `constitution.md` Articles 1-11 | Every carousel run via wr2-design-architect |
| **internal-print-a4** (PDF brief, A4) | `surfaces/internal-print-a4.md` + `surfaces/internal-print-a4/_template.css` + `_render.py` + `example-brief.html` | Every internal brief, regulatory primer, client case quote, strategy doc |
| **web-mouth** (Next.js frontend) | `apps/mouth/CLAUDE.md` + `packages/core/styles/bz-tokens.css` | Frontend dev (separate stack — not maintained in this skill) |
| **email-template** (Brevo HTML email) | TBD (open backlog — no spec yet) | Future brevo template work |

## Files in this skill

### Always load (cross-surface)
- `constitution.md` — hard brand rules. Articles 2/3/6.3-6.7/7/8 are mandatory across all surfaces.
- `tokens.json` — machine-readable design tokens (palette, type, spacing).
- `voice/forbidden-phrases.md` — closed-set list of phrases to never emit.

### Load when drafting copy (any surface)
- `voice/on-tone-examples.md` — 5+ verbatim examples of Bali Zero voice that worked.
- `voice/off-tone-examples.md` — 3+ examples of voice failures, with diagnosis.

### Carousel surface (load per slide)
- `layouts/cover-photo.md` — load when slide_index == 1 OR layout_family == cover-photo
- `layouts/photo-headline-yellow-sub.md` — on demand
- `layouts/qa-dialogue.md` — on demand
- `layouts/timeline-pinboard.md` — on demand
- `layouts/dark-status-list.md` — on demand
- `layouts/statement-bomb.md` — load when designing closing slide
- `past/` — 64 carousels as JPG sets + metadata.json pairs (imported 2026-05-08); see `past/README.md` for schema

### Internal-print-a4 surface
- `surfaces/internal-print-a4.md` — hard rules (cover/interior layout, typography deviations, callouts, tables)
- `surfaces/internal-print-a4/_template.css` — canonical stylesheet, do NOT inline
- `surfaces/internal-print-a4/_render.py` — Playwright headless Chromium → PDF (A4 zero-margin)
- `surfaces/internal-print-a4/example-brief.html` — skeleton clone target

### Proposed amendments (not yet merged)
- `_proposed-amendments/` — drafts awaiting Antonello git-commit to merge into constitution.

## Brand DNA (one-paragraph summary)

Bali Zero is the Indonesian-business-services agency for expat founders, investors, and high-information immigrants in Bali. The brand voice is investigative-journalistic — authority + calculated alarm, not hospitality. The visual system is editorial dark-mode (antracite + black backgrounds, yellow accent for data, red minimal for status/logo), bold geometric sans-serif uppercase, full-bleed photoreal hero images in 35mm-film cinematic grading. Carousels are 1080×1350 portrait, 7-10 slides, with mandatory cover-photo slide 1, "FACTS (SOURCED) VS OUR TAKE" frame slide 2 in many runs, and statement-bomb single-line closing. The differentiator vs competitors (Lets Move Indonesia, Emerhub, Flado): they sell hospitality and reassurance; Bali Zero tells you what's at stake and cites the regulation verbatim.

## Quick palette (full version in tokens.json)

| Role | Token | Hex |
|---|---|---|
| Background primary | `color.bg.antracite` | `#373D42` |
| Background secondary | `color.bg.black` | `#000000` |
| Body text | `color.text.white` | `#FFFFFF` |
| Accent data | `color.accent.yellow` | `#F4C430` |
| Status critico / logo | `color.status.red` | `#C8102E` |

NEVER green, blue, purple, pastel, beige.

## Quick typography (full version in tokens.json)

- Single family: Montserrat 700/800 (fallback Inter 700/800, Poppins 700/800).
- Titles UPPERCASE always. Body UPPERCASE ≤35w OR Title Case ≤50w (Article 6.1.1 — pick ONE per carousel/document).
- Letter-spacing 0.02em titles, 0em body.
- Numbers/data often emphasized in yellow or bold.

## Quick voice (full in voice/)

Seven tone registers (slug in italian, content in english):
- **rituale** — solemn opening, "every quarter the perimeter tightens"
- **analitico** — fact-dense, regulatory verbatim
- **ironico** — dry calling-out of marketing claims
- **militante** — sentence-bomb single-line "permits are permissions, they can be rescinded"
- **pedagogico** — explainer mode, still uppercase
- **poetico** — rare, used for closing or pivot slide
- **tecnico** — bilingual lexicon-heavy (KITAS, PT PMA, hak pakai)

Body length: 25-50 words/slide (Article 6.1, revised 2026-05-08). Never longer. Numbers concrete always. No emoji.

## How agents use this skill (per-surface)

### wr2-design-architect (carousel-ig surface)
1. Load `constitution.md`, `tokens.json`, `voice/forbidden-phrases.md`.
2. While drafting copy: load `voice/on-tone-examples.md` + `voice/off-tone-examples.md`.
3. Per slide: load matching `layouts/<family>.md`.
4. Style reference: load 3-5 PNGs from `past/` semantically similar to topic.

### Any agent / human authoring an A4 brief (internal-print-a4 surface)
1. Read `surfaces/internal-print-a4.md` (hard rules).
2. Copy `surfaces/internal-print-a4/example-brief.html` to working dir.
3. Reference `_template.css` via relative path (do NOT inline tokens).
4. Edit cover + interior pages in place.
5. Render: `python3 ~/.claude/skills/bali-zero-brand/surfaces/internal-print-a4/_render.py --html <Brief>.html --pdf ~/Desktop/<Brief>.pdf`
6. QA against constitution Articles 2/3/6.3-6.7/7 (forbidden phrases, palette, no-emoji).

## Limitations

- This skill is brand-cortex only. Pipeline orchestration lives in `~/.claude/agents/wr2-design-architect.md`.
- Skill files are markdown + JSON, version-controlled in `~/.claude/skills/bali-zero-brand/` (not yet under git — should be added when stable).
- `past/` directory contains **64 carousels** imported 2026-05-08 from the WR2 Automation standard archive. Folder pattern `unknown__carousel-NN__<md5>/` with 7 JPGs (`01.jpg`..`07.jpg`) plus `metadata.json` carrying fields: `topic_slug, domain, audience_segment, tone_register_primary, layout_family_primary, last_tagged_by, notes_damar`. Damar tags via `/tag` UI on the queue server (`POST /api/tag-past`); tagged carousels are RAG-retrievable by wr2-design-architect Step 1.4 (semantic similarity to current topic). See `past/README.md` for full schema and tagging workflow.
