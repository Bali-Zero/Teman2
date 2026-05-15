/**
 * audit-internal-links.ts
 *
 * Read-only audit script — scans all .mdx articles under
 * apps/mouth/src/content/articles/**\/*.mdx, extracts every internal link,
 * counts inbound links per slug, and emits a CSV report.
 *
 * Link sources extracted:
 *   1. Markdown links:          [text](/path/to/slug)  or  [text](relative-slug)
 *   2. JSX / HTML href attrs:   href="/path/to/slug"   or  href='…'
 *   3. Frontmatter YAML:        relatedArticles: [ "slug-foo", … ]
 *
 * Run with:
 *   npx tsx scripts/audit-internal-links.ts
 * or via npm:
 *   npm run audit:links   (from apps/mouth/)
 *
 * Output:
 *   scripts/output/internal-links-audit.csv
 */

import fs from "fs";
import path from "path";

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

/** Root of apps/mouth — script is run from that directory */
const MOUTH_ROOT: string = path.resolve(__dirname, "..");

/** Directory that contains all MDX article files */
const ARTICLES_DIR: string = path.join(
  MOUTH_ROOT,
  "src",
  "content",
  "articles",
);

/** Output CSV file path */
const OUTPUT_FILE: string = path.join(
  MOUTH_ROOT,
  "scripts",
  "output",
  "internal-links-audit.csv",
);

/** Minimum inbound links before a page is considered healthy */
const MIN_INBOUND_LINKS = 5;

/**
 * Money pages that must always be flagged when inbound count < MIN_INBOUND_LINKS,
 * regardless of overall article count.
 */
const PRIORITY_SLUGS: ReadonlySet<string> = new Set([
  "tax-residency-indonesia",
  "npwp-foreigners-guide",
  "tax-incentives-indonesia",
  "rental-income-tax-indonesia",
  "tax-calendar-indonesia",
  "vat-ppn-guide",
  "indonesia-zero-tax-foreign-income-2026",
  "capital-gains-tax-indonesia",
  "pph-21-expat-guide",
  "coretax-efiling-spt-guide",
  "tax-holiday-pioneer-industries-list-2026",
]);

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ArticleRecord {
  /** Bare slug: last path segment without extension, e.g. "tax-residency-indonesia" */
  slug: string;
  /** Category derived from directory name, e.g. "tax" */
  category: string;
  /** Absolute file path for reference */
  filePath: string;
}

interface LinkAuditRow {
  slug: string;
  category: string;
  inbound_count: number;
  linking_pages: string; // comma-separated list of slugs that link to this page
  needs_links: "NEEDS_LINKS" | "OK";
  is_priority: "YES" | "";
}

// ---------------------------------------------------------------------------
// Helpers — file system
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
 * Derive a bare slug and category from the absolute file path.
 *
 * Examples:
 *   .../articles/tax/tax-residency-indonesia.mdx   → { slug: "tax-residency-indonesia",    category: "tax" }
 *   .../articles/immigration/kitas-guide.id.mdx    → { slug: "kitas-guide.id",              category: "immigration" }
 *
 * NOTE: We preserve locale suffixes (.id, .fr, etc.) in the slug because
 * they represent distinct pages.  Links that omit the locale are matched
 * against the bare (English) slug only.
 */
function recordFromPath(filePath: string): ArticleRecord {
  const relativeToArticles = path.relative(ARTICLES_DIR, filePath);
  // e.g. "tax/tax-residency-indonesia.mdx"  or  "immigration/kitas-guide.id.mdx"

  const parts = relativeToArticles.split(path.sep);
  // category is the first directory segment
  const category = parts.length > 1 ? parts[0] : "uncategorised";
  // slug is the filename without the .mdx extension
  const slug = path.basename(filePath, ".mdx");

  return { slug, category, filePath };
}

// ---------------------------------------------------------------------------
// Helpers — link extraction
// ---------------------------------------------------------------------------

/**
 * Pattern 1 — Markdown links:  [label](href)
 * Capture group 1 = href value.
 */
const MARKDOWN_LINK_RE = /\[(?:[^\]]*)\]\(([^)]+)\)/g;

/**
 * Pattern 2 — JSX / HTML href attributes.
 * Matches  href="..."  and  href='...'
 * Capture group 1 = href value.
 */
const JSX_HREF_RE = /href=["']([^"']+)["']/g;

/**
 * Pattern 3 — YAML frontmatter relatedArticles list entries.
 * Matches lines like:   - "some-slug"   or   - some-slug
 * We only look for these lines inside a detected relatedArticles block.
 */
const FRONTMATTER_RE = /^---\r?\n([\s\S]*?)\r?\n---/;
const RELATED_ARTICLES_RE = /^relatedArticles:\s*\n((?:[ \t]*-[ \t]+.*\n?)*)/m;
const YAML_LIST_ITEM_RE = /^[ \t]*-[ \t]+["']?([^"'\n\r]+)["']?/gm;

/**
 * Normalise a raw href value to a bare slug (last non-empty path segment).
 *
 * Examples:
 *   /tax/tax-residency-indonesia          → "tax-residency-indonesia"
 *   /insights/tax/npwp-foreigners-guide   → "npwp-foreigners-guide"
 *   tax-residency-indonesia               → "tax-residency-indonesia"
 *   #section-heading                      → null  (fragment-only → skip)
 *   https://external.com/page            → null  (external → skip)
 *   mailto:info@balizero.com             → null  (non-http → skip)
 */
function normaliseHref(raw: string): string | null {
  const trimmed = raw.trim();

  // Skip external links, mail, tel, javascript: etc.
  if (/^(https?:|mailto:|tel:|javascript:|#)/.test(trimmed)) {
    return null;
  }

  // Skip anchor-only fragments
  if (trimmed.startsWith("#")) return null;

  // Strip query params and fragments
  const withoutQF = trimmed.split("?")[0].split("#")[0];

  // Split on "/" and take the last non-empty segment
  const segments = withoutQF.split("/").filter((s) => s.length > 0);
  if (segments.length === 0) return null;

  return segments[segments.length - 1];
}

/**
 * Extract all internal link targets (as bare slugs) from a single MDX file's content.
 * Returns a deduplicated array of bare slugs found in this file.
 */
function extractLinkedSlugs(content: string): string[] {
  const found = new Set<string>();

  // --- Pattern 1: Markdown links ---
  let match: RegExpExecArray | null;
  MARKDOWN_LINK_RE.lastIndex = 0;
  while ((match = MARKDOWN_LINK_RE.exec(content)) !== null) {
    const slug = normaliseHref(match[1]);
    if (slug) found.add(slug);
  }

  // --- Pattern 2: JSX href attributes ---
  JSX_HREF_RE.lastIndex = 0;
  while ((match = JSX_HREF_RE.exec(content)) !== null) {
    const slug = normaliseHref(match[1]);
    if (slug) found.add(slug);
  }

  // --- Pattern 3: relatedArticles in YAML frontmatter ---
  const fmMatch = FRONTMATTER_RE.exec(content);
  if (fmMatch) {
    const frontmatter = fmMatch[1];
    const raMatch = RELATED_ARTICLES_RE.exec(frontmatter);
    if (raMatch) {
      const listBlock = raMatch[1];
      YAML_LIST_ITEM_RE.lastIndex = 0;
      while ((match = YAML_LIST_ITEM_RE.exec(listBlock)) !== null) {
        const rawValue = match[1].trim();
        // relatedArticles values are bare slugs or relative paths
        const slug = normaliseHref(rawValue) ?? rawValue;
        if (slug && slug.length > 0) found.add(slug);
      }
    }
  }

  return Array.from(found);
}

// ---------------------------------------------------------------------------
// CSV helpers
// ---------------------------------------------------------------------------

/**
 * Escape a CSV cell value: wrap in double quotes if it contains commas,
 * newlines, or double quotes.  Doubles any embedded double-quote characters.
 */
function csvCell(value: string | number): string {
  const str = String(value);
  if (/[",\n\r]/.test(str)) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
}

function toCsvRow(fields: (string | number)[]): string {
  return fields.map(csvCell).join(",");
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

function main(): void {
  console.log("=== Internal Links Audit ===");
  console.log(`Articles dir : ${ARTICLES_DIR}`);
  console.log(`Output file  : ${OUTPUT_FILE}\n`);

  // --- 1. Collect all MDX files and build article registry ---

  const allFiles = collectMdxFiles(ARTICLES_DIR);
  console.log(`Files found  : ${allFiles.length}`);

  // Map from bare slug → ArticleRecord  (first definition wins for duplicates)
  const articlesBySlug = new Map<string, ArticleRecord>();

  for (const filePath of allFiles) {
    const record = recordFromPath(filePath);
    if (!articlesBySlug.has(record.slug)) {
      articlesBySlug.set(record.slug, record);
    }
  }

  // --- 2. Build inbound link graph ---
  //
  // inboundLinks: targetSlug → Set<sourceSlug> (slugs that link TO the target)

  const inboundLinks = new Map<string, Set<string>>();

  // Initialise entries for all known slugs so zero-inbound articles appear in output
  for (const slug of articlesBySlug.keys()) {
    inboundLinks.set(slug, new Set<string>());
  }

  for (const [sourceSlug, record] of articlesBySlug.entries()) {
    const content = fs.readFileSync(record.filePath, "utf-8");
    const linkedSlugs = extractLinkedSlugs(content);

    for (const targetSlug of linkedSlugs) {
      // Only count links whose target is a known article slug
      if (!articlesBySlug.has(targetSlug)) continue;
      // Ignore self-links
      if (targetSlug === sourceSlug) continue;

      if (!inboundLinks.has(targetSlug)) {
        inboundLinks.set(targetSlug, new Set<string>());
      }
      inboundLinks.get(targetSlug)!.add(sourceSlug);
    }
  }

  // --- 3. Build sorted rows ---

  const rows: LinkAuditRow[] = [];

  for (const [slug, linkers] of inboundLinks.entries()) {
    const record = articlesBySlug.get(slug)!;
    const inboundCount = linkers.size;
    const needsLinks = inboundCount < MIN_INBOUND_LINKS ? "NEEDS_LINKS" : "OK";
    const isPriority = PRIORITY_SLUGS.has(slug) ? "YES" : "";

    rows.push({
      slug,
      category: record.category,
      inbound_count: inboundCount,
      linking_pages: Array.from(linkers).sort().join(", "),
      needs_links: needsLinks,
      is_priority: isPriority,
    });
  }

  // Sort: priority pages first, then by inbound_count ascending (worst first), then alpha
  rows.sort((a, b) => {
    const aPriority = a.is_priority === "YES" ? 0 : 1;
    const bPriority = b.is_priority === "YES" ? 0 : 1;
    if (aPriority !== bPriority) return aPriority - bPriority;
    if (a.inbound_count !== b.inbound_count)
      return a.inbound_count - b.inbound_count;
    return a.slug.localeCompare(b.slug);
  });

  // --- 4. Write CSV ---

  const outputDir = path.dirname(OUTPUT_FILE);
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }

  const CSV_HEADER = toCsvRow([
    "slug",
    "category",
    "inbound_count",
    "linking_pages",
    "needs_links",
    "is_priority",
  ]);

  const csvLines: string[] = [CSV_HEADER];

  for (const row of rows) {
    csvLines.push(
      toCsvRow([
        row.slug,
        row.category,
        row.inbound_count,
        row.linking_pages,
        row.needs_links,
        row.is_priority,
      ]),
    );
  }

  fs.writeFileSync(OUTPUT_FILE, csvLines.join("\n") + "\n", "utf-8");

  // --- 5. Summary report ---

  const totalArticles = articlesBySlug.size;
  const needsLinksCount = rows.filter(
    (r) => r.needs_links === "NEEDS_LINKS",
  ).length;
  const okCount = rows.filter((r) => r.needs_links === "OK").length;
  const priorityNeedsLinks = rows.filter(
    (r) => r.is_priority === "YES" && r.needs_links === "NEEDS_LINKS",
  );

  console.log("\n--- Results ---");
  console.log(`Total articles (unique slugs) : ${totalArticles}`);
  console.log(`OK (≥${MIN_INBOUND_LINKS} inbound links)       : ${okCount}`);
  console.log(
    `NEEDS_LINKS (<${MIN_INBOUND_LINKS} inbound)    : ${needsLinksCount}`,
  );

  if (priorityNeedsLinks.length > 0) {
    console.log(
      `\n⚠️  Priority (money) pages with NEEDS_LINKS: ${priorityNeedsLinks.length}`,
    );
    for (const row of priorityNeedsLinks) {
      console.log(
        `   ${row.slug.padEnd(50)} ${row.inbound_count} inbound link(s)`,
      );
    }
  } else {
    console.log("\n✅  All priority money pages have ≥5 inbound links.");
  }

  console.log(`\nCSV written to: ${OUTPUT_FILE}`);
}

main();
