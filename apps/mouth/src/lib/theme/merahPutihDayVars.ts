import type { CSSProperties } from "react";

/**
 * MERAH PUTIH — the DAY token set (identity law R4).
 *
 * Spec: `research/design/2026-08-27-r4-identity-merah-putih-token-spec.md`
 * Winning rendering direction: «Cap Dinas» v2 (contest 2026-08-30,
 * `research/design/2026-08-30-merah-putih-rendering-contest-result.md`).
 *
 * WHY THIS FILE EXISTS (and why it is not an edit to `rumahVars.ts`):
 * `rumahVars` is the older "Rumah Putih" set — same warm paper and ink, but its
 * accent is the NAVY `#1e3863`, which R4 RETIRES from the whole public
 * perimeter. Editing rumahVars would silently repaint the homepage and the blog,
 * which are not in this lane's perimeter. So: same scoping contract, new set.
 *
 * SCOPING CONTRACT (do NOT break it — inherited from rumahVars.ts):
 *   - Apply `MERAH_PUTIH_DAY_VARS` INLINE on the converted route's own top-level
 *     wrapper, NEVER on a shared `layout.tsx`. CSS custom properties inherit, so
 *     everything inside the wrapper resolves the day values while NavShell and
 *     Footer — DOM ancestors that read `--nav-bg` / `--footer-bg` — keep the
 *     shell's own theme.
 *   - The wrapper this lands on already carries `data-funnel="visa"`, which the
 *     shared theme paints via `[data-theme="editorial"] [data-funnel="visa"]`
 *     (`packages/core/tokens/themes/editorial.css:56`) → navy gradient ground and
 *     the RETIRED red `#ff3344`. An inline style on that same element beats that
 *     selector, so the override needs no `!important` and no theme fork.
 *   - No file under `packages/core/tokens/` changes. Other routes are untouched.
 *
 * CONTRAST (WCAG 2.x, every ratio COMPUTED — R4 §4 forbids estimating them;
 * recomputed against these exact values by
 * `scripts/tests/test_merah_putih_day_contrast.py`, which fails the build if any
 * pair below drifts):
 *   ink       #16213a on carta 14.79 · on elevated 16.00
 *   ink-soft  #475372 on carta  7.07 · on elevated  7.64
 *   muted     #6f6a5e on carta  4.98
 *   merah        #C8102E on carta 5.44 · white on it 5.88
 *   merah-action #D01033 on carta 5.11 · white on it 5.52
 *   merah-press  #c40020 on carta 5.77 · white on it 6.24
 *   eligible #16683f 6.29 · likely #2a6f97 5.08 · conditional #7a5209 6.39
 *   error    #a83a44 5.79 · white on it 6.26
 *   border-input #7a8093 on carta 3.64 · on elevated 3.94  (≥3 non-text bar)
 *   hairline #e3e1da on carta 1.21 — DECORATIVE ONLY, never the sole identifier
 *     of an interactive component (WCAG 2.2 SC 1.4.11). Interactive boundaries
 *     use `--border-strong`. This is the trap that made `#ddd8cb` (1.32) unusable
 *     as a component border even though the winning mockup paints dividers with it.
 *   RETIRED  #ff3344 on carta 3.34 — fails AA; this is what we are removing.
 */
export const MERAH_PUTIH_DAY_VARS = {
  // ── Grounds ────────────────────────────────────────────────────────────────
  // Overrides editorial's navy GRADIENT with a flat carta; `-solid` matters for
  // the components that read the solid form (nav band, print).
  "--surface-base": "#f7f6f2",
  "--surface-base-solid": "#f7f6f2",
  "--surface-raised": "#ffffff",
  "--surface-sunken": "#efece4",
  "--surface-deep": "#efece4",
  "--surface-overlay": "rgba(247, 246, 242, 0.94)",
  "--surface-scrim": "rgba(22, 33, 58, 0.45)",
  "--bz-elevated": "#ffffff",

  // ── Ink ────────────────────────────────────────────────────────────────────
  "--text-primary": "#16213a",
  "--text-secondary": "#475372",
  "--text-tertiary": "#6f6a5e",
  "--foreground": "#16213a",
  "--text-on-accent": "#ffffff",

  // ── Boundaries ─────────────────────────────────────────────────────────────
  // subtle/default are DECORATIVE (1.21 / 1.42 on carta). Anything that
  // identifies an interactive component must read `--border-strong` (3.64).
  "--border-subtle": "#e3e1da",
  "--border-default": "#d5d0c2",
  "--border-strong": "#7a8093",

  // ── Aliases that MUST be restated, not inherited ──────────────────────────
  // `semantic.css` declares these at :root as `var(--text-secondary)` /
  // `var(--border-subtle)`. A var() inside a custom-property declaration is
  // substituted using the cascade AT THE DECLARING ELEMENT — so an alias
  // declared at :root resolves against :ROOT's values and hands its
  // already-computed result down by inheritance. Overriding --text-secondary
  // on a wrapper deep in the tree therefore does NOT move the alias: it would
  // keep the dark theme's value while everything around it turned to paper.
  // These two are the most-consumed tokens in this perimeter (42 and 36 uses),
  // so the leak would have been wide and quiet. Restated with the same values
  // their sources take above.
  "--color-text-muted": "#475372",
  "--color-border-subtle": "#e3e1da",

  // ── The red family (R4 §3) ────────────────────────────────────────────────
  // STRUCTURE (brand marks, progress fill, rules) vs ACTION (CTA, links) are
  // two duties, never interchangeable — and selection is NEVER red (R4 §4.5).
  "--accent-funnel": "#C8102E",
  "--accent-funnel-text": "#D01033",
  "--cta-bg": "#D01033",
  "--cta-bg-hover": "#c40020",
  "--cta-primary-bg": "#D01033",
  "--text-link": "#D01033",

  // ── Semantic states (R4 §3) ───────────────────────────────────────────────
  "--state-success": "#16683f",
  "--state-likely": "#2a6f97",
  "--state-info": "#2a6f97",
  "--state-warning": "#7a5209",
  "--state-danger": "#a83a44",
  "--state-error": "#a83a44",
  "--color-error": "#a83a44",

  // WhatsApp is the ICON of the human exit — never a green button with white
  // text on it (white on #25d366 measures 1.98). The ink is what carries text.
  "--accent-whatsapp": "#25d366",
  "--accent-whatsapp-ink": "#0d3a1f",

  // ── Shell ─────────────────────────────────────────────────────────────────
  // The funnel header is slim ON CARTA — never a red band (R4 §4.3 restraint
  // budget). The full-bleed merah band is the home hero's single exception.
  "--nav-bg": "#f7f6f2",
  "--footer-bg": "#f7f6f2",
  "--footer-text": "#475372",

  // ── Typography ────────────────────────────────────────────────────────────
  // `/visa/layout.tsx` forces Montserrat on the whole visa funnel via an inline
  // `fontFamily`. R4 retires Montserrat from the web. We neutralise it HERE, on
  // our own wrapper, rather than editing the shared visa layout — the rest of
  // the funnel is a different lane's perimeter.
  // Inter and Cormorant are self-hosted and mounted on <html> by the root
  // layout. IBM Plex Mono is NOT loaded in this app (only 4 woff2 files exist:
  // cormorant, inter, league-spartan, montserrat), so `--font-mono` resolves to
  // ui-monospace — the same fallback every other mono surface in this app
  // already uses. Declared, not pretended: loading a fifth face is a perf decision of
  // its own, tracked in PENDING-ARMS, not smuggled into a palette change.
  fontFamily: "var(--font-sans), Inter, ui-sans-serif, system-ui, sans-serif",
} as CSSProperties;

/**
 * Marker className paired with `MERAH_PUTIH_DAY_VARS` on every converted
 * wrapper, so scoped CSS (and the print stylesheet) can target the day scope
 * without re-stating the whole selector chain.
 */
export const MERAH_PUTIH_DAY_CLASS = "merah-putih-day";

/**
 * The wrapper cannot paint its own ancestors, and <body> is an ancestor.
 *
 * MEASURED 2026-08-31 on the running app, which is the only reason this exists:
 * with the wrapper correctly carta, `getComputedStyle(document.body)` still
 * returned `rgb(29, 39, 59)` — the shared editorial navy — on BOTH routes, and
 * body was 88px taller than the wrapper on each. That is a navy band under the
 * content, plus a navy page in print and behind overscroll rubber-banding.
 *
 * `:has()` keeps the cure scoped to exactly the pages that opted in: no route
 * without a `.merah-putih-day` wrapper is affected, so this stays a route-level
 * change and never becomes a global stylesheet edit. Where `:has()` is
 * unsupported the page simply keeps today's behaviour — the same navy it has
 * now, never something worse.
 *
 * Inject with `<style>{MERAH_PUTIH_DAY_BODY_CSS}</style>` inside the wrapper.
 */
export const MERAH_PUTIH_DAY_BODY_CSS = `
body:has(.merah-putih-day) {
  background: #f7f6f2;
  color: #16213a;
}
@media print {
  body:has(.merah-putih-day) {
    background: #ffffff;
  }
}
`;
