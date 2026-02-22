# KBLI 2025 Navigator Pro — SOTA Design Strategy

## For balizero.com | Prepared by Senior Web Design Analysis

---

## 1. CURRENT STATE ASSESSMENT

### Design Maturity Score: 7/10

**Strengths:**

- Modern indigo/violet color palette with clean gradients
- Well-structured 3-view architecture (Chat → Database → Dashboard)
- Excellent Markdown rendering in chat with code blocks and tables
- Responsive sidebar with hamburger menu on mobile
- Strong data visualization with Recharts (bar + pie charts)
- Bilingual EN/ID toggle working well
- Copy-to-clipboard on AI messages
- File attachment handling with drag-and-drop

**Critical Weaknesses:**

- No split-panel layout (chat and content are separate views — user loses context)
- Missing WCAG accessibility (no ARIA labels, color-only status indicators, no focus-visible)
- Sidebar text contrast fails WCAG AA (slate-300 on navy-800)
- Mobile UX friction: small touch targets, no lazy loading for 1,562 codes
- No dark mode support
- `alert()` used for errors instead of toast notifications
- Database pagination is prev/next only — no page jump for 45+ pages
- No skeleton loaders (uses "..." placeholder)
- No keyboard shortcuts for power users

---

## 2. COMPETITIVE LANDSCAPE

### Direct Competitors (Indonesia)

| Tool                     | Strengths                                                      | Weaknesses                                 |
| ------------------------ | -------------------------------------------------------------- | ------------------------------------------ |
| **KBLI.co.id**           | Modern hero, sector cards, FDI/licensing context, 2025-updated | No AI chat, no dashboard, limited search   |
| **OSS Indonesia (BKPM)** | Official government system, risk-based licensing               | Poor UX, steep learning curve, no guidance |
| **PermitIndo**           | KBLI lookup + licensing                                        | Basic UI, no AI, no analytics              |

### Global Best-in-Class References

| Category     | Model                   | Pattern to Adopt                                                  |
| ------------ | ----------------------- | ----------------------------------------------------------------- |
| Code Lookup  | **SICCODE.com**         | Multi-entry discovery (search + hierarchical browse in parallel)  |
| Code Lookup  | **NAICS.com**           | Statistics column ("# entities"), API-first, crosswalk exports    |
| AI Chatbot   | **Intercom Fin**        | Filtered knowledge base, confidence scoring, graceful degradation |
| AI Chatbot   | **Salesforce Einstein** | Context-aware embedded panel, suggest→customize→execute flow      |
| Data Browser | **Airtable Interface**  | Flexible views (grid/gallery), column management, smart defaults  |
| Data Browser | **Notion Tables**       | Property types, inline editing, summary rows, persistent filters  |
| Dashboard    | **Stripe Dashboard**    | Visual app identity bar, consistency over novelty, list as hub    |
| Dashboard    | **Wise (Fintech)**      | Generous white space, trust pattern, progress indicators          |

### Market Gap = Our Opportunity

**No existing tool combines:** AI-powered KBLI finder + regulatory rules engine + PMA/FDI database + workflow wizard + analytics dashboard. We are building a genuinely novel product.

---

## 3. SOTA DESIGN STRATEGY

### Architecture: Split-Panel with AI Sidebar

```
┌─ Top Navigation Bar ──────────────────────────────────────────┐
│ [Logo] KBLI 2025 Navigator Pro   [Finder|Browse|Dashboard]    │
│                                      [EN/ID] [AI Chat] [CTA]  │
├───────────────┬────────────────────────────────────────────────┤
│               │                                                │
│   AI CHAT     │              MAIN CONTENT AREA                 │
│   PANEL       │                                                │
│   (380px)     │   Code Finder / Browse Sectors / Dashboard     │
│               │                                                │
│  Persistent   │   Dynamic based on active tab                  │
│  across all   │                                                │
│  views        │                                                │
│               │                                                │
│  Collapsible  │                                                │
│  toggle       │                                                │
├───────────────┴────────────────────────────────────────────────┤
│ Footer: balizero.com × 3Om Consulting | BPS Reg. No. 7/2025  │
└────────────────────────────────────────────────────────────────┘
```

### Key Design Decisions

**1. AI Chat as Persistent Sidebar (not separate view)**

- Why: Users lose context when switching between chat and database. Intercom/Einstein pattern shows embedded chat outperforms modal/overlay chat.
- How: 380px left panel, collapsible via toggle button in top nav. Chat remembers what code user is viewing.
- Context awareness: "You're looking at code 62011. Want to know about licensing?"

**2. Top Navigation Tabs (not sidebar nav)**

- Why: Sidebar navigation wastes horizontal space when combined with chat panel. Top tabs (Finder | Browse | Dashboard) keep layout clean.
- How: Pill-style tabs in top bar with active indicator. Reduces from 3 hierarchy levels to 2.

**3. Code Finder as Default View (not chat)**

- Why: Most users arrive with intent to find a code, not chat. KBLI.co.id and SICCODE.com lead with search.
- How: Large search input with bilingual autocomplete, instant results below.

**4. Expandable Code Cards (not modal dialogs)**

- Why: Modals break flow. Airtable/Notion pattern shows inline expansion is faster.
- How: Click card → expands inline showing: Transition Status, OSS Licensing, Min. Investment. Actions: "Ask AI" + "OSS Portal".

**5. Horizontal Bar Charts (not pie charts)**

- Why: Pie charts with >4 segments are hard to read (UXPin research). Bar charts with labeled segments are scannable.
- How: Replace Recharts PieChart with progress-bar-style distribution visualizations.

---

## 4. DESIGN SYSTEM SPECIFICATION

### Color Palette

```
Primary:     #4f46e5 (Indigo 600 — trust, expertise)
Secondary:   #7c3aed (Violet 600 — innovation, AI)
Surface:     #ffffff (cards, panels)
Background:  #f8fafc (Slate 50 — subtle warmth)
Border:      #e2e8f0 (Slate 200)
Text:        #0f172a (Slate 900 — high contrast)
Muted:       #64748b (Slate 500)
Subtle:      #94a3b8 (Slate 400)

Status Colors:
  Success:   #22c55e (Green 500) — Low Risk, TERBUKA
  Warning:   #f59e0b (Amber 500) — Medium Risk, TERBATAS
  Danger:    #ef4444 (Red 500) — High Risk, TERTUTUP
  Info:      #3b82f6 (Blue 500) — Aggregated, transition
  Neutral:   #a78bfa (Violet 400) — BPS_ONLY, statistical
```

### Typography

```
Font:        Inter (or system -apple-system stack)
Headings:    800 weight, -0.02em tracking
Body:        400-500 weight, 1.5-1.65 line height
Labels:      700 weight, 0.08em tracking, uppercase, 10-11px
Code/Mono:   JetBrains Mono or system monospace
```

### Component Tokens

```
Border Radius:
  Small:     6px (badges, tags)
  Medium:    10px (buttons, inputs)
  Large:     14px (cards, panels)

Shadows:
  Card:      0 1px 3px rgba(0,0,0,0.04)
  Hover:     0 4px 20px rgba(99,102,241,0.1)
  Modal:     0 20px 60px rgba(0,0,0,0.15)

Spacing:
  xs: 4px | sm: 8px | md: 12px | lg: 16px | xl: 24px | 2xl: 32px
```

### Component Inventory

| Component                        | Status      | Priority |
| -------------------------------- | ----------- | -------- |
| Button (primary/secondary/ghost) | ✅ Redesign | P0       |
| Badge (risk/PMA/status/sector)   | ✅ Redesign | P0       |
| Card (expandable code card)      | ✅ New      | P0       |
| Search Input (with autocomplete) | ✅ New      | P0       |
| Chat Bubble (user/AI/error)      | ✅ Redesign | P0       |
| Progress Bar (horizontal)        | ✅ New      | P1       |
| Stat Card (KPI display)          | ✅ Redesign | P1       |
| Skeleton Loader                  | 🆕 New      | P1       |
| Toast Notification               | 🆕 New      | P1       |
| Tooltip                          | 🆕 New      | P2       |
| Modal (generic, focus-trapped)   | ✅ Redesign | P2       |
| Tabs (nav tabs, content tabs)    | 🆕 New      | P1       |
| Filter Pill (toggle group)       | ✅ Redesign | P1       |
| Avatar (user/AI)                 | ✅ Redesign | P2       |
| Pagination (with page jump)      | ✅ Redesign | P1       |

---

## 5. MOBILE STRATEGY

### Breakpoints

- `< 640px` (sm): Single column, chat as full-screen overlay, bottom nav
- `640–1024px` (md): Chat collapsible, 2-column cards
- `> 1024px` (lg): Split-panel layout, 3-column cards

### Mobile-First Patterns

1. **Chat becomes bottom sheet** on mobile (swipe up to expand, swipe down to minimize)
2. **Filters collapse** into a single "Filters" button that opens modal
3. **Sector browse** becomes horizontal scroll of icon pills
4. **Cards stack** single-column with full-width expansion
5. **Touch targets** minimum 44px (iOS) / 48px (Material Design)

---

## 6. ACCESSIBILITY ROADMAP (WCAG 2.1 AA)

### Phase 1 (P0): Critical Fixes

- [ ] Add `aria-label` to all icon-only buttons
- [ ] Add `role="navigation"` to sidebar/tabs
- [ ] Add `aria-live="polite"` to chat message area
- [ ] Fix sidebar contrast (slate-300 on navy-800 → white on navy-800)
- [ ] Add `focus-visible` rings to all interactive elements
- [ ] Link form labels with `htmlFor` + `id`

### Phase 2 (P1): Enhanced A11y

- [ ] Add `aria-expanded` to expandable cards
- [ ] Create focus trap for modal dialogs
- [ ] Add keyboard shortcuts (Cmd+K search, Escape close)
- [ ] Add skip-to-content link
- [ ] Pair all color indicators with text/icon
- [ ] Add `role="status"` to loading indicators

### Phase 3 (P2): Best-in-Class

- [ ] High-contrast mode toggle
- [ ] Screen reader optimized chat flow
- [ ] Voice input for search (Web Speech API)
- [ ] Reduced motion preference support

---

## 7. IMPLEMENTATION ROADMAP

### Sprint 1 (Week 1-2): Layout Revolution

- [ ] Implement split-panel layout (Chat sidebar + Main content)
- [ ] Move navigation from sidebar to top bar tabs
- [ ] Create new design token system (colors, spacing, radii)
- [ ] Build reusable Button, Badge, Card components

### Sprint 2 (Week 3-4): Code Finder Excellence

- [ ] Redesign search with bilingual autocomplete
- [ ] Create expandable code cards with inline detail
- [ ] Add sector browse with icon grid
- [ ] Implement advanced filtering (risk, PMA, sector)

### Sprint 3 (Week 5-6): AI Chat Evolution

- [ ] Persistent chat sidebar with context awareness
- [ ] Suggestion cards with conversation flows
- [ ] Copy/Save/Share actions on AI responses
- [ ] Error handling with toast notifications

### Sprint 4 (Week 7-8): Dashboard & Polish

- [ ] Redesign dashboard with bar charts (not pie)
- [ ] Add skeleton loaders and progress indicators
- [ ] Implement dark mode
- [ ] Accessibility audit + fixes
- [ ] Mobile optimization pass

---

## 8. UNIQUE VALUE PROPOSITION

**For balizero.com:**

> "The only AI-powered Indonesian business classification navigator that combines intelligent code search, real-time regulatory compliance data, and foreign investment analysis — all in one modern interface."

**Competitive moat:**

1. **AI Expert Chat** — No competitor has conversational KBLI guidance
2. **PMA/FDI Deep Integration** — TERBUKA/TERBATAS/TERTUTUP with % and conditions
3. **KBLI 2020→2025 Transition Mapping** — Unique dataset with 4 status types
4. **Risk-Based Advisory** — OSS-RBA risk levels with sector-specific warnings
5. **Bilingual EN↔ID** — Serving both Indonesian business owners and foreign investors

---

_Document prepared for 3Om Consulting / balizero.com_
_KBLI 2025 Navigator Pro — Version 3 Design Strategy_
