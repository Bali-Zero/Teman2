import { defineConfig, devices } from "@playwright/test";

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
    baseURL: process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000",

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

  // In CI we always need the webServer (there is no pre-running dev server).
  // Locally, opt out by setting PLAYWRIGHT_EXTERNAL_SERVER=1 so that the
  // already-running `npm run dev` on :3000 is used instead.
  webServer: process.env.PLAYWRIGHT_EXTERNAL_SERVER
    ? undefined
    : {
        command: "npm run dev",
        url: "http://127.0.0.1:3000",
        reuseExistingServer: !process.env.CI,
        timeout: 180 * 1000,
        stdout: "pipe",
        stderr: "pipe",
      },
});
