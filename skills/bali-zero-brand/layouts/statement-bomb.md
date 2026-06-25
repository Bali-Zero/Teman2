# Layout family: statement-bomb

> Closing slide. Max 2 visual lines bold centered statement. NO body. NO CTA.

> **Revision 2026-05-08**: relaxed from "single line" to "max 2 visual lines". Reason: examples in past WR2 ("PERMITS ARE PERMISSIONS. THEY CAN BE RESCINDED.") naturally split into 2 lines at 72px on 960px width. Single-line constraint forced ≤7 words ceiling, killing rhythm. Auto font-shrink mechanism added to prevent overflow on borderline cases.

## When to use

- Always closing slide of every WR2 carousel.
- Hard fail at constitution Article 9.5 if closing uses any other family.

## Parameters

```yaml
statement: string  # 3-15 words UPPERCASE, max 2 visual lines after render
emphasis_word: string  # optional, one word in yellow within the statement
auto_shrink: bool  # if rendered text exceeds 2 lines, font-size drops to 56px (default true)
```

## HTML/CSS skeleton

```html
<!doctype html>
<html><head>
<link rel="stylesheet" href="../_base.css">
<style>
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@700;800&display=swap');
body {
  background: var(--color-bg-black);
  display: flex; align-items: center; justify-content: center;
  padding: var(--spacing-edge-margin) var(--spacing-edge-margin) 180px var(--spacing-edge-margin);
}
.statement {
  font-weight: var(--font-weight-extrabold);
  font-size: var(--font-size-statement-bomb);
  line-height: var(--line-height-tight);
  letter-spacing: var(--letter-spacing-title);
  color: var(--color-text-white);
  text-transform: uppercase; text-align: center;
  max-width: 100%;
}
.statement.shrunk {
  font-size: var(--font-size-statement-bomb-shrunk);
}
.emphasis { color: var(--color-accent-yellow); }
</style></head>
<body>
  <div class="statement" data-zone-type="text">{{statement_html_with_emphasis_span}}</div>
  <div class="logo" data-zone-type="logo">3 ALI ZERO</div>
</body></html>
```

## Examples (from past WR2 set)

- "EVERY QUARTER, THE PERIMETER TIGHTENS." (rituale)
- "PERMITS ARE PERMISSIONS. THEY CAN BE RESCINDED." (rituale, 2 sentences = 2 lines visually)
- "INVESTMENT IS NOT IMMIGRATION." (militante)
- "THIS IS NOT ANTI-INVESTMENT. THIS IS ANTI-IMPUNITY." (rituale, 2-line statement)
- "THE NOMINEE IS YOUR LEASE LANDLORD ON PAPER. THEY CAN EVICT." (tecnico → emotional pivot)

## Common failures

- Statement >15 words → exceeds 2-line ceiling at 72px, route back to writer
- Statement renders >2 lines after auto-shrink at 56px → hard fail, ask writer to compress
- CTA hard-sell ("DM us", "book now", "link in bio") → constitution Article 6.6 fail
- Emoji → constitution Article 6.7 fail
- Body added → not statement-bomb anymore, route to different family
- Question mark → engagement-bait pattern, hard fail
- Quotes around statement → looks like attributed quote, dilutes authority

## Render-time fit check (Playwright assertion)

After page render, before screenshot:
```js
const lines = await page.evaluate(() => {
  const el = document.querySelector('.statement');
  return Math.round(el.getBoundingClientRect().height / parseFloat(getComputedStyle(el).lineHeight));
});
if (lines > 2) {
  // shrink font from 72 → 56 → 48; abort if still >2 at 48
  await page.addStyleTag({content: '.statement { font-size: 56px !important; }'});
  // re-check
}
```
