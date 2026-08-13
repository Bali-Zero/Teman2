import localFont from "next/font/local";

/**
 * Montserrat — shared sans font for the apps/mouth funnel (kbli, visa,
 * book layouts). All three call sites previously ran their own
 * `Montserrat({...})` from next/font/google with overlapping-but-different
 * weight subsets (book: 400/500/600, kbli+visa: 400-900). One shared
 * module here — weight range covers the union — avoids three duplicate
 * @font-face declarations for the same font file.
 *
 * Consumer wires the variable where needed:
 *   import { montserrat } from "@balizero/core/fonts/montserrat";
 *   <div className={montserrat.variable} style={{ fontFamily: "var(--font-montserrat), system-ui, sans-serif" }}>
 *
 * Self-hosted (2026-08-13): see fonts/inter.ts header for why (build-time
 * fetch to fonts.gstatic.com was crashing CI builds). File is the Google
 * Fonts CSS2 API `latin` subset variable woff2, axis wght 100-900 — covers
 * the 400-900 range used across every call site.
 */
export const montserrat = localFont({
  src: "./files/montserrat-latin-variable.woff2",
  weight: "400 900",
  variable: "--font-montserrat",
  display: "swap",
  // No CSS custom-property fallback chain is declared anywhere for
  // --font-montserrat; kbli/visa layouts hardcode
  // `var(--font-montserrat), system-ui, sans-serif` inline (globals.css /
  // primitives.css have no --font-montserrat entry). Mirrored verbatim.
  fallback: ["system-ui", "sans-serif"],
  adjustFontFallback: "Arial",
});
