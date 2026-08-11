// =============================================================================
// BODY-DERIVED EXCERPT — when there is no description, what gets invented must
// still be prose.
//
// WHY THIS EXISTS. When an article carries neither `seoDescription` nor
// `excerpt`, `extractBodyExcerpt` derives one from the body, and the result
// becomes `<meta name="description">` — the sentence Google prints under the
// link. It skipped a JSX component by testing whether a line STARTS with `<`:
//
//     <InfoCard                       <- skipped
//       title="Quick Summary"         <- kept, as "prose"
//       items={[{ label: "Should I Worry?", value: "Yes" }]}
//     />                              <- kept
//
// A component spans many lines and only the first one starts with `<`, so
// everything after it was accepted as the opening paragraph. Measured live
// 2026-08-11: 52 articles served
// `title="Quick Summary" items={[ { label: "Should I Worry?", value: "Yes" }…`
// as their meta description.
//
// HOW IT WAS FOUND, which is the part worth remembering: repairing a DIFFERENT
// defect removed 36 corrupt `seoDescription` values, and the stated expectation
// was "those pages will have no meta description and Google will synthesise one
// from the body". That was wrong — they fell through to this function instead.
// The prediction about a consequence was not the same thing as observing it,
// and only the live check told them apart.
//
// TWO LEVELS, on purpose: unit cases pin the shapes, and a corpus sweep proves
// the real articles are clean — a hand-written fixture cannot vouch for 3,353
// files, and a corpus sweep alone would not say WHICH shape broke.
// =============================================================================

import fs from "fs";
import path from "path";
import matter from "gray-matter";
import { describe, expect, it } from "vitest";
import { extractBodyExcerpt } from "./articles";

const ARTICLES_PATH = path.join(process.cwd(), "src/content/articles");

/** Anything that says "this is source code, not a sentence". */
const LOOKS_LIKE_SOURCE =
  /=\{|items=|label:\s*"|value:\s*"|\/>|\}\]|^<[A-Za-z]/;

const PROSE =
  "Indonesia's immigration framework changed materially in 2026, and the " +
  "practical consequences for foreign residents are not what the headlines say.";

describe("extractBodyExcerpt", () => {
  it("skips a multi-line JSX component and returns the paragraph after it", () => {
    const body = [
      "<InfoCard",
      '  title="Quick Summary"',
      "  items={[",
      '    { label: "Should I Worry?", value: "Yes" },',
      '    { label: "Risk Level", value: "High" },',
      "  ]}",
      "/>",
      "",
      PROSE,
      "",
    ].join("\n");
    const out = extractBodyExcerpt(body);
    expect(out).toBe(PROSE);
    expect(out).not.toMatch(LOOKS_LIKE_SOURCE);
  });

  it("skips a self-closing component written on one line", () => {
    const body = ['<Callout kind="warning" />', "", PROSE, ""].join("\n");
    expect(extractBodyExcerpt(body)).toBe(PROSE);
  });

  it("skips a component with children and a closing tag", () => {
    const body = [
      "<Callout>",
      "  Something inside the component, which is not the article's opening.",
      "</Callout>",
      "",
      PROSE,
      "",
    ].join("\n");
    expect(extractBodyExcerpt(body)).toBe(PROSE);
  });

  it("still skips headings, and still finds the first real paragraph", () => {
    const body = ["## TL;DR", "", PROSE, ""].join("\n");
    expect(extractBodyExcerpt(body)).toBe(PROSE);
  });

  it("returns empty rather than something wrong when there is no prose", () => {
    expect(extractBodyExcerpt('<InfoCard\n  title="x"\n/>\n')).toBe("");
    expect(extractBodyExcerpt("")).toBe("");
  });

  it("no published article derives a description that is source code", () => {
    // Only articles that actually reach this function are judged: the page uses
    // `seoDescription || excerpt` and falls through only when both are absent.
    const offenders: string[] = [];
    let checked = 0;
    for (const folder of fs.readdirSync(ARTICLES_PATH)) {
      const dir = path.join(ARTICLES_PATH, folder);
      if (!fs.statSync(dir).isDirectory()) continue;
      for (const file of fs.readdirSync(dir)) {
        if (!file.endsWith(".mdx")) continue;
        let parsed;
        try {
          parsed = matter(fs.readFileSync(path.join(dir, file), "utf-8"));
        } catch {
          continue;
        }
        const sd = parsed.data?.seoDescription;
        const ex = parsed.data?.excerpt;
        const hasReal = (v: unknown) => typeof v === "string" && v.trim();
        if (hasReal(sd) || hasReal(ex)) continue;
        checked++;
        const derived = extractBodyExcerpt(parsed.content);
        if (derived && LOOKS_LIKE_SOURCE.test(derived)) {
          offenders.push(
            `${folder}/${file} — ${JSON.stringify(derived.slice(0, 80))}`,
          );
        }
      }
    }
    expect(
      checked,
      "no article falls through to the body — sweep saw nothing",
    ).toBeGreaterThan(0);
    expect(
      offenders,
      `these articles would publish source code as their meta description:\n${offenders.join("\n")}`,
    ).toEqual([]);
  });
});
