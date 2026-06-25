# Layout family: photo-fullbleed-top

> Full-bleed photo + reinforced TOP scrim + kicker/heading/body overlaid at the
> TOP. Sibling of `photo-fullbleed` (bottom). Use when the photo's calm/dark zone
> is in the lower half. Body is UPPERCASE. Antonello 2026-06-13: slides 2+ must
> not all clone the cover — the title sits top OR bottom depending on the photo.

## Parameters

```yaml
subheading: string   # 2-8 words UPPERCASE yellow kicker (optional)
heading: string      # 4-10 words UPPERCASE
body: string         # 20-90 words UPPERCASE, sits under the heading at the top
image_prompt: string
image_url: string
regulation_code: string?
```

## HTML/CSS skeleton (Playwright HTML→PNG render)

```html
<!doctype html>
<html><head>
<link rel="stylesheet" href="../_base.css">
<style>
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@700;800&display=swap');
html, body { background: var(--color-bg-black); margin: 0; padding: 0; }
.hero { position: absolute; inset: 0; background-color: var(--color-bg-black); background-image: url('{{image_url}}'); background-size: cover; background-position: center; }
.scrim { position: absolute; inset: 0; background: linear-gradient(180deg, rgba(0,0,0,0.92) 0%, var(--color-overlay-darken-60) 34%, rgba(0,0,0,0.12) 62%, rgba(0,0,0,0.30) 100%); }
.regulation-badge { position: absolute; top: auto; bottom: 56px; right: 56px; }
.content { position: absolute; left: var(--spacing-edge-margin); right: var(--spacing-edge-margin); top: 120px; color: var(--color-text-white); }
.subheading { font-weight: var(--font-weight-extrabold); font-size: var(--font-size-subheadline); line-height: var(--line-height-snug); letter-spacing: var(--letter-spacing-title); color: var(--color-accent-yellow); text-transform: uppercase; margin-bottom: 18px; }
.heading { font-weight: var(--font-weight-extrabold); font-size: var(--font-size-headline-slide); line-height: var(--line-height-tight); letter-spacing: var(--letter-spacing-title); color: var(--color-text-white); text-transform: uppercase; text-wrap: balance; margin-bottom: 22px; text-shadow: 0 2px 18px rgba(0,0,0,0.55); }
.body { font-weight: var(--font-weight-bold); font-size: 38px; line-height: var(--line-height-normal); letter-spacing: var(--letter-spacing-body); color: var(--color-text-white); text-transform: uppercase; text-shadow: 0 1px 12px rgba(0,0,0,0.6); }
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

## Common failures
- Body over ~80 words → overflows downward into the photo; cut to 2-4 sentences.
- Photo with a bright TOP → the 0.92-black top stop of `.scrim` is mandatory for legibility, do not soften it.
- Heading/subhead not white/yellow → palette fail (Article 2). Missing logo → Article 4 fail.
