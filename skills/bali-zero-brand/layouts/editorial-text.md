# Layout family: editorial-text

> Text-only prose slide: full antracite canvas (NO hero photo) with headline + yellow sub-headline + body, centered vertically. The text-on-color home for non-hero slides.

## When to use

- Non-hero mid slides (smart-hero decision 2026-06-13): dense lists, stacked
  facts, verbatim citations, explainer prose — copy that reads BETTER as clean
  text-on-color than as text floating over a decorative photo.
- The fallback for any non-hero, non-"take" body slide (composer routes
  `is_hero_image: false` here instead of the photo layout, avoiding the
  empty-hero void-trap).
- Derived from `photo-headline-yellow-sub` minus the hero photo: same type
  hierarchy (white heading, yellow sub, white body) on the full 1350px canvas.

## Parameters

```yaml
subheading: string # 2-8 words UPPERCASE yellow accent (optional kicker)
heading: string # 4-10 words UPPERCASE
body: string # 25-110 words UPPERCASE, 2-5 sentences (more room — no photo)
```

## HTML/CSS skeleton

```html
<!doctype html>
<html>
  <head>
    <link rel="stylesheet" href="../_base.css" />
    <style>
      @import url("https://fonts.googleapis.com/css2?family=Montserrat:wght@700;800&display=swap");
      .text-panel {
        width: var(--canvas-width);
        height: var(--canvas-height);
        background: var(--color-bg-antracite);
        /* Vertically CENTRE the stack so the empty anthracite distributes
     symmetrically above and below (balanced "breathing room") instead of
     piling into one half — top-anchoring left a ~50% bottom void the vision
     critic read as a layout bug, and bottom-anchoring left a top void
     (2026-06-13 E2E, both rejected). A large heading (84px) + sentence-case
     body fills more of the canvas so the residual void is small and centred.
     A top yellow rule anchors the block editorially (NYT/FT). Per-element
     margin-bottom drives vertical rhythm (no flex gap — Golden Visa fix). */
        padding: 110px var(--spacing-edge-margin) 180px
          var(--spacing-edge-margin);
        display: flex;
        flex-direction: column;
        justify-content: center;
      }
      .top-rule {
        width: 90px;
        height: 8px;
        background: var(--color-accent-yellow);
        margin-bottom: 44px;
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
        /* 84px (was 60px): on a text-only slide the headline is the only large
     element — it must dominate and help fill the canvas (2026-06-13). */
        font-size: var(--font-size-headline-cover);
        line-height: var(--line-height-tight);
        letter-spacing: var(--letter-spacing-title);
        color: var(--color-text-white);
        text-transform: uppercase;
        text-wrap: balance;
        margin-bottom: 32px;
        /* gap to body absorbs a 2-3 line heading wrap without bleed. */
      }
      .body {
        font-weight: var(--font-weight-bold);
        /* 40px (was --font-size-body-lg 32px): on a text-only slide a larger body
     fills more of the tall canvas and is more legible for 2-5 sentences of
     prose. With the .baseline-rule below, the residual lower space reads as
     deliberate editorial margin, not a dead-air void (eyeballed on the real
     29-34-word bodies, 2026-06-30 — pure flex center/space-evenly could NOT
     cure a short block in a tall canvas; #1861 reverted). */
        font-size: 40px;
        line-height: 1.5;
        letter-spacing: var(--letter-spacing-body);
        color: var(--color-text-white);
        /* Sentence case (NOT all-caps): an all-caps bold body shared the exact
     typographic register of the all-caps heading (flat hierarchy, vision
     critic 2026-06-13) AND read as a dense grey block. Sentence case gives a
     clear register break from the UPPERCASE heading and is far more legible
     for 2-5 sentences of prose. */
        text-transform: none;
      }
      .baseline-rule {
        /* Footer hairline that BOOKENDS the top yellow .top-rule, framing the lower
     negative space as intentional editorial margin (NYT/FT footer rule) instead
     of a dead-air void. Absolutely positioned just above the logo; never
     collides with the centered text block (verified on the densest real body,
     6 lines @ 40px). 2026-06-30. */
        position: absolute;
        left: var(--spacing-edge-margin);
        right: var(--spacing-edge-margin);
        bottom: 200px;
        height: 2px;
        background: rgba(255, 255, 255, 0.14);
      }
    </style>
  </head>
  <body>
    <div class="text-panel" data-zone-type="text">
      <div class="top-rule"></div>
      <div class="subheading">{{subheading}}</div>
      <div class="heading">{{heading}}</div>
      <div class="body">{{body}}</div>
    </div>
    <div class="baseline-rule"></div>
    <div class="logo" data-zone-type="logo">3 ALI ZERO</div>
  </body>
</html>
```

## Common failures

- Body length over ~110 words → overflows the centered stack toward the logo;
  cut to 2-5 sentences.
- Heading and subheading both white (forgot the yellow accent) → palette fail.
- Adding a hero photo → not editorial-text anymore, route to
  photo-headline-yellow-sub (and set `is_hero_image: true`).
