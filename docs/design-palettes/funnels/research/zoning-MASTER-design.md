# Bali Zoning Map — MASTER Design Synthesis

> Sources: DeepSeek Reasoner (275 lines) · Claude Code product analysis · Web research (8 topics)
> Gemini brainstorm: pending (will be appended when available)
> Date: 2026-04-12

---

## TL;DR — The 8 Design Decisions

| # | Decision | Consensus | Confidence |
|---|----------|-----------|------------|
| 1 | **Map type** | Static reveal with semantic drill-down | 3/3 agree |
| 2 | **Tone** | Forensic/clinical, not fearful | 3/3 agree |
| 3 | **Risk display** | Always show both OK zones AND risks | 3/3 agree |
| 4 | **Jargon handling** | Badge + plain English + tooltip | 3/3 agree |
| 5 | **Layout ratio** | 60/40 map/panel desktop, stacked mobile | 3/3 agree |
| 6 | **Lead capture** | AFTER zone reveal, never gated | 3/3 agree |
| 7 | **Case study position** | Evidence of capability, not fear anchor | 2/3 agree |
| 8 | **Panel style** | Glass card, slide-in, scrollable | 3/3 agree |

---

## 1. Investigation Tool UX — What "Serious" Looks Like

### Consensus from all sources:

The tool must feel like a **forensic report viewer**, not a marketing funnel. Design cues:

- **Structured cards** with traffic-light indicators (Thomson Reuters Clear pattern)
- **Progressive disclosure**: click for more detail, never overwhelm on first view
- **Cited sources**: every claim links to a regulation or data point
- **Monospace for data**: zone codes, regulation numbers, dates
- **Sans-serif for narrative**: explanations, implications, actions

### Tools that define the space:
1. **Landgrid** (landgrid.com) — parcel visualization, 3-click progressive disclosure
2. **Palantir Foundry** — ontology-driven, dark mode, relationship mapping
3. **GISTARU** (gistaru.atrbpn.go.id) — Indonesia's official zoning viewer (our source of truth)
4. **Chainalysis Reactor** — confidence scoring, trail-following UX
5. **Thomson Reuters Clear** — structured report cards for investigation

### What to steal:
- Landgrid's "I believe this because..." citation pattern
- GISTARU's zone color vocabulary (pink/yellow/green/dark-green/orange)
- Chainalysis's confidence indicators (high/medium/low)
- Thomson Reuters' structured card layout

---

## 2. Static Reveal > Interactive Zoom

**Universal consensus**: static SVG with semantic drill-down beats interactive zoom.

### Why:
- No library dependency (pure SVG requirement)
- Instant interaction (no tile loading)
- Predictable for users (click region → see answer)
- Mobile-friendly (no pinch-zoom ambiguity)
- A11y: keyboard navigable, screen reader friendly
- Performance: <200KB vs multi-MB tile sets

### The drill-down pattern:
```
Level 0: Full Bali → 9 kabupaten visible, muted colors
Level 1: Click kabupaten → region fills with zone colors, neighbors dim
Level 2: Click preset location → side panel slides in with full analysis
```

### SVG architecture:
- One `<svg>` with 9 kabupaten `<path>` elements
- Each path has `data-kabupaten` attribute
- Preset locations as `<circle>` pins within each kabupaten
- CSS transitions for hover/select states
- No viewBox manipulation (no "zoom") — just opacity/color changes

---

## 3. Tone: Forensic, Not Fearful

### The pathologist model:
Present findings like a medical report — clinical, thorough, actionable.

**Copy rules:**
- ❌ "DANGER! Foreigners BANNED!"
- ✅ "Zone classification: Lindung (Protected). Foreign development: Not permitted under RDTR Badung 2023."
- ❌ "Don't make the same mistake as Ruslana!"
- ✅ "Case analysis: XO Pandawa, 2025 — Hak Milik certificate presented as valid for foreign purchase. Our verification identified RTRW designation mismatch."

### Visual tone:
- Property violet (#9880d8) as PRIMARY accent for this tool — not signal red
- Signal red (#ff2d4c) ONLY for actual danger states (black zone, scam warning)
- Glass cards with subtle glow = "evidence display" aesthetic
- Dot grid background = precision measurement environment

### Trust signals:
- "Data sourced from RDTR [Kabupaten] [Year]" on every zone card
- "Verified against GISTARU [date]" timestamp
- Link to original source for independent verification
- Uncertainty indicators where boundaries are approximate

---

## 4. Show Both — Risks AND Opportunities

### Design philosophy: "Full Spectrum with Foreigner Lens"

Every zone shows:
1. **Official classification** (neutral fact, government color code)
2. **Foreign ownership implications** (what you CAN do, what you CAN'T)
3. **Recommended legal structure** (Hak Pakai? HGB via PMA? Leasehold?)
4. **PBG feasibility** (risk level for building permit)

### Color system for our tool:
| Zone | Our Color | Meaning for foreigners |
|------|-----------|----------------------|
| Permukiman (Residential) | `#10b981` (green) | ✅ Permitted via Hak Pakai or PT PMA HGB |
| Pariwisata (Tourism) | `#f59e0b` (amber) | ⚠️ Permitted but complex — PBG requirements strict |
| Perdagangan (Commercial) | `#f59e0b` (amber) | ⚠️ Possible via PT PMA only |
| Pertanian (Agriculture) | `#ef4444` (red) | 🔴 Restricted — conversion process required |
| Lindung (Protected) | `#1a1a1a` (black) | ⛔ No development — do not buy |
| Sempadan (Buffer) | `#ef4444` (red) | 🔴 No construction — setback requirements |
| Suci (Sacred) | `#1a1a1a` (black) | ⛔ No development — temple buffer |
| Subak (Rice paddy) | `#ef4444` (red) | 🔴 Heritage protected — no conversion |

### Black zone honesty:
When a location is in a black/banned zone, show:
- Clear "DO NOT BUY as foreigner" message
- No upsell, no DD offer
- Instead: "Consider these nearby zones where development is permitted"
- This builds trust for when they DO find a viable location

---

## 5. Indonesian Legal Jargon — Badge Pattern

### Three-layer progressive disclosure:

**Layer 1** (always visible): Badge with English translation
```html
<span class="legal-badge">
  <span class="indo-term">RDTR</span>
  <span class="eng-term">District Zoning Plan</span>
</span>
```

**Layer 2** (hover/click): Plain explanation
```
"The detailed zoning map for this district. Determines what can be
built on each plot of land. Updated every 5-10 years."
```

**Layer 3** (link): Full regulatory context
```
"Peraturan Bupati Badung No. 28 Tahun 2023 — RDTR Wilayah Perencanaan Petang"
```

### Key terms translation table (always show in side panel):
| Indonesian | English | Implication |
|-----------|---------|-------------|
| Hak Milik (SHM) | Freehold Title | ⛔ NEVER for foreigners — if offered, it's a scam |
| Hak Pakai | Right to Use | ✅ For foreign residents, up to 80yr |
| HGB | Right to Build | ✅ Via PT PMA company, up to 80yr |
| Hak Sewa | Leasehold | ✅ Simplest option, 25-99yr |
| PBG | Building Permit | Required before construction |
| RDTR | Zoning Plan | Determines what can be built |
| Sertifikat | Land Certificate | Proves ownership type |
| Nominee | Indonesian front-person | ⛔ ILLEGAL — zero legal protection |

---

## 6. Layout: 60/40 with Glass Panel

### Desktop (≥1024px):
```
┌──────────────────────────────────────────────────┐
│  [Bali Zoning Map]                    │ [Panel]  │
│  60% width                            │ 40%      │
│  SVG map                              │ Glass    │
│  Dot grid bg                          │ card     │
│  9 kabupaten                          │ Scrolls  │
│  Preset pins                          │ internally│
└──────────────────────────────────────────────────┘
```

### Mobile (≤768px):
```
┌────────────────────┐
│  [Map] 35% height  │
│  Full width         │
├────────────────────┤
│  [Panel] 65%       │
│  Bottom sheet      │
│  Swipe up/down     │
└────────────────────┘
```

### Panel information hierarchy:
1. Zone classification badge (color + name + English)
2. Foreign ownership status (traffic light)
3. Hak Milik scam warning (always visible, banner)
4. PBG risk indicator (with historical data if available)
5. 3 actionable steps ("What to verify")
6. DD price (USD 850) + timeline (7 days)
7. WhatsApp CTA (primary action)
8. Case study link (Ruslana — evidence, not fear)
9. Lead capture (email, optional, ungated)

---

## 7. Lead Capture: After Value, Always

### Journey:
1. Land on page → see Bali map with search/presets
2. Select location → see full zone analysis (FREE, ungated)
3. Read analysis → understand risk/opportunity
4. Bottom of panel: "Email me a free 1-page zoning summary for [location]"
5. Email field + optional "What are you planning?" dropdown
6. Submit → receive PDF via email + enter nurture sequence

### Why AFTER:
- Cal.com, Linear, Vercel pattern: show value → build trust → convert
- Legal industry norm: initial consultation free, detailed analysis paid
- Users who see value first convert 3-5x higher (DeepSeek cites Zeigarnik effect)
- Gating information on a trust-building tool DESTROYS trust

### What the free email contains:
- 1-page PDF with zone classification for their selected location
- 3 specific regulatory citations
- 1 similar case study
- CTA: "Get full Due Diligence report — USD 850, 7-day delivery"

---

## 8. What We're Adding Beyond the Original Plan

### From DeepSeek:
1. **Temporal dimension** — "This was agricultural until 2019" context
2. **Adjacency analysis** — zone surrounded by protected zones = access risk
3. **Uncertainty indicators** — "Boundary approximate ±50m"
4. **Verification pathway** visualization — step 1 → step 2 → step 3 process

### From web research:
5. **GISTARU link** — "Verify this yourself on the official government portal"
6. **Bingin demolition** — real enforcement case study (July 2025)
7. **$10.4B at-risk stat** — ~10,500 nominee properties in Bali
8. **Banjar/adat rules** — cultural restrictions beyond official zoning

### From Codex-substitute:
9. **Success stories** — not just failures. "340 clients purchased safely in this zone"
10. **Comparison mode** (future) — compare two locations side by side

### What we're NOT doing (scope control):
- No real-time zoning API (prototype uses preset data)
- No actual map zoom (static SVG only)
- No PDF export (future feature)
- No user accounts (lead capture = email only)
- No multiple languages (English only for now)

---

## Implementation Blueprint

### File: `docs/design-palettes/funnels/04-zoning-map.html`

### Structure:
1. Home page context section (simulated, coherent with bz-pages-draft.html)
2. Standalone zoning map tool
3. 10 demo locations with realistic zone data
4. 9 kabupaten SVG paths (hand-drawn stylized)
5. Side panel with full analysis
6. Lead capture form
7. WhatsApp CTA
8. Case study section
9. Mobile responsive (390×844 viewport)
10. A11y: keyboard nav, ARIA labels, focus management, screen reader

### Design tokens to reuse from bz-pages-draft.html:
- All `--bz-*` variables (base, surface, primary, text, border)
- `--cat-property: #9880d8` as page accent
- `.bz-glass` card treatment
- `.bz-gborder` mouse-aware glow
- `.bz-lift` hover interaction
- `.bz-reveal` scroll-driven animation
- `.bz-grain` texture overlay
- Dot grid body background

### New tokens needed:
- Zone colors (green/amber/red/black mapped to palette)
- Legal badge styling
- Traffic light indicator
- PBG risk meter
