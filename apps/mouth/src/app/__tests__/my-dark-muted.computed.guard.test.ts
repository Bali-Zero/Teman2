import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { describe, it, expect } from "vitest";

/**
 * my (client portal) dark theme — muted text clears WCAG 2.2 SC 1.4.3.
 *
 * WHAT THIS GUARD PROVES. In `[data-theme="operative-dark"][data-product="my"]`
 * the muted aliases the portal reads (`--tx-tertiary`, `--bz-text-3`) reach
 * 4.5:1 against both grounds that block declares (`--bz-base`, `--bz-card`),
 * computed with real relative luminance after compositing the alpha over each
 * ground. Values come from `globals.css` itself, so the ground is never a
 * frozen literal here.
 *
 * WHY IT EXISTS. The kita dark block lifted muted from 0.45 to 0.62 alpha;
 * the my dark block kept 0.45, which composites to 4.23:1 on the base and
 * 4.18:1 on the card. The portal header ships a theme toggle, so a client can
 * land on that block.
 *
 * WHAT IT DOES NOT PROVE:
 *   - It does not render. A component painting its own colour over these
 *     tokens is invisible here.
 *   - It does not cover the light block, which does not redeclare these
 *     aliases (see the comment above that block in globals.css).
 */

const MY_DARK = '[data-theme="operative-dark"][data-product="my"]';
const AA_NORMAL_TEXT = 4.5;

function repoFile(...parts: string[]): string {
  let dir = __dirname;
  for (let i = 0; i < 12; i++) {
    try {
      readFileSync(join(dir, "package.json"), "utf-8");
      readFileSync(join(dir, "packages", "core", "tokens", "operative.css"));
      return join(dir, ...parts);
    } catch {
      /* not the root — keep walking */
    }
    dir = dirname(dir);
  }
  throw new Error("repo root not found from " + __dirname);
}

const css = readFileSync(
  repoFile("apps", "mouth", "src", "app", "globals.css"),
  "utf-8",
);

function extractBlock(source: string, selector: string): string {
  const anchored = new RegExp(
    `${selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\s*\\{`,
  );
  const hit = anchored.exec(source);
  if (!hit) throw new Error(`selector not found in globals.css: ${selector}`);
  const start = source.indexOf("{", hit.index);
  let depth = 0;
  for (let i = start; i < source.length; i++) {
    if (source[i] === "{") depth++;
    else if (source[i] === "}" && --depth === 0)
      return source.slice(start + 1, i);
  }
  throw new Error(`unbalanced braces after ${selector}`);
}

function parseTokens(block: string): Record<string, string> {
  const out: Record<string, string> = {};
  const re = /(--[a-z0-9-]+)\s*:\s*([^;]+);/gi;
  let m: RegExpExecArray | null;
  while ((m = re.exec(block))) out[m[1]] = m[2].trim();
  return out;
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

function ratioAgainst(fgValue: string, groundValue: string): number {
  const fg = parseColor(fgValue);
  const ground = parseColor(groundValue);
  const painted = [0, 1, 2].map((i) =>
    Math.round(fg.rgb[i] * fg.alpha + ground.rgb[i] * (1 - fg.alpha)),
  ) as RGB;
  return contrastRatio(painted, ground.rgb);
}

const dark = parseTokens(extractBlock(css, MY_DARK));

describe("probe positive controls", () => {
  it("contrast formula returns the spec's fixed values", () => {
    expect(contrastRatio([0, 0, 0], [255, 255, 255])).toBeCloseTo(21, 2);
    expect(contrastRatio([255, 255, 255], [255, 255, 255])).toBeCloseTo(1, 2);
  });

  it("extracted the my dark block, with both grounds and both aliases", () => {
    for (const t of ["--bz-base", "--bz-card", "--tx-tertiary", "--bz-text-3"])
      expect(dark[t], `${t} missing from the my dark block`).toBeDefined();
  });

  it("the secondary step in the same block passes (the probe can say yes)", () => {
    expect(
      ratioAgainst(dark["--tx-secondary"], dark["--bz-card"]),
    ).toBeGreaterThanOrEqual(AA_NORMAL_TEXT);
  });
});

describe("my dark — muted text clears AA on both grounds", () => {
  for (const token of ["--tx-tertiary", "--bz-text-3"]) {
    for (const ground of ["--bz-base", "--bz-card"]) {
      it(`${token} on ${ground}`, () => {
        expect(ratioAgainst(dark[token], dark[ground])).toBeGreaterThanOrEqual(
          AA_NORMAL_TEXT,
        );
      });
    }
  }

  it("GUILT: the pre-fix 0.45 alpha fails the same check", () => {
    const regressed = "rgba(247, 244, 238, 0.45)";
    expect(ratioAgainst(regressed, dark["--bz-card"])).toBeLessThan(
      AA_NORMAL_TEXT,
    );
  });
});
