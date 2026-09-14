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
  rule: "raw-hex" | "bz-red" | "state-danger" | "copper-ground";
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

// ---------------------------------------------------------------------------
// The fourth detector, added after the browser capture showed three gate
// buttons filled COPPER with a label on them.
//
// The rule is "copper is a person, never the ground behind a label", and no
// source text can see a label. What it CAN see is the pairing that always
// produces one: a copper background declared next to a foreground colour.
// The copper masthead rule is the innocent twin — it is a 52x3 bar with
// nothing written on it, so it declares a background and no colour at all.
//
// STATED LIMIT: the pairing is judged inside ONE declaration — the string
// literal holding the class list, or the object literal holding the style
// keys. A fill and a label assembled from two different declarations and
// joined at runtime escape it. The first draft used a three-line window
// instead and immediately accused the masthead rule for sitting above an
// unrelated eyebrow colour: proximity is not scope, and the innocence case
// is what said so.
// ---------------------------------------------------------------------------

/** The tokens that resolve to copper on kita. `--bz-accent` is the trap: its
 * name says "accent" and its value says copper. */
const COPPER_TOKEN =
  /var\(\s*--(bz-accent|bz-copper|bz-copper-text|bz-sidebar-active-fill)\b/;
const COPPER_GROUND = new RegExp(
  // `background: var(--bz-accent)` / `backgroundColor:` / `bg-[var(--bz-copper)]`
  `(background(-?[Cc]olor)?\\s*:[^;\\n]*|bg-\\[)${COPPER_TOKEN.source}`,
);
/** A foreground colour: `color:` as its own key (never `borderColor`), or a
 * Tailwind text colour. */
const FOREGROUND = /(^|[^A-Za-z-])color\s*:|text-\[/;

/**
 * Every string literal and every brace block in a source, with its range.
 * One left-to-right pass: a `{` inside a string is not a block, and a quote
 * inside a block is not a brace.
 */
function spans(src: string): {
  strings: [number, number][];
  blocks: [number, number][];
} {
  const strings: [number, number][] = [];
  const blocks: [number, number][] = [];
  const open: number[] = [];
  let quote: string | null = null;
  let qStart = 0;
  for (let i = 0; i < src.length; i++) {
    const c = src[i];
    if (quote) {
      if (c === "\\") i++;
      else if (c === quote) {
        strings.push([qStart, i]);
        quote = null;
      }
      continue;
    }
    if (c === '"' || c === "'" || c === "`") {
      quote = c;
      qStart = i;
    } else if (c === "{") open.push(i);
    else if (c === "}") {
      const from = open.pop();
      if (from !== undefined) blocks.push([from, i]);
    }
  }
  return { strings, blocks };
}

/** The smallest span containing `at`, or null. */
function innermost(
  ranges: [number, number][],
  at: number,
): [number, number] | null {
  let best: [number, number] | null = null;
  for (const r of ranges) {
    if (r[0] <= at && at <= r[1]) {
      if (!best || r[1] - r[0] < best[1] - best[0]) best = r;
    }
  }
  return best;
}

/**
 * Pure detector: every copper ground that has a label in the SAME declaration.
 *
 * "The same declaration" is the string literal the class list lives in, or the
 * object literal the style keys live in — never mere proximity. Two adjacent
 * `const` lines are two declarations, which is why the masthead rule sitting
 * above an eyebrow colour is not a finding.
 */
export function findCopperGround(source: string): Finding[] {
  const src = stripComments(source);
  const { strings, blocks } = spans(src);
  const out: Finding[] = [];
  const seen = new Set<number>();
  const re = new RegExp(COPPER_GROUND.source, "g");
  let m: RegExpExecArray | null;
  while ((m = re.exec(src)) !== null) {
    const at = m.index;
    const lineNo = src.slice(0, at).split("\n").length;
    if (seen.has(lineNo)) continue;
    const line = src.split("\n")[lineNo - 1];
    if (/token-lint-ok:/.test(line)) continue;
    const scope = innermost(strings, at) ?? innermost(blocks, at);
    const text = scope ? src.slice(scope[0], scope[1] + 1) : line;
    if (FOREGROUND.test(text)) {
      seen.add(lineNo);
      out.push({ line: lineNo, text: line.trim(), rule: "copper-ground" });
    }
  }
  return out;
}

describe("copper is never the ground behind a label", () => {
  for (const file of SHELL_FILES) {
    it(`${file} is clean (innocence)`, () => {
      const source = readFileSync(join(SRC, file), "utf8");
      expect(findCopperGround(source)).toEqual([]);
    });
  }

  it("GUILT: names the gate's acknowledge button as it was written", () => {
    // Verbatim from GateScreen before this window, and visible in the capture:
    // a copper pill with white-ish text on it.
    const found = findCopperGround(
      [
        "              style={{",
        '                background: "var(--bz-accent)",',
        '                color: "var(--bz-base)",',
        "              }}",
      ].join("\n"),
    );
    expect(found).toHaveLength(1);
    expect(found[0].rule).toBe("copper-ground");
    expect(found[0].line).toBe(2);
  });

  it("GUILT: names the Tailwind spelling of the same pairing", () => {
    expect(
      findCopperGround(
        'className="bg-[var(--bz-copper)] text-[var(--bz-base)]"',
      ),
    ).toHaveLength(1);
  });

  it("GUILT: names the sidebar's active fill, which is copper on kita", () => {
    expect(
      findCopperGround(
        [
          "                    {",
          '                      background: "var(--bz-sidebar-active-fill)",',
          '                      color: "#fff",',
          "                    }",
        ].join("\n"),
      ),
    ).toHaveLength(1);
  });

  it("INNOCENCE: the 52x3 masthead rule carries no label", () => {
    expect(
      findCopperGround(
        'const GATE_RULE = "h-[3px] w-[52px] bg-[var(--bz-copper)]";',
      ),
    ).toEqual([]);
  });

  it("INNOCENCE: copper as a WORD's colour is the alphabet working", () => {
    expect(
      findCopperGround('className="text-[var(--bz-copper-text)]"'),
    ).toEqual([]);
    expect(
      findCopperGround('  style={{ color: "var(--bz-copper-text)" }}'),
    ).toEqual([]);
  });

  it("INNOCENCE: a copper BORDER next to a copper word is the outlined pill", () => {
    expect(
      findCopperGround(
        [
          '  className="border-[var(--bz-copper)]"',
          '  style={{ color: "var(--bz-copper-text)" }}',
        ].join("\n"),
      ),
    ).toEqual([]);
  });

  it("INNOCENCE: borderColor is not a foreground", () => {
    // `borderColor` contains the letters of `color` — an entity guard must not
    // read it as one, or the outlined pill becomes a violation.
    expect(FOREGROUND.test('borderColor: "var(--bz-copper)"')).toBe(false);
  });

  it("INNOCENCE: the forest action ground is not copper", () => {
    expect(
      findCopperGround(
        [
          "const GATE_ACTION_STYLE = {",
          '  background: "var(--state-success)",',
          '  color: "var(--bz-base)",',
          "};",
        ].join("\n"),
      ),
    ).toEqual([]);
  });
});
