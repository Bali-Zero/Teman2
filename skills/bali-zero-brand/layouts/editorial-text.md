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
        /* DEAD-AIR FIX 2026-06-30 (measured): the panel was full canvas height
     (1350px) and centred its stack with justify-content:center, but the .logo
     is position:absolute (bottom:70px) — INVISIBLE to the flex layout, so it
     reserved no space. On a short (2-sentence) body the centred stack ended at
     ~y889 while the logo sat fixed at y1200 → a measured 23% dead band between
     them ("logo floats disconnected", "content anchored upper 40-45%"). The
     asymmetric 110/180 padding biased the block a further 35px upward.
     CURE: shrink the panel to canvas-minus-logo-band (250px = 80 logo + 70
     bottom margin + 100 buffer) so the flow ends ABOVE the logo, drop the
     asymmetric vertical padding, and distribute slack with space-evenly so a
     short body fills the upper-three-quarters and the logo closes the frame
     (gap lands in the healthy 12-18% range). A long body has little slack so
     space-evenly degrades to near-centre automatically — both extremes balance.
     Measured (2026-06-30): short body→logo gap 23%→15%, long 16.5%→~11% with
     the 250px band (the 230px band measured 9.8% on a ~90-word long body — near
     the 8% floor; 250px buys headroom for max-length ~110-word bodies). A top
     yellow rule anchors the block editorially (NYT/FT). Per-element
     margin-bottom still drives heading↔body rhythm. */
        height: calc(var(--canvas-height) - 250px);
        background: var(--color-bg-antracite);
        padding: 0 var(--spacing-edge-margin);
        display: flex;
        flex-direction: column;
        justify-content: space-evenly;
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
        font-size: var(--font-size-body-lg);
        line-height: var(--line-height-normal);
        letter-spacing: var(--letter-spacing-body);
        color: var(--color-text-white);
        /* Sentence case (NOT all-caps): an all-caps bold body shared the exact
     typographic register of the all-caps heading (flat hierarchy, vision
     critic 2026-06-13) AND read as a dense grey block. Sentence case gives a
     clear register break from the UPPERCASE heading and is far more legible
     for 2-5 sentences of prose. */
        text-transform: none;
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
