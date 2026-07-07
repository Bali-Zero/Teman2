# Layout family: cover-photo

> Slide 1 only. Hero photo full-bleed + headline + yellow sub-headline. No body. No brand name in title.

## When to use

- Always slide 1 of every WR2 carousel.
- Hard fail at constitution Article 9.3 if cover slide uses any other family.

## Parameters

```yaml
heading: string  # 4-12 words, UPPERCASE, plain English
subheading: string  # 1-6 words, UPPERCASE, yellow accent, often a tag/category
image_prompt: string  # full editorial image prompt for Codex $imagegen
image_url: string  # post-generation, the Tigris S3 URL
regulation_code: string?  # OPTIONAL, e.g. "KEP-71/PJ/2026" — renders as red badge top-right when present (SOTA pattern #3, added 2026-05-12)
```

**`regulation_code` field**: storyboarder MUST populate this when `brief.primary_regulation_code` is non-empty. The badge appears top-right as a small red rectangle with white mono-font code. Pattern adopted from FT / Kontan / Tempo IG covers. Reference: `_external-bench-2026-05.md` pattern #3.

## HTML/CSS skeleton (Playwright HTML→PNG render)

> Renderer auto-injects `_base.css` (which contains `:root` token vars derived from tokens.json) before this layout's `<style>` block. **Never inline hex codes** — only `var(--token-name)` references. Constitution Article 2 enforcement.

```html
<!doctype html>
<html><head>
<link rel="stylesheet" href="../_base.css">
<style>
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@700;800&display=swap');
/* Cover-photo guard 2026-05-10 (Golden Visa S1 white-bg fix): if image_url
   is empty/missing, the `background-image: url('')` resolves to nothing and
   the page background defaults to white (Article 2 violation). Force the
   document body to antracite/black so the hero zone falls back to brand
   color rather than white. The hero `<div>` then layers on top when image
   is present. */
html, body { background: var(--color-bg-black); margin: 0; padding: 0; }
.hero {
  position: absolute; inset: 0;
  background-color: var(--color-bg-black);
  background-image: url('{{image_url}}');
  background-size: cover; background-position: center;
}
.gradient {
  position: absolute; inset: 0;
  background: linear-gradient(180deg, rgba(0,0,0,0.0) 30%, var(--color-overlay-darken-60) 70%, var(--color-bg-black) 100%);
}
.content {
  position: absolute;
  left: var(--spacing-edge-margin);
  right: var(--spacing-edge-margin);
  /* 270px (was 180px): safe-zone above the enlarged logo — logo top sits at
     70+140=210px from the bottom; the text block must never reach into it
     (critic 2026-06-13: logo read as a third word of the last headline line) */
  bottom: 270px;
  color: var(--color-text-white);
}
.subheading {
  font-weight: var(--font-weight-extrabold);
  /* Cover kicker bumped 36->46px (critic 2026-06-13): the eyebrow/category
     was too faint to register as the context cue. Larger + extrabold so it
     anchors the hook even on a quick read. */
  font-size: 46px;
  line-height: var(--line-height-snug);
  letter-spacing: var(--letter-spacing-title);
  color: var(--color-accent-yellow);
  margin-bottom: 24px;
  text-transform: uppercase;
}
.heading {
  font-weight: var(--font-weight-extrabold);
  font-size: var(--font-size-headline-cover);
  line-height: var(--line-height-tight);
  letter-spacing: var(--letter-spacing-title);
  color: var(--color-text-white);
  text-transform: uppercase;
  /* keep multi-word noun phrases together across line breaks
     (critic 2026-06-13: "FIVE PROPERTY / TRAPS" split read wrong) */
  text-wrap: balance;
}
/* Cover-only: the 80px base logo reads ~6px at IG thumbnail scale —
   no brand signal on scroll (critic 2026-06-13). Enlarged on the cover;
   140px (not 160px) so its top stays below the .content safe-zone. */
.logo {
  width: 140px;
  height: 140px;
}
</style></head>
<body>
  <div class="hero" data-zone-type="hero-photo"></div>
  <div class="gradient" data-zone-type="overlay"></div>
  {{#if regulation_code}}<div class="regulation-badge" data-zone-type="text">{{regulation_code}}</div>{{/if}}
  <div class="content" data-zone-type="text">
    <div class="subheading">{{subheading}}</div>
    <div class="heading">{{heading}}</div>
  </div>
  <div class="logo" data-zone-type="logo">3 ALI ZERO</div>
</body></html>
```

> `data-zone-type` attributes feed the region-aware critic (Article 2.3). Critic measures palette compliance only on `text` and `logo` zones.

## Image prompt template

```
35mm film editorial photograph, chiaroscuro lighting, teal-amber color grading,
shot on ARRI Alexa Mini LF, low saturation outside palette,
{{topic_specific_subject}},
no faces, no palm trees, no beaches, no infinity pools,
no AI-art fingerprints, photoreal, cinematic,
4:5 portrait composition with negative space at bottom for text overlay
```

## Examples (from past WR2 set)

- Topic "Marina developer crackdown" → subject = "abandoned construction site at dusk, scaffolding silhouette, single security light, distant fence line"
- Topic "SPT extension KEP-71" → subject = "stack of paper documents on dark wood desk, single lamp, blurred hand of bureaucrat in background"
- Topic "B211A obsolescence" → subject = "old immigration stamp page in passport, magnifying glass, shallow depth of field"

## Common failures

- Image too bright/saturated → critic rubric 1 fail (palette)
- Subject contains banned cliché → critic rubric 4 fail
- Heading 13+ words → too dense, breaks visual hierarchy
- Subheading not yellow → constitution Article 2 fail (palette token misuse)
- Missing logo → constitution Article 4 fail
