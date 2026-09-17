import { defineConfig, devices } from "@playwright/test";

/**
 * GARUDA VOA DELIBERA fase 2 — dedicated config for
 * `e2e/voa-tint.computed.guard.spec.ts`.
 *
 * Why a Playwright spec and not a vitest `.test.tsx` under
 * `src/app/visa/voa/` (as first sketched): jsdom, which every vitest test
 * in this repo runs under (`vitest.config.ts` — `environment: "jsdom"`),
 * does not resolve CSS custom properties in `getComputedStyle`. Verified
 * directly against this repo's own jsdom dependency before writing this
 * file: a `<div class="price">` styled by `color: var(--bz-data)` in an
 * injected `<style>` tag reports `getComputedStyle(el).color` as the
 * literal string `"var(--bz-data)"`, never the resolved colour — and this
 * whole R19 surface is built entirely on `var()` tokens. A guard built on
 * that would either never fire (comparing a string to a hue/saturation
 * check always false) or require faking the cascade by hand, which is not
 * "reading the computed style" — it is reimplementing CSS. A real browser
 * resolves it correctly, so this is a Playwright spec, following the same
 * `getComputedStyle` pattern already used in `e2e/service-pages-light.spec.ts`.
 *
 * Why its own config and not `playwright.config.ts`: that shared config's
 * `webServer` starts one `next build && next start` process for every spec
 * under `testDir`, with a fixed `env` block every other spec also depends
 * on. This funnel is gated server-side by `GARUDA_PUBLIC_ENABLED` (see
 * `src/app/visa/voa/flag.ts`) — fail-closed, so an unset flag 404s the
 * route before a single element renders. Adding that flag to the shared
 * `webServer.env` would flip it on for every other spec sharing that
 * process too. A dedicated config with its own `webServer.env`, `testMatch`
 * and a lighter single-browser project (this guard reads computed
 * colour, not layout — no engine matrix needed) isolates that flag to the
 * one spec that requires it. Precedented by `playwright.prodlike.config.ts`
 * and `playwright.production.config.ts`, both already dedicated configs
 * for a single spec file for analogous reasons.
 *
 * Local run without a fresh `next build` (a production build is not
 * reproducible from a broker worktree — see the worktree's own memory on
 * this): start `next dev --webpack` yourself with `GARUDA_PUBLIC_ENABLED=1`,
 * then run this config with `PLAYWRIGHT_EXTERNAL_SERVER=1` pointed at that
 * port, mirroring the escape hatch `playwright.config.ts` already documents
 * for the same reason (dev's `unsafe-eval` requirement is irrelevant here —
 * this guard reads computed CSS, not CSP-gated hydration behaviour).
 */
const E2E_PORT = process.env.BZ_E2E_PORT ?? "3000";

export default defineConfig({
  testDir: "./e2e",
  testMatch: "voa-tint.computed.guard.spec.ts",
  timeout: 60_000,
  expect: { timeout: 15_000 },
  retries: 0,
  workers: 1,
  fullyParallel: false,
  forbidOnly: true,
  reporter: [["line"]],
  outputDir: "output/playwright/voa-tint-results",

  use: {
    baseURL: `http://127.0.0.1:${E2E_PORT}`,
    screenshot: "off",
    video: "off",
    trace: "off",
    actionTimeout: 15_000,
    navigationTimeout: 30_000,
  },

  projects: [
    {
      name: "chromium-voa-tint",
      use: { ...devices["Desktop Chrome"] },
    },
  ],

  webServer: process.env.PLAYWRIGHT_EXTERNAL_SERVER
    ? undefined
    : {
        command: `npm run build && npm run start -- --port ${E2E_PORT}`,
        url: `http://127.0.0.1:${E2E_PORT}`,
        env: {
          GARUDA_PUBLIC_ENABLED: "true",
          NEXT_PUBLIC_HIDE_QUERY_DEVTOOLS: "1",
          NEXT_PUBLIC_HIDE_CELL_WIDGET: "1",
        },
        reuseExistingServer: !process.env.CI,
        timeout: 300 * 1000,
        stdout: "pipe",
        stderr: "pipe",
      },
});
