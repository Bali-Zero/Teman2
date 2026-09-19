/**
 * Anti-regression fence (PLAN.md §4 "Slice C1", G3-a; MANDATE-vo.md "Slice
 * C1b"): the R19 atlas map
 * (research/design/2026-09-11-r19-design-reuse-map-apps-mouth.md:148-153)
 * collapses the four outcome states onto two colours. This test reads the
 * SHIPPED `oracle.css` from disk (no CSS-in-JS import) and fails if any two
 * of the four `--oracle-state-*` foreground tokens, or any two of the four
 * `-bg` tokens, resolve to the same COLOUR VALUE in any context that
 * declares any of them. `oracle.css` itself is untouched by this PR.
 *
 * vo-gate-c1 (GATE-C1-REPORT-6820.md) passed the C1 fence but found two
 * MEDIUM holes: it compared raw declaration TEXT, not resolved colours
 * (OBS-1 — `#4ADE80` vs `#4ade80` passed green), and it found blocks by
 * anchoring on one token, so a context overriding a SUBSET of the four was
 * invisible (OBS-2). Slice C1b closes both, plus two LOW holes (OBS-5 block
 * identity by line number, OBS-6 no comment awareness). The parsing/
 * comparison mechanism lives in the sibling `oracle-state-tokens.helpers.ts`
 * (not `_lib/` — that directory is frozen for design PRs, R19 map §4.5, and
 * unrelated to this fence).
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import {
  assertDistinct,
  parseEffectiveBlocks,
  type StateValues,
} from "./oracle-state-tokens.helpers";

const CSS_PATH = join(__dirname, "oracle.css");
const CSS = readFileSync(CSS_PATH, "utf8");

const LIGHT_IDENTITY = '.oracle-root, .oracle-root[data-oracle-theme="light"]';
const DARK_IDENTITY = '.oracle-root[data-oracle-theme="dark"]';
const BOOTSTRAP_IDENTITY =
  'html[data-oracle-theme-bootstrap="dark"] .oracle-root[data-oracle-theme="light"]:not([data-oracle-theme-ready])';
const PREFERS_DARK_IDENTITY =
  '@media (prefers-color-scheme: dark) :: html:not([data-oracle-theme-bootstrap]) .oracle-root[data-oracle-theme="light"]:not([data-oracle-theme-ready])';
const EXPECTED_IDENTITIES = [
  LIGHT_IDENTITY,
  DARK_IDENTITY,
  BOOTSTRAP_IDENTITY,
  PREFERS_DARK_IDENTITY,
];

// ─── B1: colour-value comparison, not declaration text ─────────────────────

describe("Visa Oracle outcome-state colour fence — B1 colour normalisation (mechanism, synthetic CSS)", () => {
  function fourTokenBlock(
    overrides: Partial<Record<string, string>> = {},
  ): string {
    const defaults: Record<string, string> = {
      eligible: "#16683f",
      likely: "#2a6f97",
      conditional: "#7a5209",
      "likely-not": "#a83a44",
      "eligible-bg": "rgba(28, 122, 77, 0.1)",
      "likely-bg": "rgba(42, 111, 151, 0.1)",
      "conditional-bg": "rgba(154, 106, 12, 0.12)",
      "likely-not-bg": "rgba(168, 58, 68, 0.1)",
      ...overrides,
    };
    const lines = Object.entries(defaults).map(
      ([name, value]) => `--oracle-state-${name}: ${value};`,
    );
    return `.oracle-root {\n${lines.join("\n")}\n}`;
  }

  it("GUILT: 3-digit hex shorthand equal to another token's 6-digit form collapses", () => {
    const [block] = parseEffectiveBlocks(
      fourTokenBlock({ eligible: "#f00", conditional: "#ff0000" }),
    );
    expect(() => assertDistinct(block.fg, "synthetic")).toThrow(
      "synthetic: --oracle-state-eligible and --oracle-state-conditional both resolve to rgba(255, 0, 0, 1)",
    );
  });

  it("GUILT: rgb() and the equivalent hex collapse", () => {
    const [block] = parseEffectiveBlocks(
      fourTokenBlock({ likely: "rgb(22, 104, 63)", eligible: "#16683f" }),
    );
    expect(() => assertDistinct(block.fg, "synthetic")).toThrow(
      "synthetic: --oracle-state-eligible and --oracle-state-likely both resolve to rgba(22, 104, 63, 1)",
    );
  });

  it("GUILT: alpha `1` and `100%` are the same opacity", () => {
    const [block] = parseEffectiveBlocks(
      fourTokenBlock({
        "eligible-bg": "rgba(1, 2, 3, 1)",
        "likely-bg": "rgba(1, 2, 3, 100%)",
      }),
    );
    expect(() => assertDistinct(block.bg, "synthetic")).toThrow(
      "synthetic: --oracle-state-eligible and --oracle-state-likely both resolve to rgba(1, 2, 3, 1)",
    );
  });

  it("GUILT: a var() reference equal to another token's literal collapses", () => {
    const css = [
      ".oracle-root {",
      "  --oracle-canopy: #16683f;",
      "  --oracle-state-eligible: var(--oracle-canopy);",
      "  --oracle-state-likely: #16683f;",
      "  --oracle-state-conditional: #7a5209;",
      "  --oracle-state-likely-not: #a83a44;",
      "  --oracle-state-eligible-bg: rgba(1, 1, 1, 0.1);",
      "  --oracle-state-likely-bg: rgba(2, 2, 2, 0.1);",
      "  --oracle-state-conditional-bg: rgba(3, 3, 3, 0.1);",
      "  --oracle-state-likely-not-bg: rgba(4, 4, 4, 0.1);",
      "}",
    ].join("\n");
    const [block] = parseEffectiveBlocks(css);
    expect(() => assertDistinct(block.fg, "synthetic")).toThrow(
      "synthetic: --oracle-state-eligible and --oracle-state-likely both resolve to rgba(22, 104, 63, 1)",
    );
  });

  it("INNOCENCE: different colours in different notations (case, shorthand, rgb vs hex) stay distinct", () => {
    const [block] = parseEffectiveBlocks(
      fourTokenBlock({ eligible: "#16683F", likely: "RGB(42, 111, 151)" }),
    );
    expect(() => assertDistinct(block.fg, "synthetic")).not.toThrow();
    expect(() => assertDistinct(block.bg, "synthetic")).not.toThrow();
  });

  it("LOUD: an unresolvable var() fails naming the token, never treated as distinct by default", () => {
    expect(() =>
      parseEffectiveBlocks(
        fourTokenBlock({ eligible: "var(--undefined-token)" }),
      ),
    ).toThrow("--undefined-token");
  });
});

// ─── B2: judge every context on its EFFECTIVE values ───────────────────────

describe("Visa Oracle outcome-state colour fence — B2 partial-override contexts (mechanism, synthetic CSS)", () => {
  const base = [
    ".oracle-root {",
    "  --oracle-state-eligible: #16683f;",
    "  --oracle-state-likely: #2a6f97;",
    "  --oracle-state-conditional: #7a5209;",
    "  --oracle-state-likely-not: #a83a44;",
    "  --oracle-state-eligible-bg: rgba(28, 122, 77, 0.1);",
    "  --oracle-state-likely-bg: rgba(42, 111, 151, 0.1);",
    "  --oracle-state-conditional-bg: rgba(154, 106, 12, 0.12);",
    "  --oracle-state-likely-not-bg: rgba(168, 58, 68, 0.1);",
    "}",
  ].join("\n");

  it("GUILT: a context overriding only TWO tokens is judged on its effective four, naming the collision", () => {
    const withOverride = `${base}\n@media (prefers-contrast: more) {\n  .oracle-root {\n    --oracle-state-likely: #16683f;\n  }\n}`;
    const blocks = parseEffectiveBlocks(withOverride);
    const contrastBlock = blocks.find((b) =>
      b.identity.startsWith("@media (prefers-contrast: more)"),
    );
    expect(contrastBlock).toBeDefined();
    // eligible is untouched (#16683f) and likely was overridden to the same
    // value — the collision only exists once the override is layered over
    // the inherited base, which is exactly what "effective" means.
    expect(() =>
      assertDistinct(
        contrastBlock!.fg,
        `${contrastBlock!.identity} foreground`,
      ),
    ).toThrow(
      `${contrastBlock!.identity} foreground: --oracle-state-eligible and --oracle-state-likely both resolve to rgba(22, 104, 63, 1)`,
    );
  });

  it("INNOCENCE: a context overriding one token to a genuinely different colour passes", () => {
    const withOverride = `${base}\n@media (prefers-contrast: more) {\n  .oracle-root {\n    --oracle-state-likely: #003366;\n  }\n}`;
    const blocks = parseEffectiveBlocks(withOverride);
    const contrastBlock = blocks.find((b) =>
      b.identity.startsWith("@media (prefers-contrast: more)"),
    )!;
    expect(() =>
      assertDistinct(contrastBlock.fg, `${contrastBlock.identity} foreground`),
    ).not.toThrow();
    // The three tokens it didn't override are inherited from the base block.
    expect(contrastBlock.fg.eligible).toBe("rgba(22, 104, 63, 1)");
    expect(contrastBlock.fg.conditional).toBe("rgba(122, 82, 9, 1)");
  });
});

// ─── B4: comment-aware extraction ───────────────────────────────────────────

describe("Visa Oracle outcome-state colour fence — B4 comment-aware extraction (mechanism, synthetic CSS)", () => {
  it("a declaration inside a CSS comment is not read as a real duplicate", () => {
    const css = [
      "/* fake dup, must not be read: --oracle-state-likely: #16683f; */",
      ".oracle-root {",
      "  --oracle-state-eligible: #16683f;",
      "  --oracle-state-likely: #2a6f97;",
      "  --oracle-state-conditional: #7a5209;",
      "  --oracle-state-likely-not: #a83a44;",
      "  --oracle-state-eligible-bg: rgba(1, 1, 1, 0.1);",
      "  --oracle-state-likely-bg: rgba(2, 2, 2, 0.1);",
      "  --oracle-state-conditional-bg: rgba(3, 3, 3, 0.1);",
      "  --oracle-state-likely-not-bg: rgba(4, 4, 4, 0.1);",
      "}",
    ].join("\n");
    const [block] = parseEffectiveBlocks(css);
    expect(() => assertDistinct(block.fg, "innocence")).not.toThrow();
  });

  it("a token declared only inside a comment does not count toward the four — missing, not silently satisfied", () => {
    const css = [
      ".oracle-root {",
      "  --oracle-state-eligible: #16683f;",
      "  --oracle-state-likely: #2a6f97;",
      "  --oracle-state-conditional: #7a5209;",
      "  /* --oracle-state-likely-not: #a83a44; */",
      "  --oracle-state-eligible-bg: rgba(1, 1, 1, 0.1);",
      "  --oracle-state-likely-bg: rgba(2, 2, 2, 0.1);",
      "  --oracle-state-conditional-bg: rgba(3, 3, 3, 0.1);",
      "  --oracle-state-likely-not-bg: rgba(4, 4, 4, 0.1);",
      "}",
    ].join("\n");
    expect(() => parseEffectiveBlocks(css)).toThrow(
      "missing --oracle-state-likely-not",
    );
  });
});

// ─── Gate-proven guilt fixtures, reproduced against a COPY of the shipped
// oracle.css (never the disk file — string mutation only) ──────────────────

describe("Visa Oracle outcome-state colour fence — gate-proven fixtures (GATE-C1-REPORT-6820.md)", () => {
  it("GUILT M4 (OBS-1): hex case difference in the dark block is a collapse, not a pass", () => {
    const mutated = CSS.replace(
      "--oracle-state-likely: #7dd3fc;",
      "--oracle-state-likely: #4ADE80;",
    );
    expect(mutated).not.toBe(CSS);
    const blocks = parseEffectiveBlocks(mutated);
    const darkBlock = blocks.find((b) => b.identity === DARK_IDENTITY)!;
    expect(() =>
      assertDistinct(darkBlock.fg, `${darkBlock.identity} foreground`),
    ).toThrow(
      `${DARK_IDENTITY} foreground: --oracle-state-eligible and --oracle-state-likely both resolve to rgba(74, 222, 128, 1)`,
    );
  });

  it("GUILT M5 (OBS-1): rgba() whitespace difference in the dark block is a collapse, not a pass", () => {
    const mutated = CSS.replace(
      "--oracle-state-eligible-bg: rgba(74, 222, 128, 0.14);",
      "--oracle-state-eligible-bg: rgba(125,211,252,0.14);",
    );
    expect(mutated).not.toBe(CSS);
    const blocks = parseEffectiveBlocks(mutated);
    const darkBlock = blocks.find((b) => b.identity === DARK_IDENTITY)!;
    expect(() =>
      assertDistinct(darkBlock.bg, `${darkBlock.identity} background`),
    ).toThrow(
      `${DARK_IDENTITY} background: --oracle-state-eligible and --oracle-state-likely both resolve to rgba(125, 211, 252, 0.14)`,
    );
  });

  it("GUILT M6 (OBS-2): a 5th context overriding only two tokens is judged on its effective four, naming the collision", () => {
    // #001122 is a value the shipped file never uses for any of the four
    // light-theme tokens (eligible #16683f, likely #2a6f97, conditional
    // #7a5209, likely-not #a83a44 — LIGHT_BASELINE below), so the ONLY
    // collision this mutation can produce is between the two tokens it sets
    // itself, isolating the B2 (subset-override) assertion from Q1 (correct
    // theme inheritance): a `.oracle-root` rule with no `data-oracle-theme`
    // condition, appended after every themed block, inherits its unset
    // tokens (eligible, likely-not) from the LIGHT block's bare `.oracle-root`
    // alternative — the only branch that is a provable generalisation of a
    // selector carrying no theme attribute at all.
    const mutated = `${CSS}\n@media (prefers-contrast: more){.oracle-root{--oracle-state-likely:#001122;--oracle-state-conditional:#001122}}\n`;
    const blocks = parseEffectiveBlocks(mutated);
    const contrastBlock = blocks.find((b) =>
      b.identity.startsWith("@media (prefers-contrast: more)"),
    );
    expect(contrastBlock).toBeDefined();
    expect(contrastBlock!.fg.eligible).toBe("rgba(22, 104, 63, 1)");
    expect(contrastBlock!.fg["likely-not"]).toBe("rgba(168, 58, 68, 1)");
    expect(() =>
      assertDistinct(
        contrastBlock!.fg,
        `${contrastBlock!.identity} foreground`,
      ),
    ).toThrow(
      `${contrastBlock!.identity} foreground: --oracle-state-likely and --oracle-state-conditional both resolve to rgba(0, 17, 34, 1)`,
    );
  });
});

// ─── Q1 (OBS-C1b-1, GATE-C1B-REPORT-6833.md Check 3 / D3b / D4): a block's
// THEME is what its full selector context PROVABLY means, not the first
// `data-oracle-theme="…"` string in it. On the shipped file, the two
// pre-hydration blocks (`oracle.css:114`, `:143`) carry
// `data-oracle-theme="light"` in their selector while declaring DARK
// values — a string-keyed model hands them out as the base for any new
// light-theme context. Reproduced here against the REAL shipped `oracle.css`
// plus an appended override, never single-block synthetic CSS. ───────────

describe("Visa Oracle outcome-state colour fence — Q1 theme inheritance is provable, not string-matched (real oracle.css)", () => {
  const LIGHT_OVERRIDE_IDENTITY = '.oracle-root[data-oracle-theme="light"]';

  it("GUILT (D3b): a light-theme override that collapses two states in the DEFAULT light theme is RED, naming the light context — not silently absorbed by the pre-hydration dark base", () => {
    const mutated = `${CSS}\n.oracle-root[data-oracle-theme="light"]{--oracle-state-likely:#16683f}\n`;
    const blocks = parseEffectiveBlocks(mutated);
    const overrideBlock = blocks.find(
      (b) => b.identity === LIGHT_OVERRIDE_IDENTITY,
    );
    expect(overrideBlock).toBeDefined();
    // The base it inherited from must be the LIGHT block (eligible
    // #16683f), never the pre-hydration dark blocks (eligible #4ade80) —
    // pin the inherited value directly, not just the resulting error.
    expect(overrideBlock!.fg.eligible).toBe("rgba(22, 104, 63, 1)");
    expect(() =>
      assertDistinct(
        overrideBlock!.fg,
        `${overrideBlock!.identity} foreground`,
      ),
    ).toThrow(
      `${LIGHT_OVERRIDE_IDENTITY} foreground: --oracle-state-eligible and --oracle-state-likely both resolve to rgba(22, 104, 63, 1)`,
    );
  });

  it("INNOCENCE (D4): the mirror override — a colour that only collides with the DARK palette — is GREEN in the light context it actually renders in", () => {
    const mutated = `${CSS}\n.oracle-root[data-oracle-theme="light"]{--oracle-state-likely:#4ade80}\n`;
    const blocks = parseEffectiveBlocks(mutated);
    const overrideBlock = blocks.find(
      (b) => b.identity === LIGHT_OVERRIDE_IDENTITY,
    )!;
    expect(overrideBlock.fg).toEqual({
      eligible: "rgba(22, 104, 63, 1)",
      likely: "rgba(74, 222, 128, 1)",
      conditional: "rgba(122, 82, 9, 1)",
      "likely-not": "rgba(168, 58, 68, 1)",
    });
    expect(() =>
      assertDistinct(overrideBlock.fg, `${overrideBlock.identity} foreground`),
    ).not.toThrow();
  });

  it("a dark-theme override still correctly inherits the DARK base (unaffected by the Q1 fix — sanity check)", () => {
    const mutated = `${CSS}\n.oracle-root[data-oracle-theme="dark"]{--oracle-state-likely:#4ade80}\n`;
    const blocks = parseEffectiveBlocks(mutated);
    // The appended override shares its selector text with the original
    // DARK block, so `identity` (selector-keyed, B3) is the same for both —
    // the ORIGINAL (fully-declared, no collision) is first, the OVERRIDE
    // (one token, inherits the rest) is last.
    const contexts = blocks.filter((b) => b.identity === DARK_IDENTITY);
    expect(contexts).toHaveLength(2);
    const [original, override] = contexts;
    expect(() =>
      assertDistinct(original.fg, `${original.identity} foreground`),
    ).not.toThrow();
    expect(() =>
      assertDistinct(override.fg, `${override.identity} foreground`),
    ).toThrow(
      `${DARK_IDENTITY} foreground: --oracle-state-eligible and --oracle-state-likely both resolve to rgba(74, 222, 128, 1)`,
    );
  });

  it("LOUD: two equally-specific but DIFFERENT candidate bases make the effective values impossible to derive with certainty — named, not guessed", () => {
    const css = [
      // Two blocks whose branch signatures are the SAME SIZE (one
      // attribute-condition each) but carry DIFFERENT keys — neither is a
      // generalisation of the other, and the override below is constrained
      // on BOTH keys at once, so both are equally-specific, equally valid,
      // disagreeing candidate bases. A real ambiguity: there is no single
      // correct inherited value.
      '.tree-a[data-oracle-theme="light"] {',
      "  --oracle-state-eligible: #111111;",
      "  --oracle-state-likely: #222222;",
      "  --oracle-state-conditional: #333333;",
      "  --oracle-state-likely-not: #444444;",
      "  --oracle-state-eligible-bg: rgba(1, 1, 1, 0.1);",
      "  --oracle-state-likely-bg: rgba(2, 2, 2, 0.1);",
      "  --oracle-state-conditional-bg: rgba(3, 3, 3, 0.1);",
      "  --oracle-state-likely-not-bg: rgba(4, 4, 4, 0.1);",
      "}",
      "@media (prefers-contrast: more) {",
      "  .tree-b {",
      "    --oracle-state-eligible: #555555;",
      "    --oracle-state-likely: #666666;",
      "    --oracle-state-conditional: #777777;",
      "    --oracle-state-likely-not: #888888;",
      "    --oracle-state-eligible-bg: rgba(5, 5, 5, 0.1);",
      "    --oracle-state-likely-bg: rgba(6, 6, 6, 0.1);",
      "    --oracle-state-conditional-bg: rgba(7, 7, 7, 0.1);",
      "    --oracle-state-likely-not-bg: rgba(8, 8, 8, 0.1);",
      "  }",
      "}",
      "@media (prefers-contrast: more) {",
      '  .tree-c[data-oracle-theme="light"] {',
      "    --oracle-state-likely: #999999;",
      "  }",
      "}",
    ].join("\n");
    let thrown: Error | undefined;
    try {
      parseEffectiveBlocks(css);
    } catch (err) {
      thrown = err as Error;
    }
    expect(thrown).toBeDefined();
    expect(thrown!.message).toContain(
      "cannot derive effective values with certainty",
    );
    expect(thrown!.message).toContain('.tree-a[data-oracle-theme="light"]');
    expect(thrown!.message).toContain(
      "@media (prefers-contrast: more) :: .tree-b",
    );
  });
});

// ─── Q4 (OBS-C1b-4): clamp channel and alpha ranges the way a browser does
// BEFORE comparing — `rgb(300, 0, 0)` renders identically to `#ff0000`, and
// alpha > 1 renders identically to fully opaque, so both pairs must collapse
// rather than stay silently distinct (the gate's P-m/P-n). ─────────────────

describe("Visa Oracle outcome-state colour fence — Q4 clamp out-of-gamut channels and alpha before comparing", () => {
  function fourTokenBlock(
    overrides: Partial<Record<string, string>> = {},
  ): string {
    const defaults: Record<string, string> = {
      eligible: "#16683f",
      likely: "#2a6f97",
      conditional: "#7a5209",
      "likely-not": "#a83a44",
      "eligible-bg": "rgba(28, 122, 77, 0.1)",
      "likely-bg": "rgba(42, 111, 151, 0.1)",
      "conditional-bg": "rgba(154, 106, 12, 0.12)",
      "likely-not-bg": "rgba(168, 58, 68, 0.1)",
      ...overrides,
    };
    const lines = Object.entries(defaults).map(
      ([name, value]) => `--oracle-state-${name}: ${value};`,
    );
    return `.oracle-root {\n${lines.join("\n")}\n}`;
  }

  it("GUILT (P-m): an out-of-gamut rgb() channel clamps to 255 the way a browser paints it, colliding with the equivalent hex", () => {
    const [block] = parseEffectiveBlocks(
      fourTokenBlock({ eligible: "rgb(300, 0, 0)", likely: "#ff0000" }),
    );
    expect(() => assertDistinct(block.fg, "synthetic")).toThrow(
      "synthetic: --oracle-state-eligible and --oracle-state-likely both resolve to rgba(255, 0, 0, 1)",
    );
  });

  it("GUILT (P-n): alpha above 1 clamps to fully opaque the way a browser paints it, colliding with alpha 1", () => {
    const [block] = parseEffectiveBlocks(
      fourTokenBlock({
        "eligible-bg": "rgba(1, 2, 3, 2)",
        "likely-bg": "rgba(1, 2, 3, 1)",
      }),
    );
    expect(() => assertDistinct(block.bg, "synthetic")).toThrow(
      "synthetic: --oracle-state-eligible and --oracle-state-likely both resolve to rgba(1, 2, 3, 1)",
    );
  });

  it("INNOCENCE: an out-of-gamut negative channel clamps to 0 without disturbing a genuinely distinct colour", () => {
    const [block] = parseEffectiveBlocks(
      fourTokenBlock({ eligible: "rgb(-40, 5, 5)" }),
    );
    expect(block.fg.eligible).toBe("rgba(0, 5, 5, 1)");
    expect(() => assertDistinct(block.fg, "synthetic")).not.toThrow();
  });
});

// ─── The shipped oracle.css itself ──────────────────────────────────────────

describe("Visa Oracle outcome-state colour fence (shipped oracle.css)", () => {
  const BLOCKS = parseEffectiveBlocks(CSS);

  it("declares --oracle-state-* tokens in exactly four contexts, identified by selector/at-rule (B3)", () => {
    // A fifth context (or a dropped one) must fail here first, before the
    // per-block assertions below even run against the wrong shape.
    expect(BLOCKS.map((b) => b.identity)).toEqual(EXPECTED_IDENTITIES);
  });

  it("INNOCENCE (B3): a comment added at the top of a copy of oracle.css leaves identity and values unchanged", () => {
    const commented = `/* a harmless reformat comment, changes no line this fence pins */\n${CSS}`;
    const blocks = parseEffectiveBlocks(commented);
    expect(blocks.map((b) => b.identity)).toEqual(
      BLOCKS.map((b) => b.identity),
    );
    for (const block of blocks) {
      expect(() =>
        assertDistinct(block.fg, `${block.identity} foreground`),
      ).not.toThrow();
      expect(() =>
        assertDistinct(block.bg, `${block.identity} background`),
      ).not.toThrow();
    }
  });

  for (const block of BLOCKS) {
    describe(`context: ${block.identity}`, () => {
      it("keeps the four foreground state colours pairwise distinct (resolved values)", () => {
        assertDistinct(block.fg, `${block.identity} foreground`);
      });

      it("keeps the four background state colours pairwise distinct (resolved values)", () => {
        assertDistinct(block.bg, `${block.identity} background`);
      });
    });
  }

  // Pinned today's light-mode (default `.oracle-root`) values verbatim, AS
  // DECLARED (not colour-normalised) — changing them is allowed, a repaint
  // is a legitimate design act, but it must be a deliberate edit to THIS
  // constant in the same PR as the oracle.css change. Collapsing two of them
  // to the same colour is never allowed; that is what the distinctness
  // assertions above catch regardless of notation.
  const LIGHT_BASELINE: StateValues = {
    eligible: "#16683f",
    likely: "#2a6f97",
    conditional: "#7a5209",
    "likely-not": "#a83a44",
  };

  it("pins the shipped light-mode (default) foreground values", () => {
    const lightBlock = BLOCKS.find((b) => b.identity === LIGHT_IDENTITY)!;
    expect(lightBlock.fgRaw).toEqual(LIGHT_BASELINE);
  });

  // TODO(C3): add a contrast-ratio assertion once a WCAG contrast helper
  // exists in apps/mouth (none does today — `grep -rn 'contrastRatio\|wcag'
  // apps/mouth/src --include='*.ts'` matches only this comment). Out of
  // scope for this one-PR-one-concern slice; see PLAN.md §4 Slice C3.
});
