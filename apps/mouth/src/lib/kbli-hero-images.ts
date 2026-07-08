// =============================================================================
// KBLI Hero Images — SUPERSEDED 2026-07-07
// =============================================================================
//
// This module used to hold a 1500+-entry map of hotlinked Unsplash photo
// URLs, one per KBLI code (~450KB of source, live third-party requests on
// every page view, no editorial control over the imagery). It has been
// replaced by a deterministic, zero-external-request cover system:
//
//   - src/lib/kbli-cover-design.ts          — design DNA (section palette +
//                                              motif, per-code "fingerprint"
//                                              geometry)
//   - src/app/api/og/kbli/[code]/route.tsx  — generated 1200x630 OG cover
//   - src/components/kbli/KBLIHeroCanvas.tsx — inline SVG hero backdrop
//
// GOLD_HERO_IMAGES is kept as an exported EMPTY Record so the sole remaining
// consumer (src/app/kbli/[code]/page.tsx, `GOLD_HERO_IMAGES[kbli.code] ??
// null`) compiles unchanged and always falls through to the gradient/pattern
// backdrop from `getHeroStyle()` (kbli-data.ts), which itself now derives
// from the same design DNA. No Unsplash URL remains anywhere in this file.

export const GOLD_HERO_IMAGES: Record<
  string,
  { src: string; alt: string; overlay: string }
> = {};
