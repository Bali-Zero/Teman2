import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright Configuration for ZANTARA Smoke Tests
 *
 * Quick health check tests to run after every deploy.
 * Tests against PRODUCTION - no local webserver needed.
 *
 * Usage:
 *   cd apps/mouth
 *   npx playwright test --config=playwright.smoke.config.ts
 *
 * With specific browser:
 *   npx playwright test --config=playwright.smoke.config.ts --project=chromium
 */
export default defineConfig({
  testDir: './e2e/smoke',
  testMatch: '**/*.spec.ts',

  // Timeout for each test (90s for AI responses)
  timeout: 90_000,

  // Expect timeout
  expect: {
    timeout: 30_000,
  },

  // No retries for smoke tests - we want to know immediately if something is broken
  retries: 0,

  // Single worker to avoid rate limiting
  workers: 1,

  // Reporter - simple list for CI, HTML for debugging
  reporter: [['list'], ['html', { outputFolder: 'playwright-report-smoke', open: 'never' }]],

  // Shared settings
  use: {
    // Production URL
    baseURL: process.env.E2E_BASE_URL || 'https://zantara.balizero.com',

    // Screenshot on failure for debugging
    screenshot: 'only-on-failure',

    // Video on failure
    video: 'retain-on-failure',

    // Trace on first retry
    trace: 'on-first-retry',

    // Viewport
    viewport: { width: 1280, height: 720 },

    // Action timeout
    actionTimeout: 30_000,
  },

  // Only Chromium for smoke tests (fastest)
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],

  // NO webServer - testing against production
});
