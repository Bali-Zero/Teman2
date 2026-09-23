import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { describe, it, expect } from "vitest";

/**
 * kita dashboard readability — token-level contrast guard.
 *
 * WHAT THIS GUARD PROVES. The kita theme blocks in `globals.css` declare
 * muted-text and hero-panel-copper values that clear WCAG 2.2 SC 1.4.3's
 * 4.5:1 floor for normal text, in BOTH themes, computed with real relative
 * luminance from the values the stylesheet actually carries.
 *
 * WHAT IT DOES NOT PROVE, stated so a green is never read as more than it is
 * (same discipline as `voa-contrast.computed.guard.test.tsx`):
 *   - It does not render anything. A component that stops reading these
 *     tokens, or paints a hard-coded colour over them, is invisible here.
 *     That is what `e2e/a11y/workspace-a11y.spec.ts` is for.
 *   - It does not walk every token. It pins the specific values the
 *     readability fix moved, plus the brand value the fix deliberately did
 *     NOT move.
 *   - It says nothing about font size. An 11px label that clears 4.5:1 is
 *     still an 11px label.
 *
 * THE TRAP THIS GUARD ENCODES, and the reason it resolves per-block rather
 * than reading the base token file: `--bz-copper` is NOT its
 * `packages/core/tokens/operative.css` value on this surface. That file
 * declares `#d4845a`; both kita blocks override it to `#a44b36`. Measuring
 * the base value answers a question nobody asked — it reads 4.91:1 against
 * the ink panel, while the value that actually ships reads 2.47:1. Any
 * future edit that reaches for the base value instead of the cascaded one
 * will produce a confidently wrong number.
 *
 * THE GROUND IS DERIVED, NEVER NAMED. The hero panel paints its band with
 * `--bz-text-1`, which is ink in light and paper in dark — the ground flips
 * between themes, which is the whole reason a single lifted copper value
 * cannot serve both. Each check below reads `--bz-text-1` out of the same
 * block it is testing, so a future theme change moves the expectation with
 * it instead of silently invalidating a frozen hex.
 */

const LIGHT = '[data-theme="operative-light"][data-product="kita"]';
const DARK = '[data-theme="operative-dark"][data-product="kita"]';

/** WCAG 2.2 SC 1.4.3, normal text. */
const AA_NORMAL_TEXT = 4.5;

function repoFile(...parts: string[]): string {
  // Walk up to the repo root rather than counting `..` segments, so moving
  // this file does not silently read the wrong stylesheet.
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

/** Brace-matched extraction. A substring search would hand back the wrong
 *  block: the short theme selectors are prefixes of these long ones. */
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

/** Alpha compositing — a translucent text colour's real contrast depends on
 *  what sits behind it, so the ground must be composited in, not ignored. */
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

/** Resolve a token to a ratio against a ground, compositing if translucent. */
function ratioAgainst(tokenValue: string, groundValue: string): number {
  const fg = parseColor(tokenValue);
  const ground = parseColor(groundValue);
  const painted =
    fg.alpha === 1 ? fg.rgb : composite(fg.rgb, fg.alpha, ground.rgb);
  return contrastRatio(painted, ground.rgb);
}

const light = parseTokens(extractBlock(globalsCss, LIGHT));
const dark = parseTokens(extractBlock(globalsCss, DARK));

describe("contrast math — positive controls", () => {
  it("computes the two ratios whose value is fixed by the spec", () => {
    // Without these, every assertion below could be passing on a formula
    // that returns a plausible-looking wrong number.
    expect(contrastRatio([0, 0, 0], [255, 255, 255])).toBeCloseTo(21, 2);
    expect(contrastRatio([255, 255, 255], [255, 255, 255])).toBeCloseTo(1, 2);
  });

  it("extracted a real block, not an empty one", () => {
    // A silently-empty parse would make every `toBeGreaterThanOrEqual`
    // below throw on undefined rather than pass — but a future refactor
    // that defaults missing tokens would turn that into a false green.
    expect(Object.keys(light).length).toBeGreaterThan(50);
    expect(Object.keys(dark).length).toBeGreaterThan(50);
  });
});

describe("kita dark — muted text clears AA on both grounds", () => {
  // `--tx-tertiary`, `--bz-text-3` and `--bz-text-muted` are the three
  // aliases the dashboard's small labels read. They move together.
  for (const token of ["--tx-tertiary", "--bz-text-3", "--bz-text-muted"]) {
    for (const groundToken of ["--bz-kita-canvas", "--bz-kita-card"]) {
      it(`${token} on ${groundToken}`, () => {
        const ratio = ratioAgainst(dark[token], dark[groundToken]);
        expect(ratio).toBeGreaterThanOrEqual(AA_NORMAL_TEXT);
      });
    }
  }

  it("GUILT: the pre-fix alpha would fail this same check", () => {
    // Proves the guard can see a regression rather than merely agreeing
    // with whatever the file currently says.
    const regressed = "rgba(247, 244, 238, 0.45)";
    const ratio = ratioAgainst(regressed, dark["--bz-kita-canvas"]);
    expect(ratio).toBeLessThan(AA_NORMAL_TEXT);
  });
});

describe("hero-panel copper clears AA in both themes", () => {
  // The alias resolves to a different step per theme because the panel's
  // ground flips. Both sides are checked against their OWN ground.
  for (const [name, block] of [
    ["light", light],
    ["dark", dark],
  ] as const) {
    it(`${name}: --bz-kita-ink-panel-copper on --bz-text-1`, () => {
      const alias = block["--bz-kita-ink-panel-copper"];
      expect(alias, "alias missing from the kita block").toBeDefined();
      const varName = /var\(\s*(--[a-z0-9-]+)/i.exec(alias)?.[1];
      expect(varName, `alias is not a var() reference: ${alias}`).toBeDefined();

      // Resolve the referenced step: either declared in this block, or
      // inherited from the base token file.
      const operativeCss = readFileSync(
        repoFile("packages", "core", "tokens", "operative.css"),
        "utf-8",
      );
      const base = parseTokens(operativeCss);
      const resolved = block[varName!] ?? base[varName!];
      expect(resolved, `cannot resolve ${varName}`).toBeDefined();

      expect(
        ratioAgainst(resolved!, block["--bz-text-1"]),
      ).toBeGreaterThanOrEqual(AA_NORMAL_TEXT);
    });

    it(`${name}: GUILT — the other theme's step would fail here`, () => {
      // The whole reason two steps exist. If a future edit collapses them
      // into one value, one of these two guilt cases stops failing.
      const other = name === "light" ? dark : light;
      const otherAlias = other["--bz-kita-ink-panel-copper"];
      const otherVar = /var\(\s*(--[a-z0-9-]+)/i.exec(otherAlias)?.[1];
      const operativeCss = readFileSync(
        repoFile("packages", "core", "tokens", "operative.css"),
        "utf-8",
      );
      const base = parseTokens(operativeCss);
      const wrongStep = other[otherVar!] ?? base[otherVar!];
      expect(ratioAgainst(wrongStep!, block["--bz-text-1"])).toBeLessThan(
        AA_NORMAL_TEXT,
      );
    });
  }
});

describe("the brand value is untouched", () => {
  it("--bz-copper still carries the kita override, not the lifted step", () => {
    // HARD RULE §6: brand identity is not movable. The fix adds a named
    // step beside it; it must never have edited this.
    expect(light["--bz-copper"]).toBe("#a44b36");
    expect(dark["--bz-copper"]).toBe("#a44b36");
  });
});
