import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { describe, it, expect } from "vitest";

/**
 * kita dashboard — the "Aturan" trigger's border clears WCAG 2.2 SC 1.4.11.
 *
 * WHAT THIS GUARD PROVES. The rest-state border of the RulesDrawer trigger in
 * `PortalChallengeWidget.tsx`, composited over the hero band it sits on
 * (`--bz-text-1`), reaches 3:1 in both kita themes. It reads the class the
 * component actually ships and the token values `globals.css` actually
 * carries, so a translucent modifier (`/50`) creeping back is caught.
 *
 * WHY IT EXISTS. The border was `…copper)]/50`: half-alpha over the band
 * measured 2.35:1 light and 2.12:1 dark in the readability harness — under
 * the 3:1 floor for a control boundary. The full-opacity token reads 5.30:1
 * and 5.26:1 on the same grounds.
 *
 * WHAT IT DOES NOT PROVE:
 *   - It does not render. A parent that paints a different ground behind the
 *     button is invisible here; `e2e/a11y/workspace-a11y.spec.ts` covers that.
 *   - It checks the hover tint only for TEXT contrast (4.5:1), because the
 *     tint replaces the old hover affordance. Focus styling is `FOCUS` and is
 *     out of scope.
 *   - It says nothing about the label size; portal-challenge-min-11px owns that.
 */

const LIGHT = '[data-theme="operative-light"][data-product="kita"]';
const DARK = '[data-theme="operative-dark"][data-product="kita"]';

/** WCAG 2.2 SC 1.4.11, non-text contrast of a UI component boundary. */
const NON_TEXT = 3;
/** WCAG 2.2 SC 1.4.3, normal text. */
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

const globalsCss = readFileSync(
  repoFile("apps", "mouth", "src", "app", "globals.css"),
  "utf-8",
);
const operativeCss = readFileSync(
  repoFile("packages", "core", "tokens", "operative.css"),
  "utf-8",
);
const widgetSrc = readFileSync(
  join(__dirname, "PortalChallengeWidget.tsx"),
  "utf-8",
);

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

function hexToRgb(value: string): RGB {
  const hex = /^#([0-9a-f]{6})$/i.exec(value.trim());
  if (!hex) throw new Error(`not a 6-digit hex: ${value}`);
  const h = hex[1];
  return [
    parseInt(h.slice(0, 2), 16),
    parseInt(h.slice(2, 4), 16),
    parseInt(h.slice(4, 6), 16),
  ];
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

const base = parseTokens(operativeCss);

/** Follow var() references through the kita block, then the base tokens. */
function resolve(block: Record<string, string>, token: string): string {
  let value = block[token] ?? base[token];
  for (let hop = 0; hop < 5 && value; hop++) {
    const ref = /^var\(\s*(--[a-z0-9-]+)\s*\)$/i.exec(value)?.[1];
    if (!ref) return value;
    value = block[ref] ?? base[ref];
  }
  if (!value) throw new Error(`cannot resolve ${token}`);
  return value;
}

/** The trigger's className, sliced from RulesDrawer up to its "Aturan" label. */
function triggerClass(): string {
  const start = widgetSrc.indexOf("function RulesDrawer");
  if (start < 0) throw new Error("RulesDrawer not found");
  const end = widgetSrc.indexOf("Aturan\n", start);
  if (end < 0) throw new Error("Aturan label not found in RulesDrawer");
  return widgetSrc.slice(start, end);
}

const cls = triggerClass();
// Rest-state border: not preceded by a variant like `hover:`.
const border = /(?<![:\w-])border-\[var\((--[a-z0-9-]+)\)\](?:\/(\d+))?/.exec(
  cls,
);
const hoverBg = /hover:bg-\[var\((--[a-z0-9-]+)\)\](?:\/(\d+))?/.exec(cls);

describe("probe positive controls", () => {
  it("contrast formula returns the spec's fixed values", () => {
    expect(contrastRatio([0, 0, 0], [255, 255, 255])).toBeCloseTo(21, 2);
    expect(contrastRatio([255, 255, 255], [255, 255, 255])).toBeCloseTo(1, 2);
  });

  it("found the trigger's rest-state border and hover tint", () => {
    expect(border, "rest-state border class not found").not.toBeNull();
    expect(hoverBg, "hover tint class not found").not.toBeNull();
  });

  it("the band behind the trigger is --bz-text-1", () => {
    // The ground is asserted, not assumed: if the band moves, this fails
    // before any ratio below can pass against the wrong colour.
    expect(widgetSrc).toContain("bg-[var(--bz-text-1)]");
  });
});

for (const [name, selector] of [
  ["light", LIGHT],
  ["dark", DARK],
] as const) {
  describe(`kita ${name} — Aturan trigger`, () => {
    const block = parseTokens(extractBlock(globalsCss, selector));
    const ground = hexToRgb(resolve(block, "--bz-text-1"));

    it("rest-state border clears 3:1 over the band", () => {
      const fg = hexToRgb(resolve(block, border![1]));
      const alpha = border![2] === undefined ? 1 : Number(border![2]) / 100;
      const painted = composite(fg, alpha, ground);
      expect(contrastRatio(painted, ground)).toBeGreaterThanOrEqual(NON_TEXT);
    });

    it("GUILT: the pre-fix /50 border fails the same check", () => {
      const fg = hexToRgb(resolve(block, border![1]));
      const painted = composite(fg, 0.5, ground);
      expect(contrastRatio(painted, ground)).toBeLessThan(NON_TEXT);
    });

    it("label text stays at 4.5:1 on the hover tint", () => {
      const text = hexToRgb(resolve(block, "--bz-kita-ink-panel-copper"));
      const tintFg = hexToRgb(resolve(block, hoverBg![1]));
      const alpha = hoverBg![2] === undefined ? 1 : Number(hoverBg![2]) / 100;
      const tinted = composite(tintFg, alpha, ground);
      expect(contrastRatio(text, tinted)).toBeGreaterThanOrEqual(
        AA_NORMAL_TEXT,
      );
    });
  });
}
