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
    const mutated = `${CSS}\n@media (prefers-contrast: more){.oracle-root{--oracle-state-likely:#16683f;--oracle-state-conditional:#16683f}}\n`;
    const blocks = parseEffectiveBlocks(mutated);
    const contrastBlock = blocks.find((b) =>
      b.identity.startsWith("@media (prefers-contrast: more)"),
    );
    expect(contrastBlock).toBeDefined();
    expect(() =>
      assertDistinct(
        contrastBlock!.fg,
        `${contrastBlock!.identity} foreground`,
      ),
    ).toThrow(
      `${contrastBlock!.identity} foreground: --oracle-state-likely and --oracle-state-conditional both resolve to rgba(22, 104, 63, 1)`,
    );
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
