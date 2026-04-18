#!/usr/bin/env node
/**
 * Quick screenshot of /dashboard via dev server (uses DEV BYPASS auth).
 * For visual QA after a11y fixes.
 */
import { chromium } from "@playwright/test";
import path from "node:path";
import fs from "node:fs/promises";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(__dirname, "..", "..", "..");
const OUT = path.join(REPO, ".artifacts", "f1-baseline", "qa");
const ROUTES = ["/dashboard", "/admin", "/clients", "/intelligence"];

await fs.mkdir(OUT, { recursive: true });
const browser = await chromium.launch();
const ctx = await browser.newContext({
  viewport: { width: 1280, height: 800 },
});
const page = await ctx.newPage();
for (const r of ROUTES) {
  try {
    await page.goto(`http://127.0.0.1:3000${r}`, {
      waitUntil: "domcontentloaded",
      timeout: 60000,
    });
    // Dev compile + DEV BYPASS path can take a while on first hit
    await page.waitForTimeout(3000);
    await page
      .waitForFunction(
        () =>
          !Array.from(document.querySelectorAll("p")).some((p) =>
            /^loading/i.test(p.textContent?.trim() || ""),
          ) && !!document.querySelector("#bz-page-title, header"),
        { timeout: 60000 },
      )
      .catch(() => undefined);
    await page.waitForTimeout(2000);
    const out = path.join(
      OUT,
      r.replace(/^\//, "").replace(/\//g, "_") + ".png",
    );
    await page.screenshot({ path: out, fullPage: false });
    console.log(`shot ${r} → ${out}`);
  } catch (e) {
    console.log(`shot ${r} ERR ${e.message}`);
  }
}
await browser.close();
