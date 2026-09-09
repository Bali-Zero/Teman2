# Full-site browser baseline

Captured from the existing loopback fixture preview on 2026-09-06 UTC / 2026-09-07 WITA, before the coordinated UI batch was built. This is historical baseline evidence, not verification of the changed source.

An isolated Playwright CLI Chromium session (`website-r19-full-site`) visited `/`, `/services`, four service detail routes, `/team`, and `/journal` at CSS viewport widths 1440, 390 and 768. All 24 combinations returned HTTP 200. Document scroll width equaled viewport width, and all visible images had loaded natural dimensions after scrolling through lazy content and requesting decode. No page exceptions or console errors were observed on the valid routes. The trace includes aborted Next RSC prefetches during navigation; these are retained rather than represented as a clean network trace.

The team atlas images have intentionally oversized source-image boxes clipped by `Team_portrait` containers with `overflow: hidden`; these do not create document overflow. Both `/services/missing-review-probe` and `/missing-review-probe` returned HTTP 404 with the default visible “This page could not be found” message, with no recovery links. This isolated Chromium baseline did not reproduce an entirely blank 404.

At 390px, service header links measured 19.6875px high; breadcrumb links measured 18.234375px. The primary CTA was 48px high. These measurements support a touch-comfort improvement, not an asserted accessibility failure without the applicable spacing exceptions. The coordinator's UI batch already addresses service controls, skip-link focus and 404 recovery.

Observed solid service color pairs produce these calculated contrast ratios: ink/paper 13.638:1, muted/paper 5.066:1, copper/paper 5.408:1, white/copper 5.989:1 and white/forest 11.567:1. This is a bounded solid-color check, not certification of every text/background pairing or image overlay.

The 360px homepage and company detail page had no horizontal document overflow. Final evidence will include the expanded mobile navigation. Full-page baseline screenshots may place the fixed home header partway down the image because the initial capture used a smooth scroll reset. The capture routine was corrected to use an instant reset for final screenshots; this artifact is not a product defect.

Evidence: `output/playwright/website-r19-full-site/baseline-metrics.json`, `baseline-cli-result.txt` and the initial PNGs in that directory. Final screenshots will live in its separate `final/` directory.

The frozen 224-file pro-slice checkpoint and its evidence were not rebuilt or changed.
