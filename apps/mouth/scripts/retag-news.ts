/**
 * retag-news.ts
 *
 * Scans immigration, business, and tax-legal article folders.
 * If the slug OR the frontmatter title matches a "news" keyword and the file
 * does NOT already have category: "news", inserts that field.
 *
 * Run with:
 *   npx ts-node scripts/retag-news.ts
 *   npx tsx   scripts/retag-news.ts
 *
 * Set DRY_RUN = false to apply actual writes.
 */

import fs from "fs";
import path from "path";

// ---------------------------------------------------------------------------
// Config — flip to false to write files
// ---------------------------------------------------------------------------

const DRY_RUN = false;

// ---------------------------------------------------------------------------
// Directories to scan (relative to apps/mouth/)
// ---------------------------------------------------------------------------

const MOUTH_ROOT = path.resolve(__dirname, "..");

const SCAN_DIRS = [
  path.join(MOUTH_ROOT, "src", "content", "articles", "immigration"),
  path.join(MOUTH_ROOT, "src", "content", "articles", "business"),
  path.join(MOUTH_ROOT, "src", "content", "articles", "tax-legal"),
];

// ---------------------------------------------------------------------------
// News keyword lists
// ---------------------------------------------------------------------------

/**
 * Keywords checked against the SLUG (hyphen-separated, lowercase).
 * Year/date patterns are intentionally excluded — too broad for evergreen articles.
 */
const SLUG_KEYWORDS = [
  "news",
  "update",
  "alert",
  "announces",
  "reshuffle",
  "arrives",
  "launches",
  "breaking",
  "latest",
  "new-regulation",
  "new-rule",
  "amendment",
  "circular",
  "decree",
  "enacted",
  "effective-",
  "deports",
  "arrests",
  "raids",
  "bans",
  "halts",
  "confirms",
  "approves",
  "rejects",
  "expels",
];

/**
 * Keywords checked against the frontmatter TITLE field (natural language,
 * may contain spaces — matched case-insensitively as substrings).
 */
const TITLE_KEYWORDS = [
  "news",
  "update",
  "alert",
  "announces",
  "reshuffle",
  "arrives",
  "launches",
  "breaking",
  "latest",
  "new regulation",
  "new rule",
  "amendment",
  "circular",
  "decree",
  "enacted",
  "effective",
  "deports",
  "arrests",
  "raids",
  "bans",
  "halts",
  "confirms",
  "approves",
  "rejects",
  "expels",
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Recursively collect all .mdx files under a directory. */
function collectMdx(dir: string): string[] {
  if (!fs.existsSync(dir)) return [];
  const results: string[] = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      results.push(...collectMdx(full));
    } else if (entry.isFile() && entry.name.endsWith(".mdx")) {
      results.push(full);
    }
  }
  return results;
}

/** Extract the bare slug from a file path (filename without .mdx). */
function slugFromPath(filePath: string): string {
  return path.basename(filePath, ".mdx");
}

/**
 * Extract the raw value of the `title:` field from the frontmatter block.
 * Returns an empty string if not found.
 */
function extractTitle(content: string): string {
  const fmMatch = content.match(/^---\r?\n([\s\S]*?)\r?\n---/);
  if (!fmMatch) return "";
  // Match: title: "Some Title" or title: Some Title (quoted or unquoted)
  const titleLine = fmMatch[1]
    .split(/\r?\n/)
    .find((l) => /^\s*title\s*:/i.test(l));
  if (!titleLine) return "";
  return titleLine
    .replace(/^\s*title\s*:\s*/i, "") // strip the key
    .replace(/^"|"$/g, "") // strip surrounding double quotes
    .replace(/^'|'$/g, "") // strip surrounding single quotes
    .trim();
}

/**
 * Check the slug against SLUG_KEYWORDS.
 * Returns the first matching keyword, or null if none match.
 */
function slugMatchKeyword(slug: string): string | null {
  const lower = slug.toLowerCase();
  return SLUG_KEYWORDS.find((kw) => lower.includes(kw)) ?? null;
}

/**
 * Check the title against TITLE_KEYWORDS.
 * Returns the first matching keyword, or null if none match.
 */
function titleMatchKeyword(title: string): string | null {
  const lower = title.toLowerCase();
  return TITLE_KEYWORDS.find((kw) => lower.includes(kw)) ?? null;
}

/**
 * Returns true when the raw frontmatter block already contains
 * a `category: "news"` (or `category: news`) field.
 * Only looks inside the first --- ... --- block.
 */
function hasNewsCategory(content: string): boolean {
  const fmMatch = content.match(/^---\r?\n([\s\S]*?)\r?\n---/);
  if (!fmMatch) return false;
  const fm = fmMatch[1];
  // Match both quoted and unquoted variants
  return /^\s*category\s*:\s*["']?news["']?\s*$/im.test(fm);
}

/**
 * Insert `category: "news"` after the first frontmatter field.
 *
 * Strategy:
 *  1. Locate the opening ---.
 *  2. Find the first non-empty line inside the frontmatter block.
 *  3. Insert category: "news" on the very next line.
 *
 * This preserves all other content byte-for-byte.
 */
function insertNewsCategory(content: string): string {
  // Match: "---\n" + everything up to closing "---"
  const fmRegex = /^(---\r?\n)([\s\S]*?)(\r?\n---)/;
  const match = content.match(fmRegex);
  if (!match) return content; // No frontmatter found — skip

  const opener = match[1]; // "---\n"
  const fmBody = match[2]; // raw frontmatter lines
  const closer = match[3]; // "\n---"

  // Split frontmatter into individual lines
  const lines = fmBody.split(/\r?\n/);

  // Find the index of the first non-empty line (= first real field)
  const firstFieldIdx = lines.findIndex((l) => l.trim() !== "");

  if (firstFieldIdx === -1) {
    // Frontmatter is empty — just prepend the field
    const newFm = `category: "news"\n${fmBody}`;
    return content.replace(fmRegex, `${opener}${newFm}${closer}`);
  }

  // Insert category: "news" right after the first field line
  lines.splice(firstFieldIdx + 1, 0, `category: "news"`);
  const newFm = lines.join("\n");
  return content.replace(fmRegex, `${opener}${newFm}${closer}`);
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

function main(): void {
  if (DRY_RUN) {
    console.log("=== DRY RUN MODE — no files will be written ===\n");
  }

  // Collect every .mdx file across all target directories
  const allFiles: string[] = SCAN_DIRS.flatMap(collectMdx);

  let totalMatched = 0;
  let totalSkipped = 0; // already had category: news
  let totalUpdated = 0;
  let dryRunPrinted = 0; // counter for the first-10 preview

  for (const filePath of allFiles) {
    const slug = slugFromPath(filePath);
    const content = fs.readFileSync(filePath, "utf-8");
    const title = extractTitle(content);

    // Step 1 — check slug OR title against their respective keyword lists
    const slugHit = slugMatchKeyword(slug);
    const titleHit = titleMatchKeyword(title);
    if (!slugHit && !titleHit) continue;
    totalMatched++;

    // Step 2 — skip if category: news already present
    if (hasNewsCategory(content)) {
      totalSkipped++;
      continue;
    }

    // Step 3 — apply or preview
    if (DRY_RUN) {
      if (dryRunPrinted < 10) {
        console.log(`[WOULD UPDATE] ${path.relative(MOUTH_ROOT, filePath)}`);
        console.log(`  slug    : ${slug}`);
        console.log(`  title   : ${title || "(no title field)"}`);

        // Show whether the trigger came from slug, title, or both
        const triggers: string[] = [];
        if (slugHit) triggers.push(`slug:"${slugHit}"`);
        if (titleHit) triggers.push(`title:"${titleHit}"`);
        console.log(`  matched : ${triggers.join(", ")}`);
        console.log();
        dryRunPrinted++;
      }
      totalUpdated++; // count "would update" in dry run
    } else {
      // Live mode — write the modified content back
      const updated = insertNewsCategory(content);
      fs.writeFileSync(filePath, updated, "utf-8");
      totalUpdated++;
    }
  }

  // ---------------------------------------------------------------------------
  // Summary
  // ---------------------------------------------------------------------------
  const label = DRY_RUN ? "Would update" : "Updated";

  console.log("=== retag-news Summary ===");
  console.log(`Total files scanned               : ${allFiles.length}`);
  console.log(`Total matched (news pattern)      : ${totalMatched}`);
  console.log(`Already had category: news (skip) : ${totalSkipped}`);
  console.log(`${label.padEnd(33)}: ${totalUpdated}`);

  if (DRY_RUN) {
    console.log("\nSet DRY_RUN = false and re-run to apply changes.");
  }
}

main();
