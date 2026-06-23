# Layout family: qa-dialogue

> Two voices in dialogue. Q&A or claim-rebuttal. Used for tension/contradiction moments.

## When to use

- When narrative requires two opposing positions ("THE DEVELOPER SAID" vs "PARLEMENT REPLIED").
- 1-2 times per carousel max.

## Parameters

```yaml
voice_a_label: string  # e.g. "THE DEVELOPER SAID"
voice_a_quote: string  # 15-50 words UPPERCASE
voice_b_label: string  # e.g. "PARLIAMENT REPLIED" — note correct spelling, NOT "PARLEMENT" (WR2 historical typo)
voice_b_quote: string  # 15-50 words UPPERCASE
voice_a_color: string  # token ref, default "color.text.white"
voice_b_color: string  # token ref, default "color.accent.yellow"
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
  padding: var(--spacing-edge-margin) var(--spacing-edge-margin) 180px var(--spacing-edge-margin);
  display: flex; flex-direction: column; gap: var(--spacing-edge-margin);
  justify-content: center;
}
.voice {
  display: flex; flex-direction: column; gap: 20px;
}
.label {
  font-weight: var(--font-weight-bold);
  font-size: var(--font-size-body-md);
  letter-spacing: 0.04em;
  text-transform: uppercase;
}
.quote {
  font-weight: var(--font-weight-extrabold);
  font-size: 44px;
  line-height: 1.15;
  letter-spacing: var(--letter-spacing-title);
  text-transform: uppercase;
}
.voice-a .label, .voice-a .quote { color: var(--color-text-white); }
.voice-b .label, .voice-b .quote { color: var(--color-accent-yellow); }
.divider {
  height: 1px; background: rgba(255,255,255,0.2); margin: 20px 0;
}
</style></head>
<body>
  <div class="voice voice-a" data-zone-type="text">
    <div class="label">{{voice_a_label}}</div>
    <div class="quote">{{voice_a_quote}}</div>
  </div>
  <div class="divider" data-zone-type="text"></div>
  <div class="voice voice-b" data-zone-type="text">
    <div class="label">{{voice_b_label}}</div>
    <div class="quote">{{voice_b_quote}}</div>
  </div>
  <div class="logo" data-zone-type="logo">3 ALI ZERO</div>
</body></html>
```

## Common failures

- Both quotes same color → fails the dialogue contrast principle
- Quote >50 words → too dense, swiper loses interest
- Labels in sentence case → constitution Article 3.3 fail
- "PARLEMENT" instead of "PARLIAMENT" → spelling fail (Article 8.1)
