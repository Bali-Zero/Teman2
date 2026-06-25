# Surface: Internal Print A4

> **Inheritance**: governed by `constitution.md` Articles 2 (palette), 3 (typography family), 6.3-6.7 (numbers/regulatory/bilingual/no-emoji), 7 (forbidden phrases), 8 (spelling/accuracy). Articles below are deviations or additions specific to the A4 print surface.
>
> Last revision: 2026-05-17 (v1.1 — official logo PNG embedded). Owner: Antonello Siano.

## A0 — Official logo (v1.1, 2026-05-17)

A0.1 **Source of truth**: `assets/balizero_logo_circle.png` (940×940 RGBA, sfondo nero,
"3ALI ZERO" rosso/bianco + Om symbol). Versioni ottimizzate generate:
- `assets/balizero_logo_circle_200.png` (30 KB) — cover use
- `assets/balizero_logo_circle_400.png` (96 KB) — high-DPI fallback
- `assets/balizero_logo_circle_80.png` (8 KB) — header interior pages
- `assets/balizero_logo_circle_200_base64.txt` — base64 string embedded nel `_template.css`

A0.2 **Default behavior**: nuovi documenti `example-brief.html` clonati hanno il PNG embedded
via classe `.bz-logo-image` su `.cover-logo` e `.page-header-logo`. NO div testuale figlio.

A0.3 **Fallback testuale** (legacy o ambienti senza embed): per usarlo, includi
`.cover-logo-text` figlio come da `example-brief.html` versione precedente.

A0.4 **Regenerazione asset**: se il logo cambia, sostituisci `assets/balizero_logo_circle.png`
e rigenera 3 size + base64 con lo script in `_render.py` (target `--rebuild-logo`).

---

## A1 — Format (deviation from carousel Art. 1)

A1.1 **Aspect**: A4 portrait (210 × 297 mm) PDF.
A1.2 **Page count**: 4-12 pages typical. No upper hard cap (a regulatory primer can run 20+).
A1.3 **Resolution**: PDF generated via Playwright headless Chromium, `print_background: True`, `prefer_css_page_size: True`, zero margins (CSS controls everything).
A1.4 **Hero photo**: NOT mandatory on A4 documents. Optional on cover; omit on interior pages.

## A2 — Page architecture

A2.1 **Cover page (always page 1)**: dark mode (`color.bg.antracite` background). Contains:
- Top: thin 1.5px gold rule full-width-with-margin (anchors brand).
- Header row: logo box (22mm square, `color.bg.black` fill, "B" in `color.status.red`, "ALI ZERO" in `color.text.white`) + brand eyebrow (`BALI ZERO · <DOC TYPE>`) + tagline (`Powered by humans, fueled by a thinking engine.`).
- Title block (vertically anchored to bottom-third):
  - Title in `color.text.white` UPPERCASE, ~42pt Montserrat 300 (light weight is the only print exception to constitution Art. 3 — see A3.2).
  - Subtitle in `color.accent.yellow`, ~22pt Montserrat 400.
  - Short gold rule (30mm) + 11pt body description.
  - Optional 1-3 chips with gold border showing key topical tags.
- Footer row: `balizero.com · Kuta / Canggu / Denpasar` SX, document scope tag DX, disclaimer line in `color.text.muted` 7pt.

A2.2 **Interior pages (page ≥ 2)**: light mode (white background, `--bz-text-body: #1F2329` text). Contains:
- Header row: mini logo (12mm square) + breadcrumb (`BALI ZERO` brand bold + document subtitle in `color.accent.yellow`) + page number (`hal. NN`) right-aligned. Gold rule 1.5px below.
- Body content (see A4 typographic system).
- Footer row: `balizero.com · Penggunaan internal` SX + tagline DX, 1px subtle border-top.

A2.3 **Page break discipline**: chapter heading (`<div class="chapter">`) MUST have `page-break-after: avoid` so it never lands at bottom of a page. Tables MUST have `page-break-inside: avoid` for tables under 30 rows; longer tables may break naturally.

## A3 — Typography (deviation from carousel Art. 3)

A3.1 **Single family**: Montserrat (per constitution Art. 3.1) — confirmed for A4 surface. Loaded via Google Fonts CDN at top of CSS.
A3.2 **Weight permissions** (A4-only deviation): Montserrat 300 (light) is permitted for cover-title display sizes (≥36pt) where bold weight at large size feels "shouty" for an internal doc. Body still uses 400/500/600/700 only. The 300 weight is **not** permitted on carousel surface.
A3.3 **Body case**: Mixed Title Case + sentence case allowed in A4 print (deviation from carousel Art. 6.1.1 strict UPPERCASE/Title-Case binary). Reason: 12-page document in all caps is unreadable. Rule: titles UPPERCASE, body sentence-case in italian/bahasa, code in monospace.
A3.4 **Code typography**: inline `<code>` allowed (background `#f3f4f6`, mono fallback `SF Mono / Monaco / Courier New` since IBM Plex Mono is constitution's source-citation font and we don't want overload). Block `.mono` for multiline code samples — left border accent yellow.

## A4 — Component vocabulary

A4.1 **Eyebrow**: 8.5pt UPPERCASE, `color.accent.yellow`, letter-spacing 0.15em, font-weight 700.
A4.2 **Section title (H1)**: 22pt Montserrat 400, `--bz-text-body`, line-height 1.15, letter-spacing -0.01em.
A4.3 **Lead paragraph**: 10.5pt, `--bz-text-secondary` (#4B5563), max-width 165mm.
A4.4 **Chapter heading**: 38pt gold digit (light Montserrat 300) + chapter title at 18pt with thin gold rule below. Margin top 10mm. Reserved for major narrative breaks (max 6-8 per document).
A4.5 **H3**: 11pt bold, page-break-after avoid.
A4.6 **Callout cards** (the canonical A4 device):
- `.callout` (info): 3px left border `color.accent.yellow`, fill `#FFFAEB` (yellow @ 8% on white), 4mm padding.
- `.callout.warning`: 3px left border `color.status.red`, fill `#FDF1F3` (red @ 6% on white).
- Title in matching accent UPPERCASE 8.5pt letter-spacing 0.1em.
- Body 9.5pt, line-height 1.5.
A4.7 **Tables**: dark header (`color.bg.antracite` fill, `color.text.white` text) on row 1, alternating zebra rows in body (`#fafbfc` even rows). Border 1px `--bz-border` (#E5E7EB).
A4.8 **Tags / chips**: rounded-pill, dark fill `color.bg.antracite` + white text 7.5pt UPPERCASE 0.05em. Variants `.tag.gold` (gold fill, dark text), `.tag.red` (red fill, white text).

## A5 — Voice & content (inherited + clarified)

A5.1 **Voice register** (from constitution Art. 6.2): A4 print typically uses **pedagogico** (briefing tone) or **analitico** (regulatory primer). Avoid **militante** for A4 (single-line statement-bomb is a carousel device). Avoid **rituale** (cover page tone, doesn't sustain 12 pages).
A5.2 **Length**: no per-slide word cap (A4 has room). But per-section: H3 → max 200 words before next H3 (avoid wall-of-text). Lists max 8 items per group (split into sub-headings if longer).
A5.3 **Bilingual rule** (inherited Art. 6.5): same. Never translate KITAS, KBLI, PT PMA, hak pakai, NPWP, PPJK, konsultan pajak, etc. Acronym UPPERCASE, bahasa lower.
A5.4 **Citation discipline** (inherited Art. 6.4): every regulatory claim MUST cite the verbatim regulation (Permenkumham 22/2023, UU 63/2024, etc.). For A4 internal briefs the source can be inline (instead of slide-bottom mono footer).
A5.5 **Emoji** (inherited Art. 6.7): no emoji in title or body. Typographic glyphs (☐ ☒ ✓ ⚠ → · —) are permitted for checklists/status — these are not emoji.

## A6 — File structure (canonical template)

A6.1 **Template files** in `~/.claude/skills/bali-zero-brand/surfaces/internal-print-a4/`:
- `_template.css` — canonical stylesheet, ~250 lines, surface-aware
- `_render.py` — Playwright headless Chromium → PDF, A4 zero-margin
- `example-brief.html` — skeleton with cover + 2 interior pages, ready to clone

A6.2 **How to use** (zero-drift workflow):
1. Copy `example-brief.html` to your working dir, rename to `<DocName>.html`.
2. Edit cover title/subtitle/description + interior chapters in place.
3. Reference `_template.css` (do NOT copy; symlink or relative path).
4. Run `python3 ~/.claude/skills/bali-zero-brand/surfaces/internal-print-a4/_render.py --html <DocName>.html --pdf ~/Desktop/<DocName>.pdf`.

A6.3 **Drift prevention**: any agent producing a new A4 brief MUST reference the canonical CSS, not re-write tokens inline. Hex codes belong to `tokens.json` only.

## A7 — Hard fail conditions (specific to A4 surface)

A7.1 Use of any color outside `tokens.json` for text/UI zones (photos exempt as in carousel Art. 2.3) → **hard fail**.
A7.2 Cover page background not `color.bg.antracite` → **hard fail**.
A7.3 Logo glyph using serif/script font → **hard fail** (constitution Art. 3.2).
A7.4 Forbidden phrases from `voice/forbidden-phrases.md` present → **hard fail**.
A7.5 Logo missing on cover OR header missing on interior pages → **hard fail**.
A7.6 Page numbering inconsistent with logical chapter sequence → **soft fail** (route back to author).

## A8 — Examples (reference past)

> **PII boundary (UU PDP / SYMBIOSIS Law 2):** the original A8 gallery named real
> client files (rendered PDFs). Those artifacts are NOT versioned in this repo —
> they live only on the operator machine. The examples below are described by
> *document type + structure pattern* (the reusable lesson), never by client identity.

- **Regulatory primer** (SIMBG-submit class) — 3-page. Reference for cover layout + tables + chip footer.
- **Client-case tax report** — 7-page client case quote, palette Bali Zero.
- **4-funnel strategy brief** — 5-page strategy brief.
- **Operational handover (bahasa)** — 11-page handover document, bahasa indonesiana.
- **Property leasehold legal due-diligence** — 8-section / 17-rendered-page **legal due diligence** ("is this document safe to sign?" review for property/visa/tax/regulatory). Introduces the **circular PNG logo override** pattern (transparent `.cover-logo` + `<img src="logo.png">`) — adopt for all external-facing briefs from 2026-05 onward. The rendered example carried client PII and is intentionally NOT versioned; clone the structure (four-beat executive-summary architecture + `.two-col` comparison pattern), never the content.

These five cover the typical span: regulatory primer (2-3 pages) → client case quote (5-8 pages) → strategy brief (5-12 pages) → legal due diligence (8+ pages). Future briefs should land in this range.
