# Bali Zero — Price List 2026 Design Spec

**Date:** 2026-05-06
**Author:** Antonello Siano (Zero) + Claude Opus 4.7 (1M ctx)
**Status:** Draft — pending owner review
**Scope:** Single artifact for client + internal use (option C — no internal/external split)
**Source of truth:** new `bali_zero_official_prices_2026.json`

---

## 1. Goal

Replace the legacy 2025 price list (PDF "PRICE LIST 2025 INTERNAL - PRICE SELLING-2.pdf" + JSON `bali_zero_official_prices_2025.json`) with a unified 2026 edition that:

1. Consolidates all Bali Zero priced services in **one** versioned source.
2. Adds the new Tax & Accounting tier provided by the Tax department (monthly tax report packages, basic annual packages, LKPM, annual personal/company tax) and the new Bali Zero Consultant fees (PMA close, NPWPD, BPJS, NPWP personal, EFIN, update data) — none of which exist in the current 2025 sources.
3. Resolves three known conflicts between PDF 2025 and JSON 2025:
   - **Investor KITAP + MERP** → Rp 55.000.000 (no ACC surcharge) ✅ user-confirmed
   - **Dependent KITAP + MERP** → Rp 33.000.000 (no ACC surcharge) ✅ user-confirmed
   - **Akta Perubahan / Revision Company** → unified into ONE row "Akta Perubahan (Revision Company) — Depend (Contact for quote)" ✅ user-confirmed
4. Eliminates structural duplicates: `Annual Tax personal`, `Annual Tax company`, `LKPM yearly` extracted ONCE in their own dedicated section instead of being repeated inside every monthly tier description.
5. Renders into THREE downstream artifacts from the SAME JSON: HTML (web/print), PDF (client-shareable), Markdown (versioned in repo).
6. Receives full senior visual treatment: cinematic cover, hero photography per macro-section, micro-icon set per service, batik ornaments — palette aligned to existing Bali Zero brand book (`docs/superpowers/specs/2026-03-27-balizero-digital-brand-book-design.md`).

---

## 2. Non-goals

- NOT redesigning the brand book or globals.css palette.
- NOT shipping a new web app or route — this is a static document deliverable.
- NOT migrating the backend RAG `PricingTool` to consume 2026 JSON in the same PR — that is a follow-up step gated on owner approval (the current `_2025.json` stays authoritative until explicitly swapped). Keeping these decoupled avoids regressing the production Bali Zero chatbot during a content-only change.
- NOT publishing the document to a public URL — distribution channel is decided ad-hoc by Zero after the artifact is shipped.

---

## 3. Source-of-truth architecture

```
                     bali_zero_official_prices_2026.json
                                  │
                                  │ (read-once)
                                  ▼
              scripts/generate_pricelist_2026.py
                                  │
                  ┌───────────────┼────────────────┐
                  ▼               ▼                ▼
           HTML (single)    PDF (Playwright)    Markdown (.md)
        ~/Desktop/...      ~/Desktop/...      docs/pricing/...
```

**Single source of truth principle:** any future price update happens in the JSON only; running the generator regenerates the three outputs deterministically. No artifact is hand-edited.

**Image embedding:** generator inlines all images as base64 in the HTML so the file is self-contained and shareable as a single attachment (no `assets/` folder dependency). PDF inherits embedded images via Playwright headless print. Markdown links to image files in `docs/pricing/assets/2026/` (relative paths, repo-tracked).

---

## 4. JSON schema (`bali_zero_official_prices_2026.json`)

Shape evolves the existing 2025 schema with three additions: top-level `version`, `effective_date`, and a new `tax_accounting` category that supports tier ranges + bundled-vs-standalone fees.

```json
{
  "version": "2026.1",
  "effective_date": "2026-01-01",
  "metadata": {
    "currency": "IDR",
    "contact": {
      "email": "zero@balizero.com",
      "whatsapp": "+62 821 3107 363",
      "location": "Kerobokan, Bali, Indonesia",
      "website": "balizero.com"
    },
    "last_updated": "2026-05-06"
  },
  "services": {
    "single_entry_visas": {
      /* 6 entries — unchanged from 2025 */
    },
    "visa_extensions": {
      /* 1 entry */
    },
    "multiple_entry_visas": {
      /* 5 entries (D1×3, D12×2) */
    },
    "kitas_permits": {
      /* ~25 entries */
    },
    "kitap_permits": {
      /* 5 entries — Investor=55M, Dependent=33M */
    },
    "tax_accounting": {
      "monthly_tax_basic": {
        /* 4 tiers, range price (low–high) */
      },
      "monthly_tax_bundled": {
        /* 4 tiers, includes LKPM + Annual */
      },
      "annual_basic_packages": {
        /* A, B, C, D + Zero Company */
      },
      "annual_standalone": {
        /* LKPM, Annual Tax Co., Annual Tax Personal, Personal additional */
      }
    },
    "company_services": {
      /* 3 entries — Akta unified */
    },
    "consultant_services": {
      /* PMA close, NPWPD, BPJS×2, NPWP personal, EFIN, update data */
    },
    "other_process": {
      /* ~21 entries */
    },
    "urgent_processing": {
      /* 1/2/3 hari */
    }
  }
}
```

Each leaf entry follows this shape (unchanged from 2025 except for new optional `description_en` and `tier_range` fields):

```json
{
  "name": "Working KITAS (Altus / Onshore)",
  "price": "36.000.000 IDR", // single price
  "tier_range": null, // OR ["1.800.000 IDR", "2.000.000 IDR"] for ranges
  "duration": "",
  "validity": "1 year",
  "notes": "",
  "description_en": "Standard work permit KITAS sponsored by Indonesian employer. Onshore process via Altus, suited to candidates already in Indonesia.",
  "icon_id": "kitas-working" // links to micro-icon asset
}
```

**Backward compatibility for backend RAG:** the current `PricingTool` reads `services.<category>.<service_name>.price` and `.text` — both fields preserved (the generator emits a synthetic `text` field on demand to keep the existing tool contract unbroken if/when the RAG swap happens). The 2026 JSON ALSO keeps the `text` Markdown field generated automatically from `name + price + description_en + contact block`.

---

## 5. Document structure (12 sections, ~20 pages PDF)

| #       | Section                              | Servizi                                                                                             | Source                       |
| ------- | ------------------------------------ | --------------------------------------------------------------------------------------------------- | ---------------------------- |
| Cover   | full-bleed dark, logo, title         | —                                                                                                   | new                          |
| ToC     | leader-dot index                     | —                                                                                                   | new                          |
| I.      | Single Entry Visas                   | 6 (C1, C2, C7A&B, C18, C22A&B 60d, C22A&B 180d)                                                     | 2025 JSON                    |
| II.     | Visa Extensions                      | 1 (C1 Tourism Extension)                                                                            | 2025 JSON                    |
| III.    | Multiple Entry Visas                 | 5 (D1×3, D12×2)                                                                                     | 2025 JSON                    |
| IV.     | KITAS Permits                        | ~25 (Working, Investor, Freelance E23, E33G, Spouse, Dependent, Retirement × Offshore/Altus/Extend) | 2025 JSON + PDF              |
| V.      | KITAP + MERP                         | 5 (Investor=55M, Dependent=33M, Retirement, MERP 1Y, MERP 2Y)                                       | 2025 JSON, conflict-resolved |
| VI.     | Tax & Accounting ⭐ NEW              | 4 sub-blocks                                                                                        | Tax dpt input 2026-05-06     |
| VII.    | Company Services                     | 3 (PT PMA, Virtual Office, Akta Perubahan)                                                          | 2025 JSON, dedup applied     |
| VIII.   | Bali Zero Consultant Services ⭐ NEW | 7 (PMA close, NPWPD, BPJS×2, NPWP personal, Update data, EFIN)                                      | Tax dpt input 2026-05-06     |
| IX.     | Other Process                        | ~21 (passports, SKTT, SKCK, EPO/ERP, mutations, cancels, born report, domicilie)                    | 2025 JSON + PDF              |
| X.      | Urgent Processing Tier               | 3 (1/2/3 hari)                                                                                      | 2025 JSON + PDF              |
| Closing | Contacts + WhatsApp QR               | —                                                                                                   | new                          |

**Tax & Accounting sub-blocks:**

- **VI.1 Monthly Tax Report — without LKPM & Annual** — 4 tiers by transaction count (0-50, 50-100, 100-200, 200+). Tier ranges: 1.8-2M / 2.5-3M / 3.5-4.5M / 5M.
- **VI.2 Monthly Tax Report — including LKPM + Annual** — 4 tiers (2.5M / 3.5M / 4.5M / 6.5M).
- **VI.3 Annual Basic Packages** — A (≤100tx, 6M, Income Tax only), B (100-200tx, 9M, Income Tax only), C (≤100tx, 12M, Income Tax + PPH 21 OR PPH Sewa), D (100-200tx, 15M, Income Tax + PPH 21 OR PPH Sewa). Plus "Annual Company ZERO (no transactions)" 3M.
- **VI.4 Annual & Compliance Stand-alone Fees** — extracted ONCE: LKPM yearly (4M), Annual Tax Company (4M), Annual Tax Personal (1M), Personal additional per extra person (1.5M).

Total unique services after dedup: **~80**.

---

## 6. Visual / Aesthetic system

### 6.1 Palette (verified from `apps/mouth/src/app/globals.css`)

| Role          | Token                               | Hex                                        | Usage                                                  |
| ------------- | ----------------------------------- | ------------------------------------------ | ------------------------------------------------------ |
| Body paper    | (new) `#fbfaf6`                     | warm cream, NOT pure white — body sections |
| Deep navy     | `--bz-base`                         | `#1d273b`                                  | cover, section dividers, footer, dark spotlight        |
| Elevated navy | `--bz-elevated`                     | `#243047`                                  | secondary dark surfaces                                |
| Copper accent | `--bz-accent` (alias `--bz-copper`) | `#d4845a`                                  | prices, CTAs, border-left service rows, roman numerals |
| Warm gold     | `--bz-accent-warm`                  | `#c9a96e`                                  | hairlines, batik patterns, kintsugi separators         |
| Cool blue     | `--bz-accent-cool`                  | `#5e7fb5`                                  | trust signals, secondary chips                         |
| Text primary  | `--bz-text-1`                       | `#edeae4`                                  | text on dark surfaces                                  |
| Text dark     | (new) `#1d273b`                     | navy on cream — body text                  |
| Text muted    | `--bz-text-2`                       | `#8c8884`                                  | descriptions, captions                                 |
| Text subtle   | `--bz-text-3`                       | `#575350`                                  | meta, page numbers                                     |

**Rationale:** the document uses a "light document + dark spotlight" registry — body sections are paper-warm cream for legibility and editorial calm; cover, section dividers and footer are deep navy to create rhythmic visual cadence. Pattern follows luxury hospitality brands (Aman, Como, Capella) — Bali Zero's natural positioning as boutique consultancy.

### 6.2 Typography

| Use                          | Font                   | Weight    | Source                                                     |
| ---------------------------- | ---------------------- | --------- | ---------------------------------------------------------- |
| Display (cover, H1 sections) | **Cormorant Garamond** | 600       | Google Fonts                                               |
| Headers (H2/H3)              | **League Spartan**     | 500       | Google Fonts (brand-consistent — already in `globals.css`) |
| Body                         | **Inter**              | 400 / 500 | Google Fonts                                               |
| Numerics / Prices            | **Inter** Tabular Nums | 600       | `font-variant-numeric: tabular-nums`                       |

All free, OAuth-free, embeddable offline (we inline `@font-face` woff2 base64 in HTML for full portability).

### 6.3 Layout system

- **Page format:** A4 portrait (794×1123 px @ 96dpi).
- **Margins:** 60px LR, 80px TB.
- **Density:** ~6 services per A4 page (no claustrophobia).
- **Section divider pattern:** full-bleed dark rectangle 180px tall — Roman numeral copper top-left, section name in Cormorant 48px cream center-left, intro caption Inter 14px muted, hero image 40% width right-aligned.
- **Service row pattern:** `border-left 3px copper`, padding 18px, name (Inter 600 16px navy) + price right-aligned (Inter tabular-nums 600 18px copper), description below (Inter italic 13px muted).
- **Spacing between rows:** 28px.

### 6.4 Image strategy — three layers, all generated via `codex exec` + Image 2 (gpt-image-1)

**Pipeline:** for each asset I shell out to `codex exec` (Codex CLI 0.128.0 confirmed installed) with a brief, capture the generated PNG path, store under `~/Desktop/Bali_Zero_Price_List_2026_assets/`, then base64-embed in the HTML. Codex CLI runs on ChatGPT Plus (zero per-image cost, OAuth-free per the no-paid-API-key rule).

**Layer 1 — Ornaments (SVG inline, no AI):**

- Batik glyph patterns (small SVG repeated as background-image @ low opacity)
- Copper hairline separators
- Roman numerals styling
- Decorative corner ornaments
- Cost: 0 generation — SVG written inline by the generator script.

**Layer 2 — Hero photography (6 images, 1920×1080 PNG):**

| #   | Section               | Hero brief (passed to Image 2)                                                                                                                                                                                                                                                                                                             |
| --- | --------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 1   | I-III. Visas          | "Cinematic still-life: open passport with embossed Indonesian visa stamp resting on travertine marble surface, soft dawn light from upper left, brass key in soft focus background, palette of warm copper and deep navy shadows, shallow depth of field, slow shutter feel, slow-magazine photography aesthetic, no text, no logos, 16:9" |
| 2   | IV-V. KITAS / KITAP   | "Cinematic editorial: tilt-shift Jakarta skyline at golden hour bokeh in background, foreground crisp printed Letter of Approval document with embossed seal partly visible, no readable text, navy + copper palette, slow shutter feel, no text, no logos, 16:9"                                                                          |
| 3   | VI. Tax & Accounting  | "Macro detail: vintage fountain pen poised over a blank ledger page, Indonesian rupiah banknotes blurred at edge, low-key chiaroscuro lighting, deep navy background, copper highlights on metal pen body, editorial slow-magazine quality, no text, no logos, 16:9"                                                                       |
| 4   | VII. Company Services | "Cinematic still-life: notarial seal pressed into deep red sealing wax on cream Akta document, hand of notary partly visible holding brass seal, low-key warm lighting, shallow depth of field, no readable text on document, copper + navy palette, no logos, 16:9"                                                                       |
| 5   | IX. Other Process     | "Top-down flat-lay: composed minimal arrangement of identity documents, immigration stamps, brass paperclips on cream linen surface, soft diffused window light, no readable text, no logos, palette copper navy gold, 16:9"                                                                                                               |
| 6   | X. Urgent Processing  | "Cinematic still-life: crystal hourglass with copper sand mid-flow, deep navy background, single beam of light from upper right, dramatic shadow, slow magazine quality, no text, no logos, 16:9"                                                                                                                                          |

**Layer 3 — Micro-icons (~25 line-art icons, 512×512 transparent PNG):**

Stylistic constraint passed to Image 2 batch:

> "Single line-art icon, 2px stroke weight, copper color #d4845a, transparent background, centered in 1024×1024 frame, minimalist editorial style, no fill, no shadows, single subject only, NO TEXT. Subject: [varies per icon]"

Subjects: passport, visa-stamp, calendar-extension, multiple-arrows, briefcase, palette-art, briefcase-search (D12), graduation-cap, marriage-rings, family, beach-chair (retirement), home-key (KITAP), notary-seal (PMA), virtual-cloud-office, akta-document, ledger (tax), bar-chart (LKPM), exit-arrow (EPO), exit-reentry-arrow (ERP), passport-arrow (mutation), id-card (SKTT), shield-check (SKCK), house-document (domicilie), baby (born report), clock-urgent.

Embedded next to each service title (12×12mm in PDF, accessible-alt in HTML).

### 6.5 Cover layout

```
┌─────────────────────────────────────────────────────┐
│                                                     │
│   [batik glyph SVG @ 8% opacity, full-bleed]        │
│                                                     │
│              [LOGO CIRCLE 200px]                    │
│                                                     │
│               BALI ZERO                             │  ← Cormorant 96px cream
│           ─────────────                             │  ← copper hairline 80px
│                                                     │
│           PRICE LIST 2026                           │  ← League Spartan 28px gold tracking
│                                                     │
│                                                     │
│        Visa · KITAS · Company                       │  ← Inter 14px copper
│        Tax · Accounting · Other                     │
│                                                     │
│  balizero.com  ·  Kerobokan, Bali, Indonesia        │  ← footer Inter 11px muted
│                                                     │
└─────────────────────────────────────────────────────┘
```

### 6.6 Senior touches

- **Page numbers** `02 / 20` editorial style serif bottom-right
- **Running header** from page 2: "Bali Zero · Price List 2026" left + section name right, copper hairline beneath
- **ToC with leader dots** menu-degustazione style
- **Color-coded edge tabs** on right margin per macro-section (printed solid bars visible at book edge)
- **Closing page**: dark brand surface, contacts large, generated **WhatsApp QR code** linking `wa.me/628213107363` (libqrencode SVG, generated inline in script)

---

## 7. Generator script — `scripts/generate_pricelist_2026.py`

**Inputs:**

- `apps/backend-rag/backend/data/bali_zero_official_prices_2026.json`
- `~/Desktop/Bali_Zero_Price_List_2026_assets/heros/*.png` (6 files)
- `~/Desktop/Bali_Zero_Price_List_2026_assets/icons/*.png` (~25 files)
- `~/Desktop/balizero_logo_circle.png` (existing brand asset)

**Outputs:**

- `~/Desktop/Bali_Zero_Price_List_2026.html` — single self-contained file (all images base64-embedded, all fonts inlined)
- `~/Desktop/Bali_Zero_Price_List_2026.pdf` — generated via Playwright headless print of the HTML
- `docs/pricing/Bali_Zero_Price_List_2026.md` + `docs/pricing/assets/2026/` (versioned in repo)

**Dependencies:**

- Python 3.11+ (already in venv)
- `jinja2` (for HTML template)
- `playwright` (for PDF render — already in repo for other carousels)
- `qrcode` (Python lib, MIT, no API)

**No paid APIs.** Image generation is delegated to `codex exec` shell-outs that the script orchestrates one-shot (or by Zero manually, ahead of time, depending on preference — see §9 Build Sequence).

---

## 8. Conflicts resolved (audit)

| #   | Item                                                                                            | Resolution                                                                                                  | Authority                                |
| --- | ----------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- | ---------------------------------------- |
| 1   | Investor KITAP + MERP price (PDF 50M+ACC vs JSON 55M)                                           | **Rp 55.000.000, no ACC**                                                                                   | user 2026-05-06                          |
| 2   | Dependent KITAP + MERP price (PDF 30M+ACC vs JSON 33M)                                          | **Rp 33.000.000, no ACC**                                                                                   | user 2026-05-06                          |
| 3   | Revision Company vs Akta Perubahan (JSON had two entries)                                       | **Unified into one row "Akta Perubahan (Revision Company) — Depend (Contact for quote)"**                   | user 2026-05-06                          |
| 4   | D12 Business Investigation (only in JSON, not PDF)                                              | **Kept** (1Y 7,5M / 2Y 10M)                                                                                 | user 2026-05-06                          |
| 5   | Annual Tax / LKPM / Personal Tax repeated across 4 monthly tiers                                | **Extracted ONCE in section VI.4**                                                                          | structural dedup, user-approved          |
| 6   | Urgent surcharges per service (EPO+300k, ERP+500k, etc.) vs Urgent processing tier (1/2/3 hari) | **Both kept** in separate sections (Other Process inline + dedicated Urgent section X) with clarifying note | structural — they are different concepts |
| 7   | Contacts (JSON had `info@balizero.com` + `+62 813 3805 1876`)                                   | **Updated to `zero@balizero.com` + `+62 821 3110 7363` + Kerobokan**                                        | user 2026-05-06                          |

---

## 9. Build sequence

1. **Author JSON** (`bali_zero_official_prices_2026.json`) — manually compose from 2025 JSON + tax dpt input + conflict resolutions. ~30 min.
2. **Author the generator script** (`scripts/generate_pricelist_2026.py` + `templates/pricelist_2026.html.j2`). ~60 min.
3. **Generate Layer 1 ornaments** (SVG inline in template). 0 min — handled in script.
4. **Generate Layer 2 heros** (`codex exec` × 6 briefs). ~10 min wallclock parallel; ~5 min curation.
5. **Generate Layer 3 icons** (`codex exec` batch × ~25 subjects). ~10 min wallclock; ~5 min curation.
6. **Run generator** → produce HTML + PDF + Markdown. ~2 min.
7. **Visual QA on PDF** — verify typography, page breaks, image embedding, color fidelity. Adjust template, regenerate. ~15 min.
8. **Commit** the JSON, the script, the template, the docs/pricing/ markdown, and the assets to repo. PDF + HTML stay on Desktop (gitignored — they are generated artifacts).
9. **Owner approval** → optional follow-up: switch backend RAG `PricingTool` to read 2026 JSON (separate PR, not in scope here).

**Total estimated wallclock:** ~2 hours.

---

## 10. Testing & verification

- **JSON schema:** `scripts/test_pricelist_2026_schema.py` (~20 LOC) validates the JSON loads, all 80 entries have required fields, no entry has empty `price` AND empty `tier_range`, contact block matches user-confirmed values.
- **Backward-compat smoke:** import `bali_zero_official_prices_2026.json` shape into a copy of `PricingService._load_prices()` to confirm it would still load (read-only test, doesn't mutate prod). Skipped if the read shape is identical to 2025 schema (which it is for non-tax sections).
- **Visual QA:** manual PDF review — page break at section dividers, no orphan service rows, color match to globals.css palette, all 6 heroes + 25 icons render correctly, QR code scans to correct WhatsApp number.
- **Reproducibility:** running `generate_pricelist_2026.py` twice produces byte-identical HTML and Markdown (deterministic). PDF may differ in metadata only.

---

## 11. Distribution & handover

- **Internal Drive:** Zero uploads HTML + PDF to Bali Zero shared Drive (manual step, out of scope for this spec).
- **Client send:** PDF attached via WhatsApp `+62 821 3107 363` or email `zero@balizero.com`.
- **Repo:** Markdown version is the auditable record at `docs/pricing/Bali_Zero_Price_List_2026.md`.
- **Backend RAG migration:** the `PricingTool` continues to read `bali_zero_official_prices_2025.json` until Zero explicitly asks to switch. The 2026 JSON sits next to it ready to be swapped in a future single-line config change.

---

## 12. Risks & mitigations

| Risk                                                                  | Mitigation                                                                                                                                                        |
| --------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Image 2 generations come out generic/cheesy                           | Brief includes explicit "slow-magazine photography aesthetic, no text, no logos, no stock-photo feel" + per-asset curation gate before embedding                  |
| Codex exec quota / availability                                       | If Codex unavailable, fallback is Canva MCP `generate-design` (also free OAuth)                                                                                   |
| Font embedding via `@font-face` base64 inflates HTML beyond 5MB       | Subset Google Fonts to Latin + `Rp 0123456789.,` glyphs only via `pyftsubset` — keeps fonts <80KB total                                                           |
| Playwright PDF prints with wrong page-break behavior on long sections | Use `page-break-inside: avoid` on `.service-row` and `page-break-before: always` on section dividers                                                              |
| Conflict re-emerges if the 2025 JSON is updated post-shipping         | Add a note at the top of `_2025.json` pointing to `_2026.json` as the new authoritative source once owner approves the swap                                       |
| Brand palette drift from `globals.css`                                | Generator references hex values inline (no CSS var dependency); a future `globals.css` repaint requires a manual sync — accepted trade-off for self-contained PDF |

---

## 13. Open items (none blocking)

- WhatsApp number `+62 821 3107 363` was given by user on 2026-05-06; the previous brand book had `+62 813 3805 1876`. **User decision is the final word.** Generator uses the new number. ⚠️ Please double-check this number before render — different formatting interpretations are possible (10 digits after +62 ID code).
- If Zero wants a multi-language version (bahasa Indonesia for team), it is a future follow-up — generator is JSON-driven, easy to add a `description_id` field per service.
