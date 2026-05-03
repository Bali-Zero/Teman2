import { Inter } from "next/font/google";

/**
 * Inter — primary sans font for the Bali Zero design system.
 *
 * Consumer wires the variable onto <html>:
 *   import { inter } from "@balizero/core/fonts/inter";
 *   <html className={inter.variable}>
 *
 * primitives.css sets --font-sans as a fallback chain ('Inter', ui-sans-serif, …).
 * When inter.variable is mounted, next/font's self-hosted value wins.
 */
export const inter = Inter({
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700", "800", "900"],
  variable: "--font-sans",
  display: "swap",
});
