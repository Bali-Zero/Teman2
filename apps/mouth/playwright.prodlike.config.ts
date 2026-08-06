import { defineConfig, devices } from "@playwright/test";

import { loadProdlikeEnvironment } from "./e2e/support/prodlike-preflight";

const environment = loadProdlikeEnvironment(process.env);
const frontendOrigin = `http://127.0.0.1:${environment.frontendPort}`;

export default defineConfig({
  testDir: "./e2e",
  testMatch: "portal-prodlike-smoke.spec.ts",
  timeout: 90_000,
  expect: { timeout: 20_000 },
  retries: 0,
  workers: 1,
  fullyParallel: false,
  forbidOnly: true,
  reporter: [["line"]],
  outputDir: "output/playwright/prodlike-results",

  use: {
    baseURL: frontendOrigin,
    screenshot: "off",
    video: "off",
    trace: "off",
    actionTimeout: 20_000,
    navigationTimeout: 30_000,
  },

  projects: [
    {
      name: "chromium-prodlike-smoke",
      use: { ...devices["Desktop Chrome"] },
    },
  ],

  webServer: {
    command:
      "node --disable-warning=MODULE_TYPELESS_PACKAGE_JSON e2e/support/prodlike-preflight-cli.ts && " +
      `npm run build && npm run start -- --hostname 127.0.0.1 --port ${environment.frontendPort}`,
    url: frontendOrigin,
    env: {
      NUZANTARA_API_URL: environment.backendApiUrl,
      NEXT_PUBLIC_API_URL: environment.backendApiUrl,
      COOKIE_DOMAIN: "localhost",
      MY_PORTAL_PRODLIKE_ENFORCE_MIDDLEWARE: "1",
      NEXT_PUBLIC_HIDE_QUERY_DEVTOOLS: "1",
      NEXT_PUBLIC_HIDE_CELL_WIDGET: "1",
    },
    reuseExistingServer: false,
    timeout: 300_000,
    stdout: "pipe",
    stderr: "pipe",
  },
});
