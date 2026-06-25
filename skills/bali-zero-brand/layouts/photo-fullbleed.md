# Layout family: photo-fullbleed

> Full-bleed background photo + reinforced bottom scrim + kicker/heading/body
> overlaid on the scrim. The "foto a tutta slide" treatment (Antonello
> 2026-06-13): every slide is an edge-to-edge image with the text floating on a
> legible gradient layer, NOT a photo-top/text-panel split. Derived from
> `cover-photo` + a `{{body}}` block + a stronger scrim so body copy stays
> readable mid-image.

## When to use

- Image-rich carousels where EVERY slide should be a full-bleed photo (cover,
  body and CTA alike), with the text overlaid on a scrim for visibility.
- Opt-in per slide via the `layout_family: "photo-fullbleed"` field in
  slides.json (the composer honours an explicit per-slide family override).
- NOT the default for body slides — the default photo body layout is
  `photo-headline-yellow-sub` (photo-top + text-panel). Use this only when the
  brief calls for full-bleed.

## Parameters

```yaml
subheading: string  # 2-8 words UPPERCASE yellow kicker (optional)
heading: string     # 4-10 words UPPERCASE
body: string        # 20-90 words, 2-4 sentences, sits on the dark scrim foot
image_prompt: string
image_url: string   # post-generation Tigris URL
regulation_code: string?  # OPTIONAL red badge top-right
```

## HTML/CSS skeleton (Playwright HTML→PNG render)

> Renderer auto-injects `_base.css` (`:root` token vars). Never inline hex —
> only `var(--token-name)`. Constitution Article 2.

```html
<!doctype html>
<html><head>
<link rel="stylesheet" href="../_base.css">
<style>
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@700;800&display=swap');
/* Full-bleed guard (Golden Visa white-bg fix): if image_url is empty the page
   falls back to brand black instead of white. */
html, body { background: var(--color-bg-black); margin: 0; padding: 0; }
.hero {
  position: absolute; inset: 0;
  background-color: var(--color-bg-black);
  background-image: url('{{image_url}}');
  background-size: cover; background-position: center;
}
/* Reinforced scrim: a soft top wash keeps the kicker legible over busy
   highlights, and a heavy bottom block (≈0.92 black) carries the heading+body.
   Stronger than the cover gradient because body copy sits over the image. */
.scrim {
  position: absolute; inset: 0;
  background: linear-gradient(
    180deg,
    rgba(0,0,0,0.30) 0%,
    rgba(0,0,0,0.10) 32%,
    var(--color-overlay-darken-60) 60%,
    rgba(0,0,0,0.92) 100%);
}
.regulation-badge {
  position: absolute; top: 56px; right: 56px;
}
.content {
  position: absolute;
  left: var(--spacing-edge-margin);
  right: var(--spacing-edge-margin);
  /* anchored above the logo; room for heading (2-3 lines) + body (2-4 lines) */
  bottom: 210px;
  color: var(--color-text-white);
}
.subheading {
  font-weight: var(--font-weight-extrabold);
  font-size: var(--font-size-subheadline);
  line-height: var(--line-height-snug);
  letter-spacing: var(--letter-spacing-title);
  color: var(--color-accent-yellow);
  text-transform: uppercase;
  margin-bottom: 18px;
}
.heading {
  font-weight: var(--font-weight-extrabold);
  font-size: var(--font-size-headline-slide);
  line-height: var(--line-height-tight);
  letter-spacing: var(--letter-spacing-title);
  color: var(--color-text-white);
  text-transform: uppercase;
  text-wrap: balance;
  margin-bottom: 22px;
  /* drop shadow lifts the headline off a bright patch of photo */
  text-shadow: 0 2px 18px rgba(0,0,0,0.55);
}
.body {
  font-weight: var(--font-weight-bold);
  font-size: 38px;
  line-height: var(--line-height-normal);
  letter-spacing: var(--letter-spacing-body);
  color: var(--color-text-white);
  text-transform: uppercase;
  text-shadow: 0 1px 12px rgba(0,0,0,0.6);
}
</style></head>
<body>
  <div class="hero" data-zone-type="hero-photo"></div>
  <div class="scrim" data-zone-type="overlay"></div>
  {{#if regulation_code}}<div class="regulation-badge" data-zone-type="text">{{regulation_code}}</div>{{/if}}
  <div class="content" data-zone-type="text">
    <div class="subheading">{{subheading}}</div>
    <div class="heading">{{heading}}</div>
    <div class="body">{{body}}</div>
  </div>
  <div class="logo" data-zone-type="logo">3 ALI ZERO</div>
</body></html>
```

> `data-zone-type` feeds the region-aware critic (Article 2.3): palette checked
> on `text` + `logo` zones only.

## Common failures

- Body over ~90 words → overflows toward the logo; cut to 2-4 sentences.
- Bright photo with no dark foot → body unreadable; the 0.92-black bottom stop
  of `.scrim` is mandatory, do not soften it.
- Heading/subhead not white/yellow → palette fail (Article 2).
- Missing logo → Article 4 fail.
