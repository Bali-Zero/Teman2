#!/usr/bin/env node
/**
 * F1 — print before/after comparison summary from .artifacts/f1-baseline.
 * Usage: node scripts/f1-summary.mjs
 */
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ART = path.resolve(
  __dirname,
  "..",
  "..",
  "..",
  ".artifacts",
  "f1-baseline",
);

const OK_ROUTES = [
  "admin",
  "analytics",
  "clients",
  "dashboard",
  "hr",
  "inbox",
  "intelligence",
];

async function aggregate(dir, routesFilter) {
  const totals = {
    violations: 0,
    critical: 0,
    serious: 0,
    moderate: 0,
    minor: 0,
  };
  const byRule = {};
  const files = (await fs.readdir(dir)).filter((f) => f.endsWith(".json"));
  for (const f of files) {
    const name = f.replace(".json", "");
    if (routesFilter && !routesFilter.includes(name)) continue;
    const d = JSON.parse(await fs.readFile(path.join(dir, f), "utf8"));
    for (const v of d.violations || []) {
      totals.violations++;
      const imp = v.impact || "minor";
      totals[imp] = (totals[imp] || 0) + 1;
      const rid = v.id;
      if (!byRule[rid]) byRule[rid] = { count: 0, impact: imp };
      byRule[rid].count++;
    }
  }
  return { totals, byRule };
}

function diff(b, a) {
  return { abs: a - b, pct: b === 0 ? null : Math.round(((a - b) / b) * 100) };
}

async function main() {
  const before = await aggregate(path.join(ART, "axe-before-dev"), OK_ROUTES);
  const after = await aggregate(path.join(ART, "axe"), OK_ROUTES);

  console.log(
    `F1 — apples-to-apples a11y, ${OK_ROUTES.length} authenticated workspace routes`,
  );
  console.log("");
  console.log(`                       BEFORE   AFTER    Δ`);
  for (const k of ["violations", "critical", "serious", "moderate"]) {
    const d = diff(before.totals[k], after.totals[k]);
    const pct = d.pct !== null ? `(${d.pct >= 0 ? "+" : ""}${d.pct}%)` : "";
    console.log(
      `  ${k.padEnd(20)}  ${String(before.totals[k]).padStart(3)}     ${String(after.totals[k]).padStart(3)}    ${(d.abs >= 0 ? "+" : "") + d.abs} ${pct}`,
    );
  }
  console.log("");
  console.log("Per rule:");
  const rules = new Set([
    ...Object.keys(before.byRule),
    ...Object.keys(after.byRule),
  ]);
  for (const r of [...rules].sort()) {
    const b = before.byRule[r]?.count || 0;
    const a = after.byRule[r]?.count || 0;
    const sign = a < b ? "✅" : a > b ? "⚠️ " : "=";
    console.log(
      `  ${sign} ${r.padEnd(28)} before=${String(b).padStart(2)}  after=${String(a).padStart(2)}  (${a - b >= 0 ? "+" : ""}${a - b})`,
    );
  }

  // Perf summary
  try {
    const perfBefore = JSON.parse(
      await fs.readFile(path.join(ART, "perf", "before.json"), "utf8"),
    );
    const perfAfter = JSON.parse(
      await fs.readFile(path.join(ART, "perf", "after.json"), "utf8"),
    );
    const ok = (a) => a.filter((r) => r.js);
    const avg = (arr, k) =>
      Math.round(arr.reduce((s, r) => s + k(r), 0) / arr.length);
    const b = ok(perfBefore);
    const a = ok(perfAfter);
    console.log("");
    console.log("Perf (Playwright Resource Timing — JS only):");
    console.log(`                       BEFORE   AFTER    Δ`);
    const stats = [
      [
        "JS transfer (KB avg)",
        avg(b, (r) => r.js.transferSize / 1024),
        avg(a, (r) => r.js.transferSize / 1024),
      ],
      [
        "JS decoded (KB avg)",
        avg(b, (r) => r.js.decodedSize / 1024),
        avg(a, (r) => r.js.decodedSize / 1024),
      ],
      ["JS chunks (avg)", avg(b, (r) => r.js.count), avg(a, (r) => r.js.count)],
    ];
    for (const [k, bv, av] of stats) {
      const d = diff(bv, av);
      const pct = d.pct !== null ? `(${d.pct >= 0 ? "+" : ""}${d.pct}%)` : "";
      console.log(
        `  ${k.padEnd(20)}  ${String(bv).padStart(3)}     ${String(av).padStart(3)}    ${(d.abs >= 0 ? "+" : "") + d.abs} ${pct}`,
      );
    }
  } catch {
    console.log("\n(no perf snapshots present)");
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
