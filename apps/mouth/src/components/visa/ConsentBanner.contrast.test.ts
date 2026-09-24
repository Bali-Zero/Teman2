import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * ConsentBanner border — token-level contrast guard (PENDING-ARMS L1775).
 *
 * WHAT THIS GUARD PROVES: the banner's `borderTop` reads the shared
 * `--bz-border` divider token instead of a hardcoded literal. `--bz-border`
 * is a deliberately low-contrast hairline everywhere else it is used in this
 * codebase (see `voa-contrast.computed.guard.test.tsx`'s own note: "a
 * 12%-opacity hairline — correct for a divider"), so this guard does NOT
 * demand SC 1.4.11's 3:1 non-text floor — a decorative section divider is
 * not the "user interface component" that criterion applies to. What it
 * demands is that the border stop being IDENTICAL to its own background,
 * which is what the reported defect actually was: the original literal,
 * `rgba(255,255,255,0.12)`, painted a WHITE hairline over a WHITE
 * (`--bz-elevated: #ffffff`) background on the operative-light theme —
 * alpha-compositing white onto white yields white regardless of the alpha
 * value, so the ratio was exactly 1.00:1 (the border literally could not be
 * seen), not merely low-contrast like every other `--bz-border` use.
 *
 * WHAT IT DOES NOT PROVE (same discipline as the sibling guards in this
 * repo, e.g. `kita-contrast.computed.guard.test.ts`): it does not render the
 * component or walk every theme this banner might mount under — only the
 * one the reported defect measured against.
 */

const CONSENT_BANNER_PATH = join(__dirname, "ConsentBanner.tsx");
const bannerSrc = readFileSync(CONSENT_BANNER_PATH, "utf-8");

const LIGHT = '[data-theme="operative-light"]';

/** Not SC 1.4.11's 3:1 (a decorative divider is exempt, see file header) —
 *  just "visibly not the same colour as the background it sits on". */
const MIN_VISIBLE_RATIO = 1.1;

function repoFile(...parts: string[]): string {
  let dir = __dirname;
  for (let i = 0; i < 12; i++) {
    try {
      readFileSync(join(dir, "package.json"), "utf-8");
      const marker = join(dir, "packages", "core", "tokens", "operative.css");
      readFileSync(marker, "utf-8");
      return join(dir, ...parts);
    } catch {
      /* not the root — keep walking */
    }
    dir = dirname(dir);
  }
  throw new Error("repo root not found from " + __dirname);
}

const globalsCss = readFileSync(
  repoFile("apps", "mouth", "src", "app", "globals.css"),
  "utf-8",
);

/** Brace-matched extraction — a substring search on the short selector would
 *  also match a longer one that starts with it (e.g. a product-scoped block). */
function extractBlock(css: string, selector: string): string {
  const anchored = new RegExp(
    `${selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\s*\\{`,
  );
  const hit = anchored.exec(css);
  if (!hit) throw new Error(`selector not found in globals.css: ${selector}`);
  const braceStart = css.indexOf("{", hit.index);
  let depth = 0;
  for (let i = braceStart; i < css.length; i++) {
    if (css[i] === "{") depth++;
    else if (css[i] === "}" && --depth === 0)
      return css.slice(braceStart + 1, i);
  }
  throw new Error(`unbalanced braces after ${selector}`);
}

function parseTokens(block: string): Record<string, string> {
  const tokens: Record<string, string> = {};
  const re = /(--[a-z0-9-]+)\s*:\s*([^;]+);/gi;
  let m: RegExpExecArray | null;
  while ((m = re.exec(block))) tokens[m[1]] = m[2].trim();
  return tokens;
}

type RGB = [number, number, number];

function parseColor(value: string): { rgb: RGB; alpha: number } {
  const hex = /^#([0-9a-f]{6})$/i.exec(value.trim());
  if (hex) {
    const h = hex[1];
    return {
      rgb: [
        parseInt(h.slice(0, 2), 16),
        parseInt(h.slice(2, 4), 16),
        parseInt(h.slice(4, 6), 16),
      ],
      alpha: 1,
    };
  }
  const rgba =
    /^rgba?\(\s*([\d.]+)[\s,]+([\d.]+)[\s,]+([\d.]+)(?:[\s,/]+([\d.]+))?\s*\)$/i.exec(
      value.trim(),
    );
  if (rgba) {
    return {
      rgb: [Number(rgba[1]), Number(rgba[2]), Number(rgba[3])],
      alpha: rgba[4] === undefined ? 1 : Number(rgba[4]),
    };
  }
  throw new Error(`unresolvable colour literal: ${value}`);
}

function composite(fg: RGB, alpha: number, bg: RGB): RGB {
  return [0, 1, 2].map((i) =>
    Math.round(fg[i] * alpha + bg[i] * (1 - alpha)),
  ) as RGB;
}

function relativeLuminance([r, g, b]: RGB): number {
  const lin = (c: number) => {
    const s = c / 255;
    return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
}

function contrastRatio(a: RGB, b: RGB): number {
  const [hi, lo] = [relativeLuminance(a), relativeLuminance(b)].sort(
    (x, y) => y - x,
  );
  return (hi + 0.05) / (lo + 0.05);
}

function ratioAgainst(tokenValue: string, groundValue: string): number {
  const fg = parseColor(tokenValue);
  const ground = parseColor(groundValue);
  const painted =
    fg.alpha === 1 ? fg.rgb : composite(fg.rgb, fg.alpha, ground.rgb);
  return contrastRatio(painted, ground.rgb);
}

const light = parseTokens(extractBlock(globalsCss, LIGHT));

describe("ConsentBanner border — sourced from a token, not a literal", () => {
  it("does not hardcode a border colour literal", () => {
    expect(bannerSrc).not.toMatch(/borderTop:\s*["'][^"']*rgba\(/);
    expect(bannerSrc).not.toMatch(/borderTop:\s*["'][^"']*#[0-9a-fA-F]{3,8}/);
  });

  it("reads the shared --bz-border token", () => {
    expect(bannerSrc).toMatch(/borderTop:\s*["']1px solid var\(--bz-border\)["']/);
  });
});

describe("ConsentBanner border — visible against --bz-elevated on operative-light", () => {
  it("extracted a real theme block, not an empty one", () => {
    expect(Object.keys(light).length).toBeGreaterThan(20);
  });

  it("--bz-border on --bz-elevated is not identical to its own background", () => {
    const ratio = ratioAgainst(light["--bz-border"], light["--bz-elevated"]);
    expect(ratio).toBeGreaterThanOrEqual(MIN_VISIBLE_RATIO);
  });

  it("GUILT: the original literal (white hairline on the white banner) was exactly 1.00:1", () => {
    // rgba(255,255,255,0.12) composited onto #ffffff is #ffffff regardless
    // of the alpha value — the original defect this token replaces.
    const ratio = ratioAgainst("rgba(255,255,255,0.12)", light["--bz-elevated"]);
    expect(ratio).toBeCloseTo(1, 2);
    expect(ratio).toBeLessThan(MIN_VISIBLE_RATIO);
  });
});
