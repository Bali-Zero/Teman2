import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

/**
 * The /kbli paper skin (styles/kbli-theme.css `.kbli-paper`, BRIEF-v2 §3.4):
 * every token that paints TEXT — ink, muted, accent, the PMA / risk /
 * transition semantics — is recomputed here from the file itself and must
 * clear WCAG AA 4.5:1 on both grounds the pages use (paper and raised). The
 * values are read from the stylesheet, so a later edit cannot slip a light
 * colour past this check.
 */
const css = readFileSync(
  path.resolve(__dirname, "../../styles/kbli-theme.css"),
  "utf8",
);

function block(selector: string): Record<string, string> {
  const start = css.indexOf(`${selector} {`);
  expect(start, `${selector} block present`).toBeGreaterThanOrEqual(0);
  const body = css.slice(start, css.indexOf("}", start));
  const out: Record<string, string> = {};
  for (const m of body.matchAll(/(--[\w-]+):\s*(#[0-9a-fA-F]{6})\s*;/g)) {
    out[m[1]] = m[2];
  }
  return out;
}

function luminance(hex: string): number {
  const [r, g, b] = [1, 3, 5].map((i) => {
    const c = parseInt(hex.slice(i, i + 2), 16) / 255;
    return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

const paper = block(".kbli-paper");

const TEXT_TOKENS = [
  "--kbli-text-primary",
  "--kbli-text-secondary",
  "--kbli-text-muted",
  "--kbli-accent",
  "--kbli-accent2",
  "--kbli-amber",
  "--kbli-pma-open",
  "--kbli-pma-restricted",
  "--kbli-pma-closed",
  "--kbli-risk-low",
  "--kbli-risk-medium-low",
  "--kbli-risk-medium-high",
  "--kbli-risk-high",
  "--kbli-map-unchanged",
  "--kbli-map-renamed",
  "--kbli-map-merged",
  "--kbli-map-new",
  "--foreground-muted",
] as const;

describe("kbli paper skin — text contrast on paper", () => {
  it("declares a paper and a raised ground", () => {
    expect(paper["--kbli-bg-base"]?.toLowerCase()).toBe("#f7f4ee");
    expect(paper["--kbli-bg-surface"]?.toLowerCase()).toBe("#fffcf7");
  });

  for (const token of TEXT_TOKENS) {
    it(`${token} reads ≥ 4.5:1 on paper and on raised`, () => {
      const value = paper[token];
      expect(value, `${token} declared as a hex in .kbli-paper`).toBeTruthy();
      expect(contrast(value, paper["--kbli-bg-base"])).toBeGreaterThanOrEqual(
        4.5,
      );
      expect(
        contrast(value, paper["--kbli-bg-surface"]),
      ).toBeGreaterThanOrEqual(4.5);
    });
  }

  it("PMA status colours read ≥ 4.5:1 on their own badge grounds", () => {
    for (const s of ["open", "restricted", "closed"]) {
      expect(
        contrast(paper[`--kbli-pma-${s}`], paper[`--kbli-pma-${s}-bg`]),
      ).toBeGreaterThanOrEqual(4.5);
    }
  });
});
