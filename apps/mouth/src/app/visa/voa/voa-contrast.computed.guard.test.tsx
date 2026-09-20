import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { UploadFlow } from "./upload/UploadFlow";
import { messageFor, COPY_UNREADABLE_INSTRUCTION } from "./upload/messages";
import VoaEligibilityPage from "./page";
import VoaResultPage from "./[hash]/page";
import { CheckoutFlow } from "./checkout/[resultId]/CheckoutFlow";
import { EXCEPTION_RULE, OrderTracker } from "./orders/OrderTracker";

/**
 * GARUDA VOA DELIBERA (d) / design-A-claude.md §8 guard 2: an error message
 * must clear 4.5:1 against its own background, and it must never be carried
 * by a red-family Tailwind utility. This is the guard for the seven sites
 * lane S3 cured (M1: `text-red-600` at `upload/UploadFlow.tsx:182,215,223`,
 * 4.40:1 on paper — an AA fail; and the four `role="alert"` sites that read
 * `--color-error`, which resolves to copper on this surface — ownership, not
 * an error status).
 *
 * SCOPE, stated so this guard's green is never read as more than it proves
 * (cicatrix family #3 — a guard must declare what it does not see, same
 * discipline as `desk-no-red.guard.test.ts`). This file checks the ERROR-TONE
 * elements this PR touched — one per screen it changed (upload's three
 * states, the wizard's submit failure, the verdict page's magic-link
 * failure, checkout's order failure, the tracker's load failure). It does
 * NOT walk every text node on all six purchase screens; that fuller sweep is
 * a different, larger guard (design-A-claude.md §8 guard 2's full text) that
 * a later lane can build on top of this one's resolver.
 *
 * JSDOM LIMIT, read before trusting a green here. jsdom "applies no
 * stylesheet (no layout engine)" — the exact words `clients-desk.test.tsx`
 * uses for the same limit — so `getComputedStyle()` never resolves a
 * Tailwind utility class (arbitrary-value or not) to a real colour, and
 * never resolves a CSS custom property reference (`var(--x)`) to its
 * cascaded value even when an ancestor declares it. Two consequences follow,
 * both handled below rather than papered over:
 *
 *   1. Contrast math needs a real value, so `resolveColor` below resolves
 *      `var(--x[, fallback])` by hand, against a token table PARSED FROM
 *      `globals.css` itself (never hand-copied), for the two blocks the
 *      wrapper in `layout.tsx` actually matches — the theme block, with the
 *      `[data-product="my"]` block cascaded over it. Neither is named here;
 *      both are derived from that wrapper (`mountedSelector` /
 *      `mountedTheme` below), because this surface has now changed ground
 *      twice and a named constant lost both times. This is real WCAG
 *      relative-luminance math (`contrastRatio`), not a string comparison —
 *      pinned against design-A-claude.md's own M1 number below as a
 *      cross-check that the formula is right.
 *   2. A Tailwind class produces NO computed colour in jsdom at all (guilty
 *      or innocent), so `getComputedStyle` alone cannot see a regression
 *      back to `text-red-600` — it would just report the initial value.
 *      Each check below therefore ALSO reads the rendered element's actual
 *      `className` (the DOM the component produced, not the `.tsx` source
 *      text) and bans the red-family utility shape. Reverting the inline
 *      `style={{ color: "var(--tx-pure)" }}` fix back to
 *      `className="text-red-600"` trips THIS half of the guard, which is
 *      the one jsdom can actually see.
 */

const GLOBALS_CSS_PATH = join(__dirname, "..", "..", "globals.css");
const globalsCss = readFileSync(GLOBALS_CSS_PATH, "utf-8");

/**
 * Brace-matched extraction — the block contains a nested `body { ... }` rule.
 *
 * The match is anchored on `selector {`, not on the selector as a bare
 * substring, because the short selectors this file now also asks for are
 * PREFIXES of the long ones. `[data-theme="operative-dark"]` occurs inside
 * `[data-theme="operative-dark"][data-product="kita"]`, so a plain indexOf
 * would hand back the workspace's block while reporting the theme's — a
 * wrong answer, which is worse than the "not found" the caller can see.
 */
function findBlock(css: string, selector: string): string | null {
  const anchored = new RegExp(
    `${selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\s*\\{`,
  );
  const hit = anchored.exec(css);
  if (!hit) return null;
  return extractFrom(css, hit.index);
}

function extractBlock(css: string, selector: string): string {
  const block = findBlock(css, selector);
  if (block === null) {
    throw new Error(`selector not found in globals.css: ${selector}`);
  }
  return block;
}

function extractFrom(css: string, selectorStart: number): string {
  const braceStart = css.indexOf("{", selectorStart);
  let depth = 0;
  let i = braceStart;
  for (; i < css.length; i++) {
    if (css[i] === "{") depth++;
    else if (css[i] === "}") {
      depth--;
      if (depth === 0) break;
    }
  }
  return css.slice(braceStart + 1, i);
}

function parseTokens(block: string): Record<string, string> {
  const tokens: Record<string, string> = {};
  const re = /(--[a-z0-9-]+)\s*:\s*([^;]+);/gi;
  let m: RegExpExecArray | null;
  while ((m = re.exec(block))) {
    tokens[m[1]] = m[2].trim();
  }
  return tokens;
}

/**
 * The theme block to resolve against is DERIVED from the layout that mounts
 * this surface, never named here.
 *
 * It used to be named here, and the comment that named it said "the surface's
 * actual wrapper today (layout.tsx:54) — not the operative-dark block S1 may
 * flip to later; this guard measures what is LIVE". S1 flipped it.
 * `layout.tsx` has declared `data-theme="operative-dark"` since the DELIBERA
 * fase 2 (a) change, and this file kept resolving every colour against
 * `operative-light` — so a required check computed real WCAG arithmetic on a
 * palette the funnel does not ship, and its green said nothing about the
 * surface. Cicatrix family #2: the check existed, it was armed, and it was
 * measuring a corpse.
 *
 * A constant cannot be kept in sync by intention; it can only be kept in sync
 * by being read from the thing it must match. `mountedSelector` parses the
 * wrapper's own attributes out of `layout.tsx`, so the next flip carries the
 * guard with it and a theme `globals.css` does not declare throws instead of
 * silently resolving to nothing.
 */
const LAYOUT_PATH = join(__dirname, "layout.tsx");
const layoutSrc = readFileSync(LAYOUT_PATH, "utf-8");

/**
 * Comments are stripped first, and the match is anchored on the ELEMENT's own
 * attribute pair rather than on the two attribute names appearing anywhere.
 *
 * Both halves are load-bearing and the first was found by running the guilt
 * mutation rather than by reading: `layout.tsx`'s docblock explains the
 * DELIBERA fase 2 (a) flip and contains the literal string
 * `[data-theme="operative-dark"]` sixteen lines ABOVE the wrapper. A bare
 * `/data-theme="(...)"/ ` therefore read the PROSE, returned the right answer
 * by coincidence, and kept returning it when the wrapper was flipped
 * underneath it — a derivation that cannot fail is not a derivation, it is
 * the hardcoded constant this change exists to remove, wearing a function.
 */
function mountedSelector(src: string): string {
  const code = src
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/^[ \t]*\/\/.*$/gm, "");
  const el =
    /<[a-z][a-z0-9]*\s[^>]*?data-theme="([a-z0-9-]+)"[^>]*?data-product="([a-z0-9-]+)"/i.exec(
      code,
    );
  if (!el) {
    throw new Error(
      "layout.tsx declares no data-theme/data-product element — this guard " +
        "cannot know what ground to measure against",
    );
  }
  return `[data-theme="${el[1]}"][data-product="${el[2]}"]`;
}

const SURFACE_SELECTOR = mountedSelector(layoutSrc);

/**
 * The THEME half alone, because the wrapper matches two blocks, not one.
 *
 * `<div data-theme="X" data-product="my" ...>` is matched by BOTH
 * `[data-theme="X"]` (0-1-0) and `[data-theme="X"][data-product="my"]`
 * (0-2-0), and the browser cascades them: the product block wins every name
 * it declares, and the theme block still supplies every name it does not.
 * Resolving against the product block ALONE therefore models a page that
 * does not exist.
 *
 * That modelling error was invisible for as long as the funnel wore the ink
 * ground, because `[data-theme="operative-dark"][data-product="my"]`
 * happens to declare all twelve type/line names itself. The daylight block
 * does not, and says so out loud: `--tx-tertiary` and `--bz-text-3` are
 * "deliberately NOT redeclared: they are already `var(--tx-secondary)`
 * aliases upstream". `voa-r19.css` reads `--tx-tertiary` four times. Under
 * the single-block model the flip to daylight did not merely mis-measure
 * those four — it threw on the first one, which is the one mercy in it: an
 * incomplete ground model that throws is a bug report, an incomplete ground
 * model that resolves is family #2, a green guard measuring a corpse.
 *
 * Alias values are kept unresolved on purpose. `--tx-tertiary` is literally
 * `var(--tx-secondary)`, and CSS substitutes that at USE time against the
 * winning `--tx-secondary` on the same element — which is the product
 * block's, not the theme block's. Merging the raw declarations and letting
 * `resolveColor` walk the chain afterwards reproduces that order exactly;
 * pre-resolving each block on its own would freeze the theme block's
 * `--tx-secondary` into the alias and hand back a colour the page never
 * paints.
 */
function mountedTheme(selector: string): string {
  const m = /^\[data-theme="[a-z0-9-]+"\]/i.exec(selector);
  if (!m) throw new Error(`no theme in mounted selector: ${selector}`);
  return m[0];
}

const THEME_SELECTOR = mountedTheme(SURFACE_SELECTOR);

/**
 * The theme block is OPTIONAL, and that is a fact about this repository
 * rather than leniency.
 *
 * `globals.css` declares a plain `[data-theme="operative-light"]` block, and
 * declares NO plain `[data-theme="operative-dark"]` one — dark's 0-1-0 layer
 * lives in `packages/core/tokens/themes/operative-dark.css`, which this file
 * does not parse. Requiring the block would therefore have made the guard
 * throw on load for a ground the funnel shipped on for a month, and a guard
 * that cannot run is worth less than one that runs narrow.
 *
 * What makes narrow safe is the sweep below ("every token voa-r19.css reads
 * resolves on the mounted ground"): a name the parsed blocks do not supply
 * fails there, by name, instead of being quietly absent. That row is the
 * reason this `?? {}` is not a hole.
 */
const THEME_BLOCK = findBlock(globalsCss, THEME_SELECTOR);
const SURFACE_TOKENS: Record<string, string> = {
  ...(THEME_BLOCK === null ? {} : parseTokens(THEME_BLOCK)),
  ...parseTokens(extractBlock(globalsCss, SURFACE_SELECTOR)),
};

function resolveColor(
  raw: string,
  tokens: Record<string, string>,
  depth = 0,
): string {
  const trimmed = raw.trim();
  const varMatch = trimmed.match(/^var\(\s*(--[a-z0-9-]+)\s*(?:,\s*(.+))?\)$/i);
  if (!varMatch) return trimmed;
  if (depth > 5) {
    throw new Error(`var() resolution too deep for ${raw}`);
  }
  const [, name, fallback] = varMatch;
  const resolved = tokens[name] ?? fallback;
  if (resolved === undefined) {
    throw new Error(`token ${name} not found and no fallback in ${raw}`);
  }
  return resolveColor(resolved, tokens, depth + 1);
}

/** `[r, g, b, alpha]`. Alpha is 1 unless the source says otherwise. */
type Rgba = [number, number, number, number];

function hexToRgb(hex: string): [number, number, number] {
  let h = hex.slice(1);
  if (h.length === 3) {
    h = h
      .split("")
      .map((c) => c + c)
      .join("");
  }
  const num = parseInt(h, 16);
  return [(num >> 16) & 255, (num >> 8) & 255, num & 255];
}

/**
 * Two shapes the operative-dark block uses that the light block never did,
 * and that the previous parser would have read as a different colour rather
 * than failing:
 *
 *  - `color-mix(in srgb, #253e33 40%, #f7f4ee)` — four of this block's state
 *    tokens are declared this way. The old `toRgb` threw on them, so flipping
 *    the selector alone would have turned the guard red on parse rather than
 *    on contrast; worse, a lenient parser would have read the first hex it
 *    found and reported the UNMIXED colour, which is a darker green than the
 *    surface renders.
 *  - `rgba(247, 244, 238, 0.12)` — `--bz-border` and both muted text tokens
 *    carry alpha here. The old parser dropped the alpha channel silently and
 *    would have judged a 12%-opacity hairline as near-white paper. Alpha is
 *    composited over the ground instead, which is what the browser does and
 *    what the eye sees.
 */
function toRgba(color: string): Rgba {
  const trimmed = color.trim();

  const mix = trimmed.match(
    /^color-mix\(\s*in\s+srgb\s*,\s*(#[0-9a-f]{3,8})\s+([\d.]+)%\s*,\s*(#[0-9a-f]{3,8})\s*\)$/i,
  );
  if (mix) {
    const [ar, ag, ab] = hexToRgb(mix[1]);
    const [br, bg, bb] = hexToRgb(mix[3]);
    const w = Number(mix[2]) / 100;
    return [
      ar * w + br * (1 - w),
      ag * w + bg * (1 - w),
      ab * w + bb * (1 - w),
      1,
    ];
  }

  if (/^#([0-9a-f]{6}|[0-9a-f]{3})$/i.test(trimmed)) {
    const [r, g, b] = hexToRgb(trimmed);
    return [r, g, b, 1];
  }

  const rgb = trimmed.match(
    /rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)(?:[,\s/]+([\d.]+))?/i,
  );
  if (rgb) {
    return [
      Number(rgb[1]),
      Number(rgb[2]),
      Number(rgb[3]),
      rgb[4] === undefined ? 1 : Number(rgb[4]),
    ];
  }
  throw new Error(`cannot parse colour: ${color}`);
}

/** Source-over composite of a possibly-translucent colour onto an opaque one. */
function over(
  fg: Rgba,
  ground: [number, number, number],
): [number, number, number] {
  const a = fg[3];
  return [
    fg[0] * a + ground[0] * (1 - a),
    fg[1] * a + ground[1] * (1 - a),
    fg[2] * a + ground[2] * (1 - a),
  ];
}

function toRgb(color: string): [number, number, number] {
  const c = toRgba(color);
  return [c[0], c[1], c[2]];
}

function relativeLuminance([r, g, b]: [number, number, number]): number {
  const lin = (c: number) => {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
}

/** WCAG 2.1 contrast ratio, §1.4.3's own formula — verified below (M1 cross-check). */
function contrastRatio(fg: string, bg: string): number {
  // The background is flattened first and then serves as the ground the
  // foreground's own alpha composites onto — the order the browser paints in.
  // Without this a translucent token is judged against the colour it would
  // have if it were opaque, which is not a colour anyone sees.
  const bgRgb = over(toRgba(bg), [255, 255, 255]);
  const l1 = relativeLuminance(over(toRgba(fg), bgRgb));
  const l2 = relativeLuminance(bgRgb);
  const [lighter, darker] = l1 > l2 ? [l1, l2] : [l2, l1];
  return (lighter + 0.05) / (darker + 0.05);
}

const RED_CLASS_RE =
  /\b(?:bg|text|border|ring|divide|fill|stroke|from|to|via)-(?:red|rose|pink|orange|crimson)-\d/;

/** The two checks a jsdom-honest guard can make: real WCAG math on whatever
 * colour is actually reachable, and a DOM-output ban on the one shape jsdom
 * cannot compute (see file header, consequence 2). */
function assertErrorTone(el: Element, tokens: Record<string, string>) {
  const style = (el as HTMLElement).style;
  expect(
    style.color,
    `${el.tagName} has no inline colour to judge — the guard only judges elements it can compute`,
  ).not.toBe("");
  const fg = resolveColor(style.color, tokens);
  expect(fg, "error text must use the ink tone, not copper or red").toBe(
    tokens["--tx-pure"],
  );
  const bg = tokens["--bz-base"];
  expect(contrastRatio(fg, bg)).toBeGreaterThanOrEqual(4.5);
  expect(el.className, `${el.tagName} className`).not.toMatch(RED_CLASS_RE);
}

describe("resolver + contrast math — guilt and innocence (cicatrix #3)", () => {
  /**
   * The regression pin for the drift this file was curing. It asserts the
   * derived selector AGAINST `layout.tsx`'s own declaration rather than
   * against a second literal — a hardcoded expectation here would reintroduce
   * exactly the two-constants-drifting-apart shape that put the guard on the
   * wrong palette in the first place.
   */
  it("resolves against the theme layout.tsx actually mounts", () => {
    expect(layoutSrc).toContain(`data-theme="operative-light"`);
    expect(SURFACE_SELECTOR).toBe(
      '[data-theme="operative-light"][data-product="my"]',
    );
    expect(THEME_SELECTOR).toBe('[data-theme="operative-light"]');
  });

  it("GUILTY: the derivation reads the source, it does not return a constant", () => {
    expect(
      mountedSelector('<div data-theme="operative-light" data-product="my">'),
    ).toBe('[data-theme="operative-light"][data-product="my"]');
    expect(() => mountedSelector("<div>no wrapper here</div>")).toThrow(
      /no data-theme/,
    );
  });

  /**
   * The exact shape that made the first version of this cure pass its own
   * guilt mutation: `layout.tsx` names one theme in its docblock and mounts
   * another. The element wins, and a `toThrow` here would not be enough —
   * the wrong ANSWER is the defect, not the absence of one.
   */
  it("GUILTY: prose that names a theme never outranks the element that mounts one", () => {
    const misleading = [
      '/* re-keyed to [data-theme="operative-dark"] in the same PR */',
      '// see the [data-theme="operative-dark"] block',
      'return <div data-theme="operative-light" data-product="my">{x}</div>;',
    ].join("\n");
    expect(mountedSelector(misleading)).toBe(
      '[data-theme="operative-light"][data-product="my"]',
    );
  });

  it("GUILTY: a theme globals.css does not declare throws, it never resolves to nothing", () => {
    expect(() =>
      extractBlock(
        globalsCss,
        '[data-theme="no-such-theme"][data-product="my"]',
      ),
    ).toThrow(/selector not found/);
  });

  it("parses real hex tokens out of globals.css, not a hand-copied guess", () => {
    expect(SURFACE_TOKENS["--tx-pure"]).toBe("#1d2c3b");
    expect(SURFACE_TOKENS["--bz-base"]).toBe("#f7f4ee");
    expect(SURFACE_TOKENS["--bz-border"]).toBe("#dad8d1");
  });

  /**
   * The cascade, proved in both directions, because a merge of two blocks
   * can be wrong in exactly two ways and only one of them throws.
   *
   * `--tx-tertiary` is the name the product block does not declare: it
   * reaches the funnel only from the theme block, and `voa-r19.css` reads it
   * four times. Before the blocks were merged this threw, which is how the
   * gap was found.
   *
   * `--tx-secondary` is the name BOTH declare, and it is the merge-order
   * pin: the theme block says #475372, the product block says #58626b, and
   * the browser gives the product block the element because it is 0-2-0.
   * Merging the other way round would still resolve every name and still be
   * green everywhere else in this file — a silent wrong answer, which is the
   * failure mode worth a row of its own.
   */
  it("treats the theme block as optional, because a mounted ground has none", () => {
    expect(
      findBlock(globalsCss, '[data-theme="operative-light"]'),
    ).not.toBeNull();
    // The ground this funnel wore before 2026-09-21. globals.css has no
    // plain block for it — see THEME_BLOCK's note.
    expect(findBlock(globalsCss, '[data-theme="operative-dark"]')).toBeNull();
    // And the prefix trap that would have hidden that: the kita block starts
    // with the same twenty-eight characters.
    expect(
      findBlock(
        globalsCss,
        '[data-theme="operative-dark"][data-product="kita"]',
      ),
    ).not.toBeNull();
  });

  it("cascades the theme block UNDER the product block, not over it", () => {
    const themeOnly = parseTokens(extractBlock(globalsCss, THEME_SELECTOR));
    const productOnly = parseTokens(extractBlock(globalsCss, SURFACE_SELECTOR));

    expect(productOnly["--tx-tertiary"]).toBeUndefined();
    expect(themeOnly["--tx-tertiary"]).toBe("var(--tx-secondary)");
    expect(SURFACE_TOKENS["--tx-tertiary"]).toBe("var(--tx-secondary)");

    expect(themeOnly["--tx-secondary"]).toBe("#475372");
    expect(productOnly["--tx-secondary"]).toBe("#58626b");
    expect(SURFACE_TOKENS["--tx-secondary"]).toBe("#58626b");

    // And the alias is walked at USE time against the winner, which is the
    // whole reason the raw declarations are merged rather than pre-resolved.
    expect(resolveColor("var(--tx-tertiary)", SURFACE_TOKENS)).toBe("#58626b");
  });

  /**
   * The row that turns "a token the ground does not declare" from a crash
   * into a named failure. Every `var()` the skin reads must resolve against
   * the ground the layout mounts — the sweep is over `voa-r19.css`'s own
   * text, so a token added to the stylesheet tomorrow is covered without an
   * edit here, and a ground flip that drops a name is red on the name.
   */
  it("every token voa-r19.css reads resolves on the mounted ground", () => {
    const read = [
      ...new Set(
        [...VOA_R19_CSS.matchAll(/var\(\s*(--[a-z0-9-]+)\s*\)/gi)].map(
          (m) => m[1],
        ),
      ),
    ].filter((n) => !n.startsWith("--font-"));
    expect(read.length).toBeGreaterThan(8);
    for (const name of read) {
      expect(
        () => toRgb(resolveColor(`var(${name})`, SURFACE_TOKENS)),
        `${name} does not resolve to a colour on ${SURFACE_SELECTOR}`,
      ).not.toThrow();
    }
  });

  /**
   * The two shapes the light block never contained. Both are checked as
   * VALUES, not as "parses without throwing": a lenient parser that returned
   * the first hex of a `color-mix` or dropped an alpha channel would also not
   * throw, and would report a colour the surface does not render.
   */
  it("mixes a color-mix token instead of reading one side of it", () => {
    // 40% #253e33 + 60% #f7f4ee — the unmixed first hex would be (37, 62, 51).
    expect(toRgb("color-mix(in srgb, #253e33 40%, #f7f4ee)")).toEqual([
      0.4 * 0x25 + 0.6 * 0xf7,
      0.4 * 0x3e + 0.6 * 0xf4,
      0.4 * 0x33 + 0.6 * 0xee,
    ]);
  });

  it("composites alpha over the ground instead of dropping it", () => {
    // Paper at 12% on near-black — the ink ground's --bz-border. Dropping
    // the alpha would read it as paper itself and call a hairline a 17:1
    // surface.
    expect(contrastRatio("rgba(247, 244, 238, 0.12)", "#121016")).toBeLessThan(
      1.6,
    );
    expect(contrastRatio("#f7f4ee", "#121016")).toBeGreaterThan(15);
  });

  /**
   * Both rows above are LITERALS now, and that is deliberate — the same
   * reasoning the M1 cross-check below states for itself.
   *
   * They read `SURFACE_TOKENS` until the funnel moved to daylight, and the
   * daylight block happens to declare neither shape: its four state tokens
   * are plain hexes and its `--bz-border` is the opaque #dad8d1. Pointed at
   * the live ground, the two rows stopped proving the PARSER could do either
   * thing and started proving the current palette does not need it — while
   * the ink block still declares four `color-mix()` values and three alpha
   * ones, and this file no longer names a ground at all. A capability proof
   * that evaporates when the theme changes was never a capability proof.
   *
   * What the live ground still owes the file is the row below: whatever it
   * declares, a hairline must be judged as a hairline.
   */
  it("judges the mounted ground's own border as a hairline, not a surface", () => {
    expect(
      contrastRatio(SURFACE_TOKENS["--bz-border"], SURFACE_TOKENS["--bz-base"]),
    ).toBeLessThan(1.6);
  });

  it("INNOCENT: the cured tone (paper on ink) clears 4.5:1", () => {
    const fg = resolveColor("var(--tx-pure)", SURFACE_TOKENS);
    const bg = SURFACE_TOKENS["--bz-base"];
    expect(contrastRatio(fg, bg)).toBeGreaterThanOrEqual(4.5);
  });

  /**
   * A FORMULA cross-check, deliberately on paper literals rather than on
   * `--bz-base`: M1's 4.40:1 was measured on the paper ground this surface
   * used to have, and the point of the row is that `contrastRatio` reproduces
   * a number someone else computed independently. Pointing it at whatever the
   * current theme's ground happens to be would turn a formula proof into a
   * theme fact and lose the cross-check.
   */
  it("GUILTY: the ORIGINAL text-red-600 hex (#DC2626) on paper measures 4.40:1 — an AA fail, matching design-A-claude.md M1's own number", () => {
    const ratio = contrastRatio("#DC2626", "#f7f4ee");
    expect(ratio).toBeCloseTo(4.4, 1);
    expect(ratio).toBeLessThan(4.5);
  });

  it("GUILTY: copper (--color-error's resolved value on this surface) is a real colour but the wrong ONE — the guard demands ink specifically, not merely 'passes contrast'", () => {
    const copper = SURFACE_TOKENS["--state-danger"];
    expect(copper).toBe("#a44b36");
    // Copper-on-paper actually clears AA (it is the sanctioned "needs you"
    // tone) — proving a bare contrast check would NOT catch M2's finding
    // that role="alert" read the wrong meaning, only the identity check does.
    expect(
      contrastRatio(copper, SURFACE_TOKENS["--bz-base"]),
    ).toBeGreaterThanOrEqual(4.5);
  });

  it("GUILTY, the DOM-output shape a computed check cannot see any other way: a red Tailwind class in the rendered className", () => {
    const { container } = render(
      <p className="text-sm text-red-600">rendered, not sourced</p>,
    );
    const p = container.querySelector("p")!;
    expect(p.className).toMatch(RED_CLASS_RE);
    // And, matching consequence 2 in the file header: jsdom gives this
    // element NO inline colour at all, so a naive computed-only check would
    // stay silent on it — which is exactly why assertErrorTone also checks
    // className, not color alone.
    expect(p.style.color).toBe("");
  });

  it("INNOCENT: the kita idiom (border/text tokens, not a fill) never trips the red-class ban", () => {
    const { container } = render(
      <p className="text-sm" style={{ color: "var(--tx-pure)" }}>
        fine
      </p>,
    );
    expect(container.querySelector("p")!.className).not.toMatch(RED_CLASS_RE);
  });
});

// ---------------------------------------------------------------------------
// Safe Clock state identities. Lives here rather than in a new file because
// this is the file that already owns the token resolver, the color-mix and
// alpha compositing, and the WCAG arithmetic — a second copy of that maths is
// the drift `voa-copy.guard.test.ts` refuses for its comment stripper, for the
// same reason.
// ---------------------------------------------------------------------------

const VOA_R19_CSS = readFileSync(join(__dirname, "voa-r19.css"), "utf-8");

interface StateRule {
  colour: string;
  widthPx: number;
}

/** Reads the four `.voa-clock--X` rules out of the stylesheet, not a table. */
function stateRule(state: string): StateRule {
  const re = new RegExp(`\\.voa-clock--${state}\\s*\\{([^}]*)\\}`, "i");
  const m = re.exec(VOA_R19_CSS);
  if (!m) throw new Error(`no rule for .voa-clock--${state}`);
  const colour = /border-left-color:\s*([^;]+);/i.exec(m[1]);
  const width = /border-left-width:\s*(\d+)px;/i.exec(m[1]);
  if (!colour || !width) {
    throw new Error(`.voa-clock--${state} must declare colour AND width`);
  }
  return {
    colour: resolveColor(colour[1].trim(), SURFACE_TOKENS),
    widthPx: Number(width[1]),
  };
}

const CLOCK_STATES = ["ample", "soon", "today", "passed"] as const;

describe("Safe Clock — four states, four identities (mandate accent 4)", () => {
  const rules = Object.fromEntries(
    CLOCK_STATES.map((s) => [s, stateRule(s)]),
  ) as Record<(typeof CLOCK_STATES)[number], StateRule>;

  /**
   * The shipped `passed` rule was `--bz-border-hover` at 1.78:1 — an absence
   * presented as the fourth colour. 1.4.11's floor for a non-text indicator
   * is 3:1.
   */
  it.each(CLOCK_STATES)("%s: the rule clears the 3:1 non-text floor", (st) => {
    expect(
      contrastRatio(rules[st].colour, SURFACE_TOKENS["--bz-base"]),
    ).toBeGreaterThanOrEqual(3);
  });

  /**
   * The floor is 3:1, so 3:1 is what this row asserts. It used to assert
   * `< 2`, which was the ink ground's own number (1.78:1) standing in for
   * the rule — and on the daylight ground the same token is R19's opaque
   * line-strong at 2.09:1. Still guilty, still under the floor, and the row
   * went red anyway because it was pinned to a measurement rather than to
   * the claim.
   */
  it("GUILTY: the retired --bz-border-hover would fail that floor", () => {
    expect(
      contrastRatio(
        resolveColor("var(--bz-border-hover)", SURFACE_TOKENS),
        SURFACE_TOKENS["--bz-base"],
      ),
    ).toBeLessThan(3);
  });

  /**
   * The claim this pins is NOT "four different tokens" — the version that
   * shipped had four different tokens and two of them were 1.11:1 apart. Each
   * PAIR must be separable on a real axis: either the rule colours are far
   * enough apart to read as different, or their widths differ.
   */
  it.each(
    CLOCK_STATES.flatMap((a, i) =>
      CLOCK_STATES.slice(i + 1).map((b) => [a, b] as const),
    ),
  )("%s vs %s is separable by colour or by width", (a, b) => {
    const byColour = contrastRatio(rules[a].colour, rules[b].colour);
    const byWidth = rules[a].widthPx !== rules[b].widthPx;
    expect(
      byColour >= 1.5 || byWidth,
      `${a}/${b}: ${byColour.toFixed(2)}:1 apart and both ${rules[a].widthPx}px`,
    ).toBe(true);
  });

  /**
   * Named explicitly rather than left implicit in the loop above: these two
   * are the pair that colour cannot separate, and the design leans on width
   * and on the word for them. If someone equalises the widths "for
   * consistency", this is the row that says why they cannot.
   *
   * WHICH pair that is, is a property of the ground, and the ground moved.
   * On the ink block the answer was ample/soon (slate and a paper-mixed
   * warning, 1.42:1 apart) while soon/today were 2.4:1 apart and could
   * afford to share 7px. On the daylight block the state tokens are plain
   * hexes and the ordering inverts: ample/soon open to 1.92:1, and
   * soon/today close to 1.06:1 — the burnt warning brown and the mark red
   * land on the same luminance. They shared 7px at that moment, which is
   * two of the four Safe Clock states rendering identically to anyone who
   * does not separate those two hues, so `today` took a width of its own.
   */
  it("soon vs today is the pair colour cannot separate — width carries it", () => {
    expect(contrastRatio(rules.soon.colour, rules.today.colour)).toBeLessThan(
      1.5,
    );
    expect(rules.soon.widthPx).not.toBe(rules.today.widthPx);
  });
});

// ---------------------------------------------------------------------------
// Tracker exception tones. Same discipline as the Safe Clock table above, on
// the other surface where a customer reads a state: five situations that all
// rendered behind one `1px solid var(--color-border-subtle)` until this table
// existed.
// ---------------------------------------------------------------------------

describe("order tracker — four exception tones, four identities", () => {
  const tones = Object.entries(EXCEPTION_RULE) as [string, string][];

  it("has a tone for every branch the tracker can render", () => {
    expect(tones.map(([k]) => k).sort()).toEqual([
      "closed",
      "needs-you",
      "refused",
      "retry",
    ]);
  });

  it.each(tones)("%s: the rule clears the 3:1 non-text floor", (_k, token) => {
    expect(
      contrastRatio(
        resolveColor(token, SURFACE_TOKENS),
        SURFACE_TOKENS["--bz-base"],
      ),
    ).toBeGreaterThanOrEqual(3);
  });

  /**
   * Distinctness measured on the RESOLVED colours, not on the token spellings.
   * Four different `var()` names that resolve to one value is the trap
   * `--state-danger` / `--bz-copper-text` sets on this theme, and a name-level
   * check walks straight into it.
   */
  it.each(
    tones.flatMap(([ka, a], i) =>
      tones.slice(i + 1).map(([kb, b]) => [ka, kb, a, b] as const),
    ),
  )("%s and %s do not resolve to the same colour", (_ka, _kb, a, b) => {
    expect(resolveColor(a, SURFACE_TOKENS)).not.toBe(
      resolveColor(b, SURFACE_TOKENS),
    );
  });

  it("GUILTY: --state-danger would collide with the needs-you copper", () => {
    expect(resolveColor("var(--state-danger)", SURFACE_TOKENS)).toBe(
      resolveColor(EXCEPTION_RULE["needs-you"], SURFACE_TOKENS),
    );
  });
});

// ---------------------------------------------------------------------------
// The seven real sites, rendered through the actual production components.
// ---------------------------------------------------------------------------

const trackerMocks = vi.hoisted(() => ({
  viewed: vi.fn(),
  wizardStep: vi.fn(),
  wizardAbandoned: vi.fn(),
  formSubmitted: vi.fn(),
  formSubmitFailed: vi.fn(),
  resultViewed: vi.fn(),
  ctaClicked: vi.fn(),
  whatsappHandoff: vi.fn(),
  shareClicked: vi.fn(),
  emailSubscribed: vi.fn(),
}));

vi.mock("@balizero/core", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@balizero/core")>();
  return {
    ...actual,
    useFunnelApp: () => trackerMocks,
  };
});

function jsonResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response;
}

const fetchMock = global.fetch as unknown as ReturnType<typeof vi.fn>;

beforeEach(() => {
  fetchMock.mockReset();
  window.localStorage.clear();
  window.sessionStorage.clear();
  vi.clearAllMocks();
});

describe("upload — three error-tone states (M1's own site)", () => {
  it("client_rejected: oversized file, rejected client-side, no fetch", async () => {
    // A wrong-MIME file (e.g. a PDF) never reaches `selectFile` here:
    // `userEvent.upload` enforces the input's own `accept` attribute the way
    // a real browser's file picker does, so a mismatched type is silently
    // not selected. An oversized JPEG has the RIGHT type and clears that
    // gate, then trips `precheckFile`'s size check — the same
    // `client_rejected` branch, reached the way a real user reaches it.
    render(<UploadFlow resultId="guard-upload-1" />);
    const input = screen.getByLabelText("Upload passport photo");
    const bigFile = new File(
      [new Uint8Array(16 * 1024 * 1024)],
      "passport.jpg",
      { type: "image/jpeg" },
    );
    await userEvent.upload(input, bigFile);

    const alert = await screen.findByRole("alert");
    const p = alert.querySelector("p")!;
    assertErrorTone(p, SURFACE_TOKENS);
  });

  it("unreadable: server returns UNREADABLE_DOCUMENT", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(422, {
        code: "UNREADABLE_DOCUMENT",
        retryable: false,
        message_key: "garuda_voa.error.unreadable_document",
      }),
    );
    render(<UploadFlow resultId="guard-upload-2" />);
    const input = screen.getByLabelText("Upload passport photo");
    const goodFile = new File([new Uint8Array(10)], "passport.jpg", {
      type: "image/jpeg",
    });
    await userEvent.upload(input, goodFile);

    const p = await screen.findByText(COPY_UNREADABLE_INSTRUCTION);
    assertErrorTone(p, SURFACE_TOKENS);
  });

  it("error: a retryable 503 (document store unavailable)", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(503, {
        code: "DOCUMENT_PROCESSING_UNAVAILABLE",
        retryable: true,
        message_key: "garuda_voa.error.document_processing_unavailable",
      }),
    );
    render(<UploadFlow resultId="guard-upload-3" />);
    const input = screen.getByLabelText("Upload passport photo");
    const goodFile = new File([new Uint8Array(10)], "passport.jpg", {
      type: "image/jpeg",
    });
    await userEvent.upload(input, goodFile);

    const p = await screen.findByText(
      messageFor("DOCUMENT_PROCESSING_UNAVAILABLE"),
    );
    assertErrorTone(p, SURFACE_TOKENS);
  });
});

describe("wizard — eligibility-check submit failure (page.tsx:541)", () => {
  it("network failure renders the WhatsApp-fallback alert in ink, not copper", async () => {
    fetchMock.mockRejectedValue(new Error("network down"));
    render(<VoaEligibilityPage />);

    fireEvent.click(
      screen.getByRole("button", { name: /Get a new Visa on Arrival/ }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    fireEvent.click(screen.getByRole("button", { name: "Tourism" }));
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    fireEvent.change(screen.getByLabelText("Nationality"), {
      target: { value: "ITA" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    fireEvent.change(screen.getByLabelText("Entry date"), {
      target: { value: "2026-09-01" },
    });
    fireEvent.change(screen.getByLabelText("Passport expiry date"), {
      target: { value: "2027-09-01" },
    });
    fireEvent.click(
      screen.getByLabelText("Storage and deletion notice acknowledgement"),
    );
    fireEvent.click(screen.getByRole("button", { name: "See result" }));

    const alert = await waitFor(() => screen.getByRole("alert"));
    assertErrorTone(alert, SURFACE_TOKENS);
  });
});

describe("verdict — magic-link resend failure ([hash]/page.tsx:404)", () => {
  it("a failed resend renders the alert in ink, not copper", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        verdict: "ACCEPT",
        reason_codes: [],
        price_idr: 790000,
      }),
    });
    fetchMock.mockResolvedValueOnce({ status: 500 });
    render(<VoaResultPage params={Promise.resolve({ hash: "guard-hash" })} />);
    await waitFor(() =>
      expect(screen.getByTestId("bz-stamp")).toBeInTheDocument(),
    );

    const user = userEvent.setup();
    await user.type(
      screen.getByLabelText(/your email/i),
      "customer@example.com",
    );
    await user.click(
      screen.getByRole("button", { name: /email me the link/i }),
    );

    const alert = await screen.findByRole("alert");
    // This one alert moved from an inline `style` to `.voa-entry__error` when
    // the entry step took the stylesheet. `assertErrorTone` judges an inline
    // colour and jsdom resolves no class, so judging THIS element means
    // judging the RULE instead — and it must keep every assertion the inline
    // check made, not just the contrast one. The load-bearing one is the
    // IDENTITY: copper measures 4.98:1 on this ground and sails past a 4.5:1
    // floor, so a contrast-only replacement would have let through exactly
    // the "copper, not ink" regression this test is named after. (Caught in
    // adversarial review before this shipped; the row below is the pin.)
    expect(alert.className).toContain("voa-entry__error");
    expect(alert.className).not.toMatch(RED_CLASS_RE);
    expect(alert.getAttribute("style")).toBeNull();
    const errColour = ruleColour(".voa-entry__error");
    expect(
      errColour,
      "error text must use the ink tone, not copper or red",
    ).toBe(SURFACE_TOKENS["--tx-pure"]);
    expect(
      contrastRatio(errColour, SURFACE_TOKENS["--bz-base"]),
    ).toBeGreaterThanOrEqual(4.5);
  });

  it("GUILTY: copper clears 4.5:1 here, so contrast alone cannot police the tone", () => {
    const copper = resolveColor("var(--bz-accent)", SURFACE_TOKENS);
    expect(copper).not.toBe(SURFACE_TOKENS["--tx-pure"]);
    expect(
      contrastRatio(copper, SURFACE_TOKENS["--bz-base"]),
    ).toBeGreaterThanOrEqual(4.5);
  });
});

describe("checkout — order-creation failure (CheckoutFlow.tsx:201)", () => {
  it("a failed order submit renders the alert in ink, not copper", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(500, {}));
    const user = userEvent.setup();
    render(<CheckoutFlow resultId="guard-checkout-1" paymentsLive={true} />);

    await user.type(
      screen.getByLabelText(/full name \(as in passport\)/i),
      "Jane Doe",
    );
    await user.type(screen.getByLabelText(/^passport number$/i), "X1234567");
    await user.type(screen.getByLabelText(/email/i), "customer@example.com");
    await user.type(screen.getByLabelText(/phone/i), "+6281234567890");
    await user.click(
      screen.getByRole("button", { name: /continue to payment/i }),
    );

    const alert = await screen.findByRole("alert");
    assertErrorTone(alert, SURFACE_TOKENS);
  });
});

describe("tracker — order load failure (OrderTracker.tsx:49)", () => {
  it("a failed order fetch renders the alert in ink, not copper", async () => {
    fetchMock.mockResolvedValue(jsonResponse(500, {}));
    render(<OrderTracker orderId="guard-order-1" />);

    const alert = await screen.findByRole("alert");
    assertErrorTone(alert, SURFACE_TOKENS);
  });
});

// ---------------------------------------------------------------------------
// "What happens next" / "What we cannot promise" — every TEXT colour in the
// block clears 1.4.3's 4.5:1. Same reason the Safe Clock section lives here:
// this is the file that owns the resolver and the WCAG arithmetic, and a
// second copy of that maths is the drift it exists to prevent.
//
// This block is the one place on the surface where the honest half of the
// message — the limits — could be quietly demoted by giving it a fainter
// token than the promises. The floor is asserted per rule, so demoting ONE of
// them is a red run, not a subtler page.
// ---------------------------------------------------------------------------

/** The four rules that carry text, named literally: a rule that disappears
 *  from the stylesheet must fail here, not silently drop out of the loop
 *  (W133 — a test parametrized over the set it tests deletes itself). */
const NEXT_TEXT_RULES = [
  ".voa-next__heading",
  ".voa-next__step",
  ".voa-next__limit",
  ".voa-next__ask",
] as const;

function ruleColour(className: string): string {
  const re = new RegExp(`\\${className}\\s*\\{([^}]*)\\}`, "i");
  const m = re.exec(VOA_R19_CSS);
  if (!m) throw new Error(`no rule for ${className}`);
  const colour = /(?:^|\s)color:\s*([^;]+);/i.exec(m[1]);
  if (!colour) throw new Error(`${className} declares no color`);
  return resolveColor(colour[1].trim(), SURFACE_TOKENS);
}

describe("NextSteps — the limits are not small print (mandate accent 3)", () => {
  it.each(NEXT_TEXT_RULES)("%s clears 4.5:1 on the surface ground", (cls) => {
    const ratio = contrastRatio(ruleColour(cls), SURFACE_TOKENS["--bz-base"]);
    expect(ratio, `${cls}: ${ratio.toFixed(2)}:1`).toBeGreaterThanOrEqual(4.5);
  });

  /**
   * A legal token that reads as "an eyebrow colour" is the shape this row
   * exists to convict — the failure is invisible without the arithmetic,
   * because nothing about the NAME looks wrong.
   *
   * The convict used to be `--tx-tertiary`, the value this rule shipped in
   * its first draft at 4.23:1 on the ink ground. It is innocent on daylight:
   * the my-block declares no `--tx-tertiary`, so it arrives from the theme
   * block as an alias of `--tx-secondary` and lands on muted ink at 5.67:1.
   * Keeping it here would have been a guilt row that acquits — the most
   * expensive kind of green, since it reports that the check can convict
   * while proving the opposite.
   *
   * `--bz-border-hover` is the daylight ground's version of the same
   * mistake and is named rather than derived: it is R19's line-strong
   * #a8aca9 at 2.09:1, which globals.css's own note calls "a line colour,
   * not a text colour" — a token any author could reasonably reach for and
   * the arithmetic refuses.
   */
  it("GUILTY: a line-grade token used as heading text fails that floor", () => {
    expect(
      contrastRatio(
        resolveColor("var(--bz-border-hover)", SURFACE_TOKENS),
        SURFACE_TOKENS["--bz-base"],
      ),
    ).toBeLessThan(4.5);
  });

  it("the limits are not fainter than the steps", () => {
    expect(ruleColour(".voa-next__limit")).toBe(ruleColour(".voa-next__step"));
  });
});

// ---------------------------------------------------------------------------
// The entry step's field has a visible edge (SC 1.4.11, 3:1).
//
// 1.4.3's 4.5:1 is the floor for TEXT; the boundary of an interactive control
// is 1.4.11's, and it is 3:1 — a distinction this surface already pays for
// once (the Safe Clock section above) and pays for again here. The field
// shipped at 1.40:1: legal, tokenised, and invisible.
// ---------------------------------------------------------------------------

/** Reads the `border:` shorthand's colour out of a rule, not a table. */
function ruleBorderColour(className: string): string {
  const m = new RegExp(`\\${className}\\s*\\{([^}]*)\\}`, "i").exec(
    VOA_R19_CSS,
  );
  if (!m) throw new Error(`no rule for ${className}`);
  const c = /border:\s*[^;]*?(var\([^)]*\)|#[0-9a-f]{3,8})\s*;/i.exec(m[1]);
  if (!c) throw new Error(`${className} declares no border colour`);
  return resolveColor(c[1].trim(), SURFACE_TOKENS);
}

/** The fill the boundary is judged against is the field's OWN background,
 *  not the page ground: that is the pair the eye has to separate. */
function ruleBackground(className: string): string {
  const m = new RegExp(`\\${className}\\s*\\{([^}]*)\\}`, "i").exec(
    VOA_R19_CSS,
  );
  if (!m) throw new Error(`no rule for ${className}`);
  const c = /background:\s*([^;]+);/i.exec(m[1]);
  if (!c) throw new Error(`${className} declares no background`);
  return resolveColor(c[1].trim(), SURFACE_TOKENS);
}

describe("the entry field is visible (mandate accent 5)", () => {
  it(".voa-entry__input's boundary clears 1.4.11's 3:1 against its own fill", () => {
    const ratio = contrastRatio(
      ruleBorderColour(".voa-entry__input"),
      ruleBackground(".voa-entry__input"),
    );
    expect(ratio, `${ratio.toFixed(2)}:1`).toBeGreaterThanOrEqual(3);
  });

  /**
   * What the field shipped with. `voa-r19.css` aliases
   * `--color-border-subtle` to `--bz-border`, which is a 12%-opacity hairline
   * — correct for a divider, and 1.40:1 under a control the customer has to
   * find and type into.
   */
  it("GUILTY: --color-border-subtle, the boundary it shipped with, fails that floor", () => {
    const ratio = contrastRatio(
      resolveColor("var(--bz-border)", SURFACE_TOKENS),
      resolveColor("var(--bz-elevated)", SURFACE_TOKENS),
    );
    expect(ratio, `${ratio.toFixed(2)}:1`).toBeLessThan(3);
  });

  it(".voa-entry__input's ink clears 4.5:1 on the same fill", () => {
    expect(
      contrastRatio(
        ruleColour(".voa-entry__input"),
        ruleBackground(".voa-entry__input"),
      ),
    ).toBeGreaterThanOrEqual(4.5);
  });

  it.each([".voa-entry__heading", ".voa-entry__body", ".voa-entry__label"])(
    "%s clears 4.5:1 on the surface ground",
    (cls) => {
      const ratio = contrastRatio(ruleColour(cls), SURFACE_TOKENS["--bz-base"]);
      expect(ratio, `${cls}: ${ratio.toFixed(2)}:1`).toBeGreaterThanOrEqual(
        4.5,
      );
    },
  );

  /** Below 16px iOS Safari zooms the viewport on focus. Stated as a number
   *  because the reason is a number, not a taste. */
  it("the field is at least 16px, or a phone zooms the form off the screen", () => {
    const m = /\.voa-entry__input\s*\{([^}]*)\}/i.exec(VOA_R19_CSS);
    const size = /font-size:\s*(\d+)px;/i.exec(m![1]);
    expect(size, ".voa-entry__input must declare font-size in px").toBeTruthy();
    expect(Number(size![1])).toBeGreaterThanOrEqual(16);
  });

  /** A 48px target is the mandate's thumb-reach floor, and the submit is the
   *  one primary action on the screen. */
  it.each([".voa-entry__input", ".voa-entry__submit"])(
    "%s is at least a 48px target",
    (cls) => {
      const m = new RegExp(`\\${cls}\\s*\\{([^}]*)\\}`, "i").exec(VOA_R19_CSS);
      const h = /min-height:\s*(\d+)px;/i.exec(m![1]);
      expect(h, `${cls} must declare min-height`).toBeTruthy();
      expect(Number(h![1])).toBeGreaterThanOrEqual(48);
    },
  );
});

// ---------------------------------------------------------------------------
// Every control on this funnel has an edge you can see (SC 1.4.11, 3:1).
//
// PR 6912 cured ONE field and the measurement that followed found the same
// shape on seven more declarations. Measured on production, not inferred:
// the wizard's four fields read 1.42:1 against their own fill — and that fill
// is itself only 1.09:1 against the page ground, so the 1px rule was the only
// thing making them look like fields. The delete control's "Cancel" and "Try
// again" read 1.37:1 with no fill and no colour cue at all, unlike their
// copper "Yes, delete" sibling. The two pills read 1.78:1 and 1.84:1; those
// two DO carry copper labels that signal interactivity on their own, so they
// are cured for consistency rather than as clear-cut failures — stated here
// so the green is never read as more than it proves.
//
// WHAT THIS SECTION DOES NOT SEE, named rather than implied: three sites could
// not be reached on production and are NOT cured here —
// `checkout/[resultId]/CheckoutFlow.tsx` (payments are switched off, so the
// form never mounts), `orders/OrderTracker.tsx`'s Delivered/Exception panels
// (need a real seeded order), and `upload/UploadFlow.tsx`'s SECONDARY/FIELD
// (need a photo through the OCR pipeline). Fixing a declaration nobody has
// ever seen painted is how a guard starts certifying guesses.
// ---------------------------------------------------------------------------

/** The two weak boundary tokens, by the numbers that retired them. */
const RETIRED_BOUNDARY_TOKENS = [
  "--color-border-subtle",
  "--bz-border-hover",
] as const;

/** Named literally: a file that disappears must fail here, not silently drop
 *  out of the sweep (W133 — a test parametrized over the set it tests). */
const CONTROL_FILES = [
  "page.tsx",
  "[hash]/page.tsx",
  "voa-r19.css",
  "checkout/[resultId]/CheckoutFlow.tsx",
  "upload/UploadFlow.tsx",
] as const;

/**
 * `orders/OrderTracker.tsx` is DELIBERATELY not on that list, and adding it
 * would be the mistake this comment exists to prevent. Its two
 * `--color-border-subtle` declarations are on `<section>` containers —
 * `DeliveredPanel` and `ExceptionPanel` — and 1.4.11 binds user-interface
 * components and graphical objects, not a card's hairline outline. The token
 * is correct there; the file carries its own note saying so.
 *
 * Both shapes a boundary is written in on this surface: `border:` (CSS and
 * the inline shorthand) and `borderColor:` / `border-color:` (the inline
 * longhand `UploadFlow` uses). The first draft of this sweep knew only the
 * first, and `UploadFlow`'s two declarations would have walked straight past
 * it — a guard that reads one spelling of the thing it bans.
 */
const boundaryRe = (token: string) =>
  new RegExp(`border(?:-?[cC]olor)?:[^;\n]*${token}`);

describe("control boundaries clear 1.4.11's 3:1 (mandate accent 6)", () => {
  it.each([".voa-clock__handoff", ".voa-next__ask"])(
    "%s's boundary clears 3:1 on the ground it sits on",
    (cls) => {
      const ratio = contrastRatio(
        ruleBorderColour(cls),
        SURFACE_TOKENS["--bz-base"],
      );
      expect(ratio, `${cls}: ${ratio.toFixed(2)}:1`).toBeGreaterThanOrEqual(3);
    },
  );

  it("GUILTY: both retired tokens fail that floor, on the ground and on a field fill", () => {
    for (const token of RETIRED_BOUNDARY_TOKENS) {
      const colour = resolveColor(
        token === "--color-border-subtle"
          ? "var(--bz-border)" // what voa-r19.css:42 aliases it to
          : `var(${token})`,
        SURFACE_TOKENS,
      );
      expect(
        contrastRatio(colour, SURFACE_TOKENS["--bz-base"]),
        `${token} on the ground`,
      ).toBeLessThan(3);
      expect(
        contrastRatio(colour, SURFACE_TOKENS["--bz-elevated"]),
        `${token} on a field fill`,
      ).toBeLessThan(3);
    }
  });

  /**
   * The inline declarations. This is a SOURCE pin, not a render: jsdom
   * resolves no cascade, and the two delete-control buttons only paint in a
   * confirming state. What it proves is narrow and exact — no control on
   * these three files declares its border with a token measured under 3:1 —
   * and that is the regression it exists to stop.
   */
  it.each(CONTROL_FILES)(
    "%s declares no control border on a retired token",
    (rel) => {
      const src = readFileSync(join(__dirname, rel), "utf-8");
      for (const token of RETIRED_BOUNDARY_TOKENS) {
        expect(
          boundaryRe(token).test(src),
          `${rel} still borders on ${token}`,
        ).toBe(false);
      }
    },
  );

  it("GUILTY: the sweep's own regex catches the shape it bans", () => {
    for (const bad of [
      `border: "1px solid var(--color-border-subtle)",`,
      `border: 1px solid var(--bz-border-hover);`,
      `borderColor: "var(--bz-border-hover)",`,
      `border-color: var(--color-border-subtle);`,
    ]) {
      const hit = RETIRED_BOUNDARY_TOKENS.some((t) => boundaryRe(t).test(bad));
      expect(hit, bad).toBe(true);
    }
  });

  it("INNOCENT: it does not convict a DIVIDER on the same token", () => {
    for (const ok of [
      "border-top: 1px solid var(--bz-border);",
      "border-bottom: 1px solid var(--color-border-subtle);",
      "border-left-color: var(--bz-border-hover);",
      "--color-border-subtle: var(--bz-border);",
    ]) {
      const hit = RETIRED_BOUNDARY_TOKENS.some((t) => boundaryRe(t).test(ok));
      expect(hit, ok).toBe(false);
    }
  });
});

// ---------------------------------------------------------------------------
// The accent is COPPER. Ruled by the owner 2026-09-20, and pinned here at the
// RESOLVED value rather than at the spelling.
//
// `voa-no-colour-literal.guard.test.ts` already scans these screens' source
// for a hex or a red-family utility. That catches a literal typed into a
// component; it cannot catch a TOKEN that resolves to red or blue one `var()`
// away — which is the shape this surface actually lives with.
// `voa-action-style.ts`'s own docblock records it: `--accent-funnel` resolves
// to `--color-red-500` for `[data-funnel="visa"]`, and only this stylesheet's
// bridge has ever held that red off the funnel. A ruling that lives in a
// selector's specificity is not a ruling, it is a coincidence with a good
// track record.
//
// SCOPE, so the green is never read as more than it proves: this judges the
// TOKENS this surface declares. It does not judge the site chrome — the
// shared "Get Started" link paints `--cta-bg` blue on every page of the site,
// GARUDA VOA screens included, and it is nav furniture rather than a funnel
// component (`semantic.css` says funnel-agnostic components must not read
// `--accent-funnel`). Changing it is a site-wide decision and not this lane's.
// ---------------------------------------------------------------------------

/**
 * Family detectors on a resolved paint value, deliberately narrow: they
 * answer "is this the red family / the blue family", not "is this warm".
 *
 * They judge HUE, and that is a correction the daylight ground forced out of
 * them. The first version was `r > 150 && g < 90 && b < 90`: it reads like a
 * hue rule and it is a LIGHTNESS rule. The ink ground's copper #c46a52 is
 * rgb(196, 106, 82) and cleared it on g = 106; the daylight ground's copper
 * #a44b36 is rgb(164, 75, 54) and did not — yet the two sit 1.2° apart in
 * hue (12.6° and 11.5°). They are one colour at two lightnesses, and the
 * owner's ruling names the colour, not the lightness. A detector that
 * convicts the darker sibling of the very tone the ruling protects is not
 * detecting a family; it is detecting darkness, and it would have read the
 * flip to daylight as a violation of a ruling the flip obeys. Cicatrix
 * family #3: judge the entity, never a proxy that correlates with it.
 *
 * Hue separates them honestly, with room to spare. The reds this surface
 * must refuse sit at or above 345° and at or below 8° — `--color-red-500`
 * #ff2d4c is 351.1°, Tailwind's text-red-600 #dc2626 is 0.0°, and the
 * closest call of all, the site's own muted brick `--bz-red` #c2453f, is
 * 2.7°. The copper family sits in the low teens. The nearest approach is
 * therefore 8.8°, between #c2453f and #a44b36 — two colours that genuinely
 * are different families, which is why the band can be drawn between them
 * at all.
 *
 * Saturation is required as well, so a near-grey is never convicted for the
 * hue noise of two channels a few units apart: the ink ground #121016 is
 * 0.16 saturated and its hue is meaningless.
 */
function rgbOf(colour: string): [number, number, number] {
  return toRgb(resolveColor(colour, SURFACE_TOKENS));
}

/** HSL hue in degrees and HSL saturation, from an sRGB triple. */
function hueSat([r, g, b]: [number, number, number]): {
  hue: number;
  sat: number;
} {
  const [R, G, B] = [r / 255, g / 255, b / 255];
  const max = Math.max(R, G, B);
  const min = Math.min(R, G, B);
  const delta = max - min;
  const light = (max + min) / 2;
  if (delta === 0) return { hue: 0, sat: 0 };
  let hue: number;
  if (max === R) hue = ((G - B) / delta) % 6;
  else if (max === G) hue = (B - R) / delta + 2;
  else hue = (R - G) / delta + 4;
  hue = (hue * 60 + 360) % 360;
  return { hue, sat: delta / (1 - Math.abs(2 * light - 1)) };
}

const CHROMATIC = 0.2;
const isRedFamily = (rgb: [number, number, number]) => {
  const { hue, sat } = hueSat(rgb);
  return sat >= CHROMATIC && (hue >= 345 || hue <= 8);
};
const isBlueFamily = (rgb: [number, number, number]) => {
  const { hue, sat } = hueSat(rgb);
  return sat >= CHROMATIC && hue >= 200 && hue <= 260;
};

/** Named literally — a token that vanishes must fail here, not drop out. */
const ACCENT_TOKENS = ["--bz-accent", "--state-danger"] as const;

describe("the accent is copper (owner ruling 2026-09-20)", () => {
  it.each(ACCENT_TOKENS)("%s resolves to neither red nor blue", (token) => {
    const rgb = rgbOf(`var(${token})`);
    expect(isRedFamily(rgb), `${token} is red: ${rgb.join(",")}`).toBe(false);
    expect(isBlueFamily(rgb), `${token} is blue: ${rgb.join(",")}`).toBe(false);
  });

  it("--state-danger is the accent itself: danger carries a WORD here, not a hue", () => {
    expect(resolveColor("var(--state-danger)", SURFACE_TOKENS)).toBe(
      resolveColor("var(--bz-accent)", SURFACE_TOKENS),
    );
  });

  /**
   * Both detectors must be able to convict, or the rows above are decoration.
   *
   * These two rows pass their value as a LITERAL fallback, and that is not a
   * shortcut — `--color-red-500` and `--cta-bg` are declared outside the block
   * `SURFACE_TOKENS` parses, so the resolver genuinely cannot see them. The
   * literals are the values MEASURED on production
   * (`getComputedStyle` on a probe inside `[data-garuda-voa="r19"]`:
   * `--color-red-500` → `rgb(255, 45, 76)`, `--cta-bg` → `rgb(58, 109, 255)`).
   * So what these two rows prove is that the detectors convict; what says
   * those are the live values is the measurement, not this file.
   */
  it("GUILTY: the red the funnel token falls back to trips the red detector", () => {
    expect(isRedFamily(rgbOf("var(--color-red-500, #ff2d4c)"))).toBe(true);
  });

  it("GUILTY: the chrome CTA's blue trips the blue detector", () => {
    expect(isBlueFamily(rgbOf("var(--cta-bg, #3a6dff)"))).toBe(true);
  });

  /**
   * The site's own muted brick red, and the row that keeps the hue band
   * from being drawn wherever it is convenient. #c2453f at 2.7° is the
   * closest a red gets to the copper family here; if the band ever widens
   * to acquit the copper by acquitting this too, the detector has stopped
   * detecting.
   */
  it("GUILTY: --bz-red, the nearest miss, still trips the red detector", () => {
    expect(isRedFamily(toRgb("#c2453f"))).toBe(true);
  });

  it("INNOCENT: copper on EITHER ground, and the surface ink, are neither", () => {
    // #a44b36 is the daylight copper and #c46a52 the ink one — the same
    // colour at two lightnesses, and the pair that broke the lightness-based
    // detector this row now guards.
    for (const c of ["#a44b36", "#c46a52", "#f7f4ee", "#121016", "#f4c430"]) {
      const rgb = toRgb(c);
      expect(isRedFamily(rgb), `${c} red`).toBe(false);
      expect(isBlueFamily(rgb), `${c} blue`).toBe(false);
    }
  });
});
