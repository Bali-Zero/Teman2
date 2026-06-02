# Carousel spec schema

A carousel is described by one JSON file. `build.py` turns it into HTML, `render.py` exports PNG/MP4.

## Top level

```jsonc
{
  "theme": "dark-editorial",      // preset string (9 presets) OR custom theme object (see themes.md)
  "font": "unbounded",            // optional font-pair override: manrope|fraunces|unbounded|archivo
  "numbering": "counter",         // optional: counter (small NN/TT) | ghost (big transparent #) | none
  "numberScope": "all",           // optional: all (1..N) | skip-cover (2nd slide = 1) | middle (skip cover & last)
  "nick": "@yourname",            // shown bottom-left on every slide (centered on CTA). "" = hide
  "size": [1080, 1350],           // optional, default Instagram portrait
  "slides": [ ... ]               // ordered list of slide objects
}
```

## Slide object

Common optional fields: `kicker`, `background`.

Text fields support two inline conventions:
- `\n` → line break (`<br>`). Use it to control where big headlines wrap.
- `[[word]]` → accent-colored span. e.g. `"5 правил спокойного [[утра]]"`.

### Types

| type | required | optional | notes |
|------|----------|----------|-------|
| `cover` | `title` | `kicker`, `lead`, `background` | slide 1. Big headline. `lead` adds a divider + subtitle. |
| `context` | `title` | `kicker`, `body`, `background` | the "what this post is" slide. |
| `tip` | `title` | `kicker`, `body`, `badge`, `visual`, `background` | numbered point. `badge` = big ghost number ("01"). `visual` = SVG id (see backgrounds.md). |
| `quote` | `title` | `author`, `background` | pull-quote, rendered in « ». |
| `cta` | `title` | `kicker`, `lead` | final call to action, centered. |

`tip` can have **either** a `visual` **or** a photo/video `background` — not both. If both are set, the background wins and the visual is ignored.

### background

```jsonc
"background": { "kind": "photo",  "src": "raw/cover.jpg" }   // crops via CSS cover; PREP photos first
"background": { "kind": "video",  "src": "raw/water.mp4" }   // exported as MP4 (text+scrim over clip)
"background": { "kind": "preset", "name": "spotlight" }      // built-in gradient bg (see backgrounds.md)
// omit background entirely → plain theme background
```

`src` is resolved relative to the spec file. `build.py` copies media into `build/assets/` with safe names (so Cyrillic / spaces in paths never break rendering).

## Minimal example

```json
{
  "theme": "dark-editorial",
  "nick": "@test_account",
  "slides": [
    { "type": "cover",   "kicker": "тестовая карусель", "title": "5 правил спокойного [[утра]]",
      "lead": "Маленькие привычки, из-за которых день перестаёт начинаться с хаоса.",
      "background": { "kind": "photo", "src": "raw/cover.jpg" } },
    { "type": "context", "title": "Утро решает\nвесь день",
      "body": "Первые 30 минут после пробуждения задают темп всему дню. Ниже — 4 привычки." },
    { "type": "tip", "badge": "01", "kicker": "привычка первая", "title": "Не хватай\nтелефон",
      "body": "Дай себе 20 минут без ленты.", "background": { "kind": "photo", "src": "raw/tip.jpg" } },
    { "type": "tip", "kicker": "привычка вторая", "title": "Стакан воды\nи свет",
      "body": "Вода запускает тело, свет — внутренние часы.", "visual": "glass-water" },
    { "type": "cta", "kicker": "это была проба", "title": "Понравился\nформат?",
      "lead": "Сохрани карусель и попробуй одно правило завтра утром." }
  ]
}
```

## Pipeline

```
python scripts/prep_media.py photo raw/cover.jpg raw/cover_crop.jpg   # crop photos (face-safe)
python scripts/build.py  spec.json                                    # -> build/carousel.html + manifest
python scripts/render.py build                                        # -> output/NN_*.png and NN_*.mp4
```
