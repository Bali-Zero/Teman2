// =============================================================================
// ARTICLE BODY INTEGRITY — an article's body must be an article.
//
// WHY THIS EXISTS. Measured live 2026-08-11 on balizero.com: three published
// articles had, as their entire Indonesian body, the authentication prompt of
// the CLI that was supposed to translate them —
//
//     Opening authentication page in your browser. Do you want to continue? [Y/n]:
//
// rendered under the byline "Bali Zero Editorial · Editorial Team · 12 min
// read", reachable by any reader clicking the language switch (`?lang=id`,
// which `getArticleByLocale` serves from the `.id.mdx` file). Two of the three
// had carried it since their very first commit — the "Add Indonesian
// translation" commit wrote the prompt instead of the translation, and nothing
// on disk could tell the difference between a translation and a tool's stdout.
//
// This is the same family as the 2026-07-21 `/insights?tag=` prompt leak, where
// raw LLM chain-of-thought reached `tags:` frontmatter and Google crawled it.
// That one got a render-layer backstop (`isReasoningLeakTag` in articles.ts) and
// a CI guard (`scripts/lint_content_reasoning_leak.py`) — both of which look at
// TAGS. The BODY had no equivalent, so the same class walked in through the
// bigger door.
//
// TWO INDEPENDENT CHECKS, deliberately. A pattern list alone goes stale the
// moment a different tool prints a different banner; a length floor alone would
// pass a 5,000-character stack trace. Either one failing is a failure.
//
// SCOPE: every `.mdx` under src/content/articles, every language. A translated
// variant is exactly where this class lands, and it is the variant nobody reads
// before publishing.
// =============================================================================

import fs from "fs";
import path from "path";
import { describe, expect, it } from "vitest";

const ARTICLES_PATH = path.join(process.cwd(), "src/content/articles");

/**
 * Bodies below this are not articles. The floor is deliberately low — this
 * gate's job is catching a tool's stdout, not judging brevity. The shortest
 * real body in the corpus at the time of writing is several thousand
 * characters, so this leaves a wide margin.
 */
const MIN_BODY_CHARS = 400;

/**
 * Stub bodies that are honest placeholders rather than leaked tool output:
 * they say, in the article's own language, that the full text is in the English
 * version. They are a content gap and are pinned so this gate can guard the
 * corpus today instead of waiting for them to be written — a NEW short body
 * must fail rather than join a silent tolerance.
 */
const KNOWN_PLACEHOLDER_BODIES = new Set([
  "digital-nomad/bali-digital-nomad-complete-guide.id.mdx",
  "digital-nomad/bali-digital-nomad-complete-guide.it.mdx",
]);

/**
 * Verbatim output of tools in the content pipeline. Matched anywhere in the
 * body, not just at the start: a leak that lands mid-article is worse, not
 * better. Case-sensitive on purpose — these are literal program output, and
 * lowercasing invites false positives.
 *
 * Every entry must be UNAMBIGUOUS PROGRAM OUTPUT — a phrase that cannot occur
 * in an article about Indonesian immigration, tax or company law. This list's
 * own first draft failed that rule and this gate caught it: `quota exceeded`
 * flagged `business/kbli-2025-visa-kitas-synergy.mdx`, whose table row reads
 * "TKA quota exceeded" about foreign-worker quotas — real prose, in a domain
 * where quotas and usage limits are the subject matter. `usage limit`,
 * `command not found` and `Please run \`` were dropped for the same reason. If
 * a candidate marker needs a "but in context it means…" to justify it, it does
 * not belong here; that is exactly the bare-phrase trap `lint_retracted_claims.py`
 * documents in its own header.
 */
const TOOL_OUTPUT_MARKERS = [
  "Opening authentication page in your browser",
  "Do you want to continue? [Y/n]",
  "Press Ctrl+C to cancel",
  "Traceback (most recent call last)",
  "npm ERR!",
  "error: unknown option",
];

function splitFrontmatter(raw: string): { body: string } | null {
  const m = raw.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n?([\s\S]*)$/);
  return m ? { body: m[2].trim() } : null;
}

function allArticles(): { rel: string; body: string }[] {
  const out: { rel: string; body: string }[] = [];
  for (const folder of fs.readdirSync(ARTICLES_PATH)) {
    const dir = path.join(ARTICLES_PATH, folder);
    if (!fs.statSync(dir).isDirectory()) continue;
    for (const file of fs.readdirSync(dir)) {
      if (!file.endsWith(".mdx")) continue;
      const parsed = splitFrontmatter(
        fs.readFileSync(path.join(dir, file), "utf-8"),
      );
      // A file whose frontmatter cannot be parsed is not silently skipped —
      // an unreadable article is reported as an empty body and fails below,
      // never as "nothing to check" (W84: a scan that could not look is not a
      // scan that found nothing).
      out.push({ rel: `${folder}/${file}`, body: parsed ? parsed.body : "" });
    }
  }
  return out;
}

describe("article body integrity", () => {
  const articles = allArticles();

  it("finds a corpus to check, instead of passing on an empty read", () => {
    expect(fs.existsSync(ARTICLES_PATH)).toBe(true);
    expect(articles.length).toBeGreaterThan(1000);
  });

  it("no article body is a tool's output", () => {
    const offenders: string[] = [];
    for (const { rel, body } of articles) {
      for (const marker of TOOL_OUTPUT_MARKERS) {
        if (body.includes(marker)) {
          offenders.push(`${rel} — contains ${JSON.stringify(marker)}`);
        }
      }
    }
    expect(
      offenders,
      `an article body is carrying tool output instead of prose:\n${offenders.join("\n")}`,
    ).toEqual([]);
  });

  it("no article body is too short to be an article", () => {
    const offenders = articles
      .filter(
        ({ rel, body }) =>
          body.length < MIN_BODY_CHARS && !KNOWN_PLACEHOLDER_BODIES.has(rel),
      )
      .map(({ rel, body }) => `${rel} — ${body.length} chars`);
    expect(
      offenders,
      `body below ${MIN_BODY_CHARS} chars — restore the real text, or pin it in KNOWN_PLACEHOLDER_BODIES if it is a deliberate stub:\n${offenders.join("\n")}`,
    ).toEqual([]);
  });

  it("the pinned placeholders still exist — a stale pin hides a real finding", () => {
    for (const rel of KNOWN_PLACEHOLDER_BODIES) {
      expect(
        fs.existsSync(path.join(ARTICLES_PATH, rel)),
        `${rel} is pinned as a known placeholder but no longer exists — remove the pin`,
      ).toBe(true);
    }
  });
});
