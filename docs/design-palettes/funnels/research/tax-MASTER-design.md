# Tax Compliance Calendar — MASTER Design Synthesis

> Sources: Gemini 3 Pro Preview (65 lines) · DeepSeek R1 (106 lines) · Codex (rate-limited, not available)
> Cross-validated with: web research (8 topics), existing code (taxes/page.tsx, lkpm/page.tsx, StatusBadge.tsx, kanban-colors.ts)
> Date: 2026-04-12

---

## Consensus Decisions (both AIs agree)

### 1. Year Strip: HORIZONTAL (unanimous)
- Gemini: "Radial is a designer's vanity trap. Degraded legibility."
- DeepSeek: "Horizontal aligns with mental model (Jan→Dec). Less cognitive load."
- **Decision**: Horizontal 12-column strip with vertical `TODAY` line. Add conic ring accent on current month (DeepSeek's hybrid idea).

### 2. Show ONLY Filtered Deadlines (unanimous)
- Gemini: "Never show a user a terrifying obligation that doesn't apply to them."
- DeepSeek: "Only filtered deadlines. Add toggle: 'Show all Indonesian tax deadlines' for curious."
- **Decision**: Default = filtered only. Optional "Show all" toggle at bottom.

### 3. Profile Selector: NOT a quiz (unanimous)
- Gemini: "Use segmented control (pill tabs), not dropdown. Let users click through and watch calendar react."
- DeepSeek: "Single dropdown with icons + short descriptions. Quizzes add friction."
- **Decision**: **Segmented pill tabs** (Gemini's insight is better — shows all options, feels interactive, matches Linear/Vercel aesthetic). Each pill shows icon + short label.

### 4. Tone: Protective, NOT Punitive (unanimous)
- Gemini: "Flip from Punitive to Protective. 'Status: Protected. We are preparing your filing.'"
- DeepSeek: "'Handled by Bali Zero' (green check) vs 'Requires your input' (yellow). Microcopy: 'We prevent that.'"
- **Decision**: Gold (#b89a40) for upcoming deadlines, never red unless past due. "We handle this" framing throughout.

### 5. Urgency: Text + Subtle Visual, NOT Animation (consensus)
- Gemini: "No animations for urgency. Use static conic ring progress + text."
- DeepSeek: "Tiered: >30d grey, 8-30d gold border, <7d subtle pulse. Never red unless past."
- **Decision**: Tiered text urgency + border color shift. NO pulse animation (Gemini's argument about bounce rates wins). Static conic ring showing time remaining.

### 6. Acronym Tooltips (unanimous)
- Both: Every Indonesian tax acronym needs plain-English inline explanation.
- Gemini: "Dotted underline → frosted-glass tooltip with explanation."
- DeepSeek: "Map to familiar concepts: 'SPT Tahunan = Annual Tax Return', 'PPh 21 = Monthly Withholding (like German Lohnsteuer).'"
- **Decision**: Dotted underline on ALL acronyms → hover tooltip with plain English + home-country analogy where possible.

---

## Key Design Innovations (from brainstorms)

### From Gemini (unique insights)
1. **"Guardian UI"** — the interface should feel like a shield, not a to-do list
2. **"Done State"** — show past 3 months with checkmarks to prove "we already handled these for you"
3. **Local nuance flex**: "Adjusted for Idul Fitri holiday" badge — massive trust signal
4. **Actionability per deadline**: tiny bulleted list of what they need to provide (e.g., "Required: bank statements, EFIN")
5. **Segmented control > dropdown** — all options visible, instant visual feedback

### From DeepSeek (unique insights)
1. **Holiday shift indicator**: 🏖️ icon when deadline shifts due to public holiday
2. **"What you DON'T need" section**: reduces anxiety by showing excluded obligations
3. **PDF export promise**: "Download your personalized tax calendar" — captures intent
4. **Timezone note**: "All deadlines WITA (Bali time, UTC+8)"
5. **Progress bar**: "8/24 filings completed this year" — builds trust
6. **"Ask Asya" per deadline card** — WhatsApp pre-filled with specific question
7. **Google Calendar sync hint**: signal future integration

---

## Corrected Deadline Data (from web research)

### CRITICAL CORRECTIONS:
| Item | Brief Said | Verified Truth |
|---|---|---|
| Monthly payment deadline | 10th | **15th** (changed 2025, JCSS) |
| BPJS Kesehatan | 10th | **15th** (ProCapita 2026) |
| VAT rate | 11% | **12% official / 11% effective** |
| 2026 individual SPT | March 31 | **April 30** (one-time relaxation) |
| PB1 deadline | Generic 15th | **Varies by regency** (7th-20th) |

### Final Deadline JSON Structure (for the tool)
```
profiles:
  individual: SPT annual, BPJS Kesehatan
  investor: SPT annual, LKPM quarterly, BPJS Kesehatan
  pma: SPT Badan, PPh 21/23/25/4(2) monthly, PPN monthly, LKPM, BPJS both, [PB1 if hospitality]
  pma_staff: all of pma + BPJS Ketenagakerjaan for staff

deadline_types:
  spt_annual_individual: { month: 3, day: 31, label: "Annual Income Tax Return" }
  spt_annual_corporate: { month: 4, day: 30, label: "Corporate Income Tax Return" }
  pph_monthly: { recurring: "monthly", day: 15, label: "Income Tax Withholding" }
  spt_masa_report: { recurring: "monthly", day: 20, label: "Monthly Tax Report" }
  ppn_vat: { recurring: "monthly", day: "end", label: "VAT Return" }
  bpjs_kesehatan: { recurring: "monthly", day: 15, label: "Health Insurance" }
  bpjs_ketenagakerjaan: { recurring: "monthly", day: 15, label: "Employment Insurance" }
  pb1_hospitality: { recurring: "monthly", day: 20, label: "Bali Hospitality Tax" }
  lkpm_quarterly: { months: [1,4,7,10], day: 10, label: "Investment Report" }
```

---

## Final Design Specification

### Layout (760×500px glass card)
```
┌─────────────────────────────────────────────────────────────┐
│ ◆ Your Tax Compliance Calendar                    [2026 ▾]  │
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ [Individual] [Investor] [PT PMA] [PMA + Staff]          │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ ┌───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┐        │
│ │Jan│Feb│Mar│Apr│May│Jun│Jul│Aug│Sep│Oct│Nov│Dec│        │
│ │ · │ · │●●●│●● │ · │ · │●● │ · │ · │●● │ · │ · │        │
│ │   │   │   │   │   │   │   │   │   │   │   │   │        │
│ └───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┘        │
│            ▲ TODAY                                           │
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Next 3 Deadlines                                        │ │
│ │                                                         │ │
│ │ ◆ Annual Income Tax Return (SPT)  ·  in 18 days        │ │
│ │   March 31 · You provide: bank statements, EFIN        │ │
│ │                                                         │ │
│ │ ◆ Investment Report (LKPM Q1)     ·  in 28 days        │ │
│ │   April 10 · We handle the filing for you               │ │
│ │                                                         │ │
│ │ ◆ Monthly Tax Withholding (PPh 21) ·  in 34 days       │ │
│ │   April 15 · Recurring monthly                          │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ 📧 Email me my personalized tax calendar  [email] [Send]│ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│  From IDR 5M/year, all-inclusive compliance                  │
│  [💬 Let us handle all your filings → Talk to Asya]         │
│                                                             │
│  ⏰ All deadlines in WITA (Bali time) · Holiday shifts noted│
└─────────────────────────────────────────────────────────────┘
```

### Color System
- **Tax gold**: `#b89a40` (from CATEGORY_COLOR.taxes) — primary accent for all tax elements
- **Urgency tiers**:
  - `>30 days`: `var(--bz-text-muted)` (#737373) border
  - `8-30 days`: `#b89a40` gold border
  - `<8 days`: `#b89a40` gold border + bold text
  - `past due`: `#f87171` red border (only state that uses red)
- **Deadline type dots**:
  - SPT/PPh: `#b89a40` gold
  - BPJS: `#5cb88a` green (from cat-business)
  - LKPM: `#9880d8` violet (from cat-property, since it's investment-related)
  - PB1: `#4ab8c4` teal (from cat-emerging)
  - PPN/VAT: `#4a8ec4` blue (from cat-visa, reused for fiscal)

### Interaction Model
1. **Default state**: Profile = "Foreign individual", current month highlighted, next 3 deadlines shown
2. **Profile switch**: Instant filter, dots animate (fade out/in), deadline cards update
3. **Dot hover**: Frosted glass tooltip with full explanation
4. **Acronym hover**: Dotted underline → tooltip with English + home-country analogy
5. **Email capture**: Input + "Send" → success state with checkmark animation
6. **CTA click**: Opens WhatsApp with pre-filled message to Asya

### Accessibility
- Keyboard navigable (Tab through pills, Enter to select)
- ARIA labels on all interactive elements
- `aria-live="polite"` on deadline list for screen reader updates on filter change
- `prefers-reduced-motion` respected (no animations)
- Color contrast: all text meets WCAG AA on `#0a0a0a` background
- Semantic HTML: `<nav>` for pills, `<ol>` for deadlines, `<time>` for dates

### Mobile (390×844)
- Pills stack 2×2 grid
- Year strip becomes horizontally scrollable with current month centered
- Deadline cards stack vertically
- CTA becomes sticky bottom bar

---

*This synthesis drives Phase 3 (build). Every decision traces to a brainstorm output or web research finding.*
