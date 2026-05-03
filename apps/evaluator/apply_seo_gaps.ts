/**
 * apply_seo_gaps.ts
 * Reads data/analysis/SEO_ACTION_PLAN_REAL_DATA.json and patches KBLI page metadata
 * if critical SEO gaps are detected.
 *
 * Usage: npx tsx apps/evaluator/apply_seo_gaps.ts [--dry-run]
 *
 * Patches applied only when:
 * - HIGH priority action items exist
 * - GSC shows 0 KBLI queries (no visibility for KBLI pages)
 */
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const PROJECT_ROOT = path.resolve(__dirname, "../../");
const ACTION_PLAN_PATH = path.join(
  PROJECT_ROOT,
  "data/analysis/SEO_ACTION_PLAN_REAL_DATA.json",
);
const PAGE_PATH = path.join(
  PROJECT_ROOT,
  "apps/mouth/src/app/kbli/[code]/page.tsx",
);

interface ActionItem {
  priority: "HIGH" | "MEDIUM" | "LOW";
  action: string;
  reason: string;
}

interface SEOPlan {
  generated_at: string;
  data_sources: { gsc: string; analytics: string };
  gsc_summary: {
    total_queries: number;
    kbli_related_queries: unknown[];
  };
  kbli_audit: { total_codes: number };
  action_items: ActionItem[];
}

function loadPlan(): SEOPlan {
  if (!fs.existsSync(ACTION_PLAN_PATH)) {
    throw new Error(
      `SEO plan not found at ${ACTION_PLAN_PATH}. Run seo_guardian_core.py first.`,
    );
  }
  return JSON.parse(fs.readFileSync(ACTION_PLAN_PATH, "utf-8")) as SEOPlan;
}

function detectCriticalGaps(plan: SEOPlan): {
  hasGaps: boolean;
  reasons: string[];
} {
  const reasons: string[] = [];

  const highItems = plan.action_items.filter((a) => a.priority === "HIGH");
  if (highItems.length > 0) {
    reasons.push(...highItems.map((i) => i.action));
  }

  if (
    plan.gsc_summary.kbli_related_queries.length === 0 &&
    plan.data_sources.gsc === "real"
  ) {
    reasons.push(
      "0 KBLI queries visible in Google Search Console — metadata urgently needs improvement",
    );
  }

  return { hasGaps: reasons.length > 0, reasons };
}

function patchKBLIPageDescription(pageContent: string, plan: SEOPlan): string {
  // Enhance the description in generateMetadata to include KBLI 2025 + Bali Zero signals
  const oldDescription = `const description = \`Complete guide for KBLI \${kbli.code} (\${kbli.titleId}). \${pmaLabel}. Check licensing requirements, risk level, and PMA rules for this Indonesian business activity.\`;`;

  const newDescription = `const description = \`KBLI 2025: \${kbli.code} — \${kbli.titleEn} (\${kbli.titleId}). \${pmaLabel}. Full licensing requirements, PMA rules, and risk level under Indonesian business classification 2025. Expert setup via Bali Zero.\`;`;

  if (!pageContent.includes(oldDescription)) {
    process.stderr.write(
      "[apply_seo_gaps] Description pattern not found — skipping patch (may already be updated).\n",
    );
    return pageContent;
  }

  return pageContent.replace(oldDescription, newDescription);
}

function patchKeywords(pageContent: string): string {
  // Add keywords field to generateMetadata if missing
  const keywordsMarker = "keywords:";
  if (pageContent.includes(keywordsMarker)) {
    log("[apply_seo_gaps] keywords field already present — skipping.");
    return pageContent;
  }

  // Insert after the description line
  const insertAfter = `  return {
    title,
    description,`;
  const withKeywords = `  return {
    title,
    description,
    keywords: \`KBLI \${kbli.code}, \${kbli.titleId}, \${kbli.titleEn}, KBLI 2025, Indonesian business classification, PT PMA Bali, company registration Indonesia\`,`;

  return pageContent.replace(insertAfter, withKeywords);
}

const log = (msg: string) => process.stdout.write(msg + "\n");

function main() {
  const dryRun = process.argv.includes("--dry-run");
  log(`[apply_seo_gaps] Mode: ${dryRun ? "DRY RUN" : "LIVE"}`);

  const plan = loadPlan();
  log(`[apply_seo_gaps] Plan generated: ${plan.generated_at}`);
  log(
    `[apply_seo_gaps] GSC data: ${plan.data_sources.gsc}, KBLI codes: ${plan.kbli_audit.total_codes}`,
  );

  const { hasGaps, reasons } = detectCriticalGaps(plan);

  if (!hasGaps) {
    log("[apply_seo_gaps] No critical SEO gaps detected. No changes needed.");
    return;
  }

  log(`[apply_seo_gaps] CRITICAL GAPS DETECTED (${reasons.length}):`);
  reasons.forEach((r, i) => log(`  ${i + 1}. ${r}`));

  const pageContent = fs.readFileSync(PAGE_PATH, "utf-8");
  let patched = pageContent;

  patched = patchKBLIPageDescription(patched, plan);
  patched = patchKeywords(patched);

  if (patched === pageContent) {
    log("[apply_seo_gaps] No patches applicable (page already up to date).");
    return;
  }

  if (dryRun) {
    log(
      "[apply_seo_gaps] DRY RUN — would patch page.tsx. Re-run without --dry-run to apply.",
    );
  } else {
    fs.writeFileSync(PAGE_PATH, patched, "utf-8");
    log(`[apply_seo_gaps] Patched: ${PAGE_PATH}`);
  }
}

main();
