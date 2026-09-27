import type { CSSProperties } from "react";
import { R19_VARS } from "@/components/r19/presentation";

/**
 * R19 DIRECTION A — the family language of the four product funnels
 * (second-home, voa, visa-oracle, kbli). Owner ruling 2026-09-24 (BRIEF-v2 §1):
 * the funnels adopt R19 Direction A instead of keeping their own systems.
 *
 * UNIFIED 2026-09-27 (gate B2 on PR #7508): this file used to restate the
 * whole Direction A palette from its own inputs (branch
 * `origin/codex/website-r19-integrated`), independently of the site-wide R19
 * shell that PR #7428/#7448 landed on main in the meantime
 * (components/r19/presentation.ts's `R19_VARS`). Two copies drifted apart on
 * three tokens (`--text-secondary` #58626B vs #435464, `--border-strong`
 * #A8ACA9 vs #a7a69f, `--text-on-accent`/`--cta-primary-fg` #FFFCF7 vs
 * #FFFFFF) and duplicated the Fraunces/Manrope font binaries under a second,
 * heavier (next/font, 125 KB + 24 KB) path. This file now SPREADS
 * `R19_VARS` first and adds only what it does not carry — a token this file
 * defines can therefore never again silently restate one main already has
 * at a different value; a later edit that tries will show up as a literal
 * duplicate key in review, not a divergent number six months later.
 *
 * Every alias below that means the same thing as an `R19_VARS` key reads it
 * with `var(--that-key)` rather than copying its literal, for the same
 * reason. Only tokens `R19_VARS` truly does not carry (control-border,
 * radii, focus ring, header shadow, hover states, the kbli-only nav-icon
 * triplet) stay literal.
 *
 * SCOPING CONTRACT (inherited from rumahVars.ts / merahPutihDayVars.ts):
 *   - Apply INLINE on the converted route's own top-level wrapper, NEVER on a
 *     shared layout.tsx. Custom properties inherit; nothing outside the wrapper
 *     moves. No file under `packages/core/tokens/` changes.
 *   - The wrapper carries `R19_CLASS` (hooks `src/styles/r19-direction-a.css`)
 *     and imports `src/styles/r19-fonts.css` (or a route that already loads
 *     `components/r19/R19Presentation.module.css`, which imports the same
 *     file) so the "R19 Fraunces"/"R19 Manrope" faces `--font-serif`/
 *     `--font-sans` name are actually registered — there is no longer a
 *     per-route next/font class to mount.
 *
 * CONTRAST (WCAG 2.x, recomputed from the RESOLVED values by `r19Vars.test.ts`,
 * which follows every `var()` alias back to its literal before measuring):
 *   text-primary #1D2C3B on base 12.96 · on sunken 11.17 · on raised 13.91
 *   text-secondary #435464 (from R19_VARS) on base/raised/wash — recomputed
 *   #FFFFFF on copper #A44B36 (from R19_VARS) — recomputed
 *   copper on base 5.26 · structure #233D52 on base 10.28
 *   control-border #7B817F on base 3.62 · on raised 3.88 (≥3 non-text)
 *   nav-icon-color #1D2C3B on nav-icon-bg #FFFCF7 — the B1 cure (2026-09-27):
 *     kbli's nav is opaque paper, not the dark funnel nav every OTHER
 *     non-R19 consumer of MobileNav has, so it must set this triplet itself.
 *   DUTY LIMITS — these hexes are ruled, their USE is constrained instead:
 *   line (`--border-subtle`, from R19_VARS) on base → decorative dividers
 *     only, never the sole boundary of an interactive component (WCAG 2.2
 *     SC 1.4.11).
 *   border-strong (from R19_VARS) on base → structural rules only, not an
 *     interactive boundary: controls read `--r19-control-border`.
 */
export const R19_DIRECTION_A_VARS = {
  // Every shared token comes from main's R19 shell, verbatim.
  ...R19_VARS,

  // ── --foreground (gate B3, PR #7508 round 3): a LITERAL, not a var()
  // alias, on purpose. kbli-theme.css's own `.kbli-paper` block (BRIEF-v2
  // R-1 §3.4) already documents this exact failure mode by name — "the
  // r19Vars.ts alias trap": globals.css's :root only ever aliases
  // `--foreground: var(--kbli-text-primary)`, and `.kbli-paper` overrides
  // `--kbli-text-primary` in a competing scoped rule rather than at :root,
  // so on the affected browsers the alias chain re-resolves to the dark
  // #ececec default instead of the paper value. `.kbli-paper` avoids the
  // trap by RESTATING every `--kbli-*` token as its own literal rather than
  // inheriting through an alias; this file follows the same proven pattern
  // for `--foreground` specifically, reading main's `--text-primary` at
  // import time so it can never silently drift from it, without going
  // through a `var()` indirection that the same trap could catch again.
  "--foreground": (R19_VARS as Record<string, string>)["--text-primary"],

  // ── Tokens R19_VARS does not carry ────────────────────────────────────────
  "--surface-base-solid": "var(--surface-base)",
  "--surface-sunken": "var(--r19-wash)",
  "--surface-deep": "var(--surface-sunken)",
  "--bz-elevated": "var(--surface-raised)", // portal name for --surface-raised
  "--cta-primary-fg": "var(--text-on-accent)",
  "--color-text-muted": "var(--text-secondary)",
  "--color-border-subtle": "var(--border-subtle)",
  "--footer-text": "var(--text-secondary)",
  "--cta-bg": "var(--cta-primary-bg)",
  "--cta-bg-hover": "#843719",
  "--tx-secondary": "var(--text-secondary)",
  "--bz-accent": "var(--accent-funnel)",
  "--text-link": "var(--accent-funnel)",
  "--r19-structure": "var(--r19-slate)",
  "--r19-copper-hover": "#843719",
  "--r19-ink-muted": "var(--text-secondary)",
  "--r19-control-border": "#7B817F",
  "--r19-radius-control": "3px",
  "--r19-radius-card": "4px",
  "--r19-focus": "0 0 0 3px var(--accent-funnel)",
  "--r19-shadow-header": "0 12px 20px #20282412",

  // ── B1 cure (gate PR #7508): MobileNav's non-R19 branch assumes a dark
  // funnel nav and paints a white icon on it; kbli's nav is opaque paper.
  "--nav-icon-color": "var(--text-primary)",
  "--nav-icon-bg": "var(--surface-raised)",
  "--nav-icon-border": "var(--border-subtle)",
} as CSSProperties;

/**
 * Marker className paired with `R19_DIRECTION_A_VARS` on every converted
 * wrapper. Hooks the scoped roles in `src/styles/r19-direction-a.css`.
 */
export const R19_CLASS = "r19-direction-a";
