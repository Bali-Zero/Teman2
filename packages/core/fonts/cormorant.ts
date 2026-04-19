import { Cormorant_Garamond } from "next/font/google";

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
 */
export const cormorant = Cormorant_Garamond({
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700"],
  variable: "--font-serif",
  display: "swap",
});
