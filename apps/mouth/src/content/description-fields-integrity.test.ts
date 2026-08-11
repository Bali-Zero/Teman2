// =============================================================================
// DESCRIPTION FIELD INTEGRITY — what Google prints, and what an LLM reads.
//
// WHY THIS EXISTS. TWO fields, two audiences, one defect.
//
// `seoDescription` becomes `<meta name="description">` and `og:description`
// (page.tsx:194, `article.seoDescription || article.excerpt`) — the sentence a
// prospective client reads in the search results and on every shared link.
// `excerpt` is BOTH that fallback and the "ZANTARA AI SUMMARY" block of the
// AI-ingestion exports (generate-llms-full.ts:73,107,120), so it is what an LLM
// reads when it answers a question about Bali Zero. Guarding only the first
// leaves the exports dirty — measured: 484 occurrences still in llms-full.txt
// after seoDescription alone was repaired, which is how `excerpt` was found.
//
// Measured live on balizero.com 2026-08-11, in EVERY language — 608 articles
// served a markdown heading in seoDescription and 675 in excerpt:
//
//     <meta name="description" content="## Facts  Indonesia's Directorate ...">
//
// and 33 of them — English and Italian among them — served this:
//
//     <meta name="description" content="## Facts aiGenerated: true
//      aiConfidenceScore: 0.85 aiOptimization:   answerSnippet: &quot;## Facts ...">
//
// A single-quoted scalar had opened and never closed, so gray-matter folded the
// FOLLOWING KEYS into the value. The search result for an immigration and tax
// advisory therefore announced that the article was AI-generated, with a
// confidence score, before anyone clicked.
//
// WHY THE KEY-LEAK CHECK IS ANCHORED DIFFERENTLY HERE. The first version of
// this check, in `frontmatter-title-integrity.test.ts`, tested whether a value
// ENDED with something key-shaped. It passed on all 33 of these, because the
// swallowed keys sit in the MIDDLE of the value, not at the end. A guard that
// only looks at the tail of a string is a guard that a longer leak walks past.
// This one looks anywhere in the value, and names the keys that actually exist
// in this frontmatter schema rather than guessing at "something with a colon" —
// prose legitimately contains colons ("Bali 2026: what changed").
//
// REMEDIATION when this fails: `python3 scripts/repair_description_fields.py`
// (`--check` to see what it would do first).
// =============================================================================

import fs from "fs";
import path from "path";
import matter from "gray-matter";
import { describe, expect, it } from "vitest";

const ARTICLES_PATH = path.join(process.cwd(), "src/content/articles");

/**
 * Keys that belong to this frontmatter schema. Finding one INSIDE a value means
 * the parser folded it in — never that an author wrote it.
 */
const SCHEMA_KEYS = [
  "aiGenerated",
  "aiConfidenceScore",
  "aiOptimization",
  "answerSnippet",
  "primaryQuestion",
  "seoTitle",
  "seoDescription",
  "coverImage",
  "publishedAt",
  "readingTime",
];
const KEY_LEAK = new RegExp(`\\b(${SCHEMA_KEYS.join("|")})\\s*:`);

const FIELDS = ["seoDescription", "excerpt"] as const;

function descriptions(): { rel: string; field: string; value: string }[] {
  const out: { rel: string; field: string; value: string }[] = [];
  for (const folder of fs.readdirSync(ARTICLES_PATH)) {
    const dir = path.join(ARTICLES_PATH, folder);
    if (!fs.statSync(dir).isDirectory()) continue;
    for (const file of fs.readdirSync(dir)) {
      if (!file.endsWith(".mdx")) continue;
      let data: Record<string, unknown> = {};
      try {
        data = (matter(fs.readFileSync(path.join(dir, file), "utf-8")).data ??
          {}) as Record<string, unknown>;
      } catch {
        data = { seoDescription: "<<UNPARSEABLE FRONTMATTER>>" };
      }
      for (const field of FIELDS) {
        const value = data[field];
        // An ABSENT value is legal — the page falls back, and for the files
        // whose value was corrupt beyond recovery that absence IS the cure.
        // Only present values are judged.
        if (typeof value === "string" && value.trim())
          out.push({ rel: `${folder}/${file}`, field, value });
      }
    }
  }
  return out;
}

describe("description field integrity", () => {
  const rows = descriptions();

  it("finds a corpus to check, instead of passing on an empty read", () => {
    expect(fs.existsSync(ARTICLES_PATH)).toBe(true);
    expect(rows.length).toBeGreaterThan(1000);
  });

  it("no meta description opens with a markdown heading", () => {
    const offenders = rows
      .filter((r) => /^\s*#{1,6}\s/.test(r.value))
      .map(
        (r) =>
          `${r.rel} [${r.field}] — ${JSON.stringify(r.value.slice(0, 60))}`,
      );
    expect(
      offenders,
      `Google would print this heading verbatim:\n${offenders.join("\n")}`,
    ).toEqual([]);
  });

  it("no meta description contains a frontmatter key — anywhere in the value", () => {
    const offenders = rows
      .filter((r) => KEY_LEAK.test(r.value))
      .map(
        (r) =>
          `${r.rel} [${r.field}] — leaks ${JSON.stringify(r.value.match(KEY_LEAK)![1])}`,
      );
    expect(
      offenders,
      `an unterminated scalar folded later keys into the description:\n${offenders.join("\n")}`,
    ).toEqual([]);
  });

  it("no meta description carries bold markers", () => {
    const offenders = rows
      .filter((r) => r.value.includes("**"))
      .map((r) => `${r.rel} [${r.field}]`);
    expect(offenders, offenders.join("\n")).toEqual([]);
  });
});
