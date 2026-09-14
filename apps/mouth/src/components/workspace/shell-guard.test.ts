import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

/**
 * A guard over the shell's own sources, because nothing else watches them.
 *
 * `scripts/token_lint.py` scopes exactly two prefixes — `app/(workspace)/` and
 * `app/portal/` — so `components/workspace/**` is invisible to it: a raw hex
 * or a resurrected `var(--bz-red, …)` fallback could land in the rail, the
 * header or the palette and no check would say a word. (The scope gap itself
 * is a harness-lane leftover, recorded in this window's pack; this test is the
 * local cure, not a request to widen the linter.)
 *
 * Three things are forbidden, and each is an ENTITY rather than a spelling:
 *
 *   - a raw hex colour, in any length, on a line that does not carry a
 *     `token-lint-ok:` reason;
 *   - a read of `--bz-red`, with or without a fallback;
 *   - a read of `--state-danger`, which on kita resolves to copper but on
 *     every other product is red, and which this surface never needs: the
 *     alphabet says the four meanings, and "needs you" is copper with a WORD.
 *
 * Comments are stripped before judging. The Header's own docstring quotes
 * `var(--bz-red, #e45c5c)` to explain why it was removed, and a guard that
 * accused the explanation would teach people to delete the explanation.
 */

const SHELL_FILES = [
  "components/workspace/AppSidebar.tsx",
  "components/workspace/Header.tsx",
  "components/workspace/KitaCommandPalette.tsx",
  "components/workspace/ZantaraWidget.tsx",
  "app/(workspace)/GateScreen.tsx",
] as const;

const SRC = join(__dirname, "..", "..");

/**
 * Drop block comments and whole-line `//` comments, keep everything else.
 * A `//` inside a string (a URL) is NOT a comment, which is why only a line
 * that STARTS with `//` is dropped.
 */
export function stripComments(source: string): string {
  return source
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .split("\n")
    .filter((line) => !line.trimStart().startsWith("//"))
    .join("\n");
}

const RAW_HEX = /#[0-9a-fA-F]{3,8}\b/;
const BZ_RED = /var\(\s*--bz-red\b/;
const STATE_DANGER = /var\(\s*--state-danger\s*\)/;

export interface Finding {
  line: number;
  text: string;
  rule: "raw-hex" | "bz-red" | "state-danger";
}

/** Pure detector: every forbidden paint in this source, with its line. */
export function findForbiddenPaint(source: string): Finding[] {
  const out: Finding[] = [];
  stripComments(source)
    .split("\n")
    .forEach((line, i) => {
      // The escape hatch is per LINE and must carry a reason, exactly like
      // token_lint's own.
      if (/token-lint-ok:/.test(line)) return;
      if (BZ_RED.test(line))
        out.push({ line: i + 1, text: line.trim(), rule: "bz-red" });
      if (STATE_DANGER.test(line))
        out.push({ line: i + 1, text: line.trim(), rule: "state-danger" });
      if (RAW_HEX.test(line))
        out.push({ line: i + 1, text: line.trim(), rule: "raw-hex" });
    });
  return out;
}

describe("the shell carries no paint of its own", () => {
  for (const file of SHELL_FILES) {
    it(`${file} is clean (innocence)`, () => {
      const source = readFileSync(join(SRC, file), "utf8");
      expect(findForbiddenPaint(source)).toEqual([]);
    });
  }
});

describe("the detector is awake (guilt)", () => {
  it("names a raw hex", () => {
    const found = findForbiddenPaint('  style={{ color: "#e45c5c" }}');
    expect(found).toHaveLength(1);
    expect(found[0].rule).toBe("raw-hex");
  });

  it("names a short hex and an eight-digit one, not only six", () => {
    expect(findForbiddenPaint('color: "#f00"')[0]?.rule).toBe("raw-hex");
    expect(findForbiddenPaint('color: "#a44b3680"')[0]?.rule).toBe("raw-hex");
  });

  it("names --bz-red with a fallback and without one", () => {
    expect(findForbiddenPaint("background: var(--bz-red)")[0]?.rule).toBe(
      "bz-red",
    );
    const withFallback = findForbiddenPaint(
      "background: var(--bz-red, #e45c5c)",
    );
    expect(withFallback.map((f) => f.rule).sort()).toEqual([
      "bz-red",
      "raw-hex",
    ]);
  });

  it("names a --state-danger read", () => {
    expect(findForbiddenPaint("color: var(--state-danger)")[0]?.rule).toBe(
      "state-danger",
    );
  });

  it("reports the LINE, so a reviewer can go there", () => {
    const found = findForbiddenPaint('const a = 1;\nconst b = "#123456";');
    expect(found[0].line).toBe(2);
  });
});

describe("the detector does not accuse the innocent", () => {
  it("ignores a hex inside a block comment", () => {
    // This is the Header's real situation: its docstring quotes the fallback
    // it removed. Accusing the explanation teaches people to delete it.
    expect(
      findForbiddenPaint("/* it used to read var(--bz-red, #e45c5c) */"),
    ).toEqual([]);
  });

  it("ignores a hex on a whole-line // comment", () => {
    expect(findForbiddenPaint('  // was "#fff" on a copper fill')).toEqual([]);
  });

  it("does not mistake a URL's slashes for a comment", () => {
    // The line is code, so a hex on it still counts.
    const found = findForbiddenPaint(
      'const u = "https://x.test"; const c = "#abcdef";',
    );
    expect(found).toHaveLength(1);
  });

  it("clears token reads, including the copper and the four meanings", () => {
    expect(
      findForbiddenPaint(
        'className="text-[var(--bz-copper-text)] border-[var(--state-warning)] bg-[var(--state-info)]"',
      ),
    ).toEqual([]);
  });

  it("honours a per-line token-lint-ok reason, and only on that line", () => {
    expect(
      findForbiddenPaint('const RED = "#e45c5c"; // token-lint-ok: planted'),
    ).toEqual([]);
    // The line above carrying the marker does not exempt the line below.
    expect(
      findForbiddenPaint('// token-lint-ok: planted\nconst RED = "#e45c5c";'),
    ).toHaveLength(1);
  });
});
