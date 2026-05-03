import lighthouse from "lighthouse";
import * as chromeLauncher from "chrome-launcher";
import fs from "node:fs";
import path from "node:path";

const URL = process.env.PRIME_URL || "http://localhost:3000/prime";
const LABEL = process.env.LABEL || "baseline";
const OUT_DIR = path.resolve(
  process.cwd(),
  "../../docs/superpowers/specs/artifacts",
);
fs.mkdirSync(OUT_DIR, { recursive: true });

async function run(formFactor) {
  const chrome = await chromeLauncher.launch({
    chromeFlags: ["--headless=new", "--no-sandbox"],
  });
  const options = {
    logLevel: "error",
    output: "json",
    onlyCategories: ["performance"],
    port: chrome.port,
    formFactor,
    screenEmulation:
      formFactor === "mobile"
        ? {
            mobile: true,
            width: 412,
            height: 915,
            deviceScaleFactor: 2.625,
            disabled: false,
          }
        : {
            mobile: false,
            width: 1440,
            height: 900,
            deviceScaleFactor: 1,
            disabled: false,
          },
  };
  const runnerResult = await lighthouse(URL, options);
  await chrome.kill();
  return runnerResult.lhr;
}

const desktop = await run("desktop");
const mobile = await run("mobile");
const out = {
  url: URL,
  label: LABEL,
  capturedAt: new Date().toISOString(),
  desktop: {
    score: desktop.categories.performance.score,
    lcp: desktop.audits["largest-contentful-paint"].numericValue,
    cls: desktop.audits["cumulative-layout-shift"].numericValue,
    tbt: desktop.audits["total-blocking-time"].numericValue,
    fcp: desktop.audits["first-contentful-paint"].numericValue,
    tti: desktop.audits["interactive"].numericValue,
  },
  mobile: {
    score: mobile.categories.performance.score,
    lcp: mobile.audits["largest-contentful-paint"].numericValue,
    cls: mobile.audits["cumulative-layout-shift"].numericValue,
    tbt: mobile.audits["total-blocking-time"].numericValue,
    fcp: mobile.audits["first-contentful-paint"].numericValue,
    tti: mobile.audits["interactive"].numericValue,
  },
};
const file = path.join(OUT_DIR, `2026-04-18-prime-${LABEL}.json`);
fs.writeFileSync(file, JSON.stringify(out, null, 2));
console.log(`Wrote ${file}`);
console.log(`Desktop LCP: ${out.desktop.lcp.toFixed(0)}ms`);
console.log(`Mobile  LCP: ${out.mobile.lcp.toFixed(0)}ms`);
