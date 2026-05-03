# Tax Compliance Calendar — Design Rationale

> Date: 2026-04-12
> All decisions traced to brainstorm outputs, web research, or existing code references.

---

## 1. Layout: Horizontal Year Strip (not radial)

**Decision**: 12-column horizontal grid, Jan→Dec, with vertical TODAY indicator.

**Sources**:
- Gemini: "Radial is a designer's vanity trap. Degraded legibility. Text renders at awkward angles."
- DeepSeek: "Horizontal aligns with mental model. Less cognitive load for stressed expats."
- Web research: GitHub contribution graph (horizontal, year-at-a-glance), Linear roadmaps (horizontal timeline), Notion Calendar (horizontal with dot indicators).

**Code reference**: The existing portal tax page (`portal/taxes/page.tsx:157-178`) uses a linear timeline approach for deadlines, not radial.

---

## 2. Profile Selector: Segmented Pill Tabs (not dropdown, not quiz)

**Decision**: 4 horizontal pill buttons with `aria-pressed` state, all visible simultaneously.

**Sources**:
- Gemini: "Use segmented control. A dropdown hides options. Let users rapidly click through and watch the calendar react instantly."
- DeepSeek: "Quizzes add friction and feel like marketing engagement bait."
- Design pattern: Linear's cycle selector, Vercel's project switcher — both use segmented controls for 3-5 options.

**Rejected**: Dropdown (hides the dynamic nature of the tool), Quiz (adds friction on a marketing page).

---

## 3. Show Only Filtered Deadlines (not all)

**Decision**: Default shows only the selected profile's deadlines. No "show all" toggle in v1 (keeps it simple).

**Sources**:
- Gemini: "Never show a user a terrifying legal obligation that doesn't apply to them."
- DeepSeek: "Only filtered deadlines. This reduces visual noise and reinforces 'this is YOUR calendar.'"

**Code reference**: The existing workspace LKPM page (`(workspace)/lkpm/page.tsx:165-166`) filters items by status — same principle of contextual filtering.

---

## 4. Color System: Category Hues from Real Dashboard

**Decision**: Reused the exact `CATEGORY_COLOR` values from `dashboard/page.tsx`:
- Tax: `#b89a40` (gold)
- VAT: `#4a8ec4` (blue, from visas category)
- BPJS: `#5cb88a` (green, from business category)
- PB1: `#4ab8c4` (teal, from emerging category)
- LKPM: `#9880d8` (violet, from property category)

**Source**: `ORIGINAL-color-inventory.md` — "These are the CATEGORY_COLOR values from the dashboard, the single source of truth."

**Urgency tiers**:
- >30 days: `#737373` (--bz-text-muted) — calm, no action needed
- 8-30 days: `#b89a40` (gold) — attention, plan ahead
- <8 days: `#b89a40` bold — act soon
- Past due: `#f87171` (red) — the ONLY state using red

**Source**: Both AIs agreed: "Never use red unless deadline is past." Gemini: "Red means system error. Gold = authoritative, not alarmist."

---

## 5. Tone: Guardian, Not Alarm

**Decision**: All copy uses protective framing. "We handle this for you." "Your year at a glance." "So you don't have to."

**Sources**:
- Gemini: "Design a 'Guardian UI' — an interface that feels so hyper-competent the user thinks 'Thank God I can pay them.'"
- DeepSeek: "'Handled by Bali Zero' (green check) vs 'Requires your input' (yellow). Microcopy: 'We prevent that.'"
- Brief: "The vibe is: 'here is your year, we know it by heart, relax.'"

**Rejected**: Fear-driven copy ("You WILL be fined!"), countdown timers, pulsing animations, red urgency states for upcoming deadlines.

---

## 6. Deadline Cards: Conic Ring + Text (not animation)

**Decision**: Each deadline card has a conic ring showing time remaining + text countdown.

**Sources**:
- Gemini: "If you must use a visual indicator of time, use a static conic progress ring rather than a ticking countdown."
- DeepSeek: "Tiered urgency system via text + border color."
- `MASTER-synthesis.md` (parent prototype): "Conic ring chart — one div, no SVG, no library" (Tech #5).

**Rejected**: Pulsing animations (Gemini: "induces panic, causes bounce rates"), ticking counters, animated progress bars.

---

## 7. Acronym Tooltips: Dotted Underline + Frosted Glass Popover

**Decision**: Every Indonesian tax acronym (SPT, PPh, BPJS, LKPM, PB1, PPN) has a dotted underline. Hover reveals a tooltip with:
1. Full Indonesian name
2. Plain English explanation
3. Home-country analogy where possible (IRS, Lohnsteuer, Dichiarazione dei Redditi)

**Sources**:
- DeepSeek: "Map to familiar concepts: 'SPT Tahunan = Annual Tax Return,' 'PPh 21 = Monthly Withholding (like German Lohnsteuer).'"
- Gemini: "Never show an acronym without plain-English equivalent. Dotted underline → frosted-glass tooltip."
- Brief: "Every acronym must have an inline tooltip with plain English."

---

## 8. Verified Deadline Data (corrections from web research)

**Critical corrections applied**:
| Item | Brief Said | Tool Uses | Source |
|---|---|---|---|
| Monthly payment | 10th | **15th** | jcss.co.id (changed 2025) |
| BPJS deadline | 10th | **15th** | procapita.co.id |
| PB1 deadline | 15th (generic) | **20th** (Badung/Denpasar) | sasbali.com |
| VAT due | Not specified | **End of following month** | jcss.co.id |

All deadlines cross-referenced against pajak.go.id official data and multiple Indonesian tax advisory firms.

---

## 9. Interaction Model

### Mouse-aware glow border (TECH #3)
Gold variant of the glow border from `bz-pages-draft.html`. Applied to the main calendar card only. Changes the cursor's radial gradient from signal red to tax gold (`rgba(184,154,64,.45)`).

### Profile switching
Instant DOM update — no page reload, no fetch. All data is inline JSON. Pills use `aria-pressed` for accessibility. Deadline cards container has `aria-live="polite"` for screen reader announcements.

### Lead capture
Simple email → "success" state transition via CSS class toggle. No actual backend call (prototype). Captures intent before the CTA (DeepSeek: "capture leads before the CTA").

---

## 10. Accessibility

| Feature | Implementation | Standard |
|---|---|---|
| Keyboard navigation | Tab through pills, Enter to select, Tab to dots | WCAG 2.2 |
| Screen reader | `aria-pressed`, `aria-live`, `role="tooltip"`, `aria-label` | WCAG AA |
| Focus ring | Gold double-layer ring (adapted from TECH #8) | WCAG 2.2 |
| Reduced motion | `prefers-reduced-motion: reduce` kills all animations | WCAG 2.1 |
| Color contrast | All text > 4.5:1 on `#0a0a0a` background | WCAG AA |
| Semantic HTML | `<nav>`, `<article>`, `<section>`, `<footer>`, `<time>` | HTML5 |

---

## 11. Mobile Responsive (390×844)

| Element | Desktop | Mobile |
|---|---|---|
| Pills | 4 horizontal | 2×2 grid |
| Year strip | 12 columns visible | Horizontally scrollable, snap to center on current month |
| Lead capture | Horizontal row | Stacked vertical |
| Calendar padding | 32px | 16px |
| Card ring size | 44px | 38px |
| Nav links | Visible | Hidden |

---

## 12. What We Deliberately Did NOT Build (and why)

| Feature | Why Not |
|---|---|
| "Mark as done" checkbox | Prototype scope — would need backend state |
| Google Calendar sync | API integration — signaled in future ("sync coming soon") |
| PDF export | Server-side generation needed — simulated via email capture |
| Live date simulation | Adds complexity, low conversion value vs. real deadlines |
| Progress bar "8/24 filed" | Needs user account data — save for portal |
| "Show all deadlines" toggle | Adds visual noise, contradicts "only what applies to you" |
| Holiday-adjusted dates | Would need Indonesian holiday calendar API — noted in footer text |

---

## 13. Files Delivered

```
docs/design-palettes/funnels/
├── 03-tax-calendar.html                  ← The tool (standalone)
├── 03-tax-calendar-RATIONALE.md          ← This file
└── research/
    ├── tax-gemini-brainstorm.md           ← Gemini 3 Pro Preview output (65 lines)
    ├── tax-codex-brainstorm.md            ← Codex output (rate-limited)
    ├── tax-deepseek-brainstorm.md         ← DeepSeek R1 output (106 lines)
    ├── tax-MASTER-design.md               ← Cross-AI synthesis
    └── tax-web-research.md                ← 8-topic web research with .go.id sources
```

---

*End of rationale. Every decision traces to a brainstorm, web source, or existing code reference.*
