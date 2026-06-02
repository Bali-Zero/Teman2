---
name: editorial-carousel
description: >
  Build editorial-style Instagram/social carousels (1080x1350 slides) from a
  topic or raw content, rendered to PNG — with optional live VIDEO-background
  slides exported as MP4, SVG visual objects, photo backgrounds with auto
  scrim, and swappable color/font themes. A lightweight HTML + Playwright +
  ffmpeg pipeline driven by one JSON spec. Use this whenever the user wants to
  make, design, or render a carousel, multi-slide post, swipe post, slideshow,
  or "карусель" for Instagram/LinkedIn/Telegram — even if they don't name the
  format — including requests to add photos, video, or themes to slides, or to
  turn an article/idea into slides. Also WRITES the carousel copy itself —
  cover, slide text, CTA and post caption — using proven viral structures
  (how-to, mistakes, insight, before/after, vs, story), so it covers requests
  to write the text/structure/scenario of a carousel even without rendering.
  (This is the JSON-spec pipeline; distinct from the dark-carousel Higgsfield
  skill.)
---

# editorial-carousel

Turn a topic or raw content into a polished carousel. One JSON **spec** describes the slides; scripts build the HTML and render each slide to a 1080×1350 PNG — or an MP4 when the slide has a video background.

**Pipeline:** `onboarding (topic) → structure copy → configure on the real text (theme/font/numbering/media) → prep media → build → render → handover`

Always start with **onboarding** unless the user has already answered those questions. Do not jump straight to rendering.

---

## Step 1 — Onboarding (ask first)

Keep onboarding **minimal** — just enough to write good copy. Ask only:

1. **Откуда берём текст** — спроси прямо: писать **с нуля по теме**, или есть **материал** — готовый текст / статья / **транскрибация видео или подкаста**? Если материал есть — возьми его (вставленный текст, ссылку, расшифровку) и строй по нему, не выдумывая сверх. Если только тема — пишем с нуля. (Это и есть «о чём карусель».)
2. **Audience / goal** *(optional)* — кому и зачем; помогает попасть в тон.
3. **Nickname / handle** *(optional)* — bottom-left on every slide (e.g. `@name`).

Do **NOT** ask slide count, theme, fonts, numbering, or photos/video here. The slide **count falls out of the copy** (Step 2); the **look and media are chosen visually, on the real text,** in the configurator (Step 3). That's the correct order — text first, then design.

---

## Step 2 — Structure the copy

Before any layout, write the actual carousel copy using the viral methodology in `references/copy_structure.md` — the words decide whether anyone swipes.

**Give the user 2 variants.** From the same source, build **two different carousels** — different angle / тип / наполнение (e.g. «инструкция» vs «ошибки», or a different hook) — and let them pick one (or ask to merge). Only after they choose do you go to the configurator. (This is the core habit of the method.)

In short, for each variant:

1. **Pick a type** — Инструкция / Ошибки / Инсайт / До-После / VS / История. The type shapes the whole arc.
2. **Nail the cover** — 1–2 lines that stop the scroll (it carries ~80% of the result).
3. **Skeleton** — one line per slide; check the narrative pulls forward (every slide earns the next swipe).
4. **Write slides** — one idea each, headline + 2–4 sentences, ≤4–5 lines.
5. **Final slide** — a concrete question or CTA, never "ставь лайк".
6. **Caption** — hook + «листай →» (100–400 chars), as a separate layer from the slides.

Keep 5–10 slides (7–8 ideal) and one consistent voice throughout. Map narrative roles → slide types (`cover` / `context` / `tip` / `quote` / `cta`) per the table in `copy_structure.md`. This copy becomes the headlines you present in the next step.

---

## Step 3 — Configure on the real copy (visual picker)

Only after the slides are written. The user chooses the **look and media by eye, on their real text**:

1. Write the approved copy into a draft `spec.json` (slides with real `title`/`kicker`/`body`/`lead`).
2. `python scripts/configurator.py --spec spec.json --out <visible-path>` → writes a **self-contained** `configurator.html` (preview shows **YOUR slides, not a demo**). The generator is pure Python — no playwright/ffmpeg needed for this step. **Put the file where the user can actually find it** (e.g. their Desktop — the skill lives in a hidden `.claude` folder) and **open it in their browser for them** with the OS "open" command. The user never hunts through folders or runs anything. (The slide-count slider is hidden — count is fixed by the copy.)
3. They click: **theme** (9), **font pair** (Manrope / Fraunces+Manrope / Unbounded+Manrope), **numbering** (счётчик `01/06` / большая цифра / нет) + **scope** (с обложки / без обложки / середина), **mode** (только текст / медиа). For media: **default type** (📷/🎬) + **default source** (своё/AI), and a **per-slide override**. On each "own" media slide there's a **«📎 загрузить файл»** picker — the chosen photo previews live in the layout and its filename is recorded; on "ai" slides the picker attaches an optional reference. Video: not on the cover, max 2. They keep uploaded files in **one folder**.
4. They hit **«Скопировать конфиг»** and paste back: `{theme, font, numbering, numberScope, mode, media:[{slide,type,source,aiMode?,file?}]}`.

Apply to the spec: `theme`, `font`, `numbering`, `numberScope`, and a per-slide `background` for each `media` entry — `photo`→`{kind:"photo"}`, `video`→`{kind:"video"}`. For `own`, use the named `file` (ask once for the folder those files live in, map by name). For `ai`, generate in Step 4 (`ai_scenes.md`): `aiMode:"auto"` → Claude proposes the concept **and** style itself (mode D); `aiMode:"ref"` → match the uploaded `file` as a **style reference** (mode E). If they'd rather just say their choices in words, that's fine — the configurator is a convenience, not a gate.

---

## Step 4 — Prep media

Only if the mode uses photos / video / AI:
- **Photos:** `python scripts/prep_media.py photo <raw> <out.jpg> --anchor top` (face-safe 1080×1350 crop).
- **Video:** `python scripts/prep_media.py video raw/in.mp4 raw/clip.mp4 --seconds 10`.
- **AI scenes (D/E):** follow `references/ai_scenes.md` — propose 3 scenes (D) or read style+colour from the ref (E); generate via Higgsfield CLI (**paid — confirm first**) or have the user generate and drop the file in, then crop it like any photo.

When using the user's **own files**, confirm which file → which slide before rendering (e.g. "`beach1.jpg` → обложка, `beach3.jpg` → слайд 3?"). Never assign photos silently.

---

## Step 5 — Build & render

1. **Prep photos** (keeps faces near the top of the 1080×1350 crop):
   `python scripts/prep_media.py photo <raw> <out.jpg> --anchor top`
2. **Write the spec** as `spec.json` next to the media. Schema → `references/spec_schema.md`.
3. **Build:** `python scripts/build.py spec.json` → `build/carousel.html` + `build/render_manifest.json`
4. **Render:** `python scripts/render.py build` → `output/NN_*.png` and `output/NN_*.mp4`
5. **Verify:** read 1–2 key slides (they're 1080×1350, safe to read) and confirm text/scrim/crop look right before declaring done.

Scripts live in `scripts/`, themes/visuals in `assets/`. Run from the skill dir or pass absolute paths.

---

## Step 6 — Handover

Deliver the final `output/` folder: `01_*.png … NN_*.png` plus any `*.mp4`, in slide order, ready to upload. Tell the user the folder path and which slides are video. Keep `build/` and raw files out of the way (they're intermediates).

---

## Hard rules (learned, don't relitigate)

1. **Every slide is 1080×1350.** Mixed photo+video carousels are fine on IG, but all items share this size or IG crops them.
2. **Slide 1 is the hook** — it must read instantly as a thumbnail. Never put a video background on the cover.
3. **Photo / video slides:** light text on a dark scrim, text anchored to the bottom. The scrim is built in; don't hand-darken. Dark text over imagery is unreadable.
4. **Num** (`NN / TT`) top-left in mono; **nick** bottom-left (centered on CTA). Keep the top-right corner clear (IG UI covers it).
5. **Max 2 text colors per slide** (text + accent). The accent follows the theme.
6. **Video:** ≤15s, 2–4 live slides max, calm ambient motion, never the cover. See `references/video_slides.md`.
7. **Big headlines:** use `\n` in the title to control line breaks; keep `line-height ≥ 1.0` (Cyrillic Й/Ё/Щ clip at lower values — the CSS already sets safe values).
8. **Reading PNGs:** never `Read` a raw photo >2000px on a side (it can crash the session). Downscale a preview first (`PIL thumbnail` to ~900px) and view that. Rendered slides (1080×1350) are safe.
9. **Render is per-slide + retried** in `render.py` on purpose — headless Chromium + software-GL crashes intermittently on big composited surfaces. If a slide fails all retries, just rerun `render.py`.
10. **Pick the look visually, not by interrogation.** Offer the configurator (`configurator.py` → open `configurator.html`) for theme/font/photo choices; only fall back to questions if the user prefers words.
11. **AI generation costs money.** Higgsfield modes (D/E) burn credits — always confirm before running a paid generation; the free path is "user generates the image and drops it in."

---

## Map

| need | file |
|------|------|
| step-by-step lesson for a new user (install → finished carousel) | `TUTORIAL.md` |
| copy structure (6 viral types, slide anatomy, caption, checklist) | `references/copy_structure.md` |
| spec JSON format + full example | `references/spec_schema.md` |
| themes (9 presets), font pairs, loud style, custom colors & fonts | `references/themes.md` |
| backgrounds (preset / photo / video) + SVG visuals | `references/backgrounds.md` |
| video slides (constraints, ffmpeg, tuning) | `references/video_slides.md` |
| AI scene backgrounds (modes D/E via Higgsfield or user-generated) | `references/ai_scenes.md` |
| working example | `examples/morning.json` |
| layout + theme CSS | `assets/styles.css` |
| **visual picker** (theme / font / photo mix, live preview) | `scripts/configurator.py` → `configurator.html` |
| spec → html | `scripts/build.py` |
| render PNG + MP4 | `scripts/render.py` |
| crop photos / normalize video | `scripts/prep_media.py` |

## Requirements
Python with `playwright` (chromium installed) and `Pillow`; `ffmpeg` + `ffprobe` on PATH (only for video slides); the `higgsfield` CLI (only for AI modes D/E, paid). All present on this machine.

**Custom fonts (tell the user at install):** to use their own fonts, drop the files into `assets/fonts/`, add an `@font-face` (or a Google Fonts `<link>` via a custom theme's `fonts` list), and reference the family in `--head-font` / `--body-font`. See `references/themes.md`. The 4 built-in families (Manrope, Fraunces, Archivo, Unbounded) + JetBrains Mono cover most needs.
