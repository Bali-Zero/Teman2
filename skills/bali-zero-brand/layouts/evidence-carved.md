# Layout family: evidence-carved

> Frame slide replacement. Replaces the older `dark-status-list` "FACTS (SOURCED) VS OUR TAKE" pattern. Uses Hammurabi cuneiform stele as background — historical, authoritative, evokes "law carved into stone". Title focus shifts from "FACTS / OUR TAKE" to "THE EVIDENCE" (or domain-specific: THE RECORD / THE CODE / THE LEDGER / WHAT THE LAW SAYS), bullets are pure facts verbatim, single closing line is small Bali Zero comment.

> Added 2026-05-09 after Antonello feedback: previous frame slide titled "FACTS (SOURCED) VS OUR TAKE" gave equal weight to facts and opinion. New design subordinates the comment to the facts.

## When to use

- Slide 2 (frame slide) of any regulatory-explainer, comparison, or testimonial-data archetype.
- Replaces `dark-status-list` for FACTS-VS-TAKE function.
- 1 per carousel max.

## Parameters

```yaml
heading: string
facts: array
take_line: string
take_label: string
```

## HTML/CSS skeleton

```html
<!doctype html>
<html>
  <head>
    <link rel="stylesheet" href="./_base.css" />
    <style>
      @import url("https://fonts.googleapis.com/css2?family=Montserrat:wght@700;800&display=swap");
      .hammurabi {
        position: absolute;
        inset: 0;
        background-image: url("hammurabi-stele.jpg");
        background-size: cover;
        background-position: center;
        filter: brightness(0.55) contrast(1.05);
      }
      .darken {
        position: absolute;
        inset: 0;
        background: linear-gradient(
          180deg,
          rgba(0, 0, 0, 0.45) 0%,
          rgba(0, 0, 0, 0.65) 100%
        );
      }
      .content {
        position: absolute;
        left: var(--spacing-edge-margin);
        right: var(--spacing-edge-margin);
        top: 80px;
        bottom: 180px;
        display: flex;
        flex-direction: column;
        color: var(--color-text-white);
      }
      .heading {
        font-weight: var(--font-weight-extrabold);
        font-size: 64px;
        line-height: var(--line-height-tight);
        letter-spacing: var(--letter-spacing-title);
        color: var(--color-text-white);
        text-transform: uppercase;
        margin-bottom: 24px;
        text-shadow: 0 2px 8px rgba(0, 0, 0, 0.6);
        white-space: pre-line;
      }
      .heading-divider {
        width: 64px;
        height: 4px;
        background: var(--color-accent-yellow);
        margin-bottom: 36px;
      }
      .facts {
        display: flex;
        flex-direction: column;
        gap: 20px;
        flex: 1;
      }
      .fact {
        display: flex;
        align-items: flex-start;
        gap: 16px;
        padding-left: 4px;
      }
      .fact .marker {
        font-weight: var(--font-weight-extrabold);
        font-size: 24px;
        color: var(--color-accent-yellow);
        line-height: 1.2;
        min-width: 36px;
      }
      .fact .text {
        flex: 1;
        min-width: 0;
        font-weight: var(--font-weight-bold);
        font-size: 26px;
        line-height: 1.3;
        letter-spacing: var(--letter-spacing-body);
        color: var(--color-text-white);
        /* text-transform removed 2026-05-22: respect storyboarder body_case_chosen=Title Case
     — uppercase on long body caused critic v1 FAIL (47/42/44 words vs ≤35 cap, S2/S4/S7 pilot
     Permenkumham 22-2024-kitap). Title Case body keeps readability + word count discipline. */
        text-shadow: 0 1px 4px rgba(0, 0, 0, 0.6);
      }
      .take {
        margin-top: 24px;
        padding: 16px 0 0 0;
        border-top: 2px solid rgba(244, 196, 48, 0.4);
      }
      .take-label {
        font-weight: var(--font-weight-bold);
        font-size: 13px;
        letter-spacing: 0.1em;
        color: var(--color-accent-yellow);
        text-transform: uppercase;
        margin-bottom: 8px;
      }
      .take-text {
        font-weight: var(--font-weight-bold);
        font-size: 22px;
        line-height: 1.25;
        letter-spacing: var(--letter-spacing-body);
        color: var(--color-text-white);
        /* text-transform removed 2026-05-22: same fix as .fact .text (word count discipline). */
        text-shadow: 0 1px 4px rgba(0, 0, 0, 0.6);
      }
    </style>
  </head>
  <body data-slide-index="2" data-layout="evidence-carved">
    <div class="hammurabi" data-zone-type="background-texture"></div>
    <div class="darken" data-zone-type="overlay"></div>
    <div class="content" data-zone-type="text">
      <div class="heading">{{heading}}</div>
      <div class="heading-divider"></div>
      <div class="facts">
        {{#each facts}}
        <div class="fact">
          <div class="marker">§{{idx}}</div>
          <div class="text">{{this}}</div>
        </div>
        {{/each}}
      </div>
      <div class="take">
        <div class="take-label">{{take_label}}</div>
        <div class="take-text">{{take_line}}</div>
      </div>
    </div>
    <div class="logo" data-zone-type="logo"></div>
  </body>
</html>
```

## Example data (KEP-71 SPT extension)

```json
{
  "heading": "THE CODE",
  "facts": [
    "KEP-71/PJ/2026 SIGNED 30 APRIL 2026 BY DIRJEN BIMO WIJAYANTO",
    "SPT TAHUNAN PPH BADAN TP2025 → 31 MAY 2026 (FROM 30 APRIL)",
    "SCOPE: PT, PT PMA, CV, UD ONLY — ORANG PRIBADI EXCLUDED",
    "AUTOMATIC. NO APPLICATION. NO LAMPIRAN."
  ],
  "take_label": "OUR TAKE",
  "take_line": "ONE MONTH. ONE CATEGORY. NO APPLICATION."
}
```

## Heading variants by register/domain

- **THE EVIDENCE** — analitico default
- **THE RECORD** — analitico, archival/historical feel
- **THE CODE** — regulatory/judicial feel (most common)
- **THE LEDGER** — tax/financial
- **WHAT THE LAW SAYS** — legal explicit
- **WHAT WE FOUND** — story-driven, investigative

## Common failures

- More than 5 facts → visual fatigue, text-zone overflow
- Fact bullets >12 words each → overlap with cuneiform texture, illegible
- `take_line` >15 words → competes with facts (purpose is OPPOSITE)
- Hammurabi background not darkened enough (filter: brightness < 0.5) → cuneiform shadows make body text unreadable
- Take section too tall → looks like another "fact" instead of subordinate comment
