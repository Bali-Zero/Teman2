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
// A fallback does not make the read innocent: `var(--state-danger, X)` still
// asks for the danger token first. The closing paren was load-bearing here and
// should not have been — same shape as BZ_RED above, which never had it.
const STATE_DANGER = /var\(\s*--state-danger\b/;

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
  // `background: var(--bz-accent)` / `backgroundColor:` / `bg-[var(--bz-copper)]`.
  //
  // The value may continue onto the NEXT line, because that is what prettier
  // does to a long declaration and it is the commonest real spelling — this
  // very tree carries `background:\n  "var(…)"` in ZantaraWidget. The first
  // draft ended the value at the newline and was therefore blind to it.
  // LIMIT: one wrap, not many; a value prettier split across three lines
  // escapes, and no shape in this tree does that today.
  `(background(-?[Cc]olor)?\\s*:[^;\\n]*(?:\\n[^;\\n]*)?|bg-\\[)${COPPER_TOKEN.source}`,
);
/**
 * A foreground colour: `color:` as its own key (never `borderColor`, which
 * contains the same letters), or a Tailwind text COLOUR.
 *
 * `text-[…]` alone is not enough — `text-[13px]` is a font size, and reading
 * it as a label would falsely accuse a copper bar that happens to set its own
 * type scale. So the arbitrary form must open with `var(` or `#`, and the
 * named forms are spelled out.
 */
const FOREGROUND =
  /(^|[^A-Za-z-])color\s*:|text-\[\s*(?:var\(|#)|text-(?:white|black|primary|secondary|tertiary|accent|muted|inherit|current)\b|text-[a-z]+-\d{2,3}\b/;

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
 * A copper token mixed BELOW half is a wash, not a ground.
 *
 * AppSidebar's notification badge is the real case: `color-mix(in srgb,
 * var(--bz-copper-text) 14%, transparent)` with a copper numeral on it. The
 * ground there is essentially the paper it sits on, the numeral is legible,
 * and the frozen concept asks for exactly that badge. A detector that read
 * "the copper token appears inside a background value" would accuse it — which
 * is guard-over-match: judging a substring instead of the entity.
 *
 * The line is drawn at 50% and the reason is statable rather than eyeballed:
 * above half, the copper IS the majority of the ground and a label on it is
 * the thing the rule forbids. Below half it is a tint of whatever it is mixed
 * into. A mix with no percentage at all is NOT cleared — an unmeasured mix
 * gets judged, because silence is not evidence of a wash.
 */
const COPPER_TOKEN_G =
  /var\(\s*--(?:bz-accent|bz-copper|bz-copper-text|bz-sidebar-active-fill)\b/;
export const COPPER_WASH_CEILING = 50;

/**
 * Copper's share of a `color-mix`, as a percentage, or null when it cannot be
 * read.
 *
 * The second review seat found the first draft read only ONE of the three
 * spellings CSS allows. All three are valid and all three are a 14% wash:
 *
 *   color-mix(in srgb, var(--bz-copper-text) 14%, transparent)
 *   color-mix(in srgb, 14% var(--bz-copper-text), transparent)
 *   color-mix(in srgb, transparent 86%, var(--bz-copper-text))
 *
 * The draft matched only the first, so the other two were falsely accused.
 * This reads components rather than a fixed order: copper's own percentage if
 * it carries one, otherwise the remainder of the other component's.
 *
 * Returns null when NEITHER component states a share — silence is not
 * evidence of a wash, so an unmeasured mix is judged as a ground.
 */
export function copperMixShare(declaration: string): number | null {
  const at = declaration.indexOf("color-mix(");
  if (at === -1) return null;
  // Read to the matching paren so a trailing `)` from an outer var() cannot
  // truncate the component list.
  let depth = 0;
  let end = -1;
  for (let i = at + "color-mix".length; i < declaration.length; i++) {
    if (declaration[i] === "(") depth++;
    else if (declaration[i] === ")") {
      depth--;
      if (depth === 0) {
        end = i;
        break;
      }
    }
  }
  if (end === -1) return null;
  const inner = declaration.slice(at + "color-mix(".length, end);

  // Split on TOP-LEVEL commas only: `var(--x, fallback)` carries its own.
  const parts: string[] = [];
  let buf = "";
  let d = 0;
  for (const ch of inner) {
    if (ch === "(") d++;
    else if (ch === ")") d--;
    if (ch === "," && d === 0) {
      parts.push(buf);
      buf = "";
    } else buf += ch;
  }
  parts.push(buf);

  // parts[0] is the interpolation method ("in srgb"); the components follow.
  const components = parts.slice(1);
  if (components.length !== 2) return null;
  const pctOf = (c: string) => {
    const m = /(\d+)\s*%/.exec(c);
    return m ? Number(m[1]) : null;
  };
  const copperIdx = components.findIndex((c) => COPPER_TOKEN_G.test(c));
  if (copperIdx === -1) return null;
  const own = pctOf(components[copperIdx]);
  if (own !== null) return own;
  const other = pctOf(components[1 - copperIdx]);
  if (other !== null) return 100 - other;
  return null;
}

/** True when this background is a copper WASH rather than a copper ground. */
export function isCopperWash(declaration: string): boolean {
  const share = copperMixShare(declaration);
  return share !== null && share < COPPER_WASH_CEILING;
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
    if (isCopperWash(text)) continue;
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

// ---------------------------------------------------------------------------
// The three defects the SECOND review seat found (codex-gpt-5.6-sol, acct2,
// read-only, on the K1c2 diff). Each was confirmed by measurement before being
// accepted — a finding is a claim until the detector is run against it — and
// each is now a guilt case, so the cure cannot silently regress.
//
// The first is the one that matters: it was not hypothetical. Prettier wraps a
// long declaration onto the next line, and this very tree carries that shape
// in ZantaraWidget. The guard was blind to the commonest real spelling of the
// thing it exists to catch.
// ---------------------------------------------------------------------------

describe("the second seat's findings stay fixed", () => {
  it("GUILT: a prettier-wrapped copper background is caught", () => {
    const found = findCopperGround(
      [
        "              style={{",
        "                background:",
        '                  "var(--bz-accent)",',
        '                color: "var(--bz-base)",',
        "              }}",
      ].join("\n"),
    );
    expect(found).toHaveLength(1);
    expect(found[0].rule).toBe("copper-ground");
  });

  it("INNOCENCE: a wrapped NON-copper background is still clean", () => {
    // The real line from ZantaraWidget: same wrapping, a token that is not
    // copper. The cure must widen the reach, not the accusation.
    expect(
      findCopperGround(
        [
          "                    {",
          "                      background:",
          '                        "var(--bz-selected-fill, var(--state-info))",',
          '                      color: "var(--bz-on-selected, var(--bz-base))",',
          "                    }",
        ].join("\n"),
      ),
    ).toEqual([]);
  });

  it("INNOCENCE: a type scale is not a label", () => {
    // `text-[13px]` is a font size. Reading it as a foreground would accuse a
    // copper bar that happens to set its own type scale.
    expect(
      findCopperGround('className="bg-[var(--bz-copper)] text-[13px]"'),
    ).toEqual([]);
  });

  it("GUILT: an arbitrary text COLOUR beside a copper fill still is one", () => {
    // The innocence above must not have bought itself by going blind.
    expect(
      findCopperGround(
        'className="bg-[var(--bz-copper)] text-[var(--bz-base)]"',
      ),
    ).toHaveLength(1);
    expect(
      findCopperGround('className="bg-[var(--bz-copper)] text-[#ffffff]"'),
    ).toHaveLength(1);
    expect(
      findCopperGround('className="bg-[var(--bz-copper)] text-white"'),
    ).toHaveLength(1);
  });

  it("GUILT: --state-danger with a fallback is still a --state-danger read", () => {
    const found = findForbiddenPaint(
      'color: "var(--state-danger, var(--bz-copper-text))"',
    );
    expect(found.map((f) => f.rule)).toContain("state-danger");
  });

  it("INNOCENCE: --state-warning and --state-success are untouched by that widening", () => {
    expect(
      findForbiddenPaint(
        'color: "var(--state-warning)"; background: "var(--state-success)"',
      ),
    ).toEqual([]);
  });
});

describe("a copper wash is not a copper ground", () => {
  const BADGE = [
    "            style={{",
    "              background:",
    '                "color-mix(in srgb, var(--bz-copper-text) 14%, transparent)",',
    '              color: "var(--bz-copper-text)",',
    "            }}",
  ].join("\n");

  it("INNOCENCE: AppSidebar's 14% badge, verbatim, is clean", () => {
    // Found by running the widened detector against the real file — the guard
    // accused the rail's own notification badge, which the frozen concept asks
    // for. The accusation was the defect, not the badge.
    expect(findCopperGround(BADGE)).toEqual([]);
    expect(isCopperWash(BADGE)).toBe(true);
  });

  it("GUILT: a mix that is MOSTLY copper is still a ground", () => {
    const mostly = BADGE.replace("14%", "96%");
    expect(isCopperWash(mostly)).toBe(false);
    expect(findCopperGround(mostly)).toHaveLength(1);
  });

  it("holds the line exactly at half, and states which side it falls on", () => {
    expect(isCopperWash(BADGE.replace("14%", "49%"))).toBe(true);
    expect(isCopperWash(BADGE.replace("14%", "50%"))).toBe(false);
  });

  it("GUILT: a mix with NO percentage is judged, not excused", () => {
    // Silence is not evidence of a wash.
    const noPct = BADGE.replace(
      "var(--bz-copper-text) 14%",
      "var(--bz-copper-text)",
    );
    expect(isCopperWash(noPct)).toBe(false);
    expect(findCopperGround(noPct)).toHaveLength(1);
  });

  it("GUILT: a SOLID copper ground is untouched by this exemption", () => {
    expect(
      findCopperGround(
        [
          "  {",
          '    background: "var(--bz-accent)",',
          '    color: "var(--bz-base)",',
          "  }",
        ].join("\n"),
      ),
    ).toHaveLength(1);
  });
});

// ---------------------------------------------------------------------------
// The SECOND seat of the council (agy-gemini-3.1-pro, fallback). Its findings,
// each measured before being accepted.
// ---------------------------------------------------------------------------

describe("copper's share is read in every spelling CSS allows", () => {
  const S = (mix: string) =>
    [
      "  {",
      `    background: "${mix}",`,
      '    color: "var(--bz-copper-text)",',
      "  }",
    ].join("\n");

  it("reads the share when the percentage FOLLOWS the colour", () => {
    const mix = "color-mix(in srgb, var(--bz-copper-text) 14%, transparent)";
    expect(copperMixShare(mix)).toBe(14);
    expect(findCopperGround(S(mix))).toEqual([]);
  });

  it("reads it when the percentage PRECEDES the colour", () => {
    // Valid CSS, and the first draft was blind to it.
    const mix = "color-mix(in srgb, 14% var(--bz-copper-text), transparent)";
    expect(copperMixShare(mix)).toBe(14);
    expect(findCopperGround(S(mix))).toEqual([]);
  });

  it("reads it as the REMAINDER when only the other component states one", () => {
    const mix = "color-mix(in srgb, transparent 86%, var(--bz-copper-text))";
    expect(copperMixShare(mix)).toBe(14);
    expect(findCopperGround(S(mix))).toEqual([]);
  });

  it("GUILT: a mostly-copper mix is a ground in every spelling too", () => {
    for (const mix of [
      "color-mix(in srgb, var(--bz-copper-text) 96%, transparent)",
      "color-mix(in srgb, 96% var(--bz-copper-text), transparent)",
      "color-mix(in srgb, transparent 4%, var(--bz-copper-text))",
    ]) {
      expect(copperMixShare(mix)).toBe(96);
      expect(findCopperGround(S(mix))).toHaveLength(1);
    }
  });

  it("GUILT: no percentage anywhere is judged, not excused", () => {
    const mix = "color-mix(in srgb, var(--bz-copper-text), transparent)";
    expect(copperMixShare(mix)).toBeNull();
    expect(findCopperGround(S(mix))).toHaveLength(1);
  });

  it("is not fooled by a var() fallback's own comma", () => {
    // `var(--a, b)` carries a comma that a naive split would read as a
    // component boundary, which would make the component count wrong and
    // silently return null — a fail-OPEN on a real wash.
    const mix =
      "color-mix(in srgb, var(--bz-copper-text, var(--state-warning)) 14%, transparent)";
    expect(copperMixShare(mix)).toBe(14);
  });

  it("GUILT: a semantic text utility is a foreground too", () => {
    // `text-primary` has no numeric shade, so the shade-based branch missed it.
    expect(
      findCopperGround('className="bg-[var(--bz-copper)] text-primary"'),
    ).toHaveLength(1);
    // And the type scale is still not one.
    expect(
      findCopperGround('className="bg-[var(--bz-copper)] text-[13px]"'),
    ).toEqual([]);
  });
});

describe("the scanner's reach, stated and then measured", () => {
  // The second seat named two shapes `spans()` cannot parse: a REGEX LITERAL
  // (its braces and quotes would push/pop the wrong stacks) and a NESTED
  // template literal (the inner backtick closes the outer span early). Both
  // are true. Rather than write a JS tokeniser inside a guard, the limit is
  // stated AND bounded by measurement.
  //
  // But "contains a regex literal" is the WRONG entity, and running the first
  // draft of this probe is what showed it: GateScreen carries
  // `.replace(/_/g, " ")`, which is inert — it holds no quote and no brace, so
  // it toggles nothing and pushes nothing. What breaks the scanner is a regex
  // CARRYING one of those characters. That is what this measures, and it fails
  // the day one appears: the moment to widen the scanner, rather than the
  // moment to discover it had gone blind.
  const DANGEROUS_REGEX_LITERAL =
    /(?:^|[=(,:]\s*)\/(?![/*])(?:\\.|\[[^\]]*\]|[^/\n\\])*["'`{}](?:\\.|\[[^\]]*\]|[^/\n\\])*\//;

  for (const file of [...SHELL_FILES]) {
    it(`${file} carries no scanner-breaking regex literal`, () => {
      const source = stripComments(readFileSync(join(SRC, file), "utf8"));
      expect(DANGEROUS_REGEX_LITERAL.test(source)).toBe(false);
    });
  }
  it("a template literal's interpolation is scoped to the WHOLE template", () => {
    // Not a defect, but worth pinning: the scanner treats a template as one
    // string span, so a copper fill inside an interpolation is judged against
    // the whole template rather than the nearest brace. That is WIDER than
    // ideal and therefore conservative — it can over-accuse, never under.
    const tpl =
      'const c = `${cond ? "bg-[var(--bz-copper)]" : ""} text-[var(--bz-base)]`;';
    expect(findCopperGround(tpl)).toHaveLength(1);
  });
});

describe("the scanner-breaking probe knows which regex literals matter", () => {
  const DANGEROUS =
    /(?:^|[=(,:]\s*)\/(?![/*])(?:\\.|\[[^\]]*\]|[^/\n\\])*["'`{}](?:\\.|\[[^\]]*\]|[^/\n\\])*\//;

  it("INNOCENCE: GateScreen's own `.replace(/_/g, ' ')` is inert", () => {
    expect(DANGEROUS.test('alert.category.replace(/_/g, " ")')).toBe(false);
  });

  it("GUILT: a regex carrying a quote would flip the scanner's string state", () => {
    expect(DANGEROUS.test("const q = /[\"']/;")).toBe(true);
  });

  it("GUILT: a regex carrying a brace would push a phantom block", () => {
    expect(DANGEROUS.test("const n = /\\d{2,3}/;")).toBe(true);
  });
});
