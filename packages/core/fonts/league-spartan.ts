import localFont from "next/font/local";

/**
 * League Spartan — display sans used by the apps/mouth "book" story layout
 * (`/book`) for numerals/stat callouts. Single call site today, but the
 * `localFont()` declaration lives here (next to the other self-hosted
 * families) rather than in apps/mouth, so the font FILE and its loader
 * config stay co-located under packages/core/fonts/ — a mouth call site
 * reaching across the package boundary via a long relative path into
 * core's internal files/ directory would be the fragile alternative.
 *
 * Consumer wires the variable where needed:
 *   import { leagueSpartan } from "@balizero/core/fonts/league-spartan";
 *   <div className={leagueSpartan.variable}>
 *
 * Self-hosted (2026-08-13): see fonts/inter.ts header for why (build-time
 * fetch to fonts.gstatic.com was crashing CI builds). File is the Google
 * Fonts CSS2 API `latin` subset variable woff2, axis wght 100-900 — covers
 * the 400-900 range requested (weights 400/600/700/800/900).
 */
export const leagueSpartan = localFont({
  src: "./files/league-spartan-latin-variable.woff2",
  weight: "400 900",
  variable: "--font-spartan",
  display: "swap",
  // No CSS custom-property fallback chain is declared anywhere for
  // --font-spartan (grepped globals.css + packages/core/tokens/*.css:
  // zero hits). Mirrors the same system-sans convention used by the
  // sibling sans families in this codebase (Inter, Montserrat) rather
  // than inventing a new one.
  fallback: ["system-ui", "sans-serif"],
  adjustFontFallback: "Arial",
});
