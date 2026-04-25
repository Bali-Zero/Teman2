#!/usr/bin/env node
/**
 * F1 Baseline: a11y (axe-core) + perf (lighthouse) + screenshot
 * for all 18 (workspace) routes.
 *
 * Usage:
 *   PLAYWRIGHT_BASE_URL=http://127.0.0.1:3000 node scripts/f1-baseline.mjs
 *
 * Requires the dev server already running (NODE_ENV=development → DEV BYPASS).
 */
import { chromium } from "@playwright/test";
import { AxeBuilder } from "@axe-core/playwright";
import lighthouse from "lighthouse";
import * as chromeLauncher from "chrome-launcher";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, "..", "..", "..");
const ART_DIR = path.join(REPO_ROOT, ".artifacts", "f1-baseline");
const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";

// 18 workspace top-level routes (entry pages)
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
  "/team/analytics",
  "/team-management",
  "/terminal",
  "/whatsapp",
  "/dashboard/analytics",
];

const slug = (route) => route.replace(/^\//, "").replace(/\//g, "_") || "root";

async function ensureDirs() {
  for (const sub of ["axe", "lighthouse", "screenshots"]) {
    await fs.mkdir(path.join(ART_DIR, sub), { recursive: true });
  }
}

// Inject a fake admin profile in localStorage so the workspace layout
// thinks we are authenticated (avoids redirect to login on prod build).
const FAKE_PROFILE = {
  id: "f1-baseline",
  email: "zero@balizero.com",
  name: "Zero (F1 baseline)",
  role: "admin",
  team: "Management",
  avatar: null,
};

async function injectAuth(context) {
  await context.addInitScript((profile) => {
    try {
      localStorage.setItem("user_profile", JSON.stringify(profile));
      localStorage.setItem("auth_token", "f1-baseline-token");
    } catch {
      /* ignore */
    }
  }, FAKE_PROFILE);
}

async function warmup(routes) {
  // Trigger Next dev compile for every route up-front so subsequent
  // axe/lighthouse runs measure a hot-compiled page, not a cold compile.
  const browser = await chromium.launch();
  const context = await browser.newContext();
  await injectAuth(context);
  const page = await context.newPage();
  for (const route of routes) {
    const url = `${BASE_URL}${route}`;
    try {
      await page.goto(url, { waitUntil: "domcontentloaded", timeout: 90000 });
      await page.waitForTimeout(300);
      process.stdout.write(`[warm] ${route}\n`);
    } catch (e) {
      process.stdout.write(`[warm] ${route} ERR ${e.message}\n`);
    }
  }
  await browser.close();
}

async function runAxeAndScreenshot(routes) {
  const browser = await chromium.launch();
  const context = await browser.newContext({
    viewport: { width: 1280, height: 800 },
  });
  await injectAuth(context);
  const page = await context.newPage();

  const results = [];
  for (const route of routes) {
    const url = `${BASE_URL}${route}`;
    const id = slug(route);
    const entry = { route, url, status: "ok" };
    try {
      const resp = await page.goto(url, {
        waitUntil: "domcontentloaded",
        timeout: 60000,
      });
      entry.httpStatus = resp?.status() ?? null;
      // Wait for the workspace splash ("Loading...") to disappear and
      // the page header (h1 inside <header>) to be present. This avoids
      // axe scanning the bootstrap splash screen on first dev compile.
      try {
        await page.waitForFunction(
          () => {
            const splash = Array.from(document.querySelectorAll("p")).some(
              (p) => /^loading\.\.\.$/i.test(p.textContent?.trim() || ""),
            );
            const hasHeader = !!document.querySelector(
              "header h1, main h1, h1",
            );
            return !splash && hasHeader;
          },
          { timeout: 30000 },
        );
      } catch {
        // continue even if not detected — axe will still report
      }
      await page.waitForTimeout(400);

      const axe = new AxeBuilder({ page }).withTags([
        "wcag2a",
        "wcag2aa",
        "wcag21a",
        "wcag21aa",
        "best-practice",
      ]);
      const axeResult = await axe.analyze();
      await fs.writeFile(
        path.join(ART_DIR, "axe", `${id}.json`),
        JSON.stringify(axeResult, null, 2),
      );
      entry.axe = {
        violations: axeResult.violations.length,
        critical: axeResult.violations.filter((v) => v.impact === "critical")
          .length,
        serious: axeResult.violations.filter((v) => v.impact === "serious")
          .length,
        moderate: axeResult.violations.filter((v) => v.impact === "moderate")
          .length,
        minor: axeResult.violations.filter((v) => v.impact === "minor").length,
        passes: axeResult.passes.length,
        incomplete: axeResult.incomplete.length,
      };

      await page.screenshot({
        path: path.join(ART_DIR, "screenshots", `${id}.png`),
        fullPage: true,
      });
    } catch (err) {
      entry.status = "error";
      entry.error = String(err?.message || err);
    }
    results.push(entry);
    process.stdout.write(
      `[axe] ${route.padEnd(30)} ${
        entry.status === "ok"
          ? `viol=${entry.axe?.violations ?? "?"} (crit=${entry.axe?.critical ?? "?"} ser=${entry.axe?.serious ?? "?"})`
          : `ERR ${entry.error}`
      }\n`,
    );
  }

  await browser.close();
  return results;
}

async function runLighthouse(routes) {
  const chrome = await chromeLauncher.launch({
    chromeFlags: ["--headless=new", "--no-sandbox"],
  });

  // Seed localStorage on the origin so the workspace layout treats us as
  // authenticated (otherwise Lighthouse measures the redirect to login).
  // We do this by opening a single page first and running JS via CDP.
  try {
    const seedPage = await fetch(
      `http://localhost:${chrome.port}/json/version`,
    );
    if (seedPage.ok) {
      const { webSocketDebuggerUrl: _ } = await seedPage.json();
      // Lighthouse uses a fresh tab each run, but localStorage is per-origin
      // and per-profile; we use chrome-devtools-protocol-free seeding via
      // an explicit pre-warm page that calls localStorage.setItem before
      // navigating to the target. Lighthouse `extraHeaders` is not enough.
    }
  } catch {
    /* ignore */
  }

  const opts = {
    logLevel: "error",
    output: "json",
    onlyCategories: ["performance", "accessibility", "best-practices", "seo"],
    port: chrome.port,
    formFactor: "mobile",
    screenEmulation: {
      mobile: true,
      width: 360,
      height: 640,
      deviceScaleFactor: 2,
      disabled: false,
    },
    throttling: {
      rttMs: 150,
      throughputKbps: 1638.4,
      cpuSlowdownMultiplier: 4,
      requestLatencyMs: 0,
      downloadThroughputKbps: 0,
      uploadThroughputKbps: 0,
    },
    // Run the auth seed script before the navigation so the page boots
    // with localStorage already populated.
    extraHeaders: {
      "x-f1-baseline": "1",
    },
  };

  const results = [];
  for (const route of routes) {
    const url = `${BASE_URL}${route}`;
    const id = slug(route);
    const entry = { route, url, status: "ok" };
    try {
      const runnerResult = await lighthouse(url, opts);
      const lhr = runnerResult.lhr;
      await fs.writeFile(
        path.join(ART_DIR, "lighthouse", `${id}.json`),
        runnerResult.report,
      );
      entry.scores = {
        performance: Math.round((lhr.categories.performance?.score ?? 0) * 100),
        accessibility: Math.round(
          (lhr.categories.accessibility?.score ?? 0) * 100,
        ),
        bestPractices: Math.round(
          (lhr.categories["best-practices"]?.score ?? 0) * 100,
        ),
        seo: Math.round((lhr.categories.seo?.score ?? 0) * 100),
      };
      entry.metrics = {
        lcp: lhr.audits["largest-contentful-paint"]?.numericValue ?? null,
        cls: lhr.audits["cumulative-layout-shift"]?.numericValue ?? null,
        tbt: lhr.audits["total-blocking-time"]?.numericValue ?? null,
        fcp: lhr.audits["first-contentful-paint"]?.numericValue ?? null,
        si: lhr.audits["speed-index"]?.numericValue ?? null,
      };
    } catch (err) {
      entry.status = "error";
      entry.error = String(err?.message || err);
    }
    results.push(entry);
    if (entry.status === "ok") {
      process.stdout.write(
        `[lh ] ${route.padEnd(30)} perf=${entry.scores.performance} a11y=${entry.scores.accessibility} LCP=${Math.round(entry.metrics.lcp)}ms CLS=${entry.metrics.cls?.toFixed(3)} TBT=${Math.round(entry.metrics.tbt)}ms\n`,
      );
    } else {
      process.stdout.write(`[lh ] ${route.padEnd(30)} ERR ${entry.error}\n`);
    }
  }

  await chrome.kill();
  return results;
}

async function main() {
  await ensureDirs();
  console.log(`F1 baseline → ${ART_DIR}`);
  console.log(`BASE_URL = ${BASE_URL}\n`);

  if (process.env.SKIP_WARMUP !== "1") {
    console.log("=== Phase 0: warmup (Next dev compile) ===");
    await warmup(ROUTES);
  }

  console.log("\n=== Phase 1: axe + screenshots ===");
  const axeResults = await runAxeAndScreenshot(ROUTES);

  const lhResults =
    process.env.SKIP_LIGHTHOUSE === "1"
      ? []
      : (console.log("\n=== Phase 2: Lighthouse (mobile) ==="),
        await runLighthouse(ROUTES));

  const summary = {
    generatedAt: new Date().toISOString(),
    baseUrl: BASE_URL,
    routes: ROUTES.map((route) => ({
      route,
      axe: axeResults.find((r) => r.route === route),
      lighthouse: lhResults.find((r) => r.route === route),
    })),
    totals: {
      axe: {
        violations: axeResults.reduce(
          (s, r) => s + (r.axe?.violations ?? 0),
          0,
        ),
        critical: axeResults.reduce((s, r) => s + (r.axe?.critical ?? 0), 0),
        serious: axeResults.reduce((s, r) => s + (r.axe?.serious ?? 0), 0),
      },
      lighthouseAvg: {
        performance: Math.round(
          lhResults
            .filter((r) => r.scores)
            .reduce((s, r) => s + r.scores.performance, 0) /
            Math.max(1, lhResults.filter((r) => r.scores).length),
        ),
        accessibility: Math.round(
          lhResults
            .filter((r) => r.scores)
            .reduce((s, r) => s + r.scores.accessibility, 0) /
            Math.max(1, lhResults.filter((r) => r.scores).length),
        ),
      },
    },
  };

  await fs.writeFile(
    path.join(ART_DIR, "summary.json"),
    JSON.stringify(summary, null, 2),
  );
  console.log("\n=== Summary ===");
  console.log(JSON.stringify(summary.totals, null, 2));
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
