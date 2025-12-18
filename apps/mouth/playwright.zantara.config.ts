import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright Configuration for ZANTARA AI Capabilities Tests
 * Tests run against PRODUCTION - no local webserver
 */
export default defineConfig({
  testDir: './e2e/zantara',
  testMatch: '**/*.spec.ts',

  // Long timeout for AI responses
  timeout: 120 * 1000,

  // No retries for capability assessment
  retries: 0,

  // Single worker to maintain conversation context
  workers: 1,

  // Reporter
  reporter: [['html', { outputFolder: 'playwright-report-zantara' }], ['list']],

  // Shared settings
  use: {
    // Production URL
    baseURL: 'https://zantara.balizero.com',

    // Screenshot on failure
    screenshot: 'only-on-failure',

    // Video on failure for debugging
    video: 'retain-on-failure',

    // Trace for debugging
    trace: 'on-first-retry',

    // Viewport
    viewport: { width: 1280, height: 720 },

    // Long action timeout for AI responses
    actionTimeout: 60 * 1000,
  },

  // Only Chromium for now
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],

  // NO webServer - testing against production
});
