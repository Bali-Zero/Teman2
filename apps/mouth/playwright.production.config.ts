import { defineConfig, devices } from "@playwright/test";

/**
 * Production journey sentinels — L11-PR1 (2026-08-29).
 *
 * WHY A SEPARATE CONFIG. `playwright.config.ts` and `playwright.prodlike.config.ts`
 * both spin up a `webServer` (a local `next build && next start`, mocked auth via
 * DEV BYPASS or a synthetic cookie jar). That is precisely why the existing 53
 * specs across 158 routes caught **0 of 6** measured 2026-08-28 production defects
 * (research/operations/2026-08-28-beyond-sota-product-ux-visual-design.md §2):
 * a local build with mocked auth cannot observe where a REAL anonymous visitor
 * lands on REAL production — split-brain auth state, an expired third-party API
 * key, a DNS-level 301 to a different host, none of those exist in a local
 * `next start`. This config therefore:
 *
 *   - has NO `webServer` block at all — it never launches anything, it points
 *     at whatever `baseURL` the caller gives it;
 *   - defaults `baseURL` to `https://balizero.com` (overridable via
 *     `PROD_SENTINEL_BASE_URL` for a canary/staging host, never for localhost —
 *     the whole premise of this suite is that "local" and "production" answer
 *     differently);
 *   - never sets `storageState` / a cookie jar / a bypass header — every test
 *     starts as a genuinely anonymous browser context, matching the visitor
 *     class each of the 4 cured/tracked defects actually affected.
 *
 * A single chromium project is enough: these are journey-truth checks (does
 * the URL/console/rendered-content match reality), not cross-browser rendering
 * checks — the existing local suites already cover multi-browser/viewport
 * matrices for these same route families.
 */
export default defineConfig({
  testDir: "./e2e/production",
  testMatch: "**/*.spec.ts",
  timeout: 60_000,
  expect: { timeout: 15_000 },

  // Never retry-hide a real production defect (prime-maps.spec.ts is SUPPOSED
  // to fail today — retries would just re-confirm the same red, at 2x cost,
  // and could mask a genuinely flaky assertion as "eventually green").
  retries: 0,
  workers: 1,
  fullyParallel: false,
  forbidOnly: true,

  reporter: [
    ["list"],
    ["json", { outputFile: "output/playwright/production-results.json" }],
  ],
  outputDir: "output/playwright/production-artifacts",

  use: {
    baseURL: process.env.PROD_SENTINEL_BASE_URL || "https://balizero.com",
    screenshot: "only-on-failure",
    video: "off",
    trace: "off",
    actionTimeout: 20_000,
    navigationTimeout: 30_000,
    // No storageState — every context is a fresh anonymous visitor.
  },

  projects: [
    {
      name: "chromium-production",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
