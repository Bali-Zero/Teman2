import type { CSSProperties } from "react";

/**
 * R19 DIRECTION A — the family language of the four product funnels
 * (second-home, voa, visa-oracle, kbli). Owner ruling 2026-09-24 (BRIEF-v2 §1):
 * the funnels adopt R19 Direction A instead of keeping their own systems.
 *
 * INPUTS: branch `origin/codex/website-r19-integrated`, paths under
 * `apps/website/src/`. Direction A proper is `components/entry.css:316-327`
 * ("Owner-approved direction A", 2026-09-07); the Oracle restates the same hexes
 * in `features/visa-oracle/atlas.css:9-16`. Every token names its input on its
 * own line, so a value that cannot be traced back to R19 does not belong here.
 *
 * SCOPING CONTRACT (inherited from rumahVars.ts / merahPutihDayVars.ts):
 *   - Apply INLINE on the converted route's own top-level wrapper, NEVER on a
 *     shared layout.tsx. Custom properties inherit; nothing outside the wrapper
 *     moves. No file under `packages/core/tokens/` changes.
 *   - The same wrapper carries `R19_CLASS` (hooks `src/styles/r19-direction-a.css`)
 *     AND `r19FontClassName` from `./r19Fonts`. The font class must sit on the
 *     SAME element or an ancestor: `--font-serif` / `--font-sans` below read
 *     `var(--font-r19-*)`, and a var() inside a custom property is substituted
 *     at the element that declares it (the alias trap explained below).
 *
 * CONTRAST (WCAG 2.x, recomputed from these exact values by `r19Vars.test.ts`):
 *   text-primary #1D2C3B on base 12.96 · on sunken 11.17 · on raised 13.91
 *   text-secondary #58626B on base 5.67 · on raised 6.08 · on wash 4.88
 *   #FFFCF7 on copper #A44B36 5.64 · on copper-hover #843719 8.07
 *   copper on base 5.26 · structure #233D52 on base 10.28
 *   control-border #7B817F on base 3.62 · on raised 3.88 (≥3 non-text)
 *   DUTY LIMITS — these hexes are ruled, their USE is constrained instead:
 *   line #DAD8D1 on base 1.30 → decorative dividers only, never the sole
 *     boundary of an interactive component (WCAG 2.2 SC 1.4.11).
 *   border-strong #A8ACA9 on base 2.09 → structural rules only. Unlike
 *     MERAH_PUTIH_DAY_VARS (where it is the 3.64 input boundary), here it is
 *     NOT an interactive boundary: controls read `--r19-control-border`.
 */
export const R19_DIRECTION_A_VARS = {
  // ── Grounds ────────────────────────────────────────────────────────────────
  "--surface-base": "#F7F4EE", // entry.css:318 --paper
  "--surface-base-solid": "#F7F4EE", // entry.css:318 --paper (solid form: nav band, print)
  "--surface-raised": "#FFFCF7", // entry.css:324 --surface
  "--surface-sunken": "#EAE3D8", // entry.css:325 --wash
  "--surface-deep": "#EAE3D8", // entry.css:325 --wash
  "--bz-elevated": "#FFFCF7", // entry.css:324 --surface (portal name, restated at visa-tools.css:31)

  // ── Ink ────────────────────────────────────────────────────────────────────
  "--text-primary": "#1D2C3B", // entry.css:319 --ink
  "--foreground": "#1D2C3B", // entry.css:319 --ink
  "--text-secondary": "#58626B", // entry.css:322 --muted
  "--text-tertiary": "#58626B", // entry.css:322 --muted (Direction A has one muted ink)
  "--text-on-accent": "#FFFCF7", // atlas.css:10 --oracle-action-ink
  "--cta-primary-fg": "#FFFCF7", // atlas.css:10 --oracle-action-ink

  // ── Boundaries ─────────────────────────────────────────────────────────────
  "--border-subtle": "#DAD8D1", // entry.css:323 --line — decorative only (1.30:1)
  "--border-default": "#DAD8D1", // entry.css:323 --line — decorative only (1.30:1)
  "--border-strong": "#A8ACA9", // atlas.css:12 --oracle-border-strong — structural only (2.09:1)

  // ── Aliases that MUST be restated, not inherited ──────────────────────────
  // `semantic.css` declares these at :root as var() over tokens this set
  // overrides. A var() inside a custom property is substituted AT THE DECLARING
  // ELEMENT, so the :root alias keeps the shell theme's value and hands it down
  // by inheritance — a wrapper override of the source token does not move it.
  // Same trap, same cure as MERAH_PUTIH_DAY_VARS lines 84-96.
  "--color-text-muted": "#58626B", // = --text-secondary (semantic.css:129), entry.css:322
  "--color-border-subtle": "#DAD8D1", // = --border-subtle (semantic.css:130), entry.css:323
  "--footer-text": "#58626B", // = --text-tertiary (semantic.css:50), entry.css:322
  "--cta-bg": "#A44B36", // = --accent-funnel (semantic.css:59), entry.css:321 --copper
  "--cta-bg-hover": "#843719", // semantic.css:60 alias; design-system.module.css:9 --bz-color-copper-hover
  // ConsentBanner's portal vocabulary (see MERAH_PUTIH_DAY_VARS) — R19 restates it too.
  "--tx-secondary": "#58626B", // visa-tools.css:32, entry.css:322
  "--bz-accent": "#A44B36", // visa-tools.css:33, entry.css:321

  // ── Action (copper is the single primary action) ──────────────────────────
  "--accent-funnel": "#A44B36", // entry.css:321 --copper
  "--accent-funnel-text": "#A44B36", // visa-tools.css:18
  "--cta-primary-bg": "#A44B36", // entry.css:321 --copper
  "--text-link": "#A44B36", // visa-tools.css:22

  // ── Shell ──────────────────────────────────────────────────────────────────
  "--nav-bg": "#F7F4EE", // entry.css:318 --paper (slim header on paper)
  "--footer-bg": "#EEE9E1", // Footer.module.css:2

  // ── Typography (fonts mounted by ./r19Fonts on the same wrapper) ──────────
  "--font-serif": 'var(--font-r19-serif), "Fraunces", Georgia, serif', // entry.css:326 --serif
  "--font-sans": 'var(--font-r19-sans), "Manrope", Arial, sans-serif', // entry.css:327 --sans

  // ── R19-only hooks (read by src/styles/r19-direction-a.css) ───────────────
  "--r19-structure": "#233D52", // entry.css:320 --forest (canopy)
  "--r19-copper": "#A44B36", // entry.css:321 --copper
  "--r19-copper-hover": "#843719", // design-system.module.css:9 --bz-color-copper-hover
  "--r19-ink-muted": "#58626B", // entry.css:322 --muted
  "--r19-wash": "#EAE3D8", // entry.css:325 --wash
  "--r19-line": "#DAD8D1", // entry.css:323 --line
  "--r19-line-strong": "#A8ACA9", // atlas.css:12 --oracle-border-strong
  "--r19-control-border": "#7B817F", // atlas.css:12 --oracle-control-border
  "--r19-radius-control": "3px", // visa-tools.css:179 primary action radius
  "--r19-radius-card": "4px", // design-system.module.css:30 0.25rem (flatter Direction A card)
  "--r19-focus": "0 0 0 3px #A44B36", // visa-tools.css:81 3px copper (drawn as outline, offset 3px)
  "--r19-shadow-header": "0 12px 20px #20282412", // entry.css:257 sticky header
  "--color-scheme": "light", // atlas.css:8 color-scheme
} as CSSProperties;

/**
 * Marker className paired with `R19_DIRECTION_A_VARS` on every converted
 * wrapper. Hooks the scoped roles in `src/styles/r19-direction-a.css`.
 */
export const R19_CLASS = "r19-direction-a";
