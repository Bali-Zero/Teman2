# Bali Zero — Palette D Session Summary

> **Date:** 2026-04-11 → 2026-04-12 (single long session)
> **Owner:** Zero
> **Scope:** from "Palette D Monochrome Modern" approval to full 7-page prototype with research-backed techniques

---

## The arc in 12 steps

### 1. Baseline recognition
- Palette D approved 2026-04-11 (decision memory)
- Tokens in `packages/core/styles/bz-tokens.css` (already written in `.worktrees/palette-b-rebrand`)
- Applied only to `apps/mouth`, rest of ecosystem still on Warm Depth (`#0c0c0e` / `#d4845a` copper) or Navy (`#051C2C`)
- Ecosystem inventory: 11 frontend surfaces + 7 client channels + 1 OPSEC exception (osint-nexus-ui)

### 2. Multi-channel design doc (1st draft)
- `bz-multichannel-draft.html` — one page overview of all surfaces + channels side by side
- Showed how Palette D lands on each surface with identical tokens
- Validated with real logo, category hue examples, emoji whitelist

### 3. Real pages replication (2nd draft)
- `bz-pages-draft.html` — 5 pages replicated **structurally** from `apps/mouth/src/app/**`:
  - **Marketing** ← `(marketing)/page.tsx` (1253 lines)
  - **Services/Visa** ← `(blog)/services/[slug]/page.tsx` (382 lines)
  - **Workspace Dashboard** ← `(workspace)/dashboard/page.tsx` (646 lines)
  - **Client Portal** ← `portal/(authenticated)/page.tsx` (540 lines)
  - **KBLI Home** ← `kbli/page.tsx` (231 lines)
- Single HTML file, tab-internal navigation (no routing)

### 4. Logo fix + real images
- Rimosso ridondanza logo + testo "Bali Zero" dove il logo già contiene il wordmark
- Copiato `balizero-logo-HD-256.png` in `docs/design-palettes/`
- Applicati 10 loghi reali (tab bar, nav, brand entrance, footer, email, gchat, ig, x/og, kbli brand)
- Symlinks a immagini reali da `apps/mouth/public/static/` (6 hero cinematic) + `apps/mouth/public/images/articles/` (4 article)

### 5. Parallel research (4 AI agents)
Launched in parallel:
- **Gemini CLI** — 1052 lines, 30+ techniques, category A→O
- **DeepSeek API** — 973 lines, 30+ techniques, animation-heavy
- **Claude Agent + Exa/Brave** — 1177 lines, 55+ techniques, with source links
- **Codex CLI** — 1000 lines (retry after sandbox trust fix)

Output: `research/MASTER-synthesis.md` (522 lines) — 10 top + 5 bonus techniques cross-validated

### 6. Color system correction (reading the real code)
Read authoritative color logic from:
- `components/process/kanban-colors.ts` — 5 states × 7 color variables, tripartite (bg 3.5%/border 8%/badge 12%)
- `components/portal/StatusBadge.tsx` — 4 groups × 12% flat
- `components/portal/ProcessStepper.tsx` — done/current/pending with pulse+spinner
- `components/services/ServicePricing.tsx` — KITAS/KITAP = orange, Visit = blue
- `app/(workspace)/dashboard/page.tsx` L28-36 — CATEGORY_COLOR with `#b89a40` not `#d4a853`
- `components/kbli/RiskBadge.tsx` — tripartite with `${color}15` bg + `${color}33` border

Created `research/ORIGINAL-color-inventory.md` — single source of truth, every color tracked to file source.

Rewrote draft tokens:
- `--cat-*` set (muted, editorial) — visa/business/tax/property/living/emerging
- `--st-*` set (bright, kanban) — inquiry/wait/invoice/active/done/fail
- Each semantic color tripartite: text + bg + border

### 7. Applied 17 techniques (round 1)
- **#1 Dotted grid mask** — body background Linear/Raycast style
- **#2 Frosted glass + inner light leak** — all card bases
- **#3 Mouse-aware glow border** — pricing, service, portal cards
- **#4 Rotating conic (`@property`)** — ONE card: Golden Visa premium tier
- **#5 Conic ring chart** — 5 dashboard metric + 3 portal status
- **#6 Skeleton shimmer dark** — utility ready
- **#7 Hover-lift + layered shadow** — all cards
- **#8 Double focus ring** — global `:focus-visible`
- **#9 Grain SVG `feTurbulence`** — hero backgrounds
- **#10 Scroll-driven reveal** — marketing sections
- **Bonus: pulse dot, L-brackets, headline shine, stream bars**

### 8. Dashboard sidebar (AppSidebar.tsx reproduction)
- Read `components/workspace/AppSidebar.tsx` (249 lines) + `types/navigation.ts`
- Recreated: 216px wide, sticky top, glass panel, logo 96px centered, 4 nav sections (Core/Work/Kita-Space/System), badge counts, active state, user footer avatar, logout link

### 9. Applied 11 more trendy techniques (round 2)
- **Aurora body background** — 4 radial gradients animated 40s
- **Bento grid asym** — utility ready
- **3D tilt** — Zantara card + Golden Visa
- **Magnetic button** — 2 marketing CTAs
- **Inline sparkline** — metric bar
- **GitHub heatmap 26×7** — team panel (182 cells deterministic random)
- **Flowing marquee** — 2 strips (marketing + dashboard intel feed)
- **Rolling digit ticker** — metric values count-up digit-by-digit
- **Cmd-K command palette** — global ⌘K overlay with 9 results
- **Variable font weight hover** — nav/sidebar/tabs
- **Native CSS masonry** — kbli sectors + kbli detail grid

### 10. Applied 6 advanced techniques (round 3)
- **View Transitions API** — tab switch crossfade with blur+scale
- **Chromatic aberration** — KBLI "2025" + marketing headlines
- **Metallic text three-stop** — Revenue "Rp 847M" (argento) + Outstanding (red metal) + Gold variant
- **Sticky reveal mask** — marketing sections with `animation-timeline: view()`
- **Container queries** — dash-metrics + portal-status-grid adapt to own container
- **Conic progress multi-stop** — health strip 3 ring (94 uptime / 76 capacity / 88 p95)

### 11. Extended to 7 pages
- **[6] Portal · Visa** ← `portal/(authenticated)/visa/page.tsx` (420 lines)
  - Sub-nav 9 voci
  - Current visa card with ring 17d + status + info grid + 3 CTAs
  - Renewal Timeline 7-step (ProcessStepper.tsx reproduction)
  - Visa History 3 years
  - Required Documents 3 cards (1 done + 2 pending)

- **[7] KBLI · 56101 detail** ← `kbli/[code]/page.tsx` (900 lines)
  - Hero with cover image + chromatic "Restaurants" + 3 badges
  - Lead paragraph with color-highlighted claims
  - 6 licensing boxes in masonry
  - Facts strip 4 metallic metrics
  - FAQ accordion 4 Q
  - Related KBLI 3 cards
  - Zantara CTA card with tilt + magnetic

### 12. Consolidation + live testing
- **Bug fix critical**: `#page-dashboard { display: grid }` overriding `.page { display: none }` — made dashboard always visible. Fixed to `#page-dashboard.active`.
- **View Transitions bug**: callback never resolved on hidden tab. Fixed with `!document.hidden` guard.
- **Performance audit** (live via Chrome extension + Playwright):
  - DOM: 75–674 nodes per page
  - Layout time: 1.5–11.7ms (all under 16.67ms frame budget)
  - 70 tab switch test: 2ms avg, 3.9ms p95
  - 100 pointermove test: 0.133ms avg
  - 8 scroll jumps 3822px: 0.25ms avg
  - **Verdict: FLUIDO in real world** on M4 Pro
- **Tab bar overflow fix**: `overflow-x: auto` + mask gradient fade + compact buttons
- **GIF animated tour** — 11 frames, 8.8MB, full tab navigation
- **7 full-page PNG screenshots** in `docs/design-palettes/screenshots/` (total 7.3MB)

---

## Final deliverables

### Files created in `docs/design-palettes/`

```
docs/design-palettes/
├── bz-multichannel-draft.html       (multi-channel overview, 58KB)
├── bz-pages-draft.html               (7 replicated pages, 224KB, 6118 lines)
├── SESSION-SUMMARY.md                (this file)
├── balizero-logo.png                 (real HD logo 59KB)
├── hero-images/                      (symlink → apps/mouth/public/static)
├── article-images/                   (symlink → apps/mouth/public/images/articles)
├── kbli-images/                      (symlink → apps/mouth/public/kbli-navigator/images)
├── screenshots/
│   ├── bz-01-marketing.png           (2.6MB, full page 3033px)
│   ├── bz-02-visa-service.png        (866KB, full page 3822px)
│   ├── bz-03-dashboard.png           (1.2MB, full page 2005px)
│   ├── bz-04-portal.png              (295KB, full page 947px)
│   ├── bz-05-kbli-home.png           (907KB, full page 1489px)
│   ├── bz-06-portal-visa.png         (371KB, full page 2065px)
│   └── bz-07-kbli-detail.png         (1.1MB, full page 2501px)
└── research/
    ├── MASTER-synthesis.md            (522 lines, top 10 picks)
    ├── ORIGINAL-color-inventory.md    (color DNA from real code)
    ├── claude-exa-futuristic-dark-ui.md  (1177 lines)
    ├── gemini-futuristic-dark-ui.md       (1052 lines)
    ├── deepseek-futuristic-dark-ui.md     (973 lines)
    └── codex-futuristic-dark-ui.md        (1000 lines)
```

Bonus: `bz-palette-d-tab-tour.gif` in `~/Downloads` (8.8MB · 11 frames · 2262×1812).

### Techniques in the draft — 34 total

Layer base (1st round, 17):
1. Dotted grid mask
2. Frosted glass + inner light leak
3. Mouse-aware glow border (cursor-driven `::before`)
4. Rotating conic border (`@property --a`)
5. Conic ring chart
6. Skeleton shimmer dark
7. Hover-lift layered shadow
8. Double-layer focus ring
9. Grain SVG `feTurbulence`
10. Scroll-driven reveal (`animation-timeline: view()`)
11. Pulse live dot (ping)
12. L-shaped corner brackets
13. Headline shine (animated gradient text)
14. Data stream equalizer bars
15. Kanban state grammar (3-intensity tints)
16. Category hue tokens (muted vs bright)
17. Tripartite semantic colors

Layer trendy (2nd round, 11):
18. Aurora body background (4 radials animated)
19. Bento grid asymmetric (utility)
20. 3D tilt on mousemove
21. Magnetic cursor follow button
22. Inline sparkline pure CSS
23. GitHub heatmap 26×7
24. Flowing marquee (infinite translateX)
25. Rolling digit ticker (0-9 scroll stacks)
26. Cmd-K command palette
27. Variable font weight hover
28. Native CSS masonry (`grid-template-rows: masonry`)

Layer advanced (3rd round, 6):
29. View Transitions API (`document.startViewTransition`)
30. Chromatic aberration (RGB split text-shadow)
31. Metallic text three-stop (argento/rosso/oro)
32. Sticky reveal mask (mask-position animate-on-scroll)
33. Container queries (`container-type: inline-size`)
34. Conic progress multi-stop (7-stop hue-rotate ring)

### Color system — final

**CAT set (editorial, muted)**
- `--cat-visa` `#4a8ec4` bg 14% / border 38%
- `--cat-business` `#5cb88a` bg 14% / border 38%
- `--cat-tax` `#b89a40` bg 15% / border 42% ← corrected from #d4a853
- `--cat-property` `#9880d8` bg 14% / border 40%
- `--cat-living` `var(--bz-primary)` = Palette D red
- `--cat-emerging` `#4ab8c4` bg 14% / border 38%

**STATE set (kanban bright)**
- `--st-inquiry` `#9ca3af` (gray)
- `--st-wait` `#fb923c → #f97316` (orange)
- `--st-invoice` `#facc15 → #eab308` (yellow)
- `--st-active` `#3b82f6 → #2563eb` (blue)
- `--st-done` `#22c55e → #16a34a` (green)
- `--st-fail` `#f87171 / #ef4444 → #dc2626` (red soft)

Each: `from/to` gradient pair + `bg` (3-4%) + `border` (7-9%) + `badge` (12%).

**Palette D dark-mode canonical**
- `--bz-base` `#0a0a0a` — viewport
- `--bz-base-cinematic` `#000000` — hero cinematic
- `--bz-surface` `#141414` — card base
- `--bz-surface-elevated` `#1f1f1f` — modal
- `--bz-primary` `#ff2d4c` — signal red (the only brand color)
- `--bz-text-primary` `#f5f5f5` — body
- `--bz-text-secondary` `#a3a3a3` — meta
- `--bz-text-muted` `#737373` — disabled
- `--bz-text-faint` `#525252` — placeholder
- `--bz-border` `rgba(255,255,255,0.08)` — divider

### Performance metrics (Playwright + Chrome extension)

| Page | DOM | Layout ms | Scroll H | Verdict |
|---|---|---|---|---|
| marketing | 213 | 5.30 | 3033px | ✅ |
| visa service | 213 | 7.80 | 3822px | ⚠️ |
| dashboard | 674 | 11.70 | 2005px | ⚠️ under budget |
| portal | 75 | 2.50 | 947px | ✅ fluido |
| kbli home | 95 | 2.70 | 1489px | ✅ |
| portal/visa | 149 | 1.50 | 2065px | ✅ fluido |
| kbli/56101 | 158 | 3.10 | 2501px | ✅ |

Frame budget: 16.67ms. All pages under budget. Dashboard is worst case at 11.7ms (leaves 5ms margin).

Stress tests passed: 70 tab switches (p95 3.9ms), 100 pointermove on tilt (avg 0.133ms), 8 scroll jumps on longest page (avg 0.25ms).

### Bugs found and fixed

1. **`#page-dashboard { display: grid }` without `.active` modifier** — dashboard was ALWAYS visible regardless of active tab. Fixed to `#page-dashboard.active`.
2. **View Transitions never committed on hidden tab** — `document.startViewTransition` awaits next paint frame, which never comes when tab is hidden. Fixed with `!document.hidden` guard, fallback to direct swap.
3. **Tab bar overflow at 1131px width** — 7 tabs didn't fit. Fixed with `overflow-x: auto`, compact padding, mask-image fade on edges.
4. **Aurora `body::after` z-index** — had z-index 0 so vignette `body::before` (z-index 1) hid it. Fixed swap to `::after` z-index 1, `::before` z-index 0.
5. **Logo + "Bali Zero" text redundancy** — the PNG already contains the wordmark. Removed text in navs/footers where logo is ≥40px.

---

## Next steps (what's not done)

### Tier 1 — ship-ready polish (1–2h)
- [ ] **Review chromatic text on low-contrast backgrounds** — the `Restaurants` heading shift 1.2px may be too subtle or too aggressive on some displays
- [ ] **Add `@media (prefers-reduced-motion)`** guards to: aurora animation, rotating conic, marquee, rolling ticker, marketing sticky-reveal
- [ ] **Test mobile breakpoint** — the draft is optimized for 1131–1920 desktop; all `grid-template-columns: repeat(N, 1fr)` need `@media (max-width: 768px)` fallback
- [ ] **Screenshot all 7 pages on iPhone 14 viewport** (390×844) to audit mobile rendering
- [ ] **Add empty states** — dashboard pipeline when no rows, portal timeline when no activity, intel feed when offline
- [ ] **Accessibility audit via Lighthouse**: target >95 for accessibility, check color contrast AAA on all state badges
- [ ] **Remove legacy `--hue-*` aliases** now that all selectors use `--cat-*` / `--st-*`
- [ ] **Consolidate duplicate CSS blocks** — the techover override block has some redundancy with the base `.service-card` rules

### Tier 2 — missing pages (3–4h)
Pages from `apps/mouth` that are NOT yet in the draft but are key:
- [ ] **`(workspace)/process/page.tsx`** (2209 lines!) — the kanban view, the color grammar source; would be the most visually rich page
- [ ] **`(workspace)/clients/page.tsx`** — clients list with filters/search/RBAC
- [ ] **`(workspace)/intelligence/page.tsx`** — Intelligence Center hub
- [ ] **`(workspace)/hr/leave/page.tsx`** — HR/Leave with the pricing-colors pattern
- [ ] **`(workspace)/lkpm/page.tsx`** — LKPM quarterly reports
- [ ] **`(workspace)/revenue/page.tsx`** — Revenue dashboard
- [ ] **`(workspace)/analytics/page.tsx`** — Analytics
- [ ] **`chat/page.tsx`** — Zantara AI chat interface
- [ ] **`(blog)/services/[slug]/page.tsx`** for `company` / `tax` / `property` — each service has its own color logic
- [ ] **`portal/(authenticated)/companies/page.tsx`** — portal company view
- [ ] **`portal/(authenticated)/vault/page.tsx`** — document vault

### Tier 3 — design system productization (1–2 days)
Right now the draft is a **prototype** with all tokens inlined. To use this in production:
- [ ] **Extract `--cat-*` + `--st-*` tokens** to `packages/core/styles/bz-tokens.css` as additional layer
- [ ] **Create `packages/core/styles/bz-tokens-kanban.css`** — imports from `kanban-colors.ts` as CSS vars
- [ ] **Write `packages/core/components/BzRing.tsx`** — React port of `.bz-ring` with props
- [ ] **Write `packages/core/components/BzSparkline.tsx`** — from the sparkline utility
- [ ] **Write `packages/core/components/BzGlowBorder.tsx`** — mouse-aware glow wrapper
- [ ] **Write `packages/core/components/BzCmdK.tsx`** — command palette
- [ ] **Write `packages/core/components/BzHeatmap.tsx`** — heatmap component
- [ ] **Apply the Palette D tokens in `apps/mouth/src/app/globals.css`** (the file that today still has Warm Depth `#d4845a` copper)
- [ ] **Convert `(blog)/services/[slug]/page.tsx`** from `bg-[#0a2540]` navy to Palette D tokens
- [ ] **Port dashboard live window** from `HeroLiveWindow.tsx` to use new tokens

### Tier 4 — real content integration (2–3 days)
- [ ] **Replace demo data** with real API calls:
  - dashboard live window → `/api/blog/homepage-hero`
  - dashboard metric bar → `useDashboardData()` hook
  - pipeline rows → `/api/crm/practices`
  - team activity → `/api/admin/team-activity/team-stats`
  - portal timeline → `usePortalTimeline`
- [ ] **Wire the ⌘K palette** to `/api/search` (clients + practices + KBLI + actions)
- [ ] **Wire Zantara card** to `/api/chat` with streaming
- [ ] **Connect Fly.io health strip** to real uptime/p95/capacity metrics

### Tier 5 — deploy & monitor (1 day)
- [ ] **Push Palette D branch** to staging Vercel
- [ ] **A/B test** Marketing page old vs new on 10% traffic
- [ ] **Playwright visual regression suite** — baseline the 7 full-page screenshots, fail CI on unexpected diff
- [ ] **Lighthouse CI** — track performance/accessibility over time
- [ ] **GA4 event tracking** — click rates on new interactions (tilt, magnetic, ⌘K usage, marquee click)
- [ ] **Roll out** to channels in order: web (least risk) → workspace/dashboard → portal → marketing (most risk)

### Tier 6 — the wider rebrand (1 week)
- [ ] **Apply Palette D tokens** to all 8 satellite apps (`calendar`, `drive`, `mail`, `knowledge`, `admin-dashboard`, `web`, `osint-nexus-ui`) via `packages/core/styles/bz-tokens.css` import
- [ ] **Channels rebrand**: email HTML template with dark/light MSO-safe, Slack Block Kit colors, Google Chat Cards v2 imageUrl, WhatsApp formatter quote style
- [ ] **Logo asset regeneration**: PNG 2048/1024/512/256/64 + SVG + favicon + apple-touch + maskable PWA
- [ ] **Brand book** PDF with tokens + do/don't + examples
- [ ] **Update `CLAUDE.md`** in `apps/mouth` with Palette D as new default
- [ ] **Retire Warm Depth** tokens from `packages/core/styles/bz-tokens.css` after full migration

---

## Important decisions taken in session

| Decision | Why | Date |
|---|---|---|
| Logo + "Bali Zero" text = ridondante | Logo PNG contiene già wordmark | 2026-04-11 |
| CAT set uses `#b89a40` not `#d4a853` | Match dashboard `CATEGORY_COLOR` source | 2026-04-11 |
| Rotating conic only on ONE card per page | Più = rumore, perde "wow" | 2026-04-11 |
| Standard tier = on_process blu (not red popular) | Tier = state progression | 2026-04-11 |
| Golden Visa tier = completed green | Premium = "your life completed" | 2026-04-11 |
| OSINT UI stays on Surveillance palette | OPSEC separation on purpose | 2026-04-11 |
| Aurora respects prefers-reduced-motion | Accessibility non-negotiable | 2026-04-11 |
| Use Real images from `apps/mouth/public/static` | No stock, no lorem | 2026-04-11 |
| View Transitions with `!document.hidden` guard | Fixes hidden tab edge case | 2026-04-12 |
| Dashboard `#page-dashboard.active` | Fix display override bug | 2026-04-12 |
| Tab bar overflow scroll + mask fade | Fix 7-tab overflow at 1131px | 2026-04-12 |

---

## Files to commit (if approved)

```
docs/design-palettes/
  bz-multichannel-draft.html        # 58 KB
  bz-pages-draft.html               # 224 KB  ← the 7-page prototype
  SESSION-SUMMARY.md                # this file
  balizero-logo.png                 # copy of HD logo
  screenshots/                      # 7 reference PNGs
    bz-01-marketing.png
    bz-02-visa-service.png
    bz-03-dashboard.png
    bz-04-portal.png
    bz-05-kbli-home.png
    bz-06-portal-visa.png
    bz-07-kbli-detail.png
  research/                         # research inputs
    MASTER-synthesis.md
    ORIGINAL-color-inventory.md
    claude-exa-futuristic-dark-ui.md
    gemini-futuristic-dark-ui.md
    deepseek-futuristic-dark-ui.md
    codex-futuristic-dark-ui.md
```

Symlinks (`hero-images/`, `article-images/`, `kbli-images/`) should NOT be committed — they point to repo assets already versioned.

---

*End of session summary. Total session elapsed: ~8h. Lines of HTML/CSS/JS written in draft: ~6100. Techniques applied: 34. Pages replicated: 7. Bugs fixed: 5. Files in research: 6.*
