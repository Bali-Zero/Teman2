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
  SELECTOR_GRAMMAR,
  type StateValues,
} from "./oracle-state-tokens.helpers";

const CSS_PATH = join(__dirname, "oracle.css");
const CSS = readFileSync(CSS_PATH, "utf8");

// U2: the shipped light base is a two-branch selector list
// (`.oracle-root, .oracle-root[data-oracle-theme="light"]`) — it is now TWO
// independent contexts, never judged on the first alternative only.
const LIGHT_BARE_IDENTITY = ".oracle-root";
const LIGHT_ATTR_IDENTITY = '.oracle-root[data-oracle-theme="light"]';
const DARK_IDENTITY = '.oracle-root[data-oracle-theme="dark"]';
const BOOTSTRAP_IDENTITY =
  'html[data-oracle-theme-bootstrap="dark"] .oracle-root[data-oracle-theme="light"]:not([data-oracle-theme-ready])';
const PREFERS_DARK_IDENTITY =
  '@media (prefers-color-scheme: dark) :: html:not([data-oracle-theme-bootstrap]) .oracle-root[data-oracle-theme="light"]:not([data-oracle-theme-ready])';
const EXPECTED_IDENTITIES = [
  LIGHT_BARE_IDENTITY,
  LIGHT_ATTR_IDENTITY,
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
    // tokens (eligible, likely-not) from the LIGHT base's bare `.oracle-root`
    // branch context (U2) — the only one that is a provable generalisation
    // of a selector carrying no theme attribute at all.
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
    // The appended override shares its selector text with the shipped
    // LIGHT_ATTR branch, so `identity` is the same for both (B3/U2) — the
    // shipped one (fully declared, no collision) is first, the appended
    // override (one token, must inherit the rest) is last.
    const contexts = blocks.filter(
      (b) => b.identity === LIGHT_OVERRIDE_IDENTITY,
    );
    expect(contexts).toHaveLength(2);
    const overrideBlock = contexts[contexts.length - 1];
    // The base it inherited from must be the LIGHT block (eligible
    // #16683f), never the pre-hydration dark blocks (eligible #4ade80) —
    // pin the inherited value directly, not just the resulting error.
    expect(overrideBlock.fg.eligible).toBe("rgba(22, 104, 63, 1)");
    expect(() =>
      assertDistinct(overrideBlock.fg, `${overrideBlock.identity} foreground`),
    ).toThrow(
      `${LIGHT_OVERRIDE_IDENTITY} foreground: --oracle-state-eligible and --oracle-state-likely both resolve to rgba(22, 104, 63, 1)`,
    );
  });

  it("INNOCENCE (D4): the mirror override — a colour that only collides with the DARK palette — is GREEN in the light context it actually renders in", () => {
    const mutated = `${CSS}\n.oracle-root[data-oracle-theme="light"]{--oracle-state-likely:#4ade80}\n`;
    const blocks = parseEffectiveBlocks(mutated);
    const contexts = blocks.filter(
      (b) => b.identity === LIGHT_OVERRIDE_IDENTITY,
    );
    expect(contexts).toHaveLength(2);
    const overrideBlock = contexts[contexts.length - 1];
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

// ─── U1: the exported grammar names exactly what this fence models ────────

describe("Visa Oracle outcome-state colour fence — U1 the exported grammar", () => {
  it("allows only @media and @supports as at-rule wrappers", () => {
    expect(SELECTOR_GRAMMAR.atRules).toEqual(["media", "supports"]);
  });
});

// ─── U1-U3 (OBS-C1c-1/2, GATE-C1C-REPORT-6845.md Check 2): H1/H2/H3, on the
// REAL shipped oracle.css plus an appended override, never fixture-local
// synthetic CSS — reproducing the gate's exact hostile contexts. ──────────

describe("Visa Oracle outcome-state colour fence — U1-U3 closed-world hostile contexts (real oracle.css)", () => {
  const FORCED_COLORS_DARK_ID =
    '@media (forced-colors: active) :: .oracle-root[data-oracle-theme="dark"]';
  const FORCED_COLORS_LIGHT_ID =
    '@media (forced-colors: active) :: .oracle-root[data-oracle-theme="light"]';

  it("GUILT (H1): a two-branch dark+light override collapsing two states in light is RED naming the LIGHT branch; the DARK branch of the SAME rule stays GREEN", () => {
    const mutated = `${CSS}\n@media (forced-colors: active) {\n  .oracle-root[data-oracle-theme="dark"],\n  .oracle-root[data-oracle-theme="light"] {\n    --oracle-state-likely: #16683f;\n  }\n}\n`;
    const blocks = parseEffectiveBlocks(mutated);
    const dark = blocks.find((b) => b.identity === FORCED_COLORS_DARK_ID)!;
    const light = blocks.find((b) => b.identity === FORCED_COLORS_LIGHT_ID)!;
    expect(dark).toBeDefined();
    expect(light).toBeDefined();
    // U2: branchSignatures[0] disappears — each comma-branch is judged on
    // its OWN palette, never both on whichever branch happened to be first.
    expect(() =>
      assertDistinct(dark.fg, `${dark.identity} foreground`),
    ).not.toThrow();
    expect(() =>
      assertDistinct(light.fg, `${light.identity} foreground`),
    ).toThrow(
      `${FORCED_COLORS_LIGHT_ID} foreground: --oracle-state-eligible and --oracle-state-likely both resolve to rgba(22, 104, 63, 1)`,
    );
  });

  it("INNOCENCE (H1 mirror): the same two-branch override with a colour neither palette uses is GREEN on both branches", () => {
    const mutated = `${CSS}\n@media (forced-colors: active) {\n  .oracle-root[data-oracle-theme="dark"],\n  .oracle-root[data-oracle-theme="light"] {\n    --oracle-state-likely: #001122;\n  }\n}\n`;
    const blocks = parseEffectiveBlocks(mutated);
    const dark = blocks.find((b) => b.identity === FORCED_COLORS_DARK_ID)!;
    const light = blocks.find((b) => b.identity === FORCED_COLORS_LIGHT_ID)!;
    expect(() =>
      assertDistinct(dark.fg, `${dark.identity} foreground`),
    ).not.toThrow();
    expect(() =>
      assertDistinct(light.fg, `${light.identity} foreground`),
    ).not.toThrow();
  });

  it('GUILT (H2): a VALUED :not([data-oracle-theme="dark"]) — the light theme, read as a positive dark constraint by a raw-text regex — throws unmodelled, naming the construct, rather than shipping a silent green', () => {
    const mutated = `${CSS}\n@media (forced-colors: active) {\n  .oracle-root:not([data-oracle-theme="dark"]) {\n    --oracle-state-likely: #16683f;\n  }\n}\n`;
    expect(() => parseEffectiveBlocks(mutated)).toThrow(
      /unmodelled selector construct ":not\(\[data-oracle-theme="dark"\]\)" in @media \(forced-colors: active\) :: \.oracle-root:not\(\[data-oracle-theme="dark"\]\)/,
    );
  });

  it("H2 mirror: the SAME throw for an innocent colour — a valued :not() is unmodelled independent of the declared value, so there is no green case for it, only loud", () => {
    const mutated = `${CSS}\n@media (forced-colors: active) {\n  .oracle-root:not([data-oracle-theme="dark"]) {\n    --oracle-state-likely: #001122;\n  }\n}\n`;
    expect(() => parseEffectiveBlocks(mutated)).toThrow(
      /unmodelled selector construct ":not\(\[data-oracle-theme="dark"\]\)"/,
    );
  });

  it("CONTROL (H3): a single-branch light override still turns the suite RED exactly as before — no fixture cross-talk with H1/H2 above", () => {
    const mutated = `${CSS}\n@media (forced-colors: active) {\n  .oracle-root[data-oracle-theme="light"] {\n    --oracle-state-likely: #16683f;\n  }\n}\n`;
    const blocks = parseEffectiveBlocks(mutated);
    const light = blocks.find((b) => b.identity === FORCED_COLORS_LIGHT_ID)!;
    expect(() =>
      assertDistinct(light.fg, `${light.identity} foreground`),
    ).toThrow(
      `${FORCED_COLORS_LIGHT_ID} foreground: --oracle-state-eligible and --oracle-state-likely both resolve to rgba(22, 104, 63, 1)`,
    );
  });

  it("further regression: a descendant of the bootstrap-dark pre-hydration block still keys dark, and a [dark] subset override still keys dark", () => {
    const descendantOfBootstrap = `${CSS}\nhtml[data-oracle-theme-bootstrap="dark"] .oracle-root[data-oracle-theme="light"]:not([data-oracle-theme-ready]) .some-child {\n  --oracle-state-likely: #4ade80;\n}\n`;
    const blocksA = parseEffectiveBlocks(descendantOfBootstrap);
    const descendant = blocksA.find((b) => b.identity.endsWith(".some-child"))!;
    expect(descendant).toBeDefined();
    // Inherits the DARK palette (eligible #4ade80) — colliding with its own
    // likely override of the SAME value.
    expect(() =>
      assertDistinct(descendant.fg, `${descendant.identity} foreground`),
    ).toThrow(
      /eligible and --oracle-state-likely both resolve to rgba\(74, 222, 128, 1\)/,
    );

    const darkSubsetOverride = `${CSS}\n.oracle-root[data-oracle-theme="dark"] {\n  --oracle-state-likely: #001122;\n}\n`;
    const blocksB = parseEffectiveBlocks(darkSubsetOverride);
    const darkContexts = blocksB.filter((b) => b.identity === DARK_IDENTITY);
    expect(darkContexts).toHaveLength(2);
    const override = darkContexts[darkContexts.length - 1];
    expect(override.fg.eligible).toBe("rgba(74, 222, 128, 1)"); // DARK's own eligible
    expect(() =>
      assertDistinct(override.fg, `${override.identity} foreground`),
    ).not.toThrow();
  });
});

// ─── U4: closed-world proof — every construct OUTSIDE the grammar throws,
// naming it; the shipped file itself parses with ZERO throws (proven by
// every describe block above, which all read `parseEffectiveBlocks(CSS)`
// or a mutation of it, and by the five-identity pin below). ───────────────

describe("Visa Oracle outcome-state colour fence — U4 closed-world: constructs outside the grammar throw", () => {
  const EIGHT_TOKENS = [
    "--oracle-state-eligible:#111111",
    "--oracle-state-likely:#222222",
    "--oracle-state-conditional:#333333",
    "--oracle-state-likely-not:#444444",
    "--oracle-state-eligible-bg:rgba(1,1,1,0.1)",
    "--oracle-state-likely-bg:rgba(2,2,2,0.1)",
    "--oracle-state-conditional-bg:rgba(3,3,3,0.1)",
    "--oracle-state-likely-not-bg:rgba(4,4,4,0.1)",
  ].join(";");

  const cases: Array<[string, string]> = [
    [
      "valued :not()",
      `.oracle-root:not([data-oracle-theme="dark"]){${EIGHT_TOKENS}}`,
    ],
    [":is()", `.oracle-root:is([data-oracle-theme="light"]){${EIGHT_TOKENS}}`],
    [
      ":where()",
      `.oracle-root:where([data-oracle-theme="light"]){${EIGHT_TOKENS}}`,
    ],
    [":has()", `.oracle-root:has([data-oracle-theme-ready]){${EIGHT_TOKENS}}`],
    ["& nesting", `&.oracle-root{${EIGHT_TOKENS}}`],
    ["@layer", `@layer test{.oracle-root{${EIGHT_TOKENS}}}`],
    [
      "@container",
      `@container (min-width: 200px){.oracle-root{${EIGHT_TOKENS}}}`,
    ],
    [
      "child combinator >",
      `.oracle-root>.oracle-root[data-oracle-theme="light"]{${EIGHT_TOKENS}}`,
    ],
    [
      "sibling combinator +",
      `.oracle-root+.oracle-root[data-oracle-theme="light"]{${EIGHT_TOKENS}}`,
    ],
  ];

  it.each(cases)(
    "GUILT: %s on a state-bearing override THROWS naming it — never zero blocks, never a keyed context",
    (_name, css) => {
      expect(() => parseEffectiveBlocks(css)).toThrow(
        /unmodelled selector construct/,
      );
    },
  );

  it("the shipped file parses with ZERO throws and the expected five-identity list", () => {
    expect(() => parseEffectiveBlocks(CSS)).not.toThrow();
    expect(parseEffectiveBlocks(CSS).map((b) => b.identity)).toEqual(
      EXPECTED_IDENTITIES,
    );
  });
});

// ─── U5 (OBS-C1c-3): a subset override whose base is itself a subset
// override composes the chain, or throws naming the whole chain — never a
// bare "missing token" that hides where the search actually stopped. ──────

describe("Visa Oracle outcome-state colour fence — U5 chain composition", () => {
  it("composes a THREE-level chain: LEAF's untouched tokens come from MID, MID's untouched tokens come from BASE", () => {
    const css = [
      '.oracle-root[data-oracle-theme="light"] {', // BASE — declares all eight
      "  --oracle-state-eligible: #111111;",
      "  --oracle-state-likely: #222222;",
      "  --oracle-state-conditional: #333333;",
      "  --oracle-state-likely-not: #444444;",
      "  --oracle-state-eligible-bg: rgba(1, 1, 1, 0.1);",
      "  --oracle-state-likely-bg: rgba(2, 2, 2, 0.1);",
      "  --oracle-state-conditional-bg: rgba(3, 3, 3, 0.1);",
      "  --oracle-state-likely-not-bg: rgba(4, 4, 4, 0.1);",
      "}",
      '.oracle-root[data-oracle-theme="light"] {', // MID — overrides only "likely"
      "  --oracle-state-likely: #555555;",
      "}",
      '.oracle-root[data-oracle-theme="light"] {', // LEAF — overrides only "conditional"
      "  --oracle-state-conditional: #666666;",
      "}",
    ].join("\n");
    const blocks = parseEffectiveBlocks(css);
    expect(blocks).toHaveLength(3);
    const leaf = blocks[2];
    expect(leaf.fg).toEqual({
      eligible: "rgba(17, 17, 17, 1)", // from BASE (MID never touched it)
      likely: "rgba(85, 85, 85, 1)", // from MID's OWN override, not BASE's
      conditional: "rgba(102, 102, 102, 1)", // LEAF's own
      "likely-not": "rgba(68, 68, 68, 1)", // from BASE
    });
  });

  it("GUILT: a context whose ONLY candidate base is itself unresolvable throws on that root cause directly, naming it — never composing past a base that cannot resolve itself", () => {
    // MID is the FIRST rule (no candidate can precede it) and itself only
    // covers one of the eight tokens: every reachable context downstream of
    // it (LEAF) shares its exact fate, but `parseEffectiveBlocks` evaluates
    // every state-bearing context independently, in document order — MID's
    // OWN failure is necessarily the first one surfaced (a length-1 chain,
    // reported at the TRUE root of the problem), before LEAF's is ever
    // reached. This is the correct, sharper failure mode the chain-walk
    // produces: not a symptom two levels downstream, but the cause itself.
    const css = [
      '.oracle-root[data-oracle-theme="light"] {', // MID — no base of its own
      "  --oracle-state-eligible: #111111;",
      "}",
      '.oracle-root[data-oracle-theme="light"] {', // LEAF — would inherit from MID
      "  --oracle-state-likely: #222222;",
      "}",
    ].join("\n");
    expect(() => parseEffectiveBlocks(css)).toThrow(
      '.oracle-root[data-oracle-theme="light"]: missing --oracle-state-likely (not declared here or in a provable inherited base)',
    );
  });
});

// ─── U6 (OBS-C1c-4): a leading statement at-rule doesn't swallow the rule
// that follows it — it used to return ZERO blocks, silently, contradicting
// the module's own "fails loud rather than silently mis-parsing". ─────────

describe("Visa Oracle outcome-state colour fence — U6 statement at-rules are consumed as no-ops", () => {
  const EIGHT_TOKENS_BLOCK = [
    "--oracle-state-eligible: #111111;",
    "--oracle-state-likely: #222222;",
    "--oracle-state-conditional: #333333;",
    "--oracle-state-likely-not: #444444;",
    "--oracle-state-eligible-bg: rgba(1, 1, 1, 0.1);",
    "--oracle-state-likely-bg: rgba(2, 2, 2, 0.1);",
    "--oracle-state-conditional-bg: rgba(3, 3, 3, 0.1);",
    "--oracle-state-likely-not-bg: rgba(4, 4, 4, 0.1);",
  ].join("\n");

  it('@import "reset.css"; before a state-bearing rule still finds it', () => {
    const css = `@import "reset.css";\n.oracle-root {\n${EIGHT_TOKENS_BLOCK}\n}`;
    const blocks = parseEffectiveBlocks(css);
    expect(blocks).toHaveLength(1);
    expect(blocks[0].identity).toBe(".oracle-root");
  });

  it('@charset "utf-8"; is consumed the same way', () => {
    const css = `@charset "utf-8";\n.oracle-root {\n${EIGHT_TOKENS_BLOCK}\n}`;
    const blocks = parseEffectiveBlocks(css);
    expect(blocks).toHaveLength(1);
  });
});

// ─── U7 (OBS-C1c-5): "at line N" names where the construct STARTS, not
// where the scanner last resumed — blank lines and stripped comments
// between rules used to shift the reported line away from the real one. ──

describe('Visa Oracle outcome-state colour fence — U7 "at line N" points at the construct itself', () => {
  it("a nested rule several blank lines after the previous rule is reported at ITS OWN line", () => {
    const css = [
      ".a { color: red; }", // line 1
      "", // line 2
      "", // line 3
      "", // line 4
      ".b {", // line 5
      "  &:hover { color: blue; }", // line 6 — the nested rule
      "}", // line 7
    ].join("\n");
    expect(() => parseEffectiveBlocks(css)).toThrow("at line 6");
  });

  it("a nested at-rule after blank lines AND a stripped comment is reported at ITS OWN line", () => {
    const css = [
      "@media (min-width: 1px) {", // line 1
      "  .a { color: red; }", // line 2
      "", // line 3
      "", // line 4
      "  /* comment */", // line 5 — stripped to blank before line-counting
      "  @supports (display: grid) { .b { color: blue; } }", // line 6
      "}", // line 7
    ].join("\n");
    expect(() => parseEffectiveBlocks(css)).toThrow("at line 6");
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
    const lightBlock = BLOCKS.find((b) => b.identity === LIGHT_ATTR_IDENTITY)!;
    expect(lightBlock.fgRaw).toEqual(LIGHT_BASELINE);
    // Both light branches (U2) declare the SAME values — the bare
    // `.oracle-root` alternative is not a second, different theme.
    const bareBlock = BLOCKS.find((b) => b.identity === LIGHT_BARE_IDENTITY)!;
    expect(bareBlock.fgRaw).toEqual(LIGHT_BASELINE);
  });

  // TODO(C3): add a contrast-ratio assertion once a WCAG contrast helper
  // exists in apps/mouth (none does today — `grep -rn 'contrastRatio\|wcag'
  // apps/mouth/src --include='*.ts'` matches only this comment). Out of
  // scope for this one-PR-one-concern slice; see PLAN.md §4 Slice C3.
});
