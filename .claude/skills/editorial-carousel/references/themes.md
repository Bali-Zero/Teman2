# Themes

Themes are CSS-variable presets on `<body data-theme="...">`. Set `spec.theme` to a preset name or a custom object.

## Built-in presets (9)

| name | vibe | bg | text | accent | head font | loud? |
|------|------|----|------|--------|-----------|-------|
| `dark-editorial` | default; moody, premium | `#0d0d0f` | `#f4f4f0` | `#f0b429` amber | Manrope 800 | — |
| `light` | clean, airy, minimal | `#f4f2ec` | `#16151a` | `#c2410c` rust | Manrope 800 | — |
| `warm-film` | beige, magazine, analog | `#ece4d6` | `#2a2218` | `#b4541f` terracotta | Fraunces (serif) | — |
| `bold-gradient` | loud, punchy | purple→pink gradient | `#ffffff` | `#fde047` yellow | Archivo 900 | — |
| `crimson` | deep red, ribbed | `#7a1518` (corduroy) | `#f6ece2` | `#dcab84` tan | Archivo 800 | — |
| `pink-lime` | white + pop colours | `#ffffff` | `#181818` | `#ec4899` pink / `#a3b80f` lime | Manrope 800 | ✅ |
| `blush` | soft pastel pink | `#f7d9e2` | `#1c1418` | `#e35d92` pink | Manrope 800 | — |
| `magenta-noir` | black + acid magenta | `#0a0a0a` | `#ffffff` | `#ff2e93` magenta | Archivo 900 | ✅ |
| `burgundy` | wine + mint, magazine | `#4b1226` | `#f0e7d6` | `#ecc14f` gold / `#a7d8c8` mint | Fraunces (serif) | ✅ |

Media slides (photo/video backgrounds) always use light text on a dark scrim regardless of theme — only the **accent** color follows the theme there.

## Font pairs (`spec.font`)

Independent of the theme — overrides the heading/body font. Set `spec.font` to one of:

| id | heading | body |
|----|---------|------|
| `manrope` | Manrope 800 | Manrope |
| `fraunces` | Fraunces (serif) | Manrope |
| `unbounded` | Unbounded 800 (display) | Manrope |
| `archivo` | Archivo 900 | Manrope |

Omit `spec.font` to keep the theme's own font. The visual configurator (`scripts/configurator.py`) sets this for you.

## "Loud" accent style

Themes marked **loud** (`pink-lime`, `magenta-noir`, `burgundy`) render the **kicker as a filled chip** in `--accent-2` and the **`[[keyword]]` as a highlighted block** in `--accent` — the look from social-media reference carousels. They use `--on-accent` / `--on-accent-2` for the text colour on those blocks, and looser heading `line-height` so blocks don't overlap. To make a new theme loud, add its `data-theme` to the three loud selector groups in `styles.css` and set `--on-accent` / `--on-accent-2`.

## Custom theme (from onboarding)

If the user wants their own colors/fonts, pass an object instead of a string:

```jsonc
"theme": {
  "base": "dark-editorial",                 // preset to inherit layout/feel from
  "fonts": [                                 // optional: extra stylesheet <link>s (e.g. Google Fonts)
    "https://fonts.googleapis.com/css2?family=Unbounded:wght@700;800&display=swap"
  ],
  "vars": {                                  // override any CSS variable
    "--bg": "#0a0e1a",
    "--text": "#eef2ff",
    "--accent": "#22d3ee",
    "--head-font": "'Unbounded', sans-serif",
    "--head-weight": "800"
  }
}
```

### Variables you can override

`--bg` (color or gradient), `--text`, `--muted` (lead/body), `--soft` (num/nick on solid slides),
`--accent`, `--accent-2` (second colour — used by the divider, and by loud chips),
`--on-accent` / `--on-accent-2` (text colour on loud keyword block / chip),
`--head-font`, `--head-weight`, `--body-font`, `--mono-font`,
`--grid` (texture line color; set transparent to disable), `--ghost` (big badge number),
`--divider` (optional; defaults to `--accent-2`, then `--accent`).

### Custom local fonts
To use font files instead of Google Fonts, add an `@font-face` via a stylesheet URL, or extend `assets/styles.css` with the `@font-face` and reference the family in `--head-font`. Keep font files inside the skill's `assets/fonts/` so the skill stays portable.

## Adding a new permanent preset
Add a `body[data-theme="my-name"] { --bg: ...; ... }` block to `assets/styles.css` and document it here. Then `spec.theme: "my-name"` just works.
