import localFont from "next/font/local";

/**
 * R19 Direction A faces for the four product funnels — Fraunces (display
 * serif) and Manrope (UI sans).
 *
 * Files: latin subset woff2 (the Google Fonts `latin` unicode-range, the same
 * cut as packages/core/fonts/*), every OpenType layout feature and every
 * variation axis kept — Fraunces opsz 9-144 / wght 100-900 / SOFT 0-100 /
 * WONK 0-1, Manrope wght 200-800. Cut with fontTools from
 * apps/mouth/public/fonts/*-variable.ttf, byte-identical to the R19 branch's
 * apps/website/public/fonts/. OFL 1.1 licences ship next to them.
 *
 * Axes are not "declared" here: next/font/local has no `axes` option (it is
 * Google-only) and no @font-face descriptor switches an axis on. They ship
 * inside the file; opsz tracks font-size through the default
 * `font-optical-sizing: auto`, and SOFT/WONK are set per role in
 * src/styles/r19-direction-a.css.
 *
 * Mount `r19FontClassName` on the same wrapper that carries
 * `R19_DIRECTION_A_VARS` (see ./r19Vars). The workspace's raw @font-face in
 * app/portal/r19-fonts.css is a separate surface and stays untouched.
 */
const serif = localFont({
  src: "./fonts/fraunces-latin.woff2",
  weight: "100 900",
  style: "normal",
  variable: "--font-r19-serif",
  display: "swap",
  fallback: ["Georgia", "serif"],
  // next/font/local defaults the metric fallback to Arial; a serif needs Times.
  adjustFontFallback: "Times New Roman",
});

const sans = localFont({
  src: "./fonts/manrope-latin.woff2",
  weight: "200 800",
  style: "normal",
  variable: "--font-r19-sans",
  display: "swap",
  fallback: ["Arial", "sans-serif"],
  adjustFontFallback: "Arial",
});

export const r19Fonts = { serif, sans };

export const r19FontClassName = `${serif.variable} ${sans.variable}`;
