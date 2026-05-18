/**
 * identify-skip-slugs.ts
 *
 * Read-only heuristic script — reads the visa nomenclature audit JSON and
 * detects which articles are "context-aware": they reference legacy visa codes
 * (B211A, C312) intentionally, within a historical/educational context.
 *
 * Context-aware articles should be added to the SKIP_SLUGS allowlist so the
 * transform script leaves them untouched.
 *
 * THIS SCRIPT NEVER MODIFIES ANY FILE.
 *
 * Run with:
 *   npx ts-node apps/mouth/scripts/identify-skip-slugs.ts
 *
 * Input  : research/marketing/2026-05-08-visa-nomenclature-audit.json
 * Output : research/marketing/2026-05-11-skip-slugs-candidates.json
 */

import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

// ---------------------------------------------------------------------------
// Configuration — paths
// ---------------------------------------------------------------------------

/** Monorepo root (two levels up from apps/mouth/scripts/) */
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const MONOREPO_ROOT = path.resolve(__dirname, "..", "..", "..");

/** Input: audit produced by audit-outdated-visa-codes.ts */
const INPUT_FILE = path.join(
  MONOREPO_ROOT,
  "research",
  "marketing",
  "2026-05-08-visa-nomenclature-audit.json",
);

/** Output: skip-slug candidates for the SKIP_SLUGS allowlist */
const OUTPUT_FILE = path.join(
  MONOREPO_ROOT,
  "research",
  "marketing",
  "2026-05-11-skip-slugs-candidates.json",
);

// ---------------------------------------------------------------------------
// Heuristic phrase lists — Family 1: migration_keyword
// ---------------------------------------------------------------------------

/**
 * Phrases that indicate the article explicitly acknowledges the legacy code
 * as superseded by a regulation change.
 * Checked against the full article body (case-insensitive).
 */
const MIGRATION_KEYWORD_PHRASES: string[] = [
  "permenkumham 22/2023",
  "permenkumham no. 22 tahun 2023",
  "digantikan oleh",
  "digantikan dengan",
  "replaced by",
  "superseded by",
  "now known as",
  "formerly known as",
  "historical reference",
  "untuk referensi historis",
];

// ---------------------------------------------------------------------------
// Heuristic phrase lists — Family 2: date_context
// ---------------------------------------------------------------------------

/**
 * Temporal anchor words/phrases. The heuristic checks whether a legacy visa
 * code (B211A or C312) appears within 10 words of any of these tokens.
 * Checked case-insensitively on the tokenised article body.
 */
const DATE_CONTEXT_ANCHORS: string[] = [
  "2023",
  "before 2023",
  "pre-2023",
  "dulu",
  "sebelumnya",
  "sampai 2023",
  "until 2023",
];

// ---------------------------------------------------------------------------
// Heuristic phrase lists — Family 3: tutorial_signal
// ---------------------------------------------------------------------------

/**
 * Phrases checked against the article title (from frontmatter "title:" field
 * or first H1 line starting with "# ").
 * Checked case-insensitively.
 */
const TUTORIAL_SIGNAL_PHRASES: string[] = [
  "evolution",
  "history",
  "timeline",
  "changes from",
  "from b211a to",
  "from b211a to c1",
  "migrasi",
  "perubahan kode",
  "regulatory shift",
];

// ---------------------------------------------------------------------------
// Legacy visa codes to detect proximity for date_context
// ---------------------------------------------------------------------------

const LEGACY_CODES = ["B211A", "C312"] as const;
type LegacyCode = (typeof LEGACY_CODES)[number];

// ---------------------------------------------------------------------------
// Heuristic family names and their priority ordering
// ---------------------------------------------------------------------------

type HeuristicFamily = "migration_keyword" | "date_context" | "tutorial_signal";

/**
 * Priority order for selecting the "strongest" family when an article matches
 * multiple families. Lower index = higher priority.
 */
const FAMILY_PRIORITY: HeuristicFamily[] = [
  "migration_keyword",
  "tutorial_signal",
  "date_context",
];

// ---------------------------------------------------------------------------
// Types for input audit JSON
// ---------------------------------------------------------------------------

interface AuditEntry {
  slug: string;
  // NOTE: the audit JSON does not include a "filepath" field.
  // The absolute path is derived from the slug at runtime.
  codes_found: string[];
  has_migration_note: boolean;
  suggested_replacement: string;
}

// ---------------------------------------------------------------------------
// Types for output JSON
// ---------------------------------------------------------------------------

type Lang = "en" | "id" | "it" | "fr" | "ru";

interface SkipCandidate {
  slug: string;
  lang: Lang;
  reason: string;
  matched_phrase: string;
  surrounding_snippet: string;
  heuristic_family: HeuristicFamily;
}

interface OutputReport {
  generated_at: string;
  total_processed: number;
  skip_count: number;
  flag_count: number;
  heuristic_breakdown: Record<HeuristicFamily, number>;
  candidates: SkipCandidate[];
}

// ---------------------------------------------------------------------------
// Helper: detect language from filepath suffix
// ---------------------------------------------------------------------------

/**
 * Derives the article language from the MDX filename suffix.
 *   foo.id.mdx  → "id"
 *   foo.it.mdx  → "it"
 *   foo.fr.mdx  → "fr"
 *   foo.ru.mdx  → "ru"
 *   foo.mdx     → "en"  (no lang suffix = default English)
 */
function detectLang(filepath: string): Lang {
  const basename = path.basename(filepath);
  // Match the optional language code immediately before ".mdx"
  const match = basename.match(/\.([a-z]{2})\.mdx$/);
  if (!match) return "en";
  const code = match[1];
  if (code === "id" || code === "it" || code === "fr" || code === "ru") {
    return code;
  }
  // Unknown suffix → treat as English
  return "en";
}

// ---------------------------------------------------------------------------
// Helper: resolve absolute disk path from article slug
// ---------------------------------------------------------------------------

/**
 * Builds the absolute MDX file path from the article slug.
 *
 * The audit JSON only contains a "slug" field (no "filepath").
 * Pattern:
 *   slug     → "business/bkpm-regulation-5-2025-fdi.fr"
 *   filepath → "<MONOREPO_ROOT>/apps/mouth/src/content/articles/business/bkpm-regulation-5-2025-fdi.fr.mdx"
 */
function resolveFilePath(slug: string): string {
  return path.join(
    MONOREPO_ROOT,
    "apps",
    "mouth",
    "src",
    "content",
    "articles",
    slug + ".mdx",
  );
}

// ---------------------------------------------------------------------------
// Helper: extract article title from raw MDX content
// ---------------------------------------------------------------------------

/**
 * Looks for:
 *   1. A "title:" key inside the frontmatter block (between "---" delimiters).
 *   2. The first Markdown H1 line (starting with "# ").
 * Returns an empty string if neither is found.
 */
function extractTitle(content: string): string {
  const lines = content.split("\n");
  let inFrontmatter = false;
  let frontmatterClosed = false;

  for (const line of lines) {
    const trimmed = line.trim();

    // Detect frontmatter boundaries
    if (trimmed === "---") {
      if (!inFrontmatter && !frontmatterClosed) {
        inFrontmatter = true;
        continue;
      }
      if (inFrontmatter) {
        inFrontmatter = false;
        frontmatterClosed = true;
        continue;
      }
    }

    // Inside frontmatter: look for "title:" key
    if (inFrontmatter) {
      const titleMatch = trimmed.match(/^title\s*:\s*["']?(.+?)["']?\s*$/i);
      if (titleMatch) return titleMatch[1];
    }

    // Outside frontmatter: look for first H1
    if (frontmatterClosed && trimmed.startsWith("# ")) {
      return trimmed.slice(2).trim();
    }
  }

  return "";
}

// ---------------------------------------------------------------------------
// Helper: extract surrounding snippet (±1 sentence) around a phrase
// ---------------------------------------------------------------------------

/**
 * Finds the position of `phrase` in `content` (case-insensitive) and returns
 * a snippet of ±1 sentence around it.
 *
 * Strategy:
 *   - Locate the phrase within the lowercased content.
 *   - Walk backwards to find the previous sentence boundary (". ", "! ", "? ").
 *   - Walk forwards to find the next sentence boundary.
 *   - Cap total snippet length at 400 characters.
 */
function extractSnippet(content: string, phrase: string): string {
  const lower = content.toLowerCase();
  const phrasePos = lower.indexOf(phrase.toLowerCase());
  if (phrasePos === -1) return "";

  const MAX_SNIPPET = 400;
  // Walk back to find sentence start
  let start = phrasePos;
  while (start > 0) {
    const prev = content[start - 1];
    if ((prev === "." || prev === "!" || prev === "?") && start < phrasePos) {
      break;
    }
    start--;
    // Limit how far back we walk
    if (phrasePos - start > MAX_SNIPPET / 2) break;
  }

  // Walk forward to find sentence end (two sentences after match)
  const phraseEnd = phrasePos + phrase.length;
  let end = phraseEnd;
  let sentenceCount = 0;
  while (end < content.length && sentenceCount < 2) {
    const ch = content[end];
    if (ch === "." || ch === "!" || ch === "?") sentenceCount++;
    end++;
    if (end - phrasePos > MAX_SNIPPET) break;
  }

  return content.slice(start, end).replace(/\s+/g, " ").trim();
}

// ---------------------------------------------------------------------------
// Family 1 check: migration_keyword
// ---------------------------------------------------------------------------

interface HeuristicMatch {
  matched: boolean;
  phrase: string;
  snippet: string;
}

/**
 * Checks whether the article body contains any migration_keyword phrase.
 * Returns the first matching phrase and a surrounding snippet.
 */
function checkMigrationKeyword(content: string): HeuristicMatch {
  const lower = content.toLowerCase();
  for (const phrase of MIGRATION_KEYWORD_PHRASES) {
    if (lower.includes(phrase.toLowerCase())) {
      return {
        matched: true,
        phrase,
        snippet: extractSnippet(content, phrase),
      };
    }
  }
  return { matched: false, phrase: "", snippet: "" };
}

// ---------------------------------------------------------------------------
// Family 2 check: date_context
// ---------------------------------------------------------------------------

/**
 * Tokenises the body into words and checks whether a legacy visa code
 * (B211A or C312) appears within 10 words of any DATE_CONTEXT_ANCHOR.
 *
 * Returns the matched anchor phrase and the raw matched phrase
 * (code + anchor or anchor + code) for the report.
 */
function checkDateContext(content: string): HeuristicMatch {
  // Normalise: lowercase, split on whitespace
  const words = content.toLowerCase().split(/\s+/);

  for (let i = 0; i < words.length; i++) {
    const word = words[i];

    // Check if this position is a legacy code token
    const isCode = LEGACY_CODES.some((code) =>
      word.includes(code.toLowerCase()),
    );
    if (!isCode) continue;

    // Examine a window of ±10 words around the code position
    const windowStart = Math.max(0, i - 10);
    const windowEnd = Math.min(words.length - 1, i + 10);
    const windowTokens = words.slice(windowStart, windowEnd + 1);

    for (const anchor of DATE_CONTEXT_ANCHORS) {
      const anchorWords = anchor.toLowerCase().split(/\s+/);
      // Check if the anchor phrase appears in the window
      for (let j = 0; j <= windowTokens.length - anchorWords.length; j++) {
        const slice = windowTokens.slice(j, j + anchorWords.length);
        if (slice.join(" ") === anchorWords.join(" ")) {
          // Reconstruct a human-readable matched phrase
          const codeToken = LEGACY_CODES.find((c) =>
            word.includes(c.toLowerCase()),
          )!;
          const matchedPhrase = `${codeToken} near "${anchor}"`;
          return {
            matched: true,
            phrase: matchedPhrase,
            snippet: extractSnippet(content, anchor),
          };
        }
      }
    }
  }

  return { matched: false, phrase: "", snippet: "" };
}

// ---------------------------------------------------------------------------
// Family 3 check: tutorial_signal
// ---------------------------------------------------------------------------

/**
 * Checks whether the article title (extracted from frontmatter or first H1)
 * contains any tutorial_signal phrase (case-insensitive).
 */
function checkTutorialSignal(content: string): HeuristicMatch {
  const title = extractTitle(content).toLowerCase();
  if (!title) return { matched: false, phrase: "", snippet: "" };

  for (const phrase of TUTORIAL_SIGNAL_PHRASES) {
    if (title.includes(phrase.toLowerCase())) {
      return {
        matched: true,
        phrase,
        // Snippet is the full title line, as the signal is in the title itself
        snippet: `Title: "${extractTitle(content)}"`,
      };
    }
  }

  return { matched: false, phrase: "", snippet: "" };
}

// ---------------------------------------------------------------------------
// Core: run all 3 heuristic families and select strongest
// ---------------------------------------------------------------------------

interface ArticleResult {
  isContextAware: boolean;
  family: HeuristicFamily | null;
  matchedPhrase: string;
  snippet: string;
}

/**
 * Runs all three heuristic families against the article content.
 * All families are always evaluated (additive).
 * If multiple match, the highest-priority family wins.
 * Priority: migration_keyword > tutorial_signal > date_context.
 */
function analyseArticle(content: string): ArticleResult {
  const results: Partial<Record<HeuristicFamily, HeuristicMatch>> = {
    migration_keyword: checkMigrationKeyword(content),
    tutorial_signal: checkTutorialSignal(content),
    date_context: checkDateContext(content),
  };

  // Select strongest matching family according to FAMILY_PRIORITY order
  for (const family of FAMILY_PRIORITY) {
    const result = results[family];
    if (result?.matched) {
      return {
        isContextAware: true,
        family,
        matchedPhrase: result.phrase,
        snippet: result.snippet,
      };
    }
  }

  return {
    isContextAware: false,
    family: null,
    matchedPhrase: "",
    snippet: "",
  };
}

// ---------------------------------------------------------------------------
// Helper: build human-readable "reason" field from family + phrase
// ---------------------------------------------------------------------------

/**
 * Generates a short, readable explanation for why an article is classified
 * as context-aware, based on the matched heuristic family.
 */
function buildReason(family: HeuristicFamily, phrase: string): string {
  switch (family) {
    case "migration_keyword":
      return `Article explicitly references the regulatory change (matched: "${phrase}")`;
    case "date_context":
      return `Legacy code appears in temporal context (${phrase})`;
    case "tutorial_signal":
      return `Article title signals historical/educational intent (matched: "${phrase}")`;
  }
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

function main(): void {
  // ------------------------------------------------------------------
  // 1. Load input audit JSON
  // ------------------------------------------------------------------
  if (!fs.existsSync(INPUT_FILE)) {
    console.error(`[ERROR] Input file not found: ${INPUT_FILE}`);
    console.error(
      "        Run audit-outdated-visa-codes.ts first to generate it.",
    );
    process.exit(1);
  }

  const rawInput = fs.readFileSync(INPUT_FILE, "utf-8");
  const auditEntries: AuditEntry[] = JSON.parse(rawInput);

  // ------------------------------------------------------------------
  // 2. Initialise counters
  // ------------------------------------------------------------------
  let skipCount = 0;
  let flagCount = 0;
  let notFoundCount = 0;
  const breakdown: Record<HeuristicFamily, number> = {
    migration_keyword: 0,
    date_context: 0,
    tutorial_signal: 0,
  };
  const candidates: SkipCandidate[] = [];

  // ------------------------------------------------------------------
  // 3. Process each audit entry
  // ------------------------------------------------------------------
  for (const entry of auditEntries) {
    // Build the absolute path from the slug — entry.filepath does not exist in the JSON
    const absPath = resolveFilePath(entry.slug);

    // Guard: file must exist on disk
    if (!fs.existsSync(absPath)) {
      console.warn(`[WARN] File not found on disk: ${absPath}`);
      notFoundCount++;
      continue;
    }

    // Read MDX as plain text — no parser needed
    let content: string;
    try {
      content = fs.readFileSync(absPath, "utf-8");
    } catch (err) {
      console.warn(`[WARN] Could not read file: ${absPath} — ${String(err)}`);
      notFoundCount++;
      continue;
    }

    // Run heuristic analysis
    const result = analyseArticle(content);

    if (result.isContextAware && result.family) {
      // Context-aware: add to candidates list
      skipCount++;
      breakdown[result.family]++;

      // Detect language from the slug suffix (e.g. "foo.fr" → "fr")
      const lang = detectLang(entry.slug);
      candidates.push({
        slug: entry.slug,
        lang,
        reason: buildReason(result.family, result.matchedPhrase),
        matched_phrase: result.matchedPhrase,
        surrounding_snippet: result.snippet,
        heuristic_family: result.family,
      });

      console.log(
        `[SKIP]  ${entry.slug} | family: ${result.family} | phrase: "${result.matchedPhrase}"`,
      );
    } else {
      // Not context-aware: needs a migration note
      flagCount++;
      console.log(`[FLAG]  ${entry.slug} | no match`);
    }
  }

  // ------------------------------------------------------------------
  // 4. Print summary to console
  // ------------------------------------------------------------------
  const total = auditEntries.length;
  console.log("\n─────────────────────────────────────────────");
  console.log(`Total processed           : ${total}`);
  console.log(`Context-aware (SKIP)      : ${skipCount}`);
  console.log(`  - migration_keyword     : ${breakdown.migration_keyword}`);
  console.log(`  - date_context          : ${breakdown.date_context}`);
  console.log(`  - tutorial_signal       : ${breakdown.tutorial_signal}`);
  console.log(`Needs migration note      : ${flagCount}`);
  console.log(`File not found on disk    : ${notFoundCount}`);
  console.log("─────────────────────────────────────────────");

  // ------------------------------------------------------------------
  // 5. Write output JSON
  // ------------------------------------------------------------------
  const report: OutputReport = {
    generated_at: new Date().toISOString(),
    total_processed: total,
    skip_count: skipCount,
    flag_count: flagCount,
    heuristic_breakdown: breakdown,
    candidates,
  };

  const outputDir = path.dirname(OUTPUT_FILE);
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }

  fs.writeFileSync(OUTPUT_FILE, JSON.stringify(report, null, 2), "utf-8");
  console.log(`\nOutput saved to: ${OUTPUT_FILE}`);
}

main();
