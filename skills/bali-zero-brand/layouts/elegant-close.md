# Layout family: elegant-close

> Optional closing slide that FOLLOWS statement-bomb. Provides soft CTA without hard-sell. Format: trust-marker line + reach-line + soft conditional invite. Always last slide of carousel when used.

> Added 2026-05-09. Constitution Article 6.6.1 governs allowed/forbidden patterns.

## When to use

- Slide N (last) of carousels where contact-invite is editorially appropriate (e.g., regulatory dossier, complex case, deadline-sensitive topic).
- ALWAYS preceded by `statement-bomb` (slide N-1). Never replaces statement-bomb — it follows.
- Optional. Many carouseli should END with statement-bomb only (purer editorial).

## Parameters

```yaml
reach_email: string   # Email channel — always "ZANTARA@BALIZERO.COM"
reach_whatsapp: string  # WhatsApp number — "+62 821 3107 363"
                        # Both channels listed (email + WhatsApp), shown as 2 lines.
invite: string        # 8-18 words. Soft conditional invite.
                      # MUST start with "IF" or "WHEN" — never imperative.
                      # e.g. "IF YOUR CASE TOUCHES THIS — A 30-MIN CALL CONFIRMS NEXT STEPS."
primary_source_url: string?  # OPTIONAL (added 2026-05-12, SOTA pattern #25)
                              # When set, renders a 120×120 QR code bottom-right
                              # pointing to the verbatim primary source (DJP / OSS /
                              # JDIH / Permenkumham PDF). NEVER a Bali Zero URL
                              # (Art 6.6 hard-sell ban).
qr_caption: string?    # OPTIONAL — 1-3 words above the QR. Default: "PRIMARY SOURCE"
                       # in Bahasa: "SUMBER ASLI"
```

**`primary_source_url` + `qr_caption`**: when present, the elegant-close slide gains a QR code in the bottom-right corner with a small caption above. The QR encodes ONLY the primary source URL (regulator-issued document or registry — never a Bali Zero own page, per Art 6.6 hard-sell ban). Indonesian audience pattern: screenshot the carousel, screenshot the QR, scan later to verify the source. This closes the credibility loop the source-citation slide opens (slide N-1 + slide N pair). Pattern adopted 2026-05-12 from NYT / AP / Reuters. Reference: `_external-bench-2026-05.md` pattern #25.

The QR PNG itself is generated server-side by the renderer using `qrencode` or `segno` (Python: `pip install segno` → `segno.make(url).save('qr.png', scale=8, dark='#C8102E', light='#FFFFFF')`). The CSS class `.qr-closing` in `_base.css` defines the 120×120 box with red border.

> Trust marker line REMOVED 2026-05-09 (Antonello: "non serve"). Email + WhatsApp now both shown — Article 6.6.1 "ONE channel" rule revised to allow both contact channels since both ARE the same Bali Zero unified front-desk (zantara@balizero.com is alias of zero@balizero.com per CLAUDE.md email rule, and the WhatsApp number is the same Zantara persona).

## HTML/CSS skeleton

```html
<!doctype html>
<html><head>
<link rel="stylesheet" href="./_base.css">
<style>
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@700;800&display=swap');
body {
  background:
    radial-gradient(ellipse 75% 50% at center, rgba(50,45,38,0.4) 0%, rgba(0,0,0,1) 78%),
    var(--color-bg-black);
  display: flex; align-items: center; justify-content: center;
  padding: 100px var(--spacing-edge-margin) 220px var(--spacing-edge-margin);
  position: relative;
  flex-direction: column;
}
body::before {
  content: ''; position: absolute; inset: 0;
  background-image:
    radial-gradient(circle at 30% 30%, rgba(255,255,255,0.018) 1px, transparent 1px),
    radial-gradient(circle at 70% 70%, rgba(255,255,255,0.014) 1px, transparent 1px);
  background-size: 5px 5px, 7px 7px;
  pointer-events: none;
}
.content {
  position: relative; z-index: 2;
  display: flex; flex-direction: column;
  align-items: center; gap: 40px;
  max-width: 880px;
  text-align: center;
}
.divider-top, .divider-bottom {
  width: 48px; height: 2px;
  background: var(--color-accent-yellow);
  opacity: 0.6;
}
.trust-marker {
  font-weight: var(--font-weight-bold);
  font-size: 14px;
  letter-spacing: 0.18em;
  color: var(--color-accent-yellow);
  text-transform: uppercase;
  line-height: 1.5;
}
.reach {
  font-weight: var(--font-weight-extrabold);
  font-size: 36px;
  letter-spacing: 0.04em;
  color: var(--color-text-white);
  text-transform: uppercase;
  text-shadow: 0 2px 12px rgba(0,0,0,0.5);
  font-family: 'IBM Plex Mono', 'Montserrat', monospace;
  margin: 8px 0;
}
.invite {
  font-weight: var(--font-weight-bold);
  font-size: 22px;
  line-height: 1.45;
  letter-spacing: var(--letter-spacing-body);
  color: rgba(255,255,255,0.82);
  text-transform: uppercase;
  max-width: 720px;
  margin-top: 16px;
}
.logo {
  width: 110px !important;
  height: 110px !important;
}
</style></head>
<body data-slide-index="{{index}}" data-layout="elegant-close">
  <div class="content" data-zone-type="text">
    <div class="divider-top"></div>
    <div class="trust-marker">{{trust_marker}}</div>
    <div class="reach">{{reach}}</div>
    <div class="invite">{{invite}}</div>
    <div class="divider-bottom"></div>
  </div>
  {{#if primary_source_url}}
  <div class="qr-closing__caption" data-zone-type="text">{{qr_caption | default: "PRIMARY SOURCE"}}</div>
  <div class="qr-closing" data-zone-type="text" style="--qr-image-url: url('qr.png');"></div>
  {{/if}}
  <div class="logo" data-zone-type="logo"></div>
</body></html>
```

## Example data — KEP-71 SPT extension

```json
{
  "trust_marker": "LICENSED KONSULTAN PAJAK · REGISTERED PPJK · 5,000+ FILINGS",
  "reach": "ZANTARA@BALIZERO.COM",
  "invite": "IF YOUR SPT TAHUNAN PPH BADAN TOUCHES THIS — ONE CALL CONFIRMS NEXT STEPS."
}
```

## Example data — visa carousel

```json
{
  "trust_marker": "VISA SPECIALISTS · 47 KITAS FILED THIS MONTH · BALI ZERO 2003",
  "reach": "WHATSAPP +62 821 3107 363",
  "invite": "WHEN YOUR CASE FEELS LIKE A FOG — WE'VE WALKED THIS PATH 5,000 TIMES."
}
```

## Common failures

- Imperative verb in invite ("CALL NOW", "BOOK", "CONTACT") → hard fail Article 6.6.1
- More than one channel in `reach` (email AND WhatsApp listed) → hard fail (pick ONE)
- Trust marker contains marketing claims ("BEST", "FASTEST", "AWARD-WINNING") → soft fail
- Invite >18 words → loses elegance, sounds like ad copy
- Missing leading "IF" or "WHEN" in invite → soft fail (imperative tone creeping in)
- Urgency language anywhere ("TODAY", "DON'T MISS", "ENDING SOON") → hard fail Article 6.6.1
- `reach` written as link/URL form (`https://...`) → use plain text only

## Render-time guards

The composer should check:
- Word count invite ≤18
- `reach` matches one of: `^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$` (email) OR `^WHATSAPP \+\d+ \d+ \d+ \d+$` (WhatsApp)
- Invite starts with `^(IF|WHEN) ` (case-insensitive)

## Editorial principle

The invite is the most important line. Its tone determines whether the slide reads as "consultant offering walk-through" (good) or "salesperson pushing for contact" (bad). The pattern that works: **IF/WHEN [reader's situation] → [Bali Zero's experiential authority]**.

Examples that work:
- "IF YOUR CASE TOUCHES THIS — A 30-MIN CALL CONFIRMS NEXT STEPS."
- "WHEN COMPLIANCE FEELS LOUD — WE READ THE QUIET PARTS."
- "IF THIS DEADLINE IS YOURS — ONE CALL WALKS THE TIMELINE."
- "WHEN A CASE FEELS LIKE A FOG — WE'VE WALKED IT 5,000 TIMES."

Examples that fail:
- "CALL US TODAY!" (imperative, urgency)
- "BOOK YOUR FREE CONSULTATION" (sales language)
- "DON'T MISS THE 31 MAY DEADLINE" (urgency)
- "WE'RE THE BEST IN BALI" (benefit claim)

## Use restraint

Not every carousel needs an `elegant-close`. Pure editorial pieces (cultural-insight, anti-cliche provocations) are STRONGER without contact invitation — the brand authority IS the closing. Use elegant-close only when:
- Topic is operational (deadline, filing, procedure, compliance)
- Reader could plausibly need help right now
- The statement-bomb closing alone leaves them suspended ("ok but what do I do?")

If statement-bomb gives complete closure, no elegant-close needed.
