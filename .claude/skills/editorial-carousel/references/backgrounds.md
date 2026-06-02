# Backgrounds & visuals

Each slide has one of four background modes, set via `background.kind` (or none).

## 1. Theme background (default)
Omit `background`. The slide uses the theme color/gradient + a subtle texture grid. Text is centered. Best for context / tip / cta slides.

## 2. Preset gradient — `kind: "preset"`
Built-in dark gradients for when you want depth without a photo. Text stays centered (no scrim).

| name | look |
|------|------|
| `spotlight` | soft top-center light pool on near-black |
| `mesh-blue` | cool blue glow, top-left |
| `mesh-warm` | warm amber glow, top-right |
| `duotone` | teal→black diagonal |

```json
"background": { "kind": "preset", "name": "spotlight" }
```
Add more presets in `assets/styles.css` under `.bg-preset.preset-<name>`.

## 3. Photo — `kind: "photo"`
Full-bleed photo with a dark scrim that darkens the lower text zone (and a touch of the top for the slide number). Text anchors to the bottom; light text. **Prep photos first** with `prep_media.py photo` so the 1080×1350 crop keeps faces near the top.

```json
"background": { "kind": "photo", "src": "raw/cover_crop.jpg" }
```

## 4. Video — `kind: "video"`
Same look as a photo slide, but the background is a moving clip and the slide is exported as **MP4**. See `video_slides.md` for constraints and how the composite works.

```json
"background": { "kind": "video", "src": "raw/water.mp4" }
```

---

## SVG visuals (`visual` field on `tip`)
A line-art object drawn beside the text — free, instant, and recolors to the theme automatically (line work = `currentColor`, highlights = `var(--accent)`).

Available in `assets/visuals/`:

| id | what |
|----|------|
| `glass-water` | tumbler with water, light accent above |
| `sunrise` | sun rising over a horizon with rays |
| `phone-off` | phone with a do-not-disturb moon |

```json
{ "type": "tip", "kicker": "привычка вторая", "title": "Стакан воды\nи свет", "visual": "glass-water" }
```

### Adding a visual
Drop a new `<id>.svg` into `assets/visuals/`. Use `stroke="currentColor"` for outlines and `fill="var(--accent)"` / `stroke="var(--accent)"` for accent details so it adapts to every theme. ViewBox roughly square (~240–320) renders well at 290px wide.
