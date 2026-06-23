# Layout family: photo-fullbleed-split

> Full-bleed photo with the kicker+heading at the TOP and the body at the BOTTOM,
> scrim reinforced at BOTH ends and a clear photo band through the middle — the
> text "travels" across the slide. Body is UPPERCASE. Antonello 2026-06-13.

## Parameters

```yaml
subheading: string   # 2-8 words UPPERCASE yellow kicker (optional)
heading: string      # 4-10 words UPPERCASE  (TOP)
body: string         # 20-80 words UPPERCASE  (BOTTOM)
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
.scrim { position: absolute; inset: 0; background: linear-gradient(180deg, rgba(0,0,0,0.90) 0%, rgba(0,0,0,0.34) 22%, rgba(0,0,0,0.05) 44%, rgba(0,0,0,0.34) 70%, rgba(0,0,0,0.92) 100%); }
.regulation-badge { position: absolute; top: 56px; right: 56px; }
.content-top { position: absolute; left: var(--spacing-edge-margin); right: var(--spacing-edge-margin); top: 120px; color: var(--color-text-white); }
.content-bottom { position: absolute; left: var(--spacing-edge-margin); right: var(--spacing-edge-margin); bottom: 200px; color: var(--color-text-white); }
.subheading { font-weight: var(--font-weight-extrabold); font-size: var(--font-size-subheadline); line-height: var(--line-height-snug); letter-spacing: var(--letter-spacing-title); color: var(--color-accent-yellow); text-transform: uppercase; margin-bottom: 18px; }
.heading { font-weight: var(--font-weight-extrabold); font-size: var(--font-size-headline-slide); line-height: var(--line-height-tight); letter-spacing: var(--letter-spacing-title); color: var(--color-text-white); text-transform: uppercase; text-wrap: balance; text-shadow: 0 2px 18px rgba(0,0,0,0.55); }
.body { font-weight: var(--font-weight-bold); font-size: 38px; line-height: var(--line-height-normal); letter-spacing: var(--letter-spacing-body); color: var(--color-text-white); text-transform: uppercase; text-shadow: 0 1px 12px rgba(0,0,0,0.6); }
</style></head>
<body>
  <div class="hero" data-zone-type="hero-photo"></div>
  <div class="scrim" data-zone-type="overlay"></div>
  {{#if regulation_code}}<div class="regulation-badge" data-zone-type="text">{{regulation_code}}</div>{{/if}}
  <div class="content-top" data-zone-type="text">
    <div class="subheading">{{subheading}}</div>
    <div class="heading">{{heading}}</div>
  </div>
  <div class="content-bottom" data-zone-type="text">
    <div class="body">{{body}}</div>
  </div>
  <div class="logo" data-zone-type="logo">3 ALI ZERO</div>
</body></html>
```

## Common failures
- Heading too long at top → collides with the mid photo band; keep ≤10 words.
- Body over ~80 words → climbs into the photo; 2-4 sentences max.
- Mid band too dark → looks like a flat fill; the 0.05 middle stop keeps the photo visible.
