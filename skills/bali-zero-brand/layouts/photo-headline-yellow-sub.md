# Layout family: photo-headline-yellow-sub

> Hero photo half-bleed (top 50%) + dark text panel (bottom 50%) with headline + yellow sub-headline + body.

## When to use

- Mid-carousel hero slides (slides 3-9 typically).
- When you need both visual and text density on one slide.
- 2-3 times per carousel max (avoid template fatigue).

## Parameters

```yaml
heading: string  # 4-10 words UPPERCASE
subheading: string  # 2-8 words UPPERCASE yellow accent
body: string  # 25-90 words UPPERCASE, 2-4 sentences
image_url: string
image_prompt: string  # if image not yet generated
```

## HTML/CSS skeleton

```html
<!doctype html>
<html><head>
<link rel="stylesheet" href="../_base.css">
<style>
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@700;800&display=swap');
.hero {
  width: var(--canvas-width); height: 540px;
  background-image: url('{{image_url}}');
  background-size: cover; background-position: center;
  position: relative;
}
.hero::after {
  content: ''; position: absolute; inset: 0;
  background: linear-gradient(180deg, rgba(0,0,0,0.0) 60%, var(--color-bg-antracite) 100%);
}
.text-panel {
  width: var(--canvas-width); height: 810px;
  background: var(--color-bg-antracite);
  padding: var(--spacing-edge-margin) var(--spacing-edge-margin) 180px var(--spacing-edge-margin);
  display: flex; flex-direction: column;
  /* center the content block vertically so a short heading+subhead+body
     fills the 810px panel instead of anchoring to the top and leaving a
     ~55% anthracite void at the bottom (vision critic: 'dead zone /
     bottom-heavy', 2026-06-12 — previously only facts slides got this via
     a conditional override; now universal for this body family). */
  justify-content: center;
  /* gap removed 2026-05-10 (Golden Visa overlap bug fix): the prior
     `gap: 24px` plus `body { margin-top: 16px }` produced inconsistent
     spacing when heading wrapped across 2-3 lines, causing the yellow
     subheading and white body to bleed into each other visually
     (Golden Visa S4/S6/S9). Now per-element margin-bottom drives vertical
     rhythm deterministically. */
}
.subheading {
  font-weight: var(--font-weight-bold);
  font-size: var(--font-size-subheadline);
  line-height: var(--line-height-snug);
  letter-spacing: var(--letter-spacing-title);
  color: var(--color-accent-yellow);
  text-transform: uppercase;
  margin-bottom: 16px;
}
.heading {
  font-weight: var(--font-weight-extrabold);
  font-size: var(--font-size-headline-slide);
  line-height: var(--line-height-tight);
  letter-spacing: var(--letter-spacing-title);
  color: var(--color-text-white);
  text-transform: uppercase;
  margin-bottom: 28px;
  /* Anti-overlap belt-and-suspenders: 28px gap to body absorbs heading
     2-3 line wrap without bleed. */
}
.body {
  font-weight: var(--font-weight-bold);
  /* 34px (was --font-size-body-md 28px): the text panel is only 810px (bottom
     half), so a larger body genuinely fills it and the body→logo gap shrinks to
     normal padding instead of a dead-air void. Eyeballed on the real 29-33-word
     hero bodies, 2026-06-30 (longest body, 5 lines, no overflow). No footer rule
     here — the panel is short enough that a bigger body alone closes the void. */
  font-size: 34px;
  line-height: 1.45;
  letter-spacing: var(--letter-spacing-body);
  color: var(--color-text-white);
  text-transform: uppercase;
}
</style></head>
<body>
  <div class="hero" data-zone-type="hero-photo"></div>
  <div class="text-panel" data-zone-type="text">
    <div class="subheading">{{subheading}}</div>
    <div class="heading">{{heading}}</div>
    <div class="body">{{body}}</div>
  </div>
  <div class="logo" data-zone-type="logo">3 ALI ZERO</div>
</body></html>
```

## Common failures

- Body length outside 25-90 words → constitution Article 6.1 fail
- Heading and subheading both white (forgot yellow) → palette fail
- Image too bright at the gradient junction → text becomes illegible at the seam
