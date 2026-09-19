/**
 * Anti-regression fence (PLAN.md §4 "Slice C1", G3-a): the R19 atlas map
 * (research/design/2026-09-11-r19-design-reuse-map-apps-mouth.md:148-153)
 * collapses the four outcome states onto two colours (`eligible`==`likely`,
 * `conditional`==`likely-not`, all four backgrounds to one wash). This test
 * reads the SHIPPED `oracle.css` from disk (no CSS-in-JS import) and fails
 * if any two of the four `--oracle-state-*` foreground tokens, or any two
 * of the four `-bg` tokens, become equal in any one of the file's four
 * theme blocks. `oracle.css` itself is untouched by this PR.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const CSS_PATH = join(__dirname, "oracle.css");

const STATE_NAMES = [
  "eligible",
  "likely",
  "conditional",
  "likely-not",
] as const;
type StateName = (typeof STATE_NAMES)[number];
type StateValues = Record<StateName, string>;

interface StateBlock {
  /** 1-based line in oracle.css where this block's `--oracle-state-eligible` sits. */
  line: number;
  fg: StateValues;
  bg: StateValues;
}

function extractToken(block: string, tokenName: string): string {
  const re = new RegExp(`--oracle-state-${tokenName}:\\s*([^;]+);`);
  const match = block.match(re);
  if (!match) {
    throw new Error(
      `--oracle-state-${tokenName} not found in block:\n${block}`,
    );
  }
  return match[1].trim();
}

/**
 * Splits `css` into one chunk per declaration of `--oracle-state-eligible`
 * (the anchor token every block declares first). A fifth chunk boundary
 * means a fifth theme block appeared — callers assert the count, which is
 * the point: an unreviewed fifth block should fail this test, not pass it
 * silently.
 */
function parseStateBlocks(css: string): StateBlock[] {
  const anchorRe = /--oracle-state-eligible:/g;
  const starts: number[] = [];
  let match: RegExpExecArray | null;
  while ((match = anchorRe.exec(css)) !== null) {
    starts.push(match.index);
  }
  return starts.map((start, i) => {
    const end = i + 1 < starts.length ? starts[i + 1] : css.length;
    const block = css.slice(start, end);
    const line = css.slice(0, start).split("\n").length;
    return {
      line,
      fg: {
        eligible: extractToken(block, "eligible"),
        likely: extractToken(block, "likely"),
        conditional: extractToken(block, "conditional"),
        "likely-not": extractToken(block, "likely-not"),
      },
      bg: {
        eligible: extractToken(block, "eligible-bg"),
        likely: extractToken(block, "likely-bg"),
        conditional: extractToken(block, "conditional-bg"),
        "likely-not": extractToken(block, "likely-not-bg"),
      },
    };
  });
}

/** Throws naming both tokens the moment two of them resolve to the same value. */
function assertDistinct(values: StateValues, label: string): void {
  const seenBy = new Map<string, StateName>();
  for (const name of STATE_NAMES) {
    const value = values[name];
    const priorName = seenBy.get(value);
    if (priorName) {
      throw new Error(
        `${label}: --oracle-state-${priorName} and --oracle-state-${name} both resolve to ${value}`,
      );
    }
    seenBy.set(value, name);
  }
}

describe("Visa Oracle outcome-state colour fence (mechanism, synthetic CSS)", () => {
  it("GUILT: two foreground states collapsing to the same value is caught, naming both tokens", () => {
    const collapsed = [
      "--oracle-state-eligible: #16683f;",
      "--oracle-state-likely: #16683f;",
      "--oracle-state-conditional: #7a5209;",
      "--oracle-state-likely-not: #a83a44;",
      "--oracle-state-eligible-bg: rgba(0, 0, 0, 0.1);",
      "--oracle-state-likely-bg: rgba(1, 1, 1, 0.1);",
      "--oracle-state-conditional-bg: rgba(2, 2, 2, 0.1);",
      "--oracle-state-likely-not-bg: rgba(3, 3, 3, 0.1);",
    ].join("\n");
    const [block] = parseStateBlocks(collapsed);
    expect(() => assertDistinct(block.fg, "synthetic")).toThrow(
      "synthetic: --oracle-state-eligible and --oracle-state-likely both resolve to #16683f",
    );
  });

  it("GUILT: two background states collapsing to the same wash is caught, naming both tokens", () => {
    const collapsed = [
      "--oracle-state-eligible: #16683f;",
      "--oracle-state-likely: #2a6f97;",
      "--oracle-state-conditional: #7a5209;",
      "--oracle-state-likely-not: #a83a44;",
      "--oracle-state-eligible-bg: rgba(9, 9, 9, 0.1);",
      "--oracle-state-likely-bg: rgba(1, 1, 1, 0.1);",
      "--oracle-state-conditional-bg: rgba(1, 1, 1, 0.1);",
      "--oracle-state-likely-not-bg: rgba(3, 3, 3, 0.1);",
    ].join("\n");
    const [block] = parseStateBlocks(collapsed);
    expect(() => assertDistinct(block.bg, "synthetic")).toThrow(
      "synthetic: --oracle-state-likely and --oracle-state-conditional both resolve to rgba(1, 1, 1, 0.1)",
    );
  });

  it("INNOCENCE: four pairwise-distinct values in both layers pass untouched", () => {
    const healthy = [
      "--oracle-state-eligible: #16683f;",
      "--oracle-state-likely: #2a6f97;",
      "--oracle-state-conditional: #7a5209;",
      "--oracle-state-likely-not: #a83a44;",
      "--oracle-state-eligible-bg: rgba(28, 122, 77, 0.1);",
      "--oracle-state-likely-bg: rgba(42, 111, 151, 0.1);",
      "--oracle-state-conditional-bg: rgba(154, 106, 12, 0.12);",
      "--oracle-state-likely-not-bg: rgba(168, 58, 68, 0.1);",
    ].join("\n");
    const [block] = parseStateBlocks(healthy);
    expect(() => assertDistinct(block.fg, "synthetic")).not.toThrow();
    expect(() => assertDistinct(block.bg, "synthetic")).not.toThrow();
  });
});

describe("Visa Oracle outcome-state colour fence (shipped oracle.css)", () => {
  const CSS = readFileSync(CSS_PATH, "utf8");
  const BLOCKS = parseStateBlocks(CSS);

  it("declares --oracle-state-eligible in exactly four theme blocks", () => {
    // A fifth block (or a dropped one) must fail here first, before the
    // per-block assertions below even run against the wrong shape.
    expect(BLOCKS.map((b) => b.line)).toEqual([65, 101, 130, 160]);
  });

  for (const block of BLOCKS) {
    describe(`theme block at oracle.css:${block.line}`, () => {
      it("keeps the four foreground state colours pairwise distinct", () => {
        assertDistinct(block.fg, `oracle.css:${block.line} foreground`);
      });

      it("keeps the four background state colours pairwise distinct", () => {
        assertDistinct(block.bg, `oracle.css:${block.line} background`);
      });
    });
  }

  // Pinned today's light-mode (default `.oracle-root`) values verbatim.
  // Changing these is allowed — a repaint is a legitimate design act — but
  // it must be a deliberate edit to THIS constant in the same PR as the
  // oracle.css change. Collapsing two of them to the same value is never
  // allowed; that is what the pairwise-distinct assertions above catch.
  const LIGHT_BASELINE: StateValues = {
    eligible: "#16683f",
    likely: "#2a6f97",
    conditional: "#7a5209",
    "likely-not": "#a83a44",
  };

  it("pins the shipped light-mode (default) foreground values", () => {
    expect(BLOCKS[0].fg).toEqual(LIGHT_BASELINE);
  });

  // TODO(C3): add a contrast-ratio assertion once a WCAG contrast helper
  // exists in apps/mouth (none does today — `grep -rn 'contrastRatio\|wcag'
  // apps/mouth/src --include='*.ts'` is empty). Out of scope for this
  // one-PR-one-concern slice; see PLAN.md §4 Slice C3.
});
