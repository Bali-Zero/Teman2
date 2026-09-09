import { defineConfig, devices } from "@playwright/test";

const E2E_PORT = process.env.BZ_E2E_PORT ?? "3000";

/**
 * Playwright Configuration for Nuzantara Frontend E2E Tests
 *
 * Tests critical user flows:
 * - Authentication (Login)
 * - Chat functionality
 * - CRM operations
 * - WebSocket connections
 * - Streaming responses
 */
export default defineConfig({
  testDir: "./e2e",
  testMatch: "**/*.spec.ts",
  testIgnore: [
    // This fail-closed smoke requires the complete synthetic contract and is
    // collected only by playwright.prodlike.config.ts.
    "portal-prodlike-smoke.spec.ts",
    // Production journey sentinels drive REAL production (balizero.com /
    // my.balizero.com) as an anonymous visitor — never against the local
    // build this config launches. Collected only by
    // playwright.production.config.ts (no webServer, no mocked auth).
    "production/**",
  ],

  // Timeout per singolo test
  timeout: 60 * 1000,

  // Retry su CI
  retries: process.env.CI ? 2 : 0,

  // Workers per parallelizzazione
  workers: process.env.CI ? 1 : undefined,

  // Reporter
  reporter: [
    ["html"],
    ["json", { outputFile: "playwright-report/results.json" }],
    ["list"],
  ],

  // Shared settings per tutti i test
  use: {
    // Base URL dell'applicazione
    baseURL: process.env.PLAYWRIGHT_BASE_URL || `http://127.0.0.1:${E2E_PORT}`,

    // Screenshot su failure
    screenshot: "only-on-failure",

    // Video su failure
    video: "retain-on-failure",

    // Trace per debugging
    trace: "on-first-retry",

    // Viewport
    viewport: { width: 1280, height: 720 },

    // Action timeout
    actionTimeout: 20 * 1000,
  },

  // Progetti per diversi browser
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "firefox",
      use: { ...devices["Desktop Firefox"] },
    },
    {
      name: "webkit",
      use: { ...devices["Desktop Safari"] },
    },
    // Mobile viewport
    {
      name: "Mobile Chrome",
      use: { ...devices["Pixel 5"] },
    },
  ],

  // Exercise the same optimized runtime and CSP path used in production.
  // The development runtime requires `unsafe-eval`, which the portal policy
  // intentionally rejects, so running `next dev` here prevents hydration and
  // leaves the client shell stuck on its loading state.
  //
  // Locally, opt out by setting PLAYWRIGHT_EXTERNAL_SERVER=1 when a compatible
  // server is already running on the configured port.
  webServer: process.env.PLAYWRIGHT_EXTERNAL_SERVER
    ? undefined
    : {
        command: `npm run build && npm run start -- --port ${E2E_PORT}`,
        url: `http://127.0.0.1:${E2E_PORT}`,
        env: {
          NEXT_PUBLIC_HIDE_QUERY_DEVTOOLS: "1",
          NEXT_PUBLIC_HIDE_CELL_WIDGET: "1",
          NEXT_PUBLIC_VISA_ORACLE_WHATSAPP_NUMBER: "628123456789",
        },
        reuseExistingServer: !process.env.CI,
        timeout: 300 * 1000,
        stdout: "pipe",
        stderr: "pipe",
      },
});
