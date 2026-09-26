import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { R19_DIRECTION_A_VARS } from "@/lib/theme/r19Vars";

/**
 * garuda-voa/voa-r19-design lane: the R19 skin must REUSE existing tokens,
 * never define new ones. This pins that at the file level, so a later PR
 * cannot quietly reintroduce a hex/rgb/hsl literal or a var() pointing at a
 * name nobody declares.
 *
 * Re-pinned 2026-09-26 (BRIEF-v2 R-1): "declared" now means globals.css OR
 * the R19 Direction A var set the layout spreads on the funnel wrapper
 * (`R19_DIRECTION_A_VARS`) — the family language is delivered there, by the
 * foundation, and nowhere else. Still no literal, still no invented name.
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
    const r19 = new Set(Object.keys(R19_DIRECTION_A_VARS));
    for (const name of refs) {
      const declared =
        new RegExp(`${name}\\s*:`).test(globalsCss) || r19.has(name);
      expect(
        declared,
        `${name} must be declared in globals.css or R19_DIRECTION_A_VARS`,
      ).toBe(true);
    }
  });

  it("is GUILTY of a name neither source declares (guilt control)", () => {
    const r19 = new Set(Object.keys(R19_DIRECTION_A_VARS));
    const name = "--voa-invented-token";
    expect(new RegExp(`${name}\\s*:`).test(globalsCss) || r19.has(name)).toBe(
      false,
    );
  });
});

describe("layout.tsx — R19 wrapper wiring", () => {
  // Re-pinned 2026-09-26 (BRIEF-v2 R-1): the faces arrive through the
  // foundation's next/font pair and the roles through its stylesheet, both
  // on the funnel's own wrapper, instead of the portal's @font-face sheet.
  it("imports the R19 roles and the scoped skin", () => {
    expect(layoutSrc).toMatch(/@\/styles\/r19-direction-a\.css/);
    expect(layoutSrc).toMatch(/\.\/voa-r19\.css/);
  });

  it("spreads the R19 var set, its class and the faces on the wrapper", () => {
    expect(layoutSrc).toMatch(/style=\{R19_DIRECTION_A_VARS\}/);
    expect(layoutSrc).toMatch(/\$\{R19_CLASS\} \$\{r19FontClassName\}/);
  });

  it("mounts the counter around every route", () => {
    expect(layoutSrc).toMatch(/<VoaCounter>\{children\}<\/VoaCounter>/);
  });

  it('marks its wrapper data-product=my for the [data-product="my"] theme blocks', () => {
    expect(layoutSrc).toMatch(/data-product="my"/);
    expect(layoutSrc).toMatch(/data-garuda-voa="r19"/);
  });
});

/**
 * Hero handoff pins. The acceptance this lane answers to names 48px. The
 * colour pin was INVERTED on 2026-09-26 with BRIEF-v2 R-1/Q4: copper is no
 * longer "ownership, never an action" — it IS the single primary action of
 * the funnel. The WhatsApp hand-off is a secondary route, so it still may not
 * wear copper (one copper action per viewport), and the wizard's own action
 * now must. Both halves read the rule blocks themselves, so a spelling
 * change (--bz-copper, --r19-copper, --bz-accent) cannot slip past.
 */
describe("voa-r19.css — hero WhatsApp handoff", () => {
  const ctaBlock = (() => {
    const start = css.indexOf(".voa-hero-wa__cta {");
    expect(start, ".voa-hero-wa__cta rule must exist").toBeGreaterThan(-1);
    return css.slice(start, css.indexOf("}", start));
  })();

  it("gives the tap target at least 48px of height", () => {
    const m = ctaBlock.match(/min-height:\s*(\d+)px/);
    expect(m, "the CTA rule must declare a min-height in px").not.toBeNull();
    expect(Number(m![1])).toBeGreaterThanOrEqual(48);
  });

  it("keeps the secondary WhatsApp route out of copper — copper is the one primary action", () => {
    for (const copper of [
      "--bz-accent",
      "--bz-copper",
      "--bz-accent-warm",
      "--r19-copper",
      "--cta-primary-bg",
    ]) {
      expect(ctaBlock, `${copper} must not reach the hero CTA`).not.toContain(
        copper,
      );
    }
  });

  it("does not reintroduce a red, in any of the names this palette retired", () => {
    for (const red of ["--accent-red", "--color-error", "--state-danger-red"]) {
      expect(css).not.toContain(red);
    }
  });
});

describe("voa-r19.css — copper IS the action (BRIEF-v2 R-1 / Q4)", () => {
  const block = (selector: string) => {
    const start = css.indexOf(`${selector} {`);
    expect(start, `${selector} rule must exist`).toBeGreaterThan(-1);
    return css.slice(start, css.indexOf("}", start));
  };

  it("the wizard's primary action is painted copper", () => {
    expect(block(".voa-wiz__next")).toMatch(
      /background:\s*var\(--r19-copper\)/,
    );
  });

  it("a not-yet action is wash + muted, never an error colour", () => {
    const notYet = block('.voa-wiz__next[data-ready="false"]');
    expect(notYet).toMatch(/var\(--r19-wash\)/);
    expect(notYet).toMatch(/var\(--r19-ink-muted\)/);
  });

  it("the shared action style is copper too", () => {
    const style = readFileSync(join(__dirname, "voa-action-style.ts"), "utf-8");
    expect(style).toMatch(/background:\s*"var\(--r19-copper\)"/);
  });
});
