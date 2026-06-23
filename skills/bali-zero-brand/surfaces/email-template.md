# Surface: email-template (Brevo HTML)

**Status**: spec drafted 2026-05-09 by `email-template-builder` agent. Pending first production email + Antonello sign-off.

## Purpose

Brand-compliant HTML email templates sent via Brevo (`/api/notifications/send-email` endpoint, `X-API-Key: $BREVO_API_KEY`). All emails MUST originate from `zantara@balizero.com` with display name `Zantara` (alias of `zero@balizero.com`) per CLAUDE.md hardcoded rule. Never from `nuzantara@`, `notifications@`.

## Cross-surface rules (inherited mandatory)

Per constitution Article 12.2, every email inherits:

- Article 2 — palette (closed namespace, `color.bg.antracite` etc.)
- Article 3 — single sans-serif family (Montserrat/Inter/Poppins, web-safe fallback for email clients)
- Article 6.3 — numbers concrete
- Article 6.4 — regulatory citations verbatim
- Article 6.5 — bilingual lexicon untranslated (KITAS, PT PMA, KBLI, hak pakai, BATARA)
- Article 6.6 — no CTA hard-sell as primary editorial content
- Article 6.7 — no emoji
- Article 7 — forbidden phrases closed list
- Article 8 — spell-check + acronym verification

## Surface-specific rules

### Format
- **Width**: 600px max content (Outlook safe). Mobile responsive at 480px breakpoint.
- **Aspect**: free-form vertical; no fixed height.
- **DOCTYPE**: HTML 4.01 Transitional (Outlook compat — yes, in 2026, Outlook still requires it).
- **Encoding**: UTF-8.
- **Inline CSS only**: no `<style>` blocks (Gmail strips them); no external stylesheets. All styles inline on tags.
- **Images**: hosted on Bali Zero CDN or absolute Brevo-hosted URL. Alt text mandatory.

### Typography (email-safe variant)
- **Headlines**: Montserrat 700 with web-safe fallback `Arial Black, Helvetica, sans-serif`.
- **Body**: Montserrat 400-500 with fallback `Arial, Helvetica, sans-serif`.
- **Sizes**: H1 28px, H2 22px, H3 18px, body 16px, fine print 13px. NEVER below 13px (accessibility).
- **Line-height**: 1.5 body, 1.2 headlines.
- **Case**: Title Case in headlines (not UPPERCASE — UPPERCASE in email triggers spam filters and reads aggressive in inbox preview).

### Palette (subset — email rendering varies)
- Background: `#FFFFFF` body OR `#2C2F38` antracite for "alert/regulatory" emails. NEVER pure black `#000000` (renders harshly on phone OLED).
- Text on white: `#1A1A1A` (slightly off-black for readability).
- Text on antracite: `#FFFFFF`.
- Accent yellow: `#F4C430` for key data points and CTA buttons (sparingly).
- Status red: `#C8102E` for deadlines and warnings only.

### Layout components (closed set)

1. **Header band** (mandatory): Bali Zero logo `3 ALI ZERO` SVG embedded as inline-SVG OR PNG hosted. 80px height. Background antracite or white per email type.
2. **Hero block** (optional): one image full-width or one large numeric callout. NO stock palms/beaches/sunsets (constitution Article 5.3).
3. **Content block** (mandatory): 1-3 sections. Each with H2 + body 30-80 words.
4. **Regulatory citation block** (when applicable): boxed callout with verbatim citation + source URL.
5. **CTA block** (optional, max 1): single button, 12px padding, antracite bg + white text OR yellow bg + antracite text. Button text ≤4 words, action verb. NEVER "Book now", "DM us", "Limited offer" (forbidden phrases). Acceptable: "Read the regulation", "Schedule your call", "Download the brief".
6. **Footer** (mandatory): from address `zantara@balizero.com`, physical address (Jl. ... Bali, Indonesia), unsubscribe link (Brevo handles), GDPR-compliant disclosure if EU recipient.

### Voice register per email type

- **Regulatory alert** (KEP-71 update, deadline reminder): `analitico` register. Body fact-dense + verbatim citation.
- **Welcome / onboarding** (new client): `pedagogico` register. Concrete next steps, no marketing fluff.
- **Newsletter** (monthly digest): `analitico` + `tecnico` mix. 3-5 items, each with verbatim citation + Bali Zero take.
- **Transactional** (quote ready, document signed): `tecnico` register. Terse, factual.

NO `rituale` (too solemn for email). NO `poetico` (too rare). NO `militante` (sentence-bomb doesn't work in email — needs CTA action).

### Banned email patterns

- Multi-image gallery (carousel). Use Instagram, not email.
- Animated GIF (most clients block).
- Web fonts (only if Google Fonts via `@import` — but inline-only rule above usually wins; use web-safe fallback chain).
- Emoji in subject line OR body (CLAUDE.md hard rule).
- "Hi {{first_name}}" with no fallback. Always have a fallback ("Hi there").
- Subject line >50 chars (truncated in inbox preview on mobile).

### Subject line discipline

- 30-50 characters max.
- Lead with concrete number or regulation if applicable: "KEP-71/PJ/2026: SPT deadline now 31 May".
- Avoid all-caps, exclamation marks, "URGENT". These trigger spam filters.
- Verbatim citation when relevant beats clever wording.

## Files in this surface

- `surfaces/email-template.md` — this spec (you are here).
- `surfaces/email-template/_template-base.html` — base HTML skeleton (TODO, to be authored on first real email).
- `surfaces/email-template/_inline-css.py` — utility to inline `<style>` blocks at render time using `premailer` library (TODO).
- `surfaces/email-template/example-regulatory-alert.html` — example regulatory alert (TODO, to be authored on first real email).

These files are placeholders. The `email-template-builder` agent will create them on first invocation, using this spec.

## Send pipeline

```bash
# After agent generates HTML, send via Brevo:
curl -X POST "https://api.balizero.com/api/notifications/send-email" \
  -H "X-API-Key: $BREVO_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "from": "zantara@balizero.com",
    "from_name": "Zantara",
    "to": "<recipient>",
    "subject": "<subject>",
    "html": "<rendered HTML>"
  }'
```

The agent does NOT send. Antonello or ops sends manually after review.

## QA checklist (mandatory before send)

- [ ] From = zantara@balizero.com (CLAUDE.md hardcoded)
- [ ] No forbidden phrase (Article 7)
- [ ] No emoji (Article 6.7)
- [ ] Regulatory citations verbatim (Article 6.4)
- [ ] Numbers concrete (Article 6.3)
- [ ] Bilingual lexicon untranslated (Article 6.5)
- [ ] Subject ≤50 chars
- [ ] CTA button (if any) with non-banned action verb
- [ ] Inline CSS (no `<style>` blocks)
- [ ] Footer with physical address + unsubscribe
- [ ] Test render in Litmus or Email on Acid (out of scope today; email-template-builder agent will not auto-render — Antonello tests manually first time)
