import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const GLOBALS_CSS = join(__dirname, "globals.css");
const BLOCK_MARKER = "MYTHOS Stage-B Batch 1";

const COMMENT_RE = /\/\*[\s\S]*?\*\//g;
const RULE_RE = /([^{}]+)\{([^{}]*)\}/g;
const VIOLATION_RE =
  /#[0-9a-fA-F]{3,8}\b|rgba?\(|hsla?\(|color-mix\(|\bwhite\b|\bblack\b/i;

// Prettier may wrap a long `var(--r19-…, …)` call across lines (whitespace,
// including newlines, between `var(` and the token name) — match that too.
const VAR_R19_START_RE = /var\(\s*--r19-/g;

/**
 * Remove every well-formed `var(--r19-…, fallback)` construct (name AND
 * fallback slot together — parens balanced, so a fallback that itself nests
 * parens like `color-mix(...)` is consumed whole). What is left is text a
 * colour literal is NOT allowed to appear in: the fallback slot is the only
 * place a literal may legally live.
 */
function stripR19VarFallbacks(text: string): string {
  let out = "";
  let i = 0;
  for (;;) {
    VAR_R19_START_RE.lastIndex = i;
    const found = VAR_R19_START_RE.exec(text);
    if (!found) {
      out += text.slice(i);
      break;
    }
    const idx = found.index;
    out += text.slice(i, idx);
    const openParen = idx + text.slice(idx).indexOf("(");
    let depth = 1;
    let j = openParen + 1;
    while (j < text.length && depth > 0) {
      if (text[j] === "(") depth++;
      else if (text[j] === ")") depth--;
      j++;
    }
    i = j;
  }
  return out;
}

interface Rule {
  selector: string;
  declarations: string[];
}

/** Slice from the Batch 1 header to the end of the Batch 2 block (EOF),
 *  strip comments, and split into `{ selector, declarations }` rules. */
function parseRumahPutihBlock(css: string): Rule[] {
  const markerIdx = css.indexOf(BLOCK_MARKER);
  if (markerIdx === -1) {
    throw new Error(`"${BLOCK_MARKER}" not found in globals.css`);
  }
  const blockStart = css.lastIndexOf("/*", markerIdx);
  const block = css.slice(blockStart);
  const stripped = block.replace(COMMENT_RE, "");

  const rules: Rule[] = [];
  for (const match of stripped.matchAll(RULE_RE)) {
    const selector = match[1].trim();
    const declarations = match[2]
      .split(";")
      .map((d) => d.trim())
      .filter(Boolean);
    rules.push({ selector, declarations });
  }
  return rules;
}

/** The actual guard: every declaration in a rule NOT scoped to
 *  `.rp-dark-island` must carry its colour literal only inside a
 *  `var(--r19-…, …)` fallback slot, never bare. */
// Rules that stay dark on purpose: their text is white and sits inside
// `.absolute`, which the ink retint skips (see the comment above each rule).
const KEPT_DARK_ISLANDS = new Set([".rumah-putih .bg-\\[\\#0a1929\\]"]);

/** A rule is a dark island only when `.rp-dark-island` is part of what it
 *  selects — `:not(.rp-dark-island …)` means the opposite. */
function isDarkIslandRule(selector: string): boolean {
  if (KEPT_DARK_ISLANDS.has(selector.replace(/\s+/g, " "))) return true;
  return selector.replace(/:not\([^()]*\)/g, "").includes(".rp-dark-island");
}

function findViolations(css: string): string[] {
  const offenders: string[] = [];
  for (const { selector, declarations } of parseRumahPutihBlock(css)) {
    if (isDarkIslandRule(selector)) continue;
    for (const decl of declarations) {
      const remainder = stripR19VarFallbacks(decl);
      if (VIOLATION_RE.test(remainder)) {
        offenders.push(`${selector.replace(/\s+/g, " ")} { ${decl} }`);
      }
    }
  }
  return offenders;
}

describe("Rumah Putih retint token guard (globals.css Batch 1 + Batch 2)", () => {
  it("GUILT: a bare colour literal outside .rp-dark-island is caught", () => {
    const guilty = `
      /* MYTHOS Stage-B Batch 1 */
      .rumah-putih .mdx-content h2 {
        color: #1e3863 !important;
      }
    `;
    expect(findViolations(guilty)).toHaveLength(1);
  });

  it("INNOCENCE: a literal kept only as the var(--r19-…, …) fallback passes", () => {
    const innocent = `
      /* MYTHOS Stage-B Batch 1 */
      .rumah-putih .mdx-content h2 {
        color: var(--r19-ink, #1e3863) !important;
      }
    `;
    expect(findViolations(innocent)).toEqual([]);
  });

  it("GUILT: a rule that only EXCLUDES .rp-dark-island is still checked", () => {
    const guilty = `
      /* MYTHOS Stage-B Batch 1 */
      .rumah-putih h2.text-white:not(.rp-dark-island *) {
        color: #1e3863 !important;
      }
      .rumah-putih button.border-white\\/20:not(.rp-dark-island *) {
        border-color: #cfccc2 !important;
      }
    `;
    expect(findViolations(guilty)).toHaveLength(2);
  });

  it("INNOCENCE: rules scoped to .rp-dark-island keep their white/rgba literals", () => {
    const island = `
      /* MYTHOS Stage-B Batch 1 */
      .rumah-putih .rp-dark-island .text-white {
        color: #ffffff !important;
        border-color: rgba(255, 255, 255, 0.2);
      }
    `;
    expect(findViolations(island)).toEqual([]);
  });

  it("the sweep actually visits a realistic number of rules (not a silently-empty slice)", () => {
    const css = readFileSync(GLOBALS_CSS, "utf8");
    const rules = parseRumahPutihBlock(css);
    // Known-good baseline: Batch 1 + Batch 2 currently carry 39 rules.
    expect(rules.length).toBeGreaterThan(20);
  });

  it("no rule outside .rp-dark-island carries a bare colour literal in globals.css", () => {
    const css = readFileSync(GLOBALS_CSS, "utf8");
    const offenders = findViolations(css);
    expect(
      offenders,
      offenders.length === 0
        ? ""
        : `\nBARE colour literal found outside a var(--r19-…, …) fallback in ` +
            `apps/mouth/src/app/globals.css's MYTHOS Stage-B block:\n  ${offenders.join(
              "\n  ",
            )}\n` +
            `  Fix: wrap the literal as the fallback of the matching R19 token, ` +
            `e.g. var(--r19-ink, #1e3863).\n`,
    ).toEqual([]);
  });
});
