# kita.balizero.com — Creative Track Proposal: Theme-Layer Directions

> **Date:** 2026-06-12
> **Track:** Creative (proposal only — owner decides; nothing here ships code)
> **Scope:** design-token/theme layer + before/after mockups for the kita workspace
> **Brand soul anchors (untouched):** dark UI · "raw stone + molten gold" · display serif · "Order from the raw / NILAI" · 3ALI ZERO logo
> **Deliverables in this folder:**
>
> - `PROPOSAL.md` (this file)
> - `tokens-draft.css` (drop-in theme-layer draft, three theme classes)
> - `mockup-1-molten-ledger.html` (before/after, self-contained)
> - `mockup-2-stone-editorial.html` (before/after, self-contained)
> - `mockup-3-kintsugi-seam.html` (before/after, self-contained)

---

## 0. TL;DR for the owner

Three named directions, each a **theme-class token swap** over the existing `--bz-*` vocabulary — no component rewrites, no new JS, no total reskin:

| #   | Direction           | One-line thesis                                                                                                                                                                              |
| --- | ------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | **Molten Ledger**   | Terminal-grade operator density: warm near-black basalt, ONE molten-gold signal color, tabular numerals everywhere — Bloomberg DNA with Bali Zero soul.                                      |
| 2   | **Stone Editorial** | Calm boutique-legal surface: warm stone base, Cormorant Garamond display serif promoted into the workspace, copper kept but spent sparingly, elevation by light not shadow.                  |
| 3   | **Kintsugi Seam**   | The brand metaphor made structural: UI panels are stone slabs, gold gradient hairlines are the kintsugi seams that join them; gold reserved for seams, focus, and the single primary action. |

**Recommendation: Direction 3 (Kintsugi Seam)** with Direction 1's numeric/typography discipline folded in. Rationale in §6.

**Bonus finding:** the current live token `--bz-text-muted: #475569` **fails WCAG AA at 1.97:1** on `--bz-bg #1d273b` (verified with the WCAG relative-luminance formula). All three directions fix this for free; it should be fixed even if no direction is adopted.

---

## 1. The "before" baseline (ground truth, read from disk 2026-06-12)

### 1.1 Live token file

`packages/design-system/tokens/bz-tokens.css` (182 lines, "Single Source of Truth", v0.1.0) — dark default:

| Token                 | Live value                 | Role                       |
| --------------------- | -------------------------- | -------------------------- |
| `--bz-bg`             | `#1d273b` (anthracite-900) | page background            |
| `--bz-bg-elevated`    | `#243047`                  | cards                      |
| `--bz-bg-surface`     | `#2a3655`                  | nested containers          |
| `--bz-accent`         | `#d4845a` (copper)         | primary accent             |
| `--bz-gold`           | `#D4A853`                  | secondary warm             |
| `--bz-text-primary`   | `#f8fafc`                  | body                       |
| `--bz-text-secondary` | `#94a3b8`                  | meta                       |
| `--bz-text-muted`     | `#475569`                  | muted — **AA FAIL 1.97:1** |
| `--bz-border`         | `rgba(255,255,255,0.08)`   | divider                    |
| Radii                 | 6 / 10 / 14 / 20 px        | —                          |
| Shadows               | 3 tiers + copper glow      | —                          |

### 1.2 Parallel system (context, not target)

`packages/core/tokens/` ships a second, layered system (primitives → semantic → 9 themes) with `--surface-base: #121016` "Warm Graphite", funnel accents (visa red `#ff2d4c`, kbli gold `#eab308`, tax cyan, property green), editorial accents (`--accent-warm: #d4845a`, `--accent-gold-muted: #c9a96e`), `--font-serif: "Cormorant Garamond"` and motion tokens **already wired to `prefers-reduced-motion`**. The workspace persona (`operative-dark.css`) keeps sans headings; the editorial persona uses the serif. This proposal **reuses that architecture pattern** (3 layers + theme class) rather than inventing a new one. Note: `.claude/rules/frontend-nextjs.md` still references `packages/core/styles/bz-tokens.css` / `--bz-base: #0c0c0e` — stale path; the live `--bz-*` file is the one in §1.1.

### 1.3 What the workspace pages actually render

Read from `apps/mouth/src/app/(workspace)/dashboard/page.tsx` (774 lines) and `clients/page.tsx` (1333 lines):

- KPI metric chips: `text-[9px] uppercase tracking-[.10em] text-white/30` labels + `text-[22px] font-black` values colored per-metric inline.
- Pipeline rows: client name `text-[11px] text-white/80`, practice title `text-[10px] text-white/35`, status dot colors hardcoded (`inquiry #9ca3af`, `quotation/documents #b89a40`, `in_progress #4a8ec4`, `completed #5cb88a`), deadline chips `#c45c78` expired / `#b89a40` urgent.
- Category stripe colors hardcoded: `visas #4a8ec4`, `business #5cb88a`, `taxes #b89a40`, `property #9880d8`, `living #d4845a`, `emerging #4ab8c4`.
- Lots of `bg-white/[0.04]`, `rgba(45,40,35,0.7)` warm browns, copper `#d4845a` inline — i.e. **style drift off the token layer** (exactly the pitfall the 2026 token literature warns about, §2).

### 1.4 Brand soul, verified on disk

`apps/mouth/src/app/login/page.tsx` L298–331: kintsugi stone image, `font-serif text-amber-100/90` "Order from the raw", `#D4AF37`/50 gold hairline, `tracking-[0.6em]` "N I L A I". This is the soul every direction below must serve, not replace.

---

## 2. Fresh research (June 2026) — what's actionable

Six-plus sources, fetched/searched 2026-06-12. Hype discarded; only what serves a dark, editorial, operator-dense UI with a stone+gold soul.

1. **Single-accent discipline is the 2026 consensus for dark dashboards.** "Pick one accent color for dark mode and let everything else sit in neutral greys. Restraint is what makes a dark interface feel premium" — with Sentry (red=error), Railway (green=healthy) as the state-driven pattern. Kita's copper currently does _everything_ (active nav, glow, badges, banners); 2026 practice says the brand accent should be spent on **the one action that matters**, with state colors doing functional work. — [925 Studios, SaaS Dashboard Design 2026](https://www.925studios.co/blog/saas-dashboard-design-examples-2026)

2. **Three-layer token architecture + OKLCH primitives.** Primitives (`oklch(L C H)`) → semantic ("never skip semantic tokens — they're what makes refactors safe") → component. Style drift (arbitrary `pl-[17px]`, hardcoded hex) is named the #1 failure mode — which is precisely what §1.3 found in the kita pages. Motion tokens (duration/easing) belong in the token layer too. — [Mavik Labs, Design Tokens That Scale in 2026](https://www.maviklabs.com/blog/design-tokens-tailwind-v4-2026/)

3. **Terminal DNA for data-dense operator UIs.** The "Fortress" pattern: dense tables, monospace/tabular numerics, amber-gold accents, layouts optimized for scanning thousands of rows without fatigue — explicitly Bloomberg-terminal-derived, and explicitly compatible with density when contrast discipline holds. Separately: show 5–9 core elements on the default view, progressive disclosure for the rest. — [Muz.li, Best Dashboard Design 2026](https://muz.li/blog/best-dashboard-design-examples-inspirations-for-2026/) + [925 Studios](https://www.925studios.co/blog/saas-dashboard-design-examples-2026)

4. **Dark-mode accessibility specifics.** AA is 4.5:1 normal text / 3:1 large text + UI components _per theme_; avoid pure black (use very dark grey — halation: pure white on pure black "glows" for astigmatic users); signal elevation with **lighter surfaces and tonal shifts, not shadows**. — [AccessibilityChecker, Dark Mode Accessibility](https://www.accessibilitychecker.org/blog/dark-mode-accessibility/) + [greeden.me, WCAG 2.1 AA dark-mode guide](https://blog.greeden.me/en/2026/02/23/complete-accessibility-guide-for-dark-mode-and-high-contrast-color-design-contrast-validation-respecting-os-settings-icons-images-and-focus-visibility-wcag-2-1-aa/)

5. **Tabular numerals beat monospace for data columns.** `font-variant-numeric: tabular-nums` in a proportional font gives aligned, scannable columns ("$1,111.11 must not look smaller than $999.99"); right-align numbers; monospace only for codes/IDs. — [Pencil & Paper, Data Table UX Patterns](https://www.pencilandpaper.io/articles/ux-pattern-analysis-enterprise-data-tables) + [Kombai, font-variant-numeric](https://kombai.com/tailwind/font-variant-numeric/)

6. **Fluid type via `clamp()`, Minor Third (1.2) ratio for dense UIs.** Asymmetric clamping (headings compress more aggressively on small viewports) preserves hierarchy without breakpoints. — [fluid-type-scale.com](https://www.fluid-type-scale.com/) + [Always Twisted, fluid scales with clamp()](https://www.alwaystwisted.com/articles/building-fluid-typographic-scales-with-clamp-and-heading)

7. **Motion restraint + semantic motion tokens.** 2026 systems (Atlassian, Carbon) name motion by intent, keep everyday UI motion "efficient and focused", and treat `prefers-reduced-motion` as non-negotiable. Glassmorphism survives only in its restrained form: subtle translucency + noise texture + gradient borders, not heavy blur. — [Atlassian Design, Motion](https://atlassian.design/foundations/motion) + [Midrocket, UI Design Trends 2026](https://midrocket.com/en/guides/ui-design-trends-2026/)

**Discarded as hype for this context:** AI-generated layout trends, heavy glassmorphism, 3D/spatial UI, scroll-driven theatrics — wrong register for a legal/immigration operator console.

---

## 3. Direction 1 — **Molten Ledger**

### Thesis

Kita is an operator console for people who scan case rows all day. Molten Ledger commits to that: a warm near-black basalt ground (stone, not navy), a single molten-gold signal color descended from the login page's `#D4AF37` seam, tabular numerals on every figure, IBM Plex Mono reserved for case codes and money. Density is a feature; the gold is rationed like ink. The display serif appears exactly once per page — the page title — as the editorial signature. This is the Bloomberg-terminal register translated into Bali Zero's material language.

### Token deltas vs current

| Token                 | Before (live)           | After (D1)                                                             | Note                                                      |
| --------------------- | ----------------------- | ---------------------------------------------------------------------- | --------------------------------------------------------- |
| `--bz-bg`             | `#1d273b`               | `#0E0D0B`                                                              | navy → warm basalt near-black (not pure black — halation) |
| `--bz-bg-elevated`    | `#243047`               | `#161412`                                                              | elevation by lightness step                               |
| `--bz-bg-surface`     | `#2a3655`               | `#1E1B17`                                                              | second elevation step                                     |
| `--bz-accent`         | `#d4845a` copper        | `#E3B341` molten gold                                                  | single signal color                                       |
| `--bz-accent-glow`    | `rgba(212,132,90,.3)`   | `rgba(227,179,65,.25)`                                                 |                                                           |
| `--bz-text-primary`   | `#f8fafc` cool          | `#F2EDE4` warm off-white                                               | warm undertone matches stone                              |
| `--bz-text-secondary` | `#94a3b8`               | `#A8A096`                                                              |                                                           |
| `--bz-text-muted`     | `#475569` **(AA FAIL)** | `#8A8276`                                                              | fixed: 5.12:1                                             |
| `--bz-border`         | `rgba(255,255,255,.08)` | `rgba(227,179,65,.12)` gold hairline / `rgba(255,255,255,.07)` neutral | gold hairlines only on section seams                      |
| `--bz-success`        | `#4db87a`               | `#4DBE8A`                                                              | state set recalibrated for AA on new base                 |
| `--bz-error`          | `#d95f5a`               | `#E5746A`                                                              |                                                           |
| `--bz-info` (new)     | —                       | `#6CA9E8`                                                              | replaces hardcoded `#4a8ec4`                              |

### Typography stance

- Display serif (Cormorant Garamond 600) **only** for the page `<h1>` — one serif moment per screen.
- Inter for everything else; **`font-variant-numeric: tabular-nums` on all KPI values, deadlines, money** (today the pages sprinkle `tabular-nums` utility inconsistently).
- IBM Plex Mono for case/practice codes (`BZ-2026-0847`).
- Fluid scale, Minor Third 1.2: `--bz-fs-display: clamp(1.5rem, 1.2rem + 1.2vw, 2.1rem)`.

### Accent logic

State-driven (post-P1.5 news accent already is): gold = "act here" (exactly one primary action per view + active nav item). Status colors carry workflow state, category colors carry editorial taxonomy — both desaturated one notch so gold always wins the eye.

### Motion policy

Hover transitions ≤150ms, `cubic-bezier(0.4,0,0.2,1)`; no ambient animation at all. `@media (prefers-reduced-motion: reduce)` zeroes all transitions (inherits the existing primitives.css pattern).

### WCAG AA verification (computed, WCAG 2.x relative-luminance formula)

| Pair                                      | Ratio       | Verdict  |
| ----------------------------------------- | ----------- | -------- |
| `#F2EDE4` on `#0E0D0B`                    | **16.66:1** | AA + AAA |
| `#F2EDE4` on `#161412`                    | **15.76:1** | AA + AAA |
| `#A8A096` on `#0E0D0B`                    | **7.52:1**  | AA + AAA |
| `#A8A096` on `#161412`                    | **7.12:1**  | AA + AAA |
| `#8A8276` (muted) on `#0E0D0B`            | **5.12:1**  | AA       |
| `#8A8276` (muted) on `#161412`            | **4.84:1**  | AA       |
| `#E3B341` (gold) on `#0E0D0B`             | **9.98:1**  | AA + AAA |
| `#E3B341` on `#161412`                    | **9.44:1**  | AA + AAA |
| `#1A1205` on `#E3B341` (CTA text on gold) | **9.53:1**  | AA + AAA |
| `#4DBE8A` success on base                 | **8.37:1**  | AA + AAA |
| `#E5746A` danger on base                  | **6.51:1**  | AA       |
| `#6CA9E8` info on base                    | **7.84:1**  | AA + AAA |

### Performance budget

- Fonts: Inter variable (already loaded) + Cormorant Garamond 600 (1 weight, ~30KB woff2) + IBM Plex Mono 400 (~25KB). **Net new: ≤2 font files / ≤60KB** (Cormorant already ships for the editorial persona — likely 0 net new on shared cache).
- Zero new JS. Zero `backdrop-filter` (the heaviest CSS effect is one `linear-gradient` hairline).
- Token swap = CSS variable reassignment: no layout change, CLS 0, no repaint cost beyond first paint.
- Reference budget held: dashboard worst-case layout was 11.7ms (SESSION-SUMMARY perf audit) — this direction removes effects, it cannot regress that.

**Mockup:** `mockup-1-molten-ledger.html`

---

## 4. Direction 2 — **Stone Editorial**

### Thesis

Kita's users are not traders; they are consultants handling people's visas and companies. Stone Editorial lowers the temperature: a warm stone base, copper retained as the single accent but spent only on the primary action, the Cormorant Garamond display serif promoted from the login page into section headings — so the workspace finally speaks the same editorial voice as balizero.com. Density yields to calm: bigger line-height, fewer borders (elevation via lighter surfaces, per 2026 dark-mode practice), progressive disclosure instead of wall-of-rows. The 5–9-elements rule governs the default view.

### Token deltas vs current

| Token                 | Before (live)           | After (D2)                      | Note                                                           |
| --------------------- | ----------------------- | ------------------------------- | -------------------------------------------------------------- |
| `--bz-bg`             | `#1d273b`               | `#131110`                       | warm basalt, one step lighter than D1                          |
| `--bz-bg-elevated`    | `#243047`               | `#1B1815`                       |                                                                |
| `--bz-bg-surface`     | `#2a3655`               | `#232019`                       |                                                                |
| `--bz-accent`         | `#d4845a`               | `#D98E62`                       | copper kept, lifted for AA headroom on darker base             |
| `--bz-gold`           | `#D4A853`               | `#D4AF37`                       | aligned to the login-page seam gold; decorative hairlines only |
| `--bz-text-primary`   | `#f8fafc`               | `#EFE9DE` warm parchment        |                                                                |
| `--bz-text-secondary` | `#94a3b8`               | `#D6CFC4` body / `#9C948A` meta | two-tier instead of one                                        |
| `--bz-text-muted`     | `#475569` **(AA FAIL)** | `#9C948A`                       | fixed: 6.29:1                                                  |
| `--bz-border`         | `rgba(255,255,255,.08)` | `rgba(239,233,222,.06)`         | softer; borders demoted, elevation promoted                    |
| `--bz-radius-lg`      | 14px                    | 16px                            | slightly rounder, calmer                                       |
| `--bz-shadow-card`    | 3-layer + ring          | single soft ambient             | shadows demoted per dark-mode elevation research               |

### Typography stance

- Cormorant Garamond 600 for page title **and** card/section headings (the editorial promotion — this is the visible difference).
- Inter body at 13–14px (up from the current 10–11px micro-text), line-height 1.55.
- `tabular-nums` on figures; serif **never** used for data.
- Fluid scale Major Third 1.25 for headings (calmer hierarchy needs wider steps).

### Accent logic

Copper = the one primary action per view. Gold `#D4AF37` exists only as non-text hairline (passes 3:1 UI-component at 8.95:1, so it can also carry small icons if ever needed). State colors unchanged from D1's recalibrated set. Category stripes muted to 60% opacity, as today.

### Motion policy

One motion idea only: 250ms ease-out fade-rise on card mount (the existing `--motion-duration-standard`). Everything else instant. Full `prefers-reduced-motion` zeroing.

### WCAG AA verification (computed)

| Pair                                                 | Ratio       | Verdict  |
| ---------------------------------------------------- | ----------- | -------- |
| `#EFE9DE` display on `#131110`                       | **15.58:1** | AA + AAA |
| `#D6CFC4` body on `#131110`                          | **12.18:1** | AA + AAA |
| `#9C948A` meta on `#131110`                          | **6.29:1**  | AA       |
| `#9C948A` meta on `#1B1815`                          | **5.91:1**  | AA       |
| `#D98E62` copper on `#131110`                        | **7.17:1**  | AA + AAA |
| `#D98E62` copper on `#1B1815`                        | **6.73:1**  | AA       |
| `#D4AF37` gold hairline vs `#131110` (UI, needs 3:1) | **8.95:1**  | PASS     |
| `#201409` on `#D98E62` (CTA text on copper)          | **6.86:1**  | AA       |

### Performance budget

- Fonts: Cormorant Garamond 600 is the only addition beyond Inter — and it already ships in the editorial persona bundle (`--font-serif` in `packages/core/tokens/primitives.css`), so **0 net-new font files** for users who have visited balizero.com; ≤1 file (~30KB) cold.
- Zero new JS; one CSS keyframe (mount fade) — removed under reduced-motion.
- Larger type + fewer rows = fewer DOM nodes per view (progressive disclosure), so layout cost goes **down**.

**Mockup:** `mockup-2-stone-editorial.html`

---

## 5. Direction 3 — **Kintsugi Seam**

### Thesis

The login page already states the philosophy: broken stone, joined with gold, worth more for the repair. Kintsugi Seam makes that the UI's structural grammar instead of a splash image. Panels are stone slabs (subtle grain, two elevation steps); where two slabs meet — section boundaries, the active nav item, the focused input, the one primary action — runs a **gold gradient seam** (`#8C6A1E → #D4AF37 → #F0D37A`), a 1–2px element that costs nothing to render. Current information density is **retained** (operators keep their rows); what changes is that structure is drawn by seams instead of boxes-in-boxes, and gold becomes the rarest, most meaningful pixel on screen. Numerals go tabular; the serif keeps its single page-title moment plus the KPI values — figures as editorial objects.

### Token deltas vs current

| Token                 | Before (live)           | After (D3)                                            | Note                                   |
| --------------------- | ----------------------- | ----------------------------------------------------- | -------------------------------------- |
| `--bz-bg`             | `#1d273b`               | `#100F0D`                                             | basalt between D1 and D2               |
| `--bz-bg-elevated`    | `#243047`               | `#181613`                                             | slab step 1                            |
| `--bz-bg-surface`     | `#2a3655`               | `#201D19`                                             | slab step 2                            |
| `--bz-accent`         | `#d4845a`               | `#DCB44A` seam gold                                   | text-grade gold                        |
| `--bz-seam` (new)     | —                       | `linear-gradient(135deg,#8C6A1E,#D4AF37 55%,#F0D37A)` | the kintsugi line; non-text decorative |
| `--bz-text-primary`   | `#f8fafc`               | `#F0EBE2`                                             |                                        |
| `--bz-text-secondary` | `#94a3b8`               | `#ABA399`                                             |                                        |
| `--bz-text-muted`     | `#475569` **(AA FAIL)** | `#ABA399` (merge tiers)                               | fixed: 7.69:1                          |
| `--bz-border`         | `rgba(255,255,255,.08)` | `rgba(240,235,226,.07)`                               | neutral hairline for non-seam edges    |
| category `visas`      | `#4a8ec4` (hardcoded)   | `--bz-cat-visa: #6FA8D6`                              | tokenized + AA                         |
| category `business`   | `#5cb88a` (hardcoded)   | `--bz-cat-business: #6FC59A`                          |                                        |
| category `taxes`      | `#b89a40` (hardcoded)   | `--bz-cat-tax: #C8A94E`                               |                                        |
| category `property`   | `#9880d8` (hardcoded)   | `--bz-cat-property: #AC97E0`                          |                                        |

(Categories move from hardcoded TSX constants into the token layer — fixing the §1.3/§2.2 style-drift finding as part of the theme work.)

### Typography stance

- Cormorant Garamond 600: page title + **KPI numerals** (the only place serif touches data — large display figures, where serif elegance reads and AA-large applies with 15:1+ headroom anyway).
- Inter for all rows/labels; `tabular-nums` on every aligned figure; IBM Plex Mono for codes.
- Fluid scale Minor Third 1.2 (density preserved).

### Accent logic

Strictly seam-driven: gold appears as (a) section seam hairlines, (b) active nav seam, (c) focus ring, (d) ONE primary action per view. Status and category colors do all other signaling — state-driven, never decorative. This is the most disciplined of the three: gold-as-fill is allowed nowhere except the primary CTA.

### Motion policy

One signature: the seam on the primary CTA carries a slow gradient shimmer (8s, `background-position`, GPU-cheap, one element per page). Hovers ≤150ms. **All of it — including the shimmer — dies under `prefers-reduced-motion: reduce`** (the mockup demonstrates the guard).

### WCAG AA verification (computed)

| Pair                                                                 | Ratio       | Verdict     |
| -------------------------------------------------------------------- | ----------- | ----------- |
| `#F0EBE2` on `#100F0D`                                               | **16.13:1** | AA + AAA    |
| `#ABA399` on `#100F0D`                                               | **7.69:1**  | AA + AAA    |
| `#ABA399` on `#181613`                                               | **7.25:1**  | AA + AAA    |
| `#DCB44A` gold on `#100F0D`                                          | **9.73:1**  | AA + AAA    |
| `#DCB44A` gold on `#181613`                                          | **9.17:1**  | AA + AAA    |
| `#6FA8D6` cat-visa on `#100F0D`                                      | **7.52:1**  | AA + AAA    |
| `#6FC59A` cat-business on `#100F0D`                                  | **9.24:1**  | AA + AAA    |
| `#C8A94E` cat-tax on `#100F0D`                                       | **8.43:1**  | AA + AAA    |
| `#C8A94E` cat-tax on `#181613`                                       | **7.95:1**  | AA          |
| `#AC97E0` cat-property on `#100F0D`                                  | **7.53:1**  | AA + AAA    |
| `#1A1205` on `#DCB44A` (CTA text on gold)                            | **9.42:1**  | AA + AAA    |
| Seam gradient (decorative, non-text) mid-stop `#D4AF37` vs `#100F0D` | **9.11:1**  | UI 3:1 PASS |

### Performance budget

- Fonts: same as D1 (Cormorant 600 + Plex Mono 400 — both already in the ecosystem; ≤2 cold files / ≤60KB, likely 0 net-new).
- Zero new JS. Seams are `linear-gradient` backgrounds on 1–2px elements — no `backdrop-filter`, no SVG filters, no shadows beyond one ambient tier.
- The one shimmer animates `background-position` on a single element (compositor-friendly) and is removed under reduced-motion. Everything else is static.
- Token swap + ~6 category-constant migrations: no DOM change, CLS 0.

**Mockup:** `mockup-3-kintsugi-seam.html`

---

## 6. Recommendation

**Adopt Direction 3 — Kintsugi Seam — and fold in Direction 1's numeric discipline** (tabular-nums everywhere, mono for codes; that part is a two-line token/utility change and belongs in any direction).

Why:

1. **It is the only direction that turns the brand soul into UI structure** rather than just a palette. "Order from the raw" stops being a login-page poster and becomes how every screen is built: raw stone slabs, gold seams.
2. **It preserves operator density** — Bali Zero staff scan case rows all day; D2's calm is beautiful but trades away rows the team actually uses. D3 changes zero information architecture.
3. **It is the cheapest to govern**: the accent rule ("gold only on seams, focus, and the one primary action") is binary and reviewable; copper-everywhere today is not.
4. It fixes two live defects en passant: the `#475569` AA failure and the hardcoded category/status hex drift.

Direction 1 is the strong second choice if the owner wants the boldest visual break. Direction 2 is the right register for the **client portal** (my.balizero.com) rather than the operator workspace — worth keeping in the drawer for that surface.

### Adoption path sketch (when/if a direction is chosen)

1. **Token layer** (~80 LOC): append the chosen theme block from `tokens-draft.css` to `packages/design-system/tokens/bz-tokens.css` as `[data-theme="kintsugi-seam"]` (or chosen direction) overriding the same `--bz-*` names. Dark default untouched.
2. **Feature flag** (~10 LOC): theme class set on `<html>` via the existing `data-theme` mechanism; gate with an env/flag (`NEXT_PUBLIC_KITA_THEME`) so it can flip per-environment and roll back by unsetting one attribute.
3. **Drift cleanup** (~60–120 LOC, incremental): migrate the dashboard/clients hardcoded hex (`CATEGORY_COLOR`, `STATUS_CONFIG`, inline `rgba(45,40,35,…)`) to the new `--bz-cat-*` / `--bz-st-*` tokens. This is the only component-file work, it is mechanical, and it pays back regardless of theme.
4. **QA**: existing post-deploy screenshot QA (CLAUDE.md §11) + the contrast table in this doc as the acceptance checklist.
5. Total estimate: **~150–250 LOC, no new dependencies, no new JS, fully reversible by removing one attribute.**

### What we do NOT change (brand-soul anchors)

- The 3ALI ZERO logo and the "Your 3ali, from ZerΩ" brand entrance — untouched on every surface.
- The login page (kintsugi stone, "Order from the raw", NILAI) — it is the source text; the theme quotes it, never edits it.
- Dark-first stance — no light-mode-by-default anywhere in the workspace.
- The display-serif identity (Cormorant Garamond) — re-weighted per direction, never removed or replaced.
- Funnel/category/status **meaning** — colors are recalibrated for contrast, but the semantic mapping (which color means what) is preserved exactly.
- The state-driven accent principle already shipped post-P1.5 for the news accent — extended, not reverted.
- OSINT-Nexus UI Surveillance palette (OPSEC separation by design, per the 2026-04-11 decision).
- Information architecture, routes, components, and density of the workspace — this is a skin at the token layer, not a redesign.

---

## 7. Method note

Contrast ratios computed with the WCAG 2.x relative-luminance formula (sRGB linearization, `(L1+0.05)/(L2+0.05)`) — script run 2026-06-12; every published pair verified, including the failing current token. Mockups are self-contained HTML (inline CSS, Google Fonts already used by the app: Inter, Cormorant Garamond, IBM Plex Mono), each showing the same dashboard fragment (KPI row + pipeline card rows) in before (current live tokens) and after (direction tokens), with realistic operator data and invented client names. Each mockup carries a working `@media (prefers-reduced-motion: reduce)` guard.
