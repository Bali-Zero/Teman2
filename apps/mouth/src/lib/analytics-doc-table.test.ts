import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * DOCUMENTATION.md §17.6 "Pre-existing Helpers Reference" is a claim about
 * analytics.ts, and nothing has ever checked it. Four of its thirteen rows
 * were false on 2026-08-14.
 *
 * Three of them were left behind by retirements. #3717 (2026-08-07) removed
 * `trackVisaCallingBlock` from the module; #4150 (2026-08-14) removed
 * `trackVisaQuizCompleted` and `trackVisaResultViewed`. Both PRs deleted the
 * export and left the row, so the table went on naming helpers that were no
 * longer there — twice in one week, and the PENDING-ARMS row driving that
 * cleanup had named DOCUMENTATION.md as part of its own definition of done
 * both times. The fourth, `trackPropertyWACTA`, simply named the wrong event.
 *
 * A retirement touches two surfaces and it is the second one that gets
 * forgotten, so the fix is not a tidier row: it is a check that fails when
 * the two disagree.
 *
 * Declared limits, so nobody reads a green run as more than it is. This
 * checks the Helper and GA4-Event columns; the Category column is free text
 * that no code consumes, and a wrong one passes. It checks that every
 * documented row is real, not that every real helper is documented — the
 * table is a reference, not an inventory. And it reads `sendGA4Event` calls
 * only: a helper that reached an event solely through `trackEvent` or
 * `trackFunnelEvent` would read as emitting nothing. No current row does.
 */

const DOC_PATH = join(__dirname, "../../DOCUMENTATION.md");
const MODULE_PATH = join(__dirname, "analytics.ts");

const HEADING = "### 17.6 Pre-existing Helpers Reference";

/** Rows the two retirements above removed. Pinned so they cannot creep back. */
const RETIRED = [
  "trackVisaQuizCompleted",
  "trackVisaResultViewed",
  "trackVisaCallingBlock",
];

interface DocRow {
  helper: string;
  event: string;
}

/** A line that opens with `| \`something\`` is meant to be a helper row. */
const LOOKS_LIKE_ROW = /^\|\s*`\w+`\s*\|/;
const PARSED_ROW = /^\|\s*`(\w+)`\s*\|[^|]*\|\s*`([^`|]+)`\s*\|/;

function parseHelperTable(markdown: string): DocRow[] {
  const start = markdown.indexOf(HEADING);
  if (start === -1) {
    throw new Error(
      `Could not find "${HEADING}" in DOCUMENTATION.md — the section was renamed or removed, so this test is no longer reading what it claims to read.`,
    );
  }
  const section = markdown.slice(start, markdown.indexOf("\n---", start));
  const rows: DocRow[] = [];
  for (const line of section.split("\n")) {
    if (!LOOKS_LIKE_ROW.test(line)) continue;
    const match = line.match(PARSED_ROW);
    if (!match) {
      // A row the parser cannot read must not be silently skipped: that is
      // exactly how a bogus row would slip past this guard unexamined.
      throw new Error(`Unparseable helper row in §17.6: ${line}`);
    }
    rows.push({ helper: match[1], event: match[2] });
  }
  return rows;
}

/** Strips line comments so a commented-out call is not read as a real one. */
function stripLineComments(source: string): string {
  return source.replace(/^[ \t]*\/\/.*$/gm, "");
}

/**
 * Extracts a function body by counting braces from its signature, rather than
 * stopping at the first `\n}`. The naive terminator both overruns a
 * single-line function (there is no `\n}` to stop at, so it swallows whatever
 * comes next) and stops early on a nested block closed at column zero.
 *
 * Finding the opening brace also has to skip the parameter list, because a
 * parameter type can contain one: `dispatchPropertyCTAClicked` is declared
 * `(payload: Record<string, string | number> & { cta_type: string }): void {`,
 * and taking the first `{` after the name lands inside that type, yielding a
 * body of `{ cta_type: string }` and no events at all.
 */
function extractBody(source: string, signature: string): string | null {
  const start = source.indexOf(signature);
  if (start === -1) return null;

  const open = findBodyBrace(source, source.indexOf("(", start));
  if (open === -1) return null;

  let depth = 0;
  for (let i = open; i < source.length; i++) {
    if (source[i] === "{") depth++;
    else if (source[i] === "}") {
      depth--;
      if (depth === 0) return source.slice(open, i + 1);
    }
  }
  return source.slice(open);
}

/**
 * Given the `(` that opens a parameter list, returns the index of the `{` that
 * opens the body: the last `{` on the first line after the parameter list that
 * has one. "Last on the line" is what steps over a return-type annotation.
 */
function findBodyBrace(source: string, paren: number): number {
  if (paren === -1) return -1;

  let depth = 0;
  let cursor = -1;
  for (let i = paren; i < source.length; i++) {
    if (source[i] === "(") depth++;
    else if (source[i] === ")") {
      depth--;
      if (depth === 0) {
        cursor = i + 1;
        break;
      }
    }
  }
  if (cursor === -1) return -1;

  while (cursor < source.length) {
    const eol = source.indexOf("\n", cursor);
    const line = source.slice(cursor, eol === -1 ? undefined : eol);
    const brace = line.lastIndexOf("{");
    if (brace !== -1) return cursor + brace;
    if (eol === -1) return -1;
    cursor = eol + 1;
  }
  return -1;
}

/**
 * Returns every GA4 event name a helper can reach, directly or through the
 * dispatchers it calls. It collects from all dispatchers rather than
 * returning at the first one: `trackPropertyArticleCTA` and
 * `trackPropertyAnalyzeCTA` both route through `dispatchPropertyCTAClicked`,
 * which is deliberate — `property_cta_clicked` is the canonical event and
 * `cta_type` separates them — but nothing guarantees a future helper calls
 * only one dispatcher, or that the first one it calls is the emitting one.
 */
function eventsEmittedBy(source: string, helper: string): string[] {
  const body = extractBody(source, `export function ${helper}(`);
  if (body === null) return [];

  const clean = stripLineComments(body);
  const events = directEvents(clean);

  for (const [, dispatcher] of clean.matchAll(/\b(dispatch\w+)\s*\(/g)) {
    const dispatched = extractBody(source, `function ${dispatcher}(`);
    if (dispatched) events.push(...directEvents(stripLineComments(dispatched)));
  }
  return events;
}

function directEvents(body: string): string[] {
  return [...body.matchAll(/sendGA4Event\(\s*"([\w]+)"/g)].map((m) => m[1]);
}

function isExported(source: string, helper: string): boolean {
  return source.includes(`export function ${helper}(`);
}

describe("DOCUMENTATION.md §17.6 helper table", () => {
  const doc = readFileSync(DOC_PATH, "utf8");
  const module = readFileSync(MODULE_PATH, "utf8");
  const rows = parseHelperTable(doc);

  it("finds a table with the shape it is supposed to guard", () => {
    // Without a floor, an emptied table would satisfy every per-row assertion
    // below by having no rows to check. Without the uniqueness check, so would
    // a table of N copies of one correct row.
    expect(rows.length).toBeGreaterThanOrEqual(10);
    expect(new Set(rows.map((r) => r.helper)).size).toBe(rows.length);
  });

  it.each(rows)("$helper is exported by analytics.ts", ({ helper }) => {
    expect(isExported(module, helper)).toBe(true);
  });

  it.each(rows)(
    "$helper emits the documented event $event",
    ({ helper, event }) => {
      expect(eventsEmittedBy(module, helper)).toContain(event);
    },
  );

  it("keeps the retired helpers out of both surfaces", () => {
    // Anchored to the module rather than to this list alone: if one of these
    // names is ever re-introduced as a real export, the row becomes legitimate
    // and this stops objecting on its own.
    for (const retired of RETIRED) {
      if (isExported(module, retired)) continue;
      expect(rows.map((r) => r.helper)).not.toContain(retired);
    }
  });

  it("innocence: correctly documented helpers are not flagged", () => {
    // One reached through a dispatcher, one direct. If the dispatcher
    // indirection ever stops resolving, the first of these fails for a reason
    // that has nothing to do with the doc being wrong.
    expect(eventsEmittedBy(module, "trackPropertyArticleCTA")).toContain(
      "property_cta_clicked",
    );
    expect(eventsEmittedBy(module, "trackVisaChatQuestion")).toContain(
      "visa_chat_question",
    );
  });
});
