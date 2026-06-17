import type { CSSProperties } from "react";

/**
 * MYTHOS "Rumah Putih" — route-scoped LIGHT theme.
 *
 * Single source of truth for the warm-paper / ink / navy palette that the
 * homepage `(marketing)/page.tsx` introduced (PR #1280) and that Stage-B
 * Batch 1 extends to the public blog/news/team pages.
 *
 * SCOPING CONTRACT (do NOT break it):
 *   - Apply `RUMAH_VARS` INLINE on a converted page's top-level wrapper
 *     (`<main>` / outer `<div>`), NEVER on the shared `(blog)/layout.tsx`.
 *     CSS custom properties inherit, so every section inside the wrapper
 *     resolves the light values, while NavShell + Footer (DOM siblings /
 *     ancestors that read `--nav-bg` / `--footer-bg`, NOT `--surface-base`)
 *     keep their editorial-dark navy anchors.
 *   - Pair with the `RUMAH_CLASS` className on the same wrapper so the
 *     scoped CSS in `globals.css` (`.rumah-putih …`) can re-tint the few
 *     hardcoded-dark Tailwind utilities used by the long-form reader
 *     (`.mdx-content`, article markdown fallback, blog cards) WITHOUT
 *     touching the shared components' source — which would leak the light
 *     theme onto pages we are not converting (/services, /property, …).
 *   - No file under `packages/core/tokens/` changes. Other routes + the
 *     subdomains are untouched.
 *
 * WCAG AA (pack rule 10): every text/bg pair below clears the floor —
 * ink #16213a on paper #f7f6f2 ≈ 13.5:1, soft-ink #475372 ≈ 7.1:1,
 * navy #1e3863 ≈ 10.8:1. Do NOT introduce off-palette colors here.
 */
export const RUMAH_VARS = {
  // Semantic re-map (Rumah Putih palette — warm paper / ink / navy)
  "--surface-base": "#f7f6f2",
  "--surface-raised": "#ffffff",
  "--text-primary": "#16213a",
  "--text-secondary": "#475372",
  "--text-tertiary": "#475372",
  "--border-subtle": "#e3e1da",
  "--border-default": "#e3e1da",
  "--border-strong": "#cfccc2",
  // Rumah Putih component hooks (chromatic-calm pass — authority via absence)
  "--rp-heading": "#1e3863",
  "--rp-accent": "#1e3863",
  "--rp-card-bg": "#ffffff",
  "--rp-card-border": "#e3e1da",
  "--rp-card-shadow": "0 1px 2px rgba(22, 33, 58, 0.05)",
  "--rp-row-bg": "#f7f6f2",
  "--rp-badge-bg": "#ffffff",
  "--rp-list-bg": "transparent",
  "--rp-list-border": "#e3e1da",
  "--rp-active-bg": "rgba(30, 56, 99, 0.07)",
  "--rp-active-border": "rgba(30, 56, 99, 0.35)",
  "--rp-glow": "none",
  "--rp-photo-inset": "24px",
  "--rp-photo-radius": "16px",
} as CSSProperties;

/**
 * MYTHOS P4 masthead: persistent solid-navy band (brand navy #1e3863 =
 * editorial `--surface-base-solid`) + 3px red rule (NavShell `accentBar`).
 * Set on the page wrapper that owns its own NavShell (e.g. the homepage).
 * Pages under `(blog)/layout.tsx` inherit the layout's NavShell, which is
 * already navy via the editorial `--nav-bg` token, so they do NOT need this.
 */
export const MASTHEAD_VARS = {
  "--nav-bg": "var(--surface-base-solid, #1e3863)",
} as CSSProperties;

/**
 * Marker className paired with `RUMAH_VARS` on every converted wrapper.
 * Hooks the scoped light overrides in `globals.css` (`.rumah-putih …`).
 */
export const RUMAH_CLASS = "rumah-putih";
