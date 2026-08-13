import localFont from "next/font/local";

/**
 * Cormorant Garamond — editorial serif for Bali Zero public funnel.
 *
 * Used on the `editorial` persona (balizero.com, visa/tax/kbli) for headings,
 * paired with Inter on body copy. kita./prime./my. personas keep their own
 * heading fonts — this variable is available globally but only applied via
 * `[data-theme='editorial']` selectors.
 *
 * Consumer wires the variable onto <html> alongside inter:
 *   <html className={`${inter.variable} ${cormorant.variable}`}>
 *
 * Also reused directly (via `.className`, no `.variable`) by the four
 * pre-portal auth pages (forgot-password, login-upgraded, magic-link,
 * magic) that previously each ran their own `Cormorant_Garamond({...})`
 * call with the same weight subset (300/400/700) — pointing them at this
 * one shared instance avoids four duplicate @font-face declarations for
 * the same font file.
 *
 * Self-hosted (2026-08-13): see fonts/inter.ts header for why (build-time
 * fetch to fonts.gstatic.com was crashing CI builds). File is the Google
 * Fonts CSS2 API `latin` subset variable woff2, axis wght 300-700 — exact
 * match for the 300-700 range requested across every call site.
 */
export const cormorant = localFont({
  src: "./files/cormorant-garamond-latin-variable.woff2",
  weight: "300 700",
  variable: "--font-serif",
  display: "swap",
  // Mirrors the --font-serif fallback chain declared in
  // packages/core/tokens/primitives.css (minus the "Cormorant Garamond"
  // head, which next/font's own generated @font-face already supplies).
  fallback: ["ui-serif", "Georgia", "Cambria", "Times New Roman", "serif"],
  // Serif metrics — next/font/local defaults adjustFontFallback to 'Arial'
  // (a sans metric match) regardless of font category, unlike
  // next/font/google which auto-detects. Must be set explicitly here or
  // the CLS-reducing fallback substitution uses the wrong metrics.
  adjustFontFallback: "Times New Roman",
});
