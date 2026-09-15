import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * garuda-voa/voa-r19-design lane: the R19 skin must REUSE existing tokens,
 * never define new ones. This pins that at the file level, so a later PR
 * cannot quietly reintroduce a hex/rgb/hsl literal or a var() pointing at a
 * name globals.css never declares.
 */

const CSS_PATH = join(__dirname, "voa-r19.css");
const GLOBALS_PATH = join(__dirname, "..", "..", "globals.css");
const LAYOUT_PATH = join(__dirname, "layout.tsx");

const css = readFileSync(CSS_PATH, "utf-8");
const globalsCss = readFileSync(GLOBALS_PATH, "utf-8");
const layoutSrc = readFileSync(LAYOUT_PATH, "utf-8");

const COLOUR_LITERAL_RE = /#[0-9a-f]{3,8}\b|rgba?\(|hsla?\(/i;

describe("voa-r19.css — token-reuse contract", () => {
  it("contains no colour literal", () => {
    expect(css).not.toMatch(COLOUR_LITERAL_RE);
  });

  it("references only var(--x) tokens already declared in globals.css", () => {
    const refs = [...css.matchAll(/var\(\s*(--[a-z0-9-]+)/gi)].map((m) => m[1]);
    expect(refs.length).toBeGreaterThan(0);
    for (const name of refs) {
      const declared = new RegExp(`${name}\\s*:`).test(globalsCss);
      expect(declared, `${name} must be declared in globals.css`).toBe(true);
    }
  });
});

describe("layout.tsx — R19 wrapper wiring", () => {
  it("imports the R19 faces and the scoped skin", () => {
    expect(layoutSrc).toMatch(/portal\/r19-fonts\.css/);
    expect(layoutSrc).toMatch(/\.\/voa-r19\.css/);
  });

  it('marks its wrapper data-product=my for the [data-product="my"] theme blocks', () => {
    expect(layoutSrc).toMatch(/data-product="my"/);
    expect(layoutSrc).toMatch(/data-garuda-voa="r19"/);
  });
});
