import localFont from "next/font/local";

/**
 * Inter — primary sans font for the Bali Zero design system.
 *
 * Self-hosted (2026-08-13): `next/font/google` fetches woff2 from
 * fonts.gstatic.com at BUILD time. When that fetch fails in GitHub Actions
 * (flaky/blocked network egress), the build dies with NextFontError and
 * takes the `E2E Tests (Playwright)` + `Frontend Tests (Next.js)` required
 * checks down with it. Self-hosting the file removes the network dependency
 * entirely. File is the Google Fonts CSS2 API `latin` subset variable woff2
 * (unicode-range starting U+0000-00FF, same subset `subsets:["latin"]`
 * requested), axis wght 100-900 — covers the 300-900 range used here.
 *
 * Consumer wires the variable onto <html>:
 *   import { inter } from "@balizero/core/fonts/inter";
 *   <html className={inter.variable}>
 *
 * primitives.css sets --font-sans as a fallback chain ('Inter', ui-sans-serif, …).
 * When inter.variable is mounted, next/font's self-hosted value wins.
 */
export const inter = localFont({
  src: "./files/inter-latin-variable.woff2",
  weight: "300 900",
  variable: "--font-sans",
  display: "swap",
  // Mirrors the --font-sans fallback chain declared in
  // packages/core/tokens/primitives.css (minus the "Inter" head, which
  // next/font's own generated @font-face already supplies).
  fallback: ["ui-sans-serif", "system-ui", "sans-serif"],
  adjustFontFallback: "Arial",
});
