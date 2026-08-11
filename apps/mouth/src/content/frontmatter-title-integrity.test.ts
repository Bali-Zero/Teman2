// =============================================================================
// FRONTMATTER TITLE INTEGRITY — a title must be a headline, not the article.
//
// WHY THIS EXISTS. Measured live 2026-08-11 on balizero.com: 101 published
// Indonesian articles had their entire article crammed into the frontmatter
// `title:` value. The translation step wrote the translated markdown into
// frontmatter scalars instead of the body, so the page rendered thousands of
// characters — with raw `#` and `**` — where the headline belongs. The longest
// was 6,811 characters. Confirmed on production before the fix: the H1 slot of
// /business/art-of-strategic-patience?lang=id read
// "# Seni Kesabaran Strategis: … **Pendahuluan** …".
//
// Three of them additionally had an unterminated single-quoted scalar
// (`seoDescription: '## Facts`), which made gray-matter swallow the FOLLOWING
// key into the value — production served
// `<meta name="description" content="## Facts seoTitle: ">`, i.e. a YAML key
// name leaking into Google's snippet.
//
// PARSED WITH THE APP'S OWN PARSER. This uses gray-matter, the same parser
// `articles.ts` uses, on purpose: a guard that reads a file differently from
// the renderer can pass while the page is broken. (Python's stricter YAML
// rejected those 3 files outright; gray-matter accepted them and rendered the
// damage. The renderer's reading is the one that reaches a human.)
//
// SCOPE: every `.mdx` under src/content/articles, every language. The defect
// landed only in `.id`, but nothing about it is Indonesian-specific — the same
// pipeline writes the other locales.
// =============================================================================

import fs from "fs";
import path from "path";
import matter from "gray-matter";
import { describe, expect, it } from "vitest";

const ARTICLES_PATH = path.join(process.cwd(), "src/content/articles");

/**
 * Generous on purpose. Length is NOT the signal this gate relies on — the
 * structural checks below are — and a real syndicated headline can be long:
 * `uk-joins-canada-germany-…` carries a legitimate 221-character English title.
 * This only catches a value so far outside headline range that it is prose.
 */
const MAX_TITLE_CHARS = 400;

type Article = { rel: string; title: unknown; raw: string };

function allArticles(): Article[] {
  const out: Article[] = [];
  for (const folder of fs.readdirSync(ARTICLES_PATH)) {
    const dir = path.join(ARTICLES_PATH, folder);
    if (!fs.statSync(dir).isDirectory()) continue;
    for (const file of fs.readdirSync(dir)) {
      if (!file.endsWith(".mdx")) continue;
      const raw = fs.readFileSync(path.join(dir, file), "utf-8");
      let title: unknown;
      try {
        title = matter(raw).data?.title;
      } catch {
        // Unreadable frontmatter is a finding, not a skip (W84: a scan that
        // could not look is not a scan that found nothing).
        title = "<<UNPARSEABLE FRONTMATTER>>";
      }
      out.push({ rel: `${folder}/${file}`, title, raw });
    }
  }
  return out;
}

describe("frontmatter title integrity", () => {
  const articles = allArticles();

  it("finds a corpus to check, instead of passing on an empty read", () => {
    expect(fs.existsSync(ARTICLES_PATH)).toBe(true);
    expect(articles.length).toBeGreaterThan(1000);
  });

  it("every article has a string title", () => {
    const offenders = articles
      .filter((a) => typeof a.title !== "string" || !a.title.trim())
      .map((a) => `${a.rel} — title is ${JSON.stringify(a.title)}`);
    expect(offenders, offenders.join("\n")).toEqual([]);
  });

  it("no title carries markdown syntax a reader would see", () => {
    const offenders: string[] = [];
    for (const { rel, title } of articles) {
      if (typeof title !== "string") continue;
      if (/^\s*#{1,6}\s/.test(title))
        offenders.push(`${rel} — starts with a markdown heading marker`);
      else if (title.includes("**"))
        offenders.push(`${rel} — contains bold markers`);
    }
    expect(
      offenders,
      `a title renders markdown to the reader — run scripts/repair_swallowed_titles.py:\n${offenders.join("\n")}`,
    ).toEqual([]);
  });

  it("no title is a multi-line block — that means it swallowed the article", () => {
    const offenders = articles
      .filter((a) => typeof a.title === "string" && a.title.includes("\n"))
      .map(
        (a) =>
          `${a.rel} — ${(a.title as string).length} chars across ${(a.title as string).split("\n").length} lines`,
      );
    expect(
      offenders,
      `title contains a line break, so prose followed the headline into the field:\n${offenders.join("\n")}`,
    ).toEqual([]);
  });

  it("no title is long enough to be prose", () => {
    const offenders = articles
      .filter(
        (a) => typeof a.title === "string" && a.title.length > MAX_TITLE_CHARS,
      )
      .map((a) => `${a.rel} — ${(a.title as string).length} chars`);
    expect(
      offenders,
      `title over ${MAX_TITLE_CHARS} chars:\n${offenders.join("\n")}`,
    ).toEqual([]);
  });

  it("no frontmatter scalar is left unterminated, swallowing the next key", () => {
    // The exact shape that reached production: a quote opens, never closes, and
    // gray-matter folds the following `key:` line into the value.
    const offenders: string[] = [];
    for (const { rel, raw } of articles) {
      const fm = raw.match(/^---\r?\n([\s\S]*?)\r?\n---/);
      if (!fm) continue;
      const data = (() => {
        try {
          return matter(raw).data as Record<string, unknown>;
        } catch {
          return {};
        }
      })();
      for (const [k, v] of Object.entries(data)) {
        if (typeof v === "string" && /\b[a-zA-Z_][\w-]*:\s*$/.test(v.trim())) {
          offenders.push(`${rel} — ${k} ends with what looks like a YAML key`);
        }
      }
    }
    expect(offenders, offenders.join("\n")).toEqual([]);
  });
});
