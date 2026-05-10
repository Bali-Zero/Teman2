# Bali Zero red-team cortex — INSTAGRAM SLIDE scope

Apply ONLY these rules when reviewing a slide spec / slides.json / rendered HTML carousel.

## Constitution articles in scope

- **Article 3.3 — Typography case**: titles UPPERCASE always. Sentence case in title = hard fail.
- **Article 6.1 — Body length**: 25-50 words per slide. Hard fail if outside range. Cover slide exempt.
- **Article 6.1.1 — Body case**: Body Title Case OR UPPERCASE — pick ONE per carousel and stick to it. Mixing = soft fail.
- **Article 6.4 — Citations verbatim**: regulation must be quoted exactly.
- **Article 6.5 — Bilingual lexicon untranslated**: KITAS, PT PMA, etc. NOT translated.
- **Article 6.7 — No emoji** in titles or body.
- **Article 8 — Acronym verification**: regulation codes must be verifiable.

## Forbidden phrases (Article 7) — full list applies

Use the closed list in `voice/forbidden-phrases.md`. Includes:

- Marketing clichés ("evolving landscape", "delve into", "ecosystem", etc.)
- Engagement bait patterns (titles ending in "?", "you won't believe", "this one trick")
- Title case violations (sentence case in slide title = hard fail)
- Emoji anywhere in slide content

## Severity for slides

- **CRITICAL**: forbidden phrase in title or body, emoji in slide, regulation hallucinated.
- **HIGH**: title case violation, body length outside 25-50, body case mixing across slides.
- **MEDIUM**: weak hook, weak closing, layout-family inconsistent with content.
- **LOW**: typography spacing issues, minor color drift.

## Bali Zero canonicals (NEVER flag)

- "3 ALI ZERO" logo wordmark
- Untranslated Indonesian terms (Article 6.5 lexicon)
