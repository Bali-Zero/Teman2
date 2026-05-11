/**
 * audit-outdated-visa-codes.ts
 *
 * Read-only audit script — scans all .mdx articles for outdated visa codes
 * (B211A, C312) and checks whether a migration note already exists.
 *
 * Run with:
 *   npx ts-node scripts/audit-outdated-visa-codes.ts
 * or:
 *   npx tsx scripts/audit-outdated-visa-codes.ts
 *
 * Output: research/marketing/2026-05-08-visa-nomenclature-audit.json
 */

import fs from "fs";
import path from "path";

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

/** Root of apps/mouth — script is run from that directory */
const MOUTH_ROOT = path.resolve(__dirname, "..");

/** Directory that contains all MDX article files */
const ARTICLES_DIR = path.join(MOUTH_ROOT, "src", "content", "articles");

/** Output file path */
const OUTPUT_FILE = path.join(
  MOUTH_ROOT,
  "..",
  "..",
  "research",
  "marketing",
  "2026-05-08-visa-nomenclature-audit.json",
);

/** Outdated visa codes to look for */
const OUTDATED_CODES = ["B211A", "C312"] as const;
type OutdatedCode = (typeof OUTDATED_CODES)[number];

/**
 * Phrases that indicate a migration note is already present in the article.
 * Covers both Bahasa Indonesia and English variants.
 */
const MIGRATION_NOTE_PHRASES: string[] = [
  "sekarang C1",
  "now C1",
  "digantikan",
  "replaced by",
  "sekarang E23",
  "now E23",
  "migration note",
];

/** Maps each outdated code to its suggested replacement */
const REPLACEMENT_MAP: Record<OutdatedCode, string> = {
  B211A: "C1",
  C312: "E23",
};

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface AuditEntry {
  slug: string;
  codes_found: string[];
  has_migration_note: boolean;
  suggested_replacement: string;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Recursively collect all .mdx file paths under a given directory.
 */
function collectMdxFiles(dir: string): string[] {
  const results: string[] = [];

  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      results.push(...collectMdxFiles(fullPath));
    } else if (entry.isFile() && entry.name.endsWith(".mdx")) {
      results.push(fullPath);
    }
  }

  return results;
}

/**
 * Derive a URL-style slug from the absolute file path.
 * Example:
 *   .../articles/immigration/how-to-apply-kitas.mdx
 *   → "immigration/how-to-apply-kitas"
 */
function slugFromPath(filePath: string): string {
  const relative = path.relative(ARTICLES_DIR, filePath);
  // Strip the .mdx extension
  return relative.replace(/\.mdx$/, "");
}

/**
 * Build the suggested_replacement string from the list of found codes.
 * If both B211A and C312 appear, join their replacements with ", ".
 */
function buildSuggestedReplacement(codesFound: string[]): string {
  const replacements = codesFound
    .filter((c): c is OutdatedCode =>
      OUTDATED_CODES.includes(c as OutdatedCode),
    )
    .map((c) => REPLACEMENT_MAP[c]);

  // Deduplicate in case the same code appears multiple times
  return [...new Set(replacements)].join(", ");
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

function main(): void {
  // Ensure the output directory exists before writing
  const outputDir = path.dirname(OUTPUT_FILE);
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
    console.log(`Created output directory: ${outputDir}`);
  }

  const allFiles = collectMdxFiles(ARTICLES_DIR);
  const auditResults: AuditEntry[] = [];

  for (const filePath of allFiles) {
    const content = fs.readFileSync(filePath, "utf-8");

    // Collect which outdated codes appear in this file
    const codesFound = OUTDATED_CODES.filter((code) => content.includes(code));

    // Skip files that contain none of the outdated codes
    if (codesFound.length === 0) continue;

    // Check whether a migration note phrase already exists
    const hasMigrationNote = MIGRATION_NOTE_PHRASES.some((phrase) =>
      content.includes(phrase),
    );

    auditResults.push({
      slug: slugFromPath(filePath),
      codes_found: codesFound,
      has_migration_note: hasMigrationNote,
      suggested_replacement: buildSuggestedReplacement(codesFound),
    });
  }

  // Write JSON output (pretty-printed, 2-space indent)
  fs.writeFileSync(OUTPUT_FILE, JSON.stringify(auditResults, null, 2), "utf-8");

  // ---------------------------------------------------------------------------
  // Summary report
  // ---------------------------------------------------------------------------

  const totalScanned = allFiles.length;
  const totalWithOutdatedCodes = auditResults.length;
  const totalWithMigrationNote = auditResults.filter(
    (e) => e.has_migration_note,
  ).length;
  const totalNeedingFix = auditResults.filter(
    (e) => !e.has_migration_note,
  ).length;

  console.log("\n=== Visa Nomenclature Audit ===");
  console.log(`Total files scanned          : ${totalScanned}`);
  console.log(`Files with outdated codes    : ${totalWithOutdatedCodes}`);
  console.log(`Already have migration note  : ${totalWithMigrationNote}`);
  console.log(`Needing fix (no note)        : ${totalNeedingFix}`);
  console.log(`\nOutput saved to: ${OUTPUT_FILE}`);
}

main();
