#!/usr/bin/env node
/**
 * F1 perf measurement using Playwright + Resource Timing API.
 *
 * Captures, per workspace route:
 *   - JS transfer size (sum of all *.js resources, gzipped over the wire)
 *   - JS resource count
 *   - LCP (largestContentfulPaint observer)
 *   - DOM content loaded
 *   - load
 *
 * Uses a fake admin profile injected via initScript so the workspace
 * layout treats us as authenticated (bypasses login redirect on prod).
 */
import { chromium } from "@playwright/test";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, "..", "..", "..");
const ART_DIR = path.join(REPO_ROOT, ".artifacts", "f1-baseline", "perf");
const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3001";
const LABEL = process.env.LABEL || "after";

const ROUTES = [
  "/admin",
  "/analytics",
  "/clients",
  "/dashboard",
  "/hr",
  "/inbox",
  "/intelligence",
  "/lkpm",
  "/notifications",
  "/omnichannel",
  "/process",
  "/revenue/analytics",
  "/settings",
];

const FAKE_PROFILE = {
  id: "f1-baseline",
  email: "zero@balizero.com",
  name: "Zero (F1 baseline)",
  role: "admin",
  team: "Management",
  avatar: null,
};

const slug = (route) => route.replace(/^\//, "").replace(/\//g, "_") || "root";

async function measure(page, route) {
  const url = `${BASE_URL}${route}`;
  const t0 = Date.now();
  await page.goto(url, { waitUntil: "domcontentloaded", timeout: 60000 });
  // Wait for layout bootstrap to settle
  await page
    .waitForFunction(
      () => {
        const splash = Array.from(document.querySelectorAll("p")).some((p) =>
          /^loading…?$/i.test(p.textContent?.trim() || ""),
        );
        return !splash;
      },
      { timeout: 20000 },
    )
    .catch(() => undefined);
  // Let LCP observer settle
  await page.waitForTimeout(2000);

  const metrics = await page.evaluate(() => {
    const resources = performance.getEntriesByType("resource");
    const js = resources.filter(
      (r) => /\.js(\?|$)/.test(r.name) || r.initiatorType === "script",
    );
    const css = resources.filter(
      (r) => /\.css(\?|$)/.test(r.name) || r.initiatorType === "link",
    );
    const sum = (rs, k) => rs.reduce((s, r) => s + (r[k] || 0), 0);

    const lcpEntries = performance.getEntriesByType("largest-contentful-paint");
    const lcp = lcpEntries.length
      ? lcpEntries[lcpEntries.length - 1].startTime
      : null;

    const nav = performance.getEntriesByType("navigation")[0];

    return {
      js: {
        count: js.length,
        transferSize: sum(js, "transferSize"),
        decodedSize: sum(js, "decodedBodySize"),
      },
      css: {
        count: css.length,
        transferSize: sum(css, "transferSize"),
      },
      totalRequests: resources.length,
      lcp,
      domContentLoaded: nav?.domContentLoadedEventEnd ?? null,
      loadEvent: nav?.loadEventEnd ?? null,
    };
  });

  const elapsed = Date.now() - t0;
  return { route, url, elapsed, ...metrics };
}

async function main() {
  await fs.mkdir(ART_DIR, { recursive: true });
  const browser = await chromium.launch();
  const results = [];
  for (const route of ROUTES) {
    // Fresh context per route → no HTTP cache pollution between routes.
    const context = await browser.newContext({
      viewport: { width: 1280, height: 800 },
    });
    await context.addInitScript((profile) => {
      try {
        localStorage.setItem("user_profile", JSON.stringify(profile));
        localStorage.setItem("auth_token", "f1-baseline-token");
      } catch {}
    }, FAKE_PROFILE);
    const page = await context.newPage();
    // Block backend API calls so we measure shell JS only, not API latency.
    await page.route("**/api/**", (req) => req.abort());
    try {
      const r = await measure(page, route);
      results.push(r);
      const jsKb = (r.js.transferSize / 1024).toFixed(1);
      const decKb = (r.js.decodedSize / 1024).toFixed(1);
      const lcp = r.lcp != null ? `${Math.round(r.lcp)}ms` : "n/a";
      process.stdout.write(
        `[perf:${LABEL}] ${route.padEnd(28)} JS=${jsKb}KB transfer / ${decKb}KB decoded (${r.js.count} files) LCP=${lcp}\n`,
      );
    } catch (err) {
      process.stdout.write(
        `[perf:${LABEL}] ${route.padEnd(28)} ERR ${err.message}\n`,
      );
      results.push({ route, error: String(err) });
    }
    await context.close();
  }
  await browser.close();

  const out = path.join(ART_DIR, `${LABEL}.json`);
  await fs.writeFile(out, JSON.stringify(results, null, 2));

  const ok = results.filter((r) => r.js);
  const lcpOk = ok.filter((r) => r.lcp != null);
  const totals = {
    routes: ok.length,
    avgJsTransferKb: Math.round(
      ok.reduce((s, r) => s + r.js.transferSize / 1024, 0) /
        Math.max(1, ok.length),
    ),
    avgJsDecodedKb: Math.round(
      ok.reduce((s, r) => s + r.js.decodedSize / 1024, 0) /
        Math.max(1, ok.length),
    ),
    avgJsCount: Math.round(
      ok.reduce((s, r) => s + r.js.count, 0) / Math.max(1, ok.length),
    ),
    avgLcpMs: lcpOk.length
      ? Math.round(lcpOk.reduce((s, r) => s + r.lcp, 0) / lcpOk.length)
      : null,
  };
  console.log(`\n=== Summary [${LABEL}] ===`);
  console.log(JSON.stringify(totals, null, 2));
  console.log(`\nFull results: ${out}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
